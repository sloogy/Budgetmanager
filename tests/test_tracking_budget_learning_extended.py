"""Regression: erweiterter Lernmodus für neue Budgets aus Tracking."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.budget_learning import (  # noqa: E402
    KIND_FIXED_RECURRING,
    KIND_IRREGULAR,
    KIND_VARIABLE_INCOME,
    KIND_VARIABLE_POT,
    apply_learning_budget_kind,
)
from model.category_forecast_mode import FORECAST_MODE_NORMAL, FORECAST_MODE_POT  # noqa: E402
from model.migrations import migrate_all  # noqa: E402
from model.budget_overview_model import BudgetOverviewModel  # noqa: E402
from model.typ_constants import TYP_EXPENSES, TYP_INCOME  # noqa: E402
from model.year_copy_rules import list_year_copy_review_rows  # noqa: E402


def _add_category(conn: sqlite3.Connection, typ: str, name: str) -> None:
    conn.execute(
        "INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day) VALUES(?,?,?,?,1)",
        (typ, name, 0, 0),
    )


def _book(conn: sqlite3.Connection, typ: str, category: str, year: int, month: int, amount: float) -> None:
    conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details, source) VALUES(?,?,?,?,?,?)",
        (f"{year:04d}-{month:02d}-15", typ, category, amount, "test", "manual"),
    )


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    migrate_all(c)
    yield c
    c.close()


def test_learning_classifies_fixed_recurring_expense(conn: sqlite3.Connection) -> None:
    _add_category(conn, TYP_EXPENSES, "Miete")
    for month in (4, 5, 6):
        _book(conn, TYP_EXPENSES, "Miete", 2026, month, 1410.0)

    suggestions = BudgetOverviewModel(conn).get_tracking_budget_suggestions(
        year=2026,
        current_month=6,
        enabled=True,
        proposal_months=2,
        stable_months=3,
        include_current_month_projection=False,
    )

    sug = next(s for s in suggestions if s.category == "Miete")
    assert sug.direction == "initial"
    assert sug.budget_kind == KIND_FIXED_RECURRING
    assert sug.suggested_amount == 1410.0


def test_learning_classifies_variable_income_and_rounds_down(conn: sqlite3.Connection) -> None:
    _add_category(conn, TYP_INCOME, "Lohn")
    for month, amount in [(4, 4820.0), (5, 5130.0), (6, 4760.0)]:
        _book(conn, TYP_INCOME, "Lohn", 2026, month, amount)

    suggestions = BudgetOverviewModel(conn).get_tracking_budget_suggestions(
        year=2026,
        current_month=6,
        types=[TYP_INCOME],
        enabled=True,
        proposal_months=2,
        stable_months=3,
        include_current_month_projection=False,
        round_to=10,
    )

    sug = next(s for s in suggestions if s.category == "Lohn")
    assert sug.direction == "initial"
    assert sug.budget_kind == KIND_VARIABLE_INCOME
    assert sug.suggested_amount == 4750.0


def test_learning_irregular_health_uses_monthly_reserve(conn: sqlite3.Connection) -> None:
    _add_category(conn, TYP_EXPENSES, "Gesundheit")
    _book(conn, TYP_EXPENSES, "Gesundheit", 2026, 3, 250.0)
    _book(conn, TYP_EXPENSES, "Gesundheit", 2026, 5, 400.0)

    suggestions = BudgetOverviewModel(conn).get_tracking_budget_suggestions(
        year=2026,
        current_month=6,
        enabled=True,
        proposal_months=2,
        stable_months=3,
        include_current_month_projection=False,
        round_to=10,
    )

    sug = next(s for s in suggestions if s.category == "Gesundheit")
    assert sug.budget_kind == KIND_IRREGULAR
    # März-Juni: 250 + 0 + 400 + 0 = 650 / 4 = 162.50 → Ausgaben auf 10er aufrunden.
    assert sug.suggested_amount == 170.0
    assert sug.observed_months == 4


def test_applying_learning_kind_updates_category_flags(conn: sqlite3.Connection) -> None:
    _add_category(conn, TYP_EXPENSES, "Franchise")

    apply_learning_budget_kind(conn, TYP_EXPENSES, "Franchise", KIND_IRREGULAR)

    row = conn.execute(
        "SELECT is_fix, is_recurring, forecast_mode FROM categories WHERE typ=? AND name=?",
        (TYP_EXPENSES, "Franchise"),
    ).fetchone()
    assert int(row["is_fix"]) == 0
    assert int(row["is_recurring"]) == 0
    assert row["forecast_mode"] == FORECAST_MODE_POT


def test_year_copy_review_includes_tracking_only_learning_rows(conn: sqlite3.Connection) -> None:
    _add_category(conn, TYP_EXPENSES, "Essen")
    for month, amount in [(9, 520.0), (10, 610.0), (11, 570.0)]:
        _book(conn, TYP_EXPENSES, "Essen", 2026, month, amount)

    suggestions = BudgetOverviewModel(conn).get_tracking_budget_suggestions(
        year=2026,
        current_month=11,
        types=[TYP_EXPENSES],
        enabled=True,
        proposal_months=2,
        stable_months=3,
        include_current_month_projection=False,
        round_to=10,
    )
    sug = next(s for s in suggestions if s.category == "Essen")
    assert sug.budget_kind == KIND_VARIABLE_POT
    assert sug.suggested_amount == 580.0

    rows = list_year_copy_review_rows(conn, 2026, typ=TYP_EXPENSES)

    row = next(r for r in rows if r.category == "Essen")
    assert row.budget_total == 6960.0  # 580 monatlich * 12
    assert row.forecast_mode == FORECAST_MODE_NORMAL
