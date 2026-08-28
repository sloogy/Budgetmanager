"""P3.1 - Die Fachschicht des Coachs rechnet aus der Datenbank, nicht aus der KI.

Der Pflichttest der Phase steht in Architekturregel 1.2 und ist eine Frage
des Anwenders, keine technische: **Funktioniert der Coach fuer jemanden, der
nie einen Bankauszug importiert hat?** Wer seine Zahlen von Hand bucht, hat
kein Haendlergedaechtnis, keine Lernbeispiele und keine eingeschaltete
Import-KI - und muss trotzdem jede Auswertung bekommen.

Diese Datei baut darum einen Haushalt, in dem es die KI schlicht nicht gibt:
zwoelf Monate ueber die produktiven Schreibwege gebucht, Budgets, Tags,
Fixkosten- und Wiederholungsattribute, ein Sparziel mit echtem Bezug, ein
Dauerauftrag. Danach werden die sieben geforderten Groessen gegen von Hand
nachgerechnete Zahlen geprueft.

Die Unabhaengigkeit von der KI wird zweifach belegt, nicht behauptet:

* ``test_engine_bindet_kein_ki_modul_ein`` liest die Importe des Prueflings.
  Wer dort je ein KI-Modul hereinholt, macht diesen Test rot, bevor
  irgendeine Rechnung falsch werden kann.
* ``test_auswertungen_sind_unabhaengig_vom_zustand_der_import_ki`` faehrt
  jede Auswertung durch alle drei Zustaende, die es geben kann: Lernspeicher
  existiert gar nicht, Lernspeicher ist gefuellt, Lernspeicher wird wieder
  geloescht. Alle drei muessen dieselben Zahlen liefern. Ein Test, der nur
  den leeren Zustand prueft, uebersieht genau den Fall, der weh taete.
"""

from __future__ import annotations

import ast
import sqlite3
from dataclasses import asdict
from datetime import date
from pathlib import Path

import pytest

from model.category_model import CategoryModel
from model.finance_insight_engine import (
    DIRECTION_DOWN,
    DIRECTION_FLAT,
    DIRECTION_UP,
    FinanceInsightEngine,
)
from model.migrations import migrate_all
from model.savings_goals_model import SavingsGoalsModel
from model.tags_model import TagsModel
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS
from tests.conftest import verbindung_merken

#: Fester Stichtag. Der laufende Monat zaehlt nicht als Vergleichswert - mit
#: ``date.today()`` waere dieser Test im Januar etwas anderes als im Juni.
HEUTE = date(2026, 1, 15)

LOHN = "Lohn"
MIETE = "Miete"
LEBENSMITTEL = "Lebensmittel"
RESTAURANT = "Restaurant"
HOBBY = "Hobby"
KLEIDUNG = "Kleidung"
NOTGROSCHEN = "Notgroschen"

#: Von Hand nachgerechnet, damit ein Rechenfehler im Pruefling nicht durch
#: dieselbe Formel im Test gedeckt wird.
ERWARTET_EINKOMMEN = 74400.0  # 12 x 6200
ERWARTET_MIETE = 21600.0  # 12 x 1800
ERWARTET_LEBENSMITTEL = 5580.0  # 410 + 420 + ... + 520
ERWARTET_RESTAURANT = 1380.0  # 9 x 80 + 3 x 220
ERWARTET_HOBBY = 2370.0  # 9 x 200 + 3 x 190
ERWARTET_KLEIDUNG = 3000.0  # 9 x 300 + 3 x 100
ERWARTET_AUSGABEN = 33930.0
ERWARTET_UEBERSCHUSS = 40470.0  # 74400 - 33930
ERWARTET_EINZAHLUNGEN = 3600.0  # 12 x 300
ERWARTET_BEZUEGE = 500.0


def _monatsbetrag(kategorie: str, monat: int) -> float:
    """Der gebuchte Betrag einer Kategorie in einem Monat des Jahres 2025."""
    if kategorie == LEBENSMITTEL:
        return 400.0 + monat * 10.0
    if kategorie == RESTAURANT:
        return 80.0 if monat <= 9 else 220.0
    if kategorie == HOBBY:
        # Bewusst knapp unter der Rauschgrenze: eine echte, aber unerhebliche
        # Veraenderung darf keinen Trend melden.
        return 200.0 if monat <= 9 else 190.0
    if kategorie == KLEIDUNG:
        return 300.0 if monat <= 9 else 100.0
    raise AssertionError(f"unbekannte Kategorie {kategorie}")


