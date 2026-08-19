"""Regression gates for v2.2.56 cockpit grid and savings-goal flow balance."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from model.migrations import CURRENT_VERSION, migrate_all
from model.savings_goals_model import (
    ACTION_CORRECTION,
    ACTION_WITHDRAWAL,
    SavingsGoalsModel,
    STATUS_SAVING,
)
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_SAVINGS

ROOT = Path(__file__).resolve().parents[1]


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate_all(conn)
    return conn


def test_schema_v18_classifies_savings_bookings_and_adds_flow_columns() -> None:
    conn = _conn()
    assert CURRENT_VERSION >= 18
    tracking_cols = {row[1] for row in conn.execute("PRAGMA table_info(tracking)")}
    goal_cols = {row[1] for row in conn.execute("PRAGMA table_info(savings_goals)")}
    assert "savings_action" in tracking_cols
    assert {"contributed_amount", "withdrawn_amount"}.issubset(goal_cols)


def test_large_project_goal_keeps_deposits_withdrawals_and_stock_separate() -> None:
    conn = _conn()
    goals = SavingsGoalsModel(conn)
    tracking = TrackingModel(conn)
    goal_id = goals.create("Hochzeit", 50_000, category="Hochzeit")

    tracking.add("2026-01-01", TYP_SAVINGS, "Hochzeit", 30_000)
    tracking.add(
        "2026-02-01",
        TYP_SAVINGS,
        "Hochzeit",
        -15_000,
        savings_action=ACTION_WITHDRAWAL,
    )

    goal = goals.get(goal_id)
    assert goal is not None
    assert goal.contributed_amount == pytest.approx(30_000)
    assert goal.withdrawn_amount == pytest.approx(15_000)
    assert goal.current_stock == pytest.approx(15_000)
    assert goal.remaining_contribution == pytest.approx(20_000)
    assert goal.progress_percent == pytest.approx(60.0)


def test_negative_correction_is_not_reported_as_project_use() -> None:
    conn = _conn()
    goals = SavingsGoalsModel(conn)
    tracking = TrackingModel(conn)
    goal_id = goals.create("Hochzeit", 50_000, category="Hochzeit")
    tracking.add("2026-01-01", TYP_SAVINGS, "Hochzeit", 30_000)
    tracking.add(
        "2026-01-02",
        TYP_SAVINGS,
        "Hochzeit",
        -1_000,
        savings_action=ACTION_CORRECTION,
    )

    goal = goals.get(goal_id)
    assert goal is not None
    assert goal.contributed_amount == pytest.approx(29_000)
    assert goal.withdrawn_amount == pytest.approx(0)
    assert goal.current_stock == pytest.approx(29_000)
    assert goal.remaining_contribution == pytest.approx(21_000)


def test_partial_release_keeps_goal_active_and_only_releases_selected_amount() -> None:
    conn = _conn()
    goals = SavingsGoalsModel(conn)
    tracking = TrackingModel(conn)
    goal_id = goals.create("Hochzeit", 50_000, category="Hochzeit")
    tracking.add("2026-01-01", TYP_SAVINGS, "Hochzeit", 30_000)
    tracking.add(
        "2026-02-01",
        TYP_SAVINGS,
        "Hochzeit",
        -15_000,
        savings_action=ACTION_WITHDRAWAL,
    )

    released = goals.release_partial(goal_id, 5_000)
    assert released is not None
    assert released.status == STATUS_SAVING
    assert released.released_available == pytest.approx(5_000)
    assert released.remaining_contribution == pytest.approx(20_000)
    assert released.current_stock == pytest.approx(15_000)


def test_default_negative_action_is_withdrawal() -> None:
    conn = _conn()
    goals = SavingsGoalsModel(conn)
    tracking = TrackingModel(conn)
    goal_id = goals.create("Projekt", 10_000, category="Projekt")
    tracking.add("2026-01-01", TYP_SAVINGS, "Projekt", 5_000)
    row_id = tracking.add("2026-01-02", TYP_SAVINGS, "Projekt", -500)
    assert tracking.get_savings_action(row_id) == ACTION_WITHDRAWAL
    goal = goals.get(goal_id)
    assert goal is not None
    assert goal.withdrawn_amount == pytest.approx(500)


def test_cockpit_uses_independent_column_hosts_and_live_placeholder() -> None:
    src = (ROOT / "views" / "cockpit_sections.py").read_text(encoding="utf-8")
    assert "self._left_layout = QVBoxLayout" in src
    assert "self._right_layout = QVBoxLayout" in src
    assert "cockpitDropPlaceholder" in src
    assert "def _show_preview" in src
    assert "def dragLeaveEvent" in src
    # The old shared-grid row placement caused right-side gaps.
    assert "self._grid.addWidget(widget, index, 1" not in src


def test_cockpit_goal_counter_and_flow_tooltip_are_data_driven() -> None:
    src = (ROOT / "views" / "tabs" / "cockpit_tab.py").read_text(encoding="utf-8")
    assert "self._active_savings_count = len(goals)" in src
    assert "cockpit.savings_flow_tip" in src
    assert "remaining_contribution" in src
