"""Regressionstests: Budgetvorschläge respektieren den Tracking-Beginn (v2.0.18).

Bug (gemeldet aus dem GUI): Bei nur EINEM gebuchten Monat, aber Budgets über
mehrere Monate, schlug die Engine bereits Anpassungen vor und zeigte unmögliche
Häufigkeiten wie "5/3". Ursache: Die Engine zählte stur bis Januar/Vorjahr
zurück und las Monate VOR dem ersten echten Buchungsmonat als reale
"0-Ausgaben"-Monate.

Fix: Untere Analysegrenze = spätester von (erste echte Buchung global,
konfigurierter Startmonat). Monate davor werden in Abweichungsfenster,
aktiven Monaten und Strähnen ignoriert. Die Langzeit-0-Reduktion (Budget
gesetzt, nie gebucht) bleibt erhalten, weil ohne jede Buchung keine Grenze
existiert und somit nicht geklammert wird.

Läuft ohne Qt/PySide6.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.budget_suggestion_engine import BudgetSuggestionEngine
from model.migrations import migrate_all
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS

# ── Helpers ──────────────────────────────────────────────────────


def _add_category(conn, typ, name, *, is_fix=False, is_recurring=False):
    conn.execute(
        "INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day) "
        "VALUES(?,?,?,?,1)",
        (typ, name, 1 if is_fix else 0, 1 if is_recurring else 0),
    )


def _set_budget(conn, typ, name, months, amount):
    for y, m in months:
        conn.execute(
            "INSERT OR REPLACE INTO budget(year, month, typ, category, amount) "
            "VALUES(?,?,?,?,?)",
            (y, m, typ, name, amount),
        )


def _book(conn, typ, name, year, month, amount):
    if amount == 0:
        return
    conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details) "
        "VALUES(?,?,?,?,?)",
        (f"{year:04d}-{month:02d}-15", typ, name, amount, "test"),
    )


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    migrate_all(c)
    yield c
    c.close()


# ── Kernregression: nur 1 gebuchter Monat → keine Vorschläge ──────


def test_single_booked_month_yields_no_suggestion(conn):
    """Budgets Jan–Jun 2026, aber nur Juni gebucht → kein Vorschlag."""
    months = [(2026, m) for m in range(1, 7)]
    _add_category(conn, TYP_INCOME, "Lohn (Netto)")
    _add_category(conn, TYP_EXPENSES, "Hobbys")
    _add_category(conn, TYP_SAVINGS, "Hochzeit")
    _set_budget(conn, TYP_INCOME, "Lohn (Netto)", months, 5000.0)
    _set_budget(conn, TYP_EXPENSES, "Hobbys", months, 40.0)
    _set_budget(conn, TYP_SAVINGS, "Hochzeit", [(2026, 6)], 400.0)
    # NUR Juni gebucht
    _book(conn, TYP_INCOME, "Lohn (Netto)", 2026, 6, 5000.0)
    _book(conn, TYP_SAVINGS, "Hochzeit", 2026, 6, 10000.0)
    # Hobbys: gar keine Buchung

    eng = BudgetSuggestionEngine(conn)
    for typ, cat in [
        (TYP_INCOME, "Lohn (Netto)"),
        (TYP_EXPENSES, "Hobbys"),
        (TYP_SAVINGS, "Hochzeit"),
    ]:
        res = eng.compute_category_suggestion(
            typ=typ, category=cat, year=2026, month=6, months_back=3
        )
        assert res is None, f"{cat}: kein Vorschlag bei nur 1 echtem Buchungsmonat"


def test_data_start_boundary_is_first_booking(conn):
    """Die ermittelte Grenze ist der erste echte Buchungsmonat (global)."""
    _add_category(conn, TYP_EXPENSES, "Essen")
    _set_budget(conn, TYP_EXPENSES, "Essen", [(2026, m) for m in range(1, 8)], 500.0)
    _book(conn, TYP_EXPENSES, "Essen", 2026, 6, 300.0)
    eng = BudgetSuggestionEngine(conn)
    assert eng._data_start_boundary() == date(2026, 6, 1)


def test_no_boundary_without_any_booking(conn):
    """Ohne jede Buchung gibt es keine Grenze (None) → Langzeit-0-Reduktion bleibt möglich."""
    _add_category(conn, TYP_EXPENSES, "Essen")
    _set_budget(conn, TYP_EXPENSES, "Essen", [(2026, m) for m in range(1, 8)], 500.0)
    eng = BudgetSuggestionEngine(conn)
    assert eng._data_start_boundary() is None


# ── Positivkontrolle: genug echte Monate NACH Start → Vorschlag ──


def test_enough_real_months_after_start_still_suggests(conn):
    """3 echte Monate (Apr–Jun) konsequent unter Budget → Senkung vorgeschlagen."""
    _add_category(conn, TYP_EXPENSES, "Essen")
    _set_budget(conn, TYP_EXPENSES, "Essen", [(2026, m) for m in range(1, 8)], 500.0)
    for m in (4, 5, 6):
        _book(conn, TYP_EXPENSES, "Essen", 2026, m, 300.0)

    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        typ=TYP_EXPENSES, category="Essen", year=2026, month=7, months_back=3
    )
    assert res is not None
    assert res.suggested_budget < 500.0
    # Ehrliche Strähne: genau die 3 echten Monate, NICHT künstlich aufs Fenster gehoben.
    assert res.streak_months == 3


def test_one_real_month_too_few_no_suggestion(conn):
    """Nur 2 echte Monate vor dem Zielmonat → noch kein Vorschlag."""
    _add_category(conn, TYP_EXPENSES, "Essen")
    _set_budget(conn, TYP_EXPENSES, "Essen", [(2026, m) for m in range(1, 8)], 500.0)
    for m in (5, 6):
        _book(conn, TYP_EXPENSES, "Essen", 2026, m, 300.0)

    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        typ=TYP_EXPENSES, category="Essen", year=2026, month=7, months_back=3
    )
    assert res is None


# ── Langzeit-0-Reduktion bleibt erhalten (Frage 2: gewollt) ──────


def test_long_unused_budget_still_reduces(conn):
    """Budget gesetzt, NIE gebucht (>=6 Monate) → Senkung greift weiterhin."""
    months = [(2025, m) for m in range(1, 13)]  # ganzes Jahr budgetiert, nie gebucht
    _add_category(conn, TYP_EXPENSES, "Hobby")
    _set_budget(conn, TYP_EXPENSES, "Hobby", months, 1500.0)
    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        typ=TYP_EXPENSES, category="Hobby", year=2025, month=12, months_back=6
    )
    assert res is not None, "Langzeit-0-Reduktion muss erhalten bleiben"
    assert res.suggested_budget < 1500.0