@pytest.fixture
def haushalt() -> sqlite3.Connection:
    """Zwoelf Monate Handarbeit - kein Import, keine KI, kein INSERT von Hand.

    Alles entsteht ueber die produktiven Schreibwege. Eine nachgebaute
    Datenbank wuerde nur beweisen, dass die Engine die Attrappe lesen kann.
    """
    conn = verbindung_merken(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_all(conn)

    kategorien = CategoryModel(conn)
    kategorien.create(TYP_INCOME, LOHN)
    kategorien.create(TYP_EXPENSES, MIETE, is_fix=True, is_recurring=True)
    for name in (LEBENSMITTEL, RESTAURANT, HOBBY, KLEIDUNG):
        kategorien.create(TYP_EXPENSES, name)
    kategorien.create(TYP_SAVINGS, NOTGROSCHEN)

    tags = TagsModel(conn)
    haushalt_tag = tags.create("Haushalt")

    SavingsGoalsModel(conn).create(NOTGROSCHEN, 12000.0, category=NOTGROSCHEN)

    tracking = TrackingModel(conn)
    for monat in range(1, 13):
        tracking.add(date(2025, monat, 25), TYP_INCOME, LOHN, 6200.0, "Monatslohn")
        tracking.add(date(2025, monat, 1), TYP_EXPENSES, MIETE, 1800.0, "Miete")
        einkauf = tracking.add(
            date(2025, monat, 4),
            TYP_EXPENSES,
            LEBENSMITTEL,
            _monatsbetrag(LEBENSMITTEL, monat),
            "Einkauf",
        )
        tags.assign_to_entry(einkauf, haushalt_tag)
        for kategorie in (RESTAURANT, HOBBY, KLEIDUNG):
            tracking.add(
                date(2025, monat, 12),
                TYP_EXPENSES,
                kategorie,
                _monatsbetrag(kategorie, monat),
                kategorie,
            )
        tracking.add(date(2025, monat, 26), TYP_SAVINGS, NOTGROSCHEN, 300.0, "Sparen")
        for kategorie, betrag in ((LEBENSMITTEL, 450.0), (MIETE, 1800.0)):
            conn.execute(
                "INSERT INTO budget(year, month, typ, category, amount) "
                "VALUES(?,?,?,?,?)",
                (2025, monat, TYP_EXPENSES, kategorie, betrag),
            )

    # Ein echter Bezug vom Sparkonto. Er ist keine negative Einzahlung, und
    # genau das muss die Auswertung unterscheiden koennen.
    tracking.add(date(2025, 8, 27), TYP_SAVINGS, NOTGROSCHEN, -500.0, "Notfall")

    conn.execute(
        "INSERT INTO recurring_transactions"
        "(typ, category, amount, details, day_of_month, is_active, start_date, created_date) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (
            TYP_EXPENSES,
            MIETE,
            1800.0,
            "Dauerauftrag Miete",
            1,
            1,
            "2025-01-01",
            "2025-01-01",
        ),
    )
    conn.commit()
    return conn


@pytest.fixture
def engine(haushalt: sqlite3.Connection) -> FinanceInsightEngine:
    return FinanceInsightEngine(haushalt)


@pytest.fixture
def jahr(engine: FinanceInsightEngine) -> list[tuple[int, int]]:
    return engine.recent_complete_months(12, today=HEUTE)


# ── Die Ausgangslage selbst ist Teil der Zusicherung ────────────────────────


def _ki_tabellen(conn: sqlite3.Connection) -> list[str]:
    """Die Tabellen des Lernspeichers, wie sie gerade wirklich existieren."""
    return sorted(
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if str(row[0]).startswith("ai_")
    )


