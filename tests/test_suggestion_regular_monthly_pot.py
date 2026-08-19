"""Regression: Fix-/Pot-Kategorie mit regelmässiger Monatsbuchung.

Hintergrund (Screenshot-Bug v2.1.0):
Eine als Fix (ohne Wiederkehrend) markierte Kategorie wird per Default als
Pot/Rückstellung klassifiziert. Lebensmittel mit Budget 400/Monat und
Buchungen in JEDEM Monat (380/420/430/510/500) erzeugte den Vorschlag 1230 –
weil die Pot-Logik die Summe mehrerer Monate (1440) gegen EIN Monatsbudget
(400) verglich (1440-400 => +830 => 1230).

Fix: Ist eine "Pot"-Kategorie in jedem Fenstermonat gebucht, ist sie de facto
eine laufende Monatsausgabe und wird pro Monat verglichen. Echte Töpfe
(lumpy/unregelmässig, z.B. Franchise) behalten die Topf-Logik.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.budget_overview_model import BudgetOverviewModel  # noqa: E402
from model.budget_suggestion_engine import BudgetSuggestionEngine  # noqa: E402
from model.migrations import migrate_all  # noqa: E402
from model.typ_constants import TYP_EXPENSES  # noqa: E402


def _add_category(conn, name, *, is_fix, is_recurring):
    conn.execute(
        "INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day) "
        "VALUES(?,?,?,?,25)",
        (TYP_EXPENSES, name, 1 if is_fix else 0, 1 if is_recurring else 0),
    )


def _set_budget_all_year(conn, name, amount, year=2026):
    for m in range(1, 13):
        conn.execute(
            "INSERT OR REPLACE INTO budget(year, month, typ, category, amount) "
            "VALUES(?,?,?,?,?)",
            (year, m, TYP_EXPENSES, name, amount),
        )


def _book(conn, name, month, amount, year=2026):
    conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, source) VALUES(?,?,?,?,?)",
        (f"{year:04d}-{month:02d}-01", TYP_EXPENSES, name, float(amount), "manual"),
    )


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    migrate_all(c)
    yield c
    c.close()


def _suggestion_for(conn, name, current_month):
    overview = BudgetOverviewModel(conn)
    for s in overview.get_suggestions(2026, current_month, min_consecutive_months=3):
        if s.category == name:
            return s
    return None


def test_regular_monthly_fix_category_is_not_inflated_like_a_pot(conn):
    """Lebensmittel 400/Monat, jeden Monat gebucht: Vorschlag bleibt monatlich.

    Kein 1230 mehr – die Erhöhung entspricht der mittleren Monats-Überschreitung,
    nicht der aufsummierten Fenster-Differenz.
    """
    _add_category(conn, "Lebensmittel", is_fix=True, is_recurring=False)
    _set_budget_all_year(conn, "Lebensmittel", 400.0)
    for month, amount in {1: 380, 2: 420, 3: 430, 4: 510, 5: 500}.items():
        _book(conn, "Lebensmittel", month, amount)

    s = _suggestion_for(conn, "Lebensmittel", current_month=6)

    assert s is not None
    assert s.direction == "deficit"
    assert s.current_budget == 400.0
    # Fenster Mär/Apr/Mai: Ist 1440 vs Budget 1200 => +240/3 = +80/Monat, *0.8 = 64 -> 460
    assert s.suggested_amount == 460.0
    # Hartes Bug-Bollwerk: niemals wieder die Summe-gegen-Einzelmonat-Inflation
    assert s.suggested_amount < 800.0


def test_regular_monthly_increase_is_modest_and_tracks_current_budget(conn):
    """Vorschlag = aktuelles Monatsbudget + normierte Monats-Überschreitung."""
    _add_category(conn, "Lebensmittel", is_fix=True, is_recurring=False)
    _set_budget_all_year(conn, "Lebensmittel", 400.0)
    for month, amount in {2: 420, 3: 430, 4: 510}.items():
        _book(conn, "Lebensmittel", month, amount)

    s = _suggestion_for(conn, "Lebensmittel", current_month=5)
    assert s is not None
    # Fenster Feb/Mär/Apr: Ist 1360 vs Budget 1200 => +160/3 = 53.3, *0.8 = 42.7 -> 440
    assert s.suggested_amount == 440.0


def test_lumpy_franchise_pot_keeps_pot_semantics(conn):
    """Echter Topf (Franchise): nur in einzelnen Monaten gebucht -> Topf-Logik bleibt.

    Budget 750/Monat, Ist 250/250/400 (3 von 6 Fenstermonaten) => Gesamttopf 750
    überschritten (900) => +120 -> 870. Darf NICHT auf die Monatslogik kippen.
    """
    _add_category(conn, "Franchise", is_fix=True, is_recurring=False)
    _set_budget_all_year(conn, "Franchise", 750.0)
    for month, amount in {1: 250, 2: 250, 3: 400}.items():
        _book(conn, "Franchise", month, amount)

    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        typ=TYP_EXPENSES, category="Franchise", year=2026, month=7, months_back=6
    )
    assert res is not None
    assert res.direction == "deficit"
    assert res.current_budget == 750.0
    assert res.suggested_budget == 870.0


def test_regular_monthly_under_budget_gives_no_increase(conn):
    """Jeden Monat gebucht, aber innerhalb des Budgets -> keine Erhöhung."""
    _add_category(conn, "Lebensmittel", is_fix=True, is_recurring=False)
    _set_budget_all_year(conn, "Lebensmittel", 500.0)
    for month, amount in {3: 400, 4: 450, 5: 480}.items():
        _book(conn, "Lebensmittel", month, amount)

    s = _suggestion_for(conn, "Lebensmittel", current_month=6)
    # Ist 1330 <= Budget 1500 im Fenster -> kein Erhöhungsvorschlag
    assert s is None or s.suggested_amount <= 500.0
