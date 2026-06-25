from __future__ import annotations

from datetime import date
import sqlite3

import pytest

from model.migrations import migrate_all
from model.savings_goals_model import SavingsGoal, SavingsGoalBoundsError, SavingsGoalsModel
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_SAVINGS


def _goal(current_amount: float, target_amount: float = 1000.0) -> SavingsGoal:
    return SavingsGoal(
        id=1,
        name="Testziel",
        target_amount=target_amount,
        current_amount=current_amount,
        deadline=None,
        category="Test",
        notes=None,
        created_date="2026-06-16",
    )


def test_progress_percent_is_clamped_between_zero_and_one_hundred():
    assert _goal(-250).progress_percent == 0.0
    assert _goal(0).progress_percent == 0.0
    assert _goal(500).progress_percent == 50.0
    assert _goal(1250).progress_percent == 100.0


def test_progress_percent_zero_target_is_zero():
    assert _goal(current_amount=500, target_amount=0).progress_percent == 0.0
    assert _goal(current_amount=-500, target_amount=0).progress_percent == 0.0


@pytest.fixture
def migrated_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate_all(conn)
    yield conn
    conn.close()


def _current_amount(conn, goal_id: int = 1) -> float:
    row = conn.execute(
        "SELECT current_amount FROM savings_goals WHERE id=?", (goal_id,)
    ).fetchone()
    return float(row[0])


def test_add_progress_rejects_withdrawal_below_zero(migrated_conn):
    model = SavingsGoalsModel(migrated_conn)
    goal_id = model.create("Hochzeit", 1000, current_amount=300, category="Hochzeit")

    with pytest.raises(SavingsGoalBoundsError) as exc:
        model.add_progress(goal_id, -500)

    assert exc.value.message_key == "savings.bounds.withdraw_too_much"
    assert _current_amount(migrated_conn, goal_id) == 300.0


def test_add_progress_rejects_deposit_above_target(migrated_conn):
    model = SavingsGoalsModel(migrated_conn)
    goal_id = model.create("Hochzeit", 1000, current_amount=900, category="Hochzeit")

    with pytest.raises(SavingsGoalBoundsError) as exc:
        model.add_progress(goal_id, 200)

    assert exc.value.message_key == "savings.bounds.deposit_too_much"
    assert _current_amount(migrated_conn, goal_id) == 900.0


def test_tracking_rejects_savings_booking_above_target(migrated_conn):
    SavingsGoalsModel(migrated_conn).create(
        "Hochzeit", 1000, current_amount=900, category="Hochzeit"
    )
    tracking = TrackingModel(migrated_conn)

    with pytest.raises(SavingsGoalBoundsError) as exc:
        tracking.add(date(2026, 6, 1), TYP_SAVINGS, "Hochzeit", 200, "zu viel")

    assert exc.value.message_key == "savings.bounds.deposit_too_much"
    assert migrated_conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 0
    assert _current_amount(migrated_conn) == 900.0


def test_tracking_rejects_savings_withdrawal_below_zero(migrated_conn):
    SavingsGoalsModel(migrated_conn).create(
        "Hochzeit", 1000, current_amount=300, category="Hochzeit"
    )
    tracking = TrackingModel(migrated_conn)

    with pytest.raises(SavingsGoalBoundsError) as exc:
        tracking.add(date(2026, 6, 1), TYP_SAVINGS, "Hochzeit", -500, "zu viel raus")

    assert exc.value.message_key == "savings.bounds.withdraw_too_much"
    assert migrated_conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 0
    assert _current_amount(migrated_conn) == 300.0