def test_der_haushalt_enthaelt_ausschliesslich_handarbeit(haushalt) -> None:
    """Ohne diese Probe wuerde der Rest der Datei die falsche Frage stellen."""
    quellen = {
        str(row[0])
        for row in haushalt.execute(
            "SELECT DISTINCT COALESCE(source,'manual') FROM tracking"
        )
    }
    assert quellen == {"manual"}

    # Die Migration legt den Lernspeicher gar nicht erst an - er entsteht erst,
    # wenn die Import-KI zum ersten Mal etwas lernt. Wer nie importiert hat,
    # hat diese Tabellen also nicht bloss leer, sondern ueberhaupt nicht.
    assert _ki_tabellen(haushalt) == []


def test_engine_bindet_kein_ki_modul_ein() -> None:
    """Der Pruefling darf die Import-KI nicht einmal importieren.

    Ein Importbaum ist der einzige Nachweis, den kein spaeterer Umbau
    versehentlich aushebelt: Wer hier ein KI-Modul hereinholt, macht diesen
    Test rot, bevor irgendeine Rechnung falsch werden kann.
    """
    quelle = Path(__file__).resolve().parents[1] / "model" / "finance_insight_engine.py"
    baum = ast.parse(quelle.read_text(encoding="utf-8"))

    module: list[str] = []
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            module.extend(alias.name for alias in knoten.names)
        elif isinstance(knoten, ast.ImportFrom) and knoten.module:
            module.append(knoten.module)

    assert module, "Keine Importe gefunden - der Test liest die falsche Datei"
    for name in module:
        teile = name.split(".")
        assert not any(
            t == "ai" or t.startswith("ai_") or "bank_import" in t for t in teile
        ), f"finance_insight_engine importiert {name}"


def test_auswertungen_sind_unabhaengig_vom_zustand_der_import_ki(
    haushalt, engine, jahr
) -> None:
    """Regel 1.2 ueber alle drei Zustaende, die es geben kann.

    Der Coach muss dieselben Zahlen nennen, ob die Import-KI **gar nicht
    existiert**, ob sie **viel gelernt hat** oder ob ihr Speicher
    **nachtraeglich verschwindet**. Ein Test, der nur den leeren Zustand
    prueft, uebersieht genau den Fall, der weh taete: dass die Engine
    stillschweigend etwas aus dem Haendlergedaechtnis mitrechnet.
    """
    ohne_ki = _alle_auswertungen(engine, jahr)
    assert _ki_tabellen(haushalt) == []

    # Zustand zwei: die KI hat gelernt - und zwar zu denselben Kategorien,
    # die der Coach auswertet. Wuerde die Engine sie anfassen, muesste sich
    # jetzt etwas bewegen.
    from model.bank_import_ai import BankImportAI

    ki = BankImportAI(haushalt)
    for text, kategorie in (
        ("MIGROS ZUERICH HB", LEBENSMITTEL),
        ("RESTAURANT KRONE", RESTAURANT),
        ("H&M BAHNHOFSTRASSE", KLEIDUNG),
    ):
        ki.learn(typ=TYP_EXPENSES, category=kategorie, description=text)
    haushalt.commit()
    assert _ki_tabellen(haushalt), "Der Lernspeicher ist nicht entstanden"
    assert _alle_auswertungen(FinanceInsightEngine(haushalt), jahr) == ohne_ki

    # Zustand drei: der Lernspeicher ist weg. Nicht geleert - geloescht.
    for tabelle in _ki_tabellen(haushalt):
        haushalt.execute(f"DROP TABLE {tabelle}")  # nosec B608 - aus sqlite_master
    haushalt.commit()
    assert _ki_tabellen(haushalt) == []
    assert _alle_auswertungen(FinanceInsightEngine(haushalt), jahr) == ohne_ki


def _alle_auswertungen(engine: FinanceInsightEngine, jahr) -> dict[str, object]:
    """Ein vergleichbarer Abzug saemtlicher Auswertungen der Engine."""
    return {
        "gesamt": asdict(engine.period_totals(jahr)),
        "je_monat": {m: asdict(t) for m, t in engine.monthly_totals(jahr).items()},
        "kategorien": [asdict(c) for c in engine.category_totals(TYP_EXPENSES, jahr)],
        "trend": asdict(engine.category_trend(TYP_EXPENSES, RESTAURANT, today=HEUTE)),
        "budget": [asdict(d) for d in engine.budget_deviations(2025, 12)],
        "sparziele": [asdict(s) for s in engine.savings_goal_states()],
        "tags": [asdict(t) for t in engine.tag_totals(TYP_EXPENSES, jahr)],
        "dauerauftraege": [asdict(r) for r in engine.recurring_commitments()],
    }


