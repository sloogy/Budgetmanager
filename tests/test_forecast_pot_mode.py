"""Regressionstests für Forecast-Modus Pot vs. inkrementell (v2.0.37).

Ziel:
- Fix ohne Wiederholung ist standardmässig ein Pot (z. B. Franchise).
- Pot wird gegen den Gesamt-Topf geprüft, nicht gegen jedes Monatsbudget.
- Inkrementell bleibt für Jahresrechnungen/Teilzahlungen verfügbar.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.budget_suggestion_engine import BudgetSuggestionEngine  # noqa: E402
from model.migrations import migrate_all  # noqa: E402
from model.typ_constants import TYP_EXPENSES  # noqa: E402


def _prev_months(year: int, month: int, n: int):
    out = []
    y, m = year, month
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    return out


def _add_category(conn, name: str, *, is_fix=True, is_recurring=False, forecast_mode="auto"):
    conn.execute(
        """
        INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day, forecast_mode)
        VALUES(?,?,?,?,1,?)
        """,
        (TYP_EXPENSES, name, 1 if is_fix else 0, 1 if is_recurring else 0, forecast_mode),
    )


def _set_budget(conn, name: str, months, amount: float):
    for y, m in months:
        conn.execute(
            """
            INSERT OR REPLACE INTO budget(year, month, typ, category, amount)
            VALUES(?,?,?,?,?)
            """,
            (y, m, TYP_EXPENSES, name, amount),
        )


def _book_amounts(conn, name: str, amounts_by_month: dict[tuple[int, int], float]):
    for (y, m), amount in amounts_by_month.items():
        if amount == 0:
            continue
        conn.execute(
            """
            INSERT INTO tracking(date, typ, category, amount, details)
            VALUES(?,?,?,?,?)
            """,
            (f"{y:04d}-{m:02d}-15", TYP_EXPENSES, name, float(amount), "forecast-pot-test"),
        )


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    migrate_all(c)
    yield c
    c.close()


def test_fixed_non_recurring_default_pot_exceeded_suggests(conn):
    """Budget 750, Ist 250/250/400/0/0/0 => Pot 900 > 750, Vorschlag erlaubt."""
    months = _prev_months(2026, 7, 7)  # Ziel Juli + 6 abgeschlossene Monate
    _add_category(conn, "Franchise", is_fix=True, is_recurring=False)
    _set_budget(conn, "Franchise", months, 750.0)
    _book_amounts(conn, "Franchise", {(2026, 1): 250, (2026, 2): 250, (2026, 3): 400})

    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        typ=TYP_EXPENSES, category="Franchise", year=2026, month=7, months_back=6
    )

    assert res is not None
    assert res.direction == "deficit"
    assert res.current_budget == 750.0
    assert res.suggested_budget == 870.0


def test_fixed_non_recurring_default_pot_zero_whole_year_highlights(conn):
    """Budget 750, Ist 0 über 12 Monate => prüfen/senken statt still ignorieren."""
    months = _prev_months(2027, 1, 13)  # Ziel Jan 2027 + Jahr 2026
    _add_category(conn, "Ungenutzter Pot", is_fix=True, is_recurring=False)
    _set_budget(conn, "Ungenutzter Pot", months, 750.0)

    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        typ=TYP_EXPENSES, category="Ungenutzter Pot", year=2027, month=1, months_back=12
    )

    assert res is not None
    assert res.suggested_budget < 750.0


def test_fixed_non_recurring_default_pot_small_partial_usage_no_suggestion(conn):
    """Budget 750, Ist 10/50/40/100/10/0/0/10 => 220 <= 750, kein Vorschlag."""
    months = _prev_months(2026, 9, 9)  # Ziel Sep + Jan-Aug
    _add_category(conn, "Franchise klein", is_fix=True, is_recurring=False)
    _set_budget(conn, "Franchise klein", months, 750.0)
    _book_amounts(
        conn,
        "Franchise klein",
        {
            (2026, 1): 10,
            (2026, 2): 50,
            (2026, 3): 40,
            (2026, 4): 100,
            (2026, 5): 10,
            (2026, 8): 10,
        },
    )

    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        typ=TYP_EXPENSES, category="Franchise klein", year=2026, month=9, months_back=8
    )

    assert res is None


def test_fixed_non_recurring_incremental_override_treats_as_yearly_bill(conn):
    """Explizit inkrementell: 900 Ist gegen 6×750 Budget ist gedeckt, also kein Erhöhen."""
    months = _prev_months(2026, 7, 7)
    _add_category(
        conn,
        "Hausratversicherung",
        is_fix=True,
        is_recurring=False,
        forecast_mode="incremental",
    )
    _set_budget(conn, "Hausratversicherung", months, 750.0)
    _book_amounts(conn, "Hausratversicherung", {(2026, 1): 250, (2026, 2): 250, (2026, 3): 400})

    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        typ=TYP_EXPENSES,
        category="Hausratversicherung",
        year=2026,
        month=7,
        months_back=6,
    )

    assert res is None


def test_pot_overuse_suggests_even_when_first_booking_is_late(conn):
    """Ein überzogener Pot darf nicht durch die Tracking-Startgrenze verschwinden."""
    months = _prev_months(2026, 7, 7)
    _add_category(conn, "Franchise spät", is_fix=True, is_recurring=False)
    _set_budget(conn, "Franchise spät", months, 750.0)
    _book_amounts(conn, "Franchise spät", {(2026, 5): 300, (2026, 6): 700})

    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        typ=TYP_EXPENSES, category="Franchise spät", year=2026, month=7, months_back=6
    )

    assert res is not None
    assert res.direction == "deficit"
    assert res.suggested_budget > 750.0


def test_pot_zero_year_does_not_reduce_when_app_usage_started_recently(conn):
    """12 Budgetmonate allein reichen nicht, wenn die echte Nutzung erst spät begann."""
    months = _prev_months(2027, 1, 13)
    _add_category(conn, "Ungenutzter alter Pot", is_fix=True, is_recurring=False)
    _add_category(conn, "Alltag", is_fix=False, is_recurring=False)
    _set_budget(conn, "Ungenutzter alter Pot", months, 750.0)
    # Globale erste echte Buchung im Dezember: Monate davor sind keine bewiesene 0-Nutzung.
    _book_amounts(conn, "Alltag", {(2026, 12): 10})

    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        typ=TYP_EXPENSES, category="Ungenutzter alter Pot", year=2027, month=1, months_back=12
    )

    assert res is None
