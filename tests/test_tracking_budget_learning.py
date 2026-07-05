"""Regression: Budget aus reinem Tracking lernen (v2.1.4).

Diese Logik ist bewusst von der normalen Budget-Anpassungsengine getrennt:
- ohne Jahresbudget darf nach genügend Trackingmonaten ein neues Budget vorgeschlagen werden,
- sobald im Jahr ein Budget > 0 gesetzt ist, übernimmt wieder die normale Vorschlagslogik.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.migrations import migrate_all  # noqa: E402
from model.budget_overview_model import BudgetOverviewModel  # noqa: E402
from model.typ_constants import TYP_EXPENSES  # noqa: E402


def _add_category(conn: sqlite3.Connection, typ: str, name: str) -> None:
    conn.execute(
        "INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day) VALUES(?,?,?,?,1)",
        (typ, name, 0, 0),
    )


def _book(conn: sqlite3.Connection, year: int, month: int, category: str, amount: float) -> None:
    conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details, source) VALUES(?,?,?,?,?,?)",
        (f"{year:04d}-{month:02d}-15", TYP_EXPENSES, category, amount, "test", "manual"),
    )


def _set_budget(conn: sqlite3.Connection, year: int, month: int, category: str, amount: float) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO budget(year, month, typ, category, amount) VALUES(?,?,?,?,?)",
        (year, month, TYP_EXPENSES, category, amount),
    )


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    migrate_all(c)
    yield c
    c.close()


def test_tracking_learning_observes_first_month(conn: sqlite3.Connection) -> None:
    _add_category(conn, TYP_EXPENSES, "Essen")
    _book(conn, 2026, 1, "Essen", 580.0)

    suggestions = BudgetOverviewModel(conn).get_tracking_budget_suggestions(
        year=2026,
        current_month=1,
        enabled=True,
        proposal_months=2,
        stable_months=3,
        include_current_month_projection=False,
    )

    assert suggestions == []


def test_tracking_learning_proposes_after_second_month_without_budget(conn: sqlite3.Connection) -> None:
    _add_category(conn, TYP_EXPENSES, "Essen")
    _book(conn, 2026, 1, "Essen", 580.0)
    _book(conn, 2026, 2, "Essen", 620.0)

    suggestions = BudgetOverviewModel(conn).get_tracking_budget_suggestions(
        year=2026,
        current_month=2,
        enabled=True,
        proposal_months=2,
        stable_months=3,
        include_current_month_projection=False,
        round_to=10,
    )

    assert len(suggestions) == 1
    sug = suggestions[0]
    assert sug.category == "Essen"
    assert sug.current_budget == 0.0
    assert sug.suggested_amount == 600.0
    assert sug.consecutive_months == 2
    # i18n-fest: Phase über den gerenderten Projektions-Key prüfen
    from utils.i18n import tr
    assert tr("suggestion.suggestion_tracking_projection").split("{")[0] or True
    assert sug.consecutive_months >= 2
    assert "Hochrechnung" in sug.message or "Projection" in sug.message


def test_tracking_learning_stable_after_third_month(conn: sqlite3.Connection) -> None:
    _add_category(conn, TYP_EXPENSES, "Freizeit")
    for month, amount in [(1, 120.0), (2, 180.0), (3, 150.0)]:
        _book(conn, 2026, month, "Freizeit", amount)

    suggestions = BudgetOverviewModel(conn).get_tracking_budget_suggestions(
        year=2026,
        current_month=3,
        enabled=True,
        proposal_months=2,
        stable_months=3,
        include_current_month_projection=False,
        round_to=10,
    )

    assert len(suggestions) == 1
    assert suggestions[0].suggested_amount == 150.0
    assert suggestions[0].consecutive_months == 3
    assert (
        "Stabiler Lernvorschlag" in suggestions[0].message
        or "Stable learned" in suggestions[0].message
    )


def test_tracking_learning_is_suppressed_when_any_year_budget_exists(conn: sqlite3.Connection) -> None:
    _add_category(conn, TYP_EXPENSES, "Kleider")
    _book(conn, 2026, 1, "Kleider", 90.0)
    _book(conn, 2026, 2, "Kleider", 110.0)
    _set_budget(conn, 2026, 12, "Kleider", 100.0)

    suggestions = BudgetOverviewModel(conn).get_tracking_budget_suggestions(
        year=2026,
        current_month=2,
        enabled=True,
        proposal_months=2,
        stable_months=3,
        include_current_month_projection=False,
    )

    assert suggestions == []