# ── Die sieben Pflichtgroessen aus P3.1 ─────────────────────────────────────


def test_gesamtausgaben(engine, jahr) -> None:
    assert engine.period_totals(jahr).expenses == pytest.approx(ERWARTET_AUSGABEN)


def test_einkommen(engine, jahr) -> None:
    assert engine.period_totals(jahr).income == pytest.approx(ERWARTET_EINKOMMEN)


def test_monatsueberschuss(engine, jahr) -> None:
    """Ueberschuss ist Einkommen minus Ausgaben - Gespartes ist nicht verbraucht."""
    gesamt = engine.period_totals(jahr)
    assert gesamt.surplus == pytest.approx(ERWARTET_UEBERSCHUSS)
    assert gesamt.average_monthly_surplus == pytest.approx(ERWARTET_UEBERSCHUSS / 12)

    dezember = engine.month_totals(2025, 12)
    # 1800 Miete + 520 Lebensmittel + 220 Restaurant + 190 Hobby + 100 Kleidung
    assert dezember.expenses == pytest.approx(2830.0)
    assert dezember.surplus == pytest.approx(6200.0 - 2830.0)

    je_monat = engine.monthly_totals(jahr)
    assert len(je_monat) == 12
    assert sum(t.surplus for t in je_monat.values()) == pytest.approx(
        ERWARTET_UEBERSCHUSS
    )


def test_ersparnisse_trennen_einzahlung_und_bezug(engine, jahr) -> None:
    """Ein Bezug ist keine negative Einzahlung - sonst waere der Bestand falsch."""
    gesamt = engine.period_totals(jahr)
    assert gesamt.savings_deposits == pytest.approx(ERWARTET_EINZAHLUNGEN)
    assert gesamt.savings_withdrawals == pytest.approx(ERWARTET_BEZUEGE)
    assert gesamt.net_savings == pytest.approx(3100.0)
    # Der Bezug darf die Ausgaben nicht beruehren: Er ist kein Konsum.
    assert gesamt.expenses == pytest.approx(ERWARTET_AUSGABEN)

    august = engine.month_totals(2025, 8)
    assert august.savings_deposits == pytest.approx(300.0)
    assert august.savings_withdrawals == pytest.approx(500.0)


def test_kategorien_mit_anteil_und_attributen(engine, jahr) -> None:
    kategorien = engine.category_totals(TYP_EXPENSES, jahr)
    nach_name = {c.category: c for c in kategorien}

    assert [c.category for c in kategorien] == [
        MIETE,
        LEBENSMITTEL,
        KLEIDUNG,
        HOBBY,
        RESTAURANT,
    ], "Groesster Posten zuerst"

    assert nach_name[MIETE].amount == pytest.approx(ERWARTET_MIETE)
    assert nach_name[LEBENSMITTEL].amount == pytest.approx(ERWARTET_LEBENSMITTEL)
    assert nach_name[RESTAURANT].amount == pytest.approx(ERWARTET_RESTAURANT)
    assert nach_name[HOBBY].amount == pytest.approx(ERWARTET_HOBBY)
    assert nach_name[KLEIDUNG].amount == pytest.approx(ERWARTET_KLEIDUNG)

    assert sum(c.share for c in kategorien) == pytest.approx(1.0)
    assert nach_name[MIETE].share == pytest.approx(ERWARTET_MIETE / ERWARTET_AUSGABEN)

    # Die Fixkostenattribute sind eine eigene Datenquelle der Phase.
    assert nach_name[MIETE].is_fix is True
    assert nach_name[MIETE].is_recurring is True
    assert nach_name[MIETE].forecast_mode == "incremental"
    assert nach_name[RESTAURANT].is_fix is False
    assert nach_name[RESTAURANT].forecast_mode == "normal"

    assert all(c.months_with_bookings == 12 for c in kategorien)


