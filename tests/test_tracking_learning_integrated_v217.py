"""Regression v2.1.7: 2.1.6-Lernlogik plus 2.1.5-Statusaktionen.

Ziel: Die bessere zentrale Budgetart-Logik aus 2.1.6 bleibt aktiv, während
persistente Nutzeraktionen aus 2.1.5 wieder funktionieren.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.budget_learning import KIND_IRREGULAR, KIND_VARIABLE_POT
from model.budget_overview_model import BudgetOverviewModel
from model.category_model import CategoryModel
from model.migrations import CURRENT_VERSION, migrate_all
from model.typ_constants import TYP_EXPENSES


def _add_category(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(
        "INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day) VALUES(?,?,?,?,1)",
        (TYP_EXPENSES, name, 0, 0),
    )


def _book(conn: sqlite3.Connection, category: str, month: int, amount: float) -> None:
    conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details, source) VALUES(?,?,?,?,?,?)",
        (f"2026-{month:02d}-15", TYP_EXPENSES, category, amount, "test", "manual"),
    )


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    migrate_all(c)
    yield c
    c.close()


def _suggest(conn: sqlite3.Connection, **overrides):
    params = dict(
        year=2026,
        current_month=7,
        enabled=True,
        proposal_months=2,
        stable_months=3,
        include_current_month_projection=False,
        round_to=10,
        auto_end=False,
        show_in_report=True,
    )
    params.update(overrides)
    return BudgetOverviewModel(conn).get_tracking_budget_suggestions(**params)


def test_learning_state_migration_and_category_cascade_tables_exist(
    conn: sqlite3.Connection,
) -> None:
    assert CURRENT_VERSION >= 15
    cols = [
        row[1]
        for row in conn.execute("PRAGMA table_info(tracking_learning_state)").fetchall()
    ]
    assert cols == ["typ", "category", "status", "snooze_until", "changed_at"]
    assert "tracking_learning_state" in CategoryModel._ALLOWED_SCHEMA_TABLES
    assert "tracking_learning_state" in CategoryModel._CATEGORY_TEXT_REFERENCE_TABLES


def test_watch_later_ignore_reset_and_force_irregular(conn: sqlite3.Connection) -> None:
    _add_category(conn, "Essen")
    for month, amount in [(4, 520), (5, 610), (6, 570)]:
        _book(conn, "Essen", month, amount)
    conn.commit()

    model = BudgetOverviewModel(conn)
    assert (
        next(
            s for s in _suggest(conn, current_month=6) if s.category == "Essen"
        ).budget_kind
        == KIND_VARIABLE_POT
    )

    model.set_learning_action(TYP_EXPENSES, "Essen", "watch_later", year=2026, month=7)
    assert all(s.category != "Essen" for s in _suggest(conn, current_month=7))
    assert any(s.category == "Essen" for s in _suggest(conn, current_month=8))

    model.set_learning_action(TYP_EXPENSES, "Essen", "irregular")
    assert (
        next(
            s for s in _suggest(conn, current_month=6) if s.category == "Essen"
        ).budget_kind
        == KIND_IRREGULAR
    )

    model.set_learning_action(TYP_EXPENSES, "Essen", "ignore")
    assert all(s.category != "Essen" for s in _suggest(conn))

    model.set_learning_action(TYP_EXPENSES, "Essen", "reset")
    assert any(s.category == "Essen" for s in _suggest(conn))


def test_auto_end_persists_ended_status(conn: sqlite3.Connection) -> None:
    _add_category(conn, "Haushalt")
    for month in range(1, 7):
        _book(conn, "Haushalt", month, 100 + month)
    conn.commit()

    assert all(s.category != "Haushalt" for s in _suggest(conn, auto_end=True))
    row = conn.execute(
        "SELECT status FROM tracking_learning_state WHERE typ=? AND category=?",
        (TYP_EXPENSES, "Haushalt"),
    ).fetchone()
    assert row is not None
    assert row[0] == "ended"


def test_show_in_report_parameter_hides_learning(conn: sqlite3.Connection) -> None:
    _add_category(conn, "Freizeit")
    _book(conn, "Freizeit", 5, 120)
    _book(conn, "Freizeit", 6, 180)
    conn.commit()

    assert _suggest(conn, show_in_report=False) == []
    assert any(s.category == "Freizeit" for s in _suggest(conn, show_in_report=True))
