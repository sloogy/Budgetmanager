"""Meldungen des BudgetManagers an das LifePlanner-Dashboard.

Der Host zeigte bisher nur, ob die Module laufen und wie viele Zeilen in den
Brueckendateien stehen. Was in einem Programm gerade schieflaeuft - ein
ueberzogenes Budget, ein Sparziel kurz vor dem Termin - stand nur dort und
war nur zu sehen, wenn man das Programm oeffnete. Genau davor sitzt der Host
aber: Er ist das Fenster, das offen ist.

Geschrieben wird nach ``lifeplanner.notice.v1``. Das Schema kommt aus dem
FreizeitManager, der solche Meldungen als einziges Modul schon lieferte
(``freizeitmanager.focus.v1``: kind, urgency, headline, detail). Es ist hier
nur vereinheitlicht, damit der Host nicht je Modul ein eigenes Format lesen
muss.

Drei Regeln, die aus dem Modul-Host-Vertrag folgen:

* **Nur Ergebnisse.** Eine Meldung traegt eine Ueberschrift, einen Zusatz und
  eine Dringlichkeit - keine Betraege in Rohform, keine Buchungen, keine
  Kategorienamen als Datensatz. Was der Host anzeigt, hat der Absender
  bereits formuliert.
* **Der Host rechnet nichts nach.** Er sammelt und stellt dar. Bewertet wird
  im Fachmodul, das die Daten hat.
* **Stabile Kennung je Meldung.** Dieselbe Sache soll nach dem naechsten
  Schreiben dieselbe Meldung sein, nicht eine zweite.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from app_info import APP_NAME, APP_VERSION
from model.lifeplanner_import_service import default_bridge_dir
from utils.atomic_write import atomar_offen

NOTICES_FILE = "budgetmanager_notices.jsonl"
MANIFEST_SCHEMA = "lifeplanner.notice.manifest.v1"
NOTICE_SCHEMA = "lifeplanner.notice.v1"

# Aufsteigend nach Dringlichkeit - der Host sortiert danach.
DRINGLICHKEITEN = ("info", "warnung", "kritisch")

# Ohne Deckel kann ein Programm das Dashboard fluten. Wer 200 Kategorien
# ueberzieht, hat ein Budgetproblem und kein Anzeigeproblem; die
# uebriggebliebenen zaehlt die Sammelmeldung.
HOECHSTZAHL = 20


@dataclass(frozen=True)
class Meldung:
    """Eine Zeile fuers Host-Dashboard."""

    kennung: str
    dringlichkeit: str
    ueberschrift: str
    zusatz: str = ""
    bereich: str = ""

    def __post_init__(self) -> None:
        if self.dringlichkeit not in DRINGLICHKEITEN:
            raise ValueError(
                f"unbekannte Dringlichkeit {self.dringlichkeit!r}; "
                f"erlaubt sind {DRINGLICHKEITEN}"
            )
        if not self.ueberschrift.strip():
            raise ValueError("eine Meldung ohne Ueberschrift sagt nichts")

    def als_zeile(self) -> dict:
        return {
            "schema": NOTICE_SCHEMA,
            "id": self.kennung,
            "urgency": self.dringlichkeit,
            "headline": self.ueberschrift,
            "detail": self.zusatz,
            "area": self.bereich,
        }


def kennung(*teile: object) -> str:
    """Stabile Kennung aus den Bestandteilen einer Meldung.

    Gekuerzter Hash statt der Klartextteile: Eine Kategorie kann
    "Therapie" oder "Anwalt" heissen, und die Kennung steht in einer Datei,
    die der Host und jedes andere Modul lesen darf.
    """
    roh = "\x1f".join(str(teil) for teil in teile)
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()[:16]


def notices_path(bridge_dir: Path | None = None) -> Path:
    return (bridge_dir or default_bridge_dir()) / NOTICES_FILE


def schreibe_meldungen(meldungen: list[Meldung], path: str | Path | None = None) -> int:
    """Schreibt die Meldungen als vollstaendigen Stand.

    Kein Anhaengen: Die Datei ist eine Momentaufnahme dessen, was gerade
    gilt. Was behoben ist, verschwindet damit von selbst, statt bis zum
    naechsten Aufraeumlauf im Dashboard zu stehen.
    """
    ziel = Path(path) if path is not None else notices_path()
    ziel.parent.mkdir(parents=True, exist_ok=True)

    geordnet = sorted(
        meldungen,
        key=lambda m: (-DRINGLICHKEITEN.index(m.dringlichkeit), m.ueberschrift),
    )
    sichtbar = geordnet[:HOECHSTZAHL]
    rest = len(geordnet) - len(sichtbar)
    if rest > 0:
        sichtbar.append(
            Meldung(
                kennung=kennung("weitere", rest),
                dringlichkeit="info",
                ueberschrift=f"{rest} weitere Meldungen",
                zusatz="Im BudgetManager ansehen.",
                bereich="sammel",
            )
        )

    with atomar_offen(ziel) as handle:
        handle.write(
            json.dumps(
                {
                    "schema": MANIFEST_SCHEMA,
                    "module": APP_NAME,
                    "module_version": APP_VERSION,
                    "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                    "profile": os.environ.get("LIFEPLANNER_PROFILE_ID", ""),
                    "count": len(sichtbar),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )
        for meldung in sichtbar:
            handle.write(
                json.dumps(meldung.als_zeile(), ensure_ascii=False, sort_keys=True)
                + "\n"
            )
    return len(sichtbar)


def sammle_meldungen(
    conn, jahr: int, monat: int, heute: date | None = None
) -> list[Meldung]:
    """Bildet den aktuellen Meldungsstand aus Budget und Sparzielen.

    Formuliert wird hier, nicht im Host: Nur der BudgetManager weiss, was
    "80 % verbraucht" bei dieser Kategorie in diesem Monat bedeutet.
    """
    meldungen: list[Meldung] = []
    meldungen.extend(_budget_meldungen(conn, jahr, monat))
    meldungen.extend(_sparziel_meldungen(conn, heute))
    return meldungen


def _budget_meldungen(conn, jahr: int, monat: int) -> list[Meldung]:
    from model.budget_warnings_model_extended import BudgetWarningsModelExtended

    modell = BudgetWarningsModelExtended(conn)
    meldungen: list[Meldung] = []
    for fall in modell.check_warnings_extended(jahr, monat):
        ueberzogen = fall.percent_used >= 100
        meldungen.append(
            Meldung(
                kennung=kennung("budget", jahr, monat, fall.typ, fall.category),
                dringlichkeit="kritisch" if ueberzogen else "warnung",
                ueberschrift=(
                    f"{fall.category}: Budget überzogen"
                    if ueberzogen
                    else f"{fall.category}: {fall.percent_used:.0f} % verbraucht"
                ),
                zusatz=f"{monat:02d}/{jahr}",
                bereich="budget",
            )
        )
    return meldungen


def _sparziel_meldungen(conn, heute: date | None = None) -> list[Meldung]:
    from model.savings_goals_model import SavingsGoalsModel

    stichtag = heute or date.today()
    modell = SavingsGoalsModel(conn)
    meldungen: list[Meldung] = []
    for ziel in modell.list_all():
        if not ziel.is_saving:
            continue

        if ziel.progress_percent >= 100:
            meldungen.append(
                Meldung(
                    kennung=kennung("sparziel_erreicht", ziel.id),
                    dringlichkeit="info",
                    ueberschrift=f"Sparziel erreicht: {ziel.name}",
                    zusatz="Kann freigegeben werden.",
                    bereich="sparziel",
                )
            )
            continue

        # Ein Termin, der naeher ist als der Sparstand, ist die Meldung, die
        # sich noch beeinflussen laesst - danach ist sie nur noch eine
        # Feststellung.
        if not ziel.deadline:
            continue
        try:
            frist = date.fromisoformat(str(ziel.deadline)[:10])
        except ValueError:
            continue
        tage = (frist - stichtag).days
        if tage < 0:
            meldungen.append(
                Meldung(
                    kennung=kennung("sparziel_ueberfaellig", ziel.id),
                    dringlichkeit="warnung",
                    ueberschrift=f"Sparziel überfällig: {ziel.name}",
                    zusatz=f"Termin war {frist.isoformat()}, {ziel.progress_percent:.0f} % erreicht.",
                    bereich="sparziel",
                )
            )
        elif tage <= 30:
            meldungen.append(
                Meldung(
                    kennung=kennung("sparziel_frist", ziel.id),
                    dringlichkeit="info",
                    ueberschrift=f"Sparziel endet bald: {ziel.name}",
                    zusatz=f"Noch {tage} Tage, {ziel.progress_percent:.0f} % erreicht.",
                    bereich="sparziel",
                )
            )
    return meldungen