def test_trends_ueber_median_und_mit_rauschgrenze(engine) -> None:
    """Drei Faelle in einem: gestiegen, gesunken, und unerheblich veraendert."""
    hoch = engine.category_trend(TYP_EXPENSES, RESTAURANT, today=HEUTE)
    assert hoch is not None
    assert hoch.previous_median == pytest.approx(80.0)
    assert hoch.recent_median == pytest.approx(220.0)
    assert hoch.delta == pytest.approx(140.0)
    assert hoch.direction == DIRECTION_UP

    runter = engine.category_trend(TYP_EXPENSES, KLEIDUNG, today=HEUTE)
    assert runter.direction == DIRECTION_DOWN
    assert runter.delta == pytest.approx(-200.0)

    # 200 -> 190 ist eine echte Veraenderung, aber unter beiden Rauschgrenzen.
    ruhig = engine.category_trend(TYP_EXPENSES, HOBBY, today=HEUTE)
    assert ruhig.delta == pytest.approx(-10.0)
    assert ruhig.direction == DIRECTION_FLAT

    # Der Median glaettet den steigenden Einkauf, statt ihm zu folgen.
    einkauf = engine.category_trend(TYP_EXPENSES, LEBENSMITTEL, today=HEUTE)
    assert einkauf.previous_median == pytest.approx(480.0)
    assert einkauf.recent_median == pytest.approx(510.0)
    assert einkauf.direction == DIRECTION_UP

    # Ueber alle Kategorien heben sich die Verschiebungen fast auf: Restaurant
    # und Lebensmittel steigen, Kleidung und Hobby sinken. Genau deshalb ist
    # ein Gesamttrend allein nutzlos - die Aussage steckt in den Kategorien.
    gesamt = engine.category_trend(TYP_EXPENSES, None, today=HEUTE)
    assert gesamt.category is None
    assert gesamt.previous_median == pytest.approx(2860.0)
    assert gesamt.recent_median == pytest.approx(2820.0)
    assert gesamt.direction == DIRECTION_FLAT


def test_trend_ohne_ausreichende_historie_ist_none(engine) -> None:
    """Ein Trend ueber Monate, die es nie gab, waere erfunden."""
    assert (
        engine.category_trend(TYP_EXPENSES, MIETE, months_per_window=7, today=HEUTE)
        is None
    )


def test_budgetabweichungen(engine) -> None:
    abweichungen = engine.budget_deviations(2025, 12, typ=TYP_EXPENSES)
    nach_name = {d.category: d for d in abweichungen}

    lebensmittel = nach_name[LEBENSMITTEL]
    assert lebensmittel.budget == pytest.approx(450.0)
    assert lebensmittel.actual == pytest.approx(520.0)
    assert lebensmittel.rest == pytest.approx(-70.0)
    assert lebensmittel.is_over is True
    assert lebensmittel.deviation_percent == pytest.approx(70.0 / 450.0 * 100.0)

    miete = nach_name[MIETE]
    assert miete.rest == pytest.approx(0.0)
    assert miete.is_over is False

    # Nie budgetiert ist etwas anderes als ueberzogen.
    restaurant = nach_name[RESTAURANT]
    assert restaurant.has_budget is False
    assert restaurant.is_over is False
    assert restaurant.is_unbudgeted is True
    assert restaurant.deviation_percent is None

    assert [d.category for d in abweichungen] == [
        LEBENSMITTEL,
        MIETE,
        RESTAURANT,
        HOBBY,
        KLEIDUNG,
    ], "Echte Ueberschreitungen zuerst, nie budgetierte danach nach Betrag"


def test_sparzielanalyse(engine) -> None:
    ziele = engine.savings_goal_states()
    assert len(ziele) == 1
    ziel = ziele[0]

    assert ziel.name == NOTGROSCHEN
    assert ziel.category == NOTGROSCHEN
    assert ziel.target_amount == pytest.approx(12000.0)
    # Der Bezug hat den Bestand gesenkt: 3600 eingezahlt, 500 entnommen.
    assert ziel.current_amount == pytest.approx(3100.0)
    assert ziel.remaining_amount == pytest.approx(8900.0)
    assert ziel.progress_percent == pytest.approx(3100.0 / 12000.0 * 100.0)

    # Die Rate kommt aus den Buchungen, nicht aus dem Bestand - und der Bezug
    # zaehlt nicht als Einzahlungsmonat mit halbem Betrag.
    assert ziel.observed_monthly_contribution == pytest.approx(300.0)
    assert ziel.contribution_months == 12


