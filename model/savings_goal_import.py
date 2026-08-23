"""Sparzielwuensche aus anderen Programmen uebernehmen.

FPM legt seit Loop 53 offene Wuensche im Brueckenordner ab: ein Wunschfueller
mit Zielbetrag und der Kategorie, unter der er hier erscheinen soll. Bis
Loop 54 las sie niemand - der Nutzer sah in FPM eine Einstellung, die hier
nichts bewirkte.

**Review-first wie beim Zahlungsimport.** Ein Vorschlag ist kein Sparziel. Er
wird gezeigt, und erst eine Bestaetigung legt etwas an. Der BudgetManager
oeffnet die Datenbank des anderen Programms nie und wird von ihr auch nicht
angefasst.

Was einmal uebernommen oder abgelehnt wurde, bleibt es. Der Zustand haengt an
der ``external_id`` des Absenders und wird hier gefuehrt, nicht in der Datei:
Die Datei ist eine Momentaufnahme und wird bei jedem Lauf ersetzt.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from model.lifeplanner_import_service import alle_bridge_dirs
from model.typ_constants import TYP_SAVINGS

WISHES_FILE = "fpm_savings_wishes.jsonl"
SCHEMA = "budgetmanager.savings_goal_request.v1"
MANIFEST_SCHEMA = "budgetmanager.savings_goal_request.manifest.v1"
# Der Name steht auch in den Abfragen ausgeschrieben: SQL aus einem
# f-String zu bauen ist auch dann eine schlechte Gewohnheit, wenn der
# eingesetzte Wert eine Konstante ist. Ein Test haelt beide gleich.
STATE_TABLE = "savings_goal_import_state"

# Wie beim Zahlungsimport: Grenzen, damit eine fehlerhafte Gegenseite hier
# keinen Schaden anrichtet.
MAX_DATEIGROESSE = 5 * 1024 * 1024
MAX_EINTRAEGE = 500
MAX_TEXT = 200
MAX_BETRAG = 10_000_000.0


@dataclass(frozen=True)
class SparzielWunsch:
    """Ein Vorschlag von aussen - noch kein Sparziel."""

    external_id: str
    source: str
    name: str
    target_amount: float
    currency: str
    category: str
    notes: str = ""
    payload_hash: str = ""


def ensure_state_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS savings_goal_import_state (
            external_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('imported','rejected')),
            goal_id INTEGER,
            processed_at TEXT NOT NULL,
            source_payload TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _hash(payload: dict[str, Any]) -> str:
    roh = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(roh).hexdigest()


def _text(wert: Any, *, limit: int = MAX_TEXT) -> str:
    return str(wert or "").replace("\x00", "").strip()[:limit]


def _lies_datensatz(roh: dict[str, Any]) -> SparzielWunsch | None:
    """Prueft einen Datensatz. Unbrauchbares wird uebergangen, nicht geraten."""
    if roh.get("schema") != SCHEMA:
        return None
    kennung = _text(roh.get("external_id"), limit=120)
    name = _text(roh.get("name"))
    if not kennung or not name:
        return None
    try:
        betrag = round(float(roh.get("target_amount") or 0.0), 2)
    except (TypeError, ValueError):
        return None
    # Ein Ziel ohne Betrag ist keines, ein unsinnig hohes ein Fehler der
    # Gegenseite. Beides wird uebergangen statt uebernommen.
    if not 0 < betrag <= MAX_BETRAG:
        return None
    return SparzielWunsch(
        external_id=kennung,
        source=_text(roh.get("source"), limit=60) or "extern",
        name=name,
        target_amount=betrag,
        currency=_text(roh.get("currency"), limit=8) or "CHF",
        category=_text(roh.get("category")),
        notes=_text(roh.get("notes"), limit=500),
        payload_hash=_hash(roh),
    )


def lies_wuensche(pfad: str | Path | None = None) -> list[SparzielWunsch]:
    """Liest die Wuensche aus allen bekannten Brueckenordnern.

    Der aktive zuletzt: Bei gleicher Kennung gewinnt, was hier und jetzt
    gilt (siehe ``bridge_registry``, Loop 31).

    Eine kaputte Zeile stoppt nichts - es ist eine Anzeige, kein Import.
    Uebernommen wird ohnehin erst auf Bestaetigung.
    """
    quellen = (
        [Path(pfad)]
        if pfad is not None
        else [o / WISHES_FILE for o in alle_bridge_dirs()]
    )
    nach_kennung: dict[str, SparzielWunsch] = {}
    for quelle in quellen:
        if not quelle.is_file():
            continue
        try:
            if quelle.stat().st_size > MAX_DATEIGROESSE:
                continue
            zeilen = quelle.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        for zeile in zeilen[: MAX_EINTRAEGE + 1]:
            if not zeile.strip():
                continue
            try:
                roh = json.loads(zeile)
            except json.JSONDecodeError:
                continue
            if not isinstance(roh, dict) or roh.get("schema") == MANIFEST_SCHEMA:
                continue
            wunsch = _lies_datensatz(roh)
            if wunsch is not None:
                nach_kennung[wunsch.external_id] = wunsch
    return sorted(nach_kennung.values(), key=lambda w: w.name.lower())


def offene_wuensche(
    conn: sqlite3.Connection, pfad: str | Path | None = None
) -> list[SparzielWunsch]:
    """Nur, worueber noch nicht entschieden wurde.

    Ein uebernommenes Ziel taucht nicht wieder auf, auch wenn der Absender
    den Wunsch weiterhin schickt - er weiss nicht, was hier passiert ist.
    """
    ensure_state_table(conn)
    entschieden = {
        str(zeile[0])
        for zeile in conn.execute("SELECT external_id FROM savings_goal_import_state")
    }
    return [w for w in lies_wuensche(pfad) if w.external_id not in entschieden]


def _merke(
    conn: sqlite3.Connection,
    wunsch: SparzielWunsch,
    status: str,
    goal_id: int | None,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO savings_goal_import_state
            (external_id, source, payload_hash, status, goal_id,
             processed_at, source_payload)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            wunsch.external_id,
            wunsch.source,
            wunsch.payload_hash,
            status,
            goal_id,
            datetime.now(UTC).isoformat(timespec="seconds"),
            json.dumps(
                {
                    "name": wunsch.name,
                    "target_amount": wunsch.target_amount,
                    "currency": wunsch.currency,
                    "category": wunsch.category,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        ),
    )
    conn.commit()


def uebernehmen(conn: sqlite3.Connection, wunsch: SparzielWunsch) -> int:
    """Legt das Sparziel an und merkt sich, dass es getan ist.

    Die Kategorie wird **nicht** angelegt, wenn es sie nicht gibt: Ein
    fremdes Programm soll den Kategorienbaum des Nutzers nicht verändern.
    Fehlt sie, entsteht das Ziel ohne Kategorie und laesst sich hier
    zuordnen.
    """
    from model.category_model import CategoryModel
    from model.savings_goals_model import SavingsGoalsModel

    ensure_state_table(conn)
    kategorie = wunsch.category or None
    if kategorie and kategorie not in CategoryModel(conn).list_names(TYP_SAVINGS):
        kategorie = None

    goal_id = SavingsGoalsModel(conn).create(
        name=wunsch.name,
        target_amount=wunsch.target_amount,
        category=kategorie,
        notes=wunsch.notes or None,
    )
    _merke(conn, wunsch, "imported", int(goal_id))
    return int(goal_id)


def ablehnen(conn: sqlite3.Connection, wunsch: SparzielWunsch) -> None:
    """Blendet den Wunsch aus, ohne etwas anzulegen."""
    ensure_state_table(conn)
    _merke(conn, wunsch, "rejected", None)