# ── Die uebrigen Datenquellen der Phase ─────────────────────────────────────


def test_tags_sind_eine_eigene_sicht_und_keine_aufteilung(engine, jahr) -> None:
    tags = engine.tag_totals(TYP_EXPENSES, jahr)
    assert len(tags) == 1
    assert tags[0].tag == "Haushalt"
    assert tags[0].bookings == 12
    assert tags[0].amount == pytest.approx(ERWARTET_LEBENSMITTEL)
    # Ein Tag haengt an einer Buchung, die auch in ihrer Kategorie steht.
    assert tags[0].amount < engine.period_totals(jahr).expenses


def test_dauerauftraege_bleiben_von_den_buchungen_getrennt(engine) -> None:
    dauerauftraege = engine.recurring_commitments()
    assert len(dauerauftraege) == 1
    assert dauerauftraege[0].category == MIETE
    assert dauerauftraege[0].amount == pytest.approx(1800.0)
    assert dauerauftraege[0].day_of_month == 1


# ── Zeitachse und Vorzeichen ────────────────────────────────────────────────


def test_der_laufende_monat_ist_kein_vergleichswert(haushalt, engine) -> None:
    """Ein halber Monat sieht wie ein sparsamer Monat aus."""
    TrackingModel(haushalt).add(
        date(2026, 1, 3), TYP_EXPENSES, LEBENSMITTEL, 90.0, "Anfang Januar"
    )
    haushalt.commit()

    assert engine.last_complete_month(today=HEUTE) == (2025, 12)
    monate = engine.recent_complete_months(12, today=HEUTE)
    assert (2026, 1) not in monate
    assert engine.period_totals(monate).expenses == pytest.approx(ERWARTET_AUSGABEN)

    # Wer den laufenden Monat trotzdem braucht, bekommt ihn ausdruecklich.
    assert engine.month_totals(2026, 1).expenses == pytest.approx(90.0)


def test_monat_ohne_buchung_steht_mit_null_in_der_reihe(engine) -> None:
    """Sonst rutscht ein aelterer Monat stillschweigend ins Vergleichsfenster."""
    monate = engine.recent_complete_months(15, today=HEUTE)
    assert monate[0] == (2024, 10)
    je_monat = engine.monthly_totals(monate)
    assert je_monat[(2024, 10)].expenses == pytest.approx(0.0)
    assert je_monat[(2024, 10)].income == pytest.approx(0.0)


def test_rueckerstattung_senkt_die_ausgaben(haushalt, engine, jahr) -> None:
    """Eine Gutschrift innerhalb des Monats verrechnet sich, statt zu addieren."""
    TrackingModel(haushalt).add(
        date(2025, 12, 20), TYP_EXPENSES, LEBENSMITTEL, -100.0, "Ruecklauf"
    )
    haushalt.commit()

    assert engine.month_totals(2025, 12).expenses == pytest.approx(2830.0 - 100.0)
    assert engine.period_totals(jahr).expenses == pytest.approx(
        ERWARTET_AUSGABEN - 100.0
    )
    nach_name = {c.category: c for c in engine.category_totals(TYP_EXPENSES, jahr)}
    assert nach_name[LEBENSMITTEL].amount == pytest.approx(
        ERWARTET_LEBENSMITTEL - 100.0
    )


def test_die_engine_haelt_keinen_eigenen_stand(haushalt, engine, jahr) -> None:
    """Kein Cache heisst: die naechste Frage sieht die neue Buchung sofort."""
    vorher = engine.period_totals(jahr).expenses
    TrackingModel(haushalt).add(
        date(2025, 6, 15), TYP_EXPENSES, RESTAURANT, 60.0, "Nachtrag"
    )
    haushalt.commit()
    assert engine.period_totals(jahr).expenses == pytest.approx(vorher + 60.0)
