from __future__ import annotations

import sqlite3
from pathlib import Path

from model.budget_model import BudgetModel
from model.migrations import migrate_all
from model.undo_redo_model import UndoRedoModel


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_all(conn)
    return conn


def test_budget_noop_save_does_not_pollute_undo_stack() -> None:
    conn = _conn()
    try:
        budget = BudgetModel(conn)
        budget.set_amount(2026, 1, "Ausgaben", "Miete", 1200.0)
        count_before = conn.execute("SELECT COUNT(*) FROM undo_stack").fetchone()[0]
        budget.set_amount(2026, 1, "Ausgaben", "Miete", 1200.0)
        count_after = conn.execute("SELECT COUNT(*) FROM undo_stack").fetchone()[0]
        assert count_after == count_before
    finally:
        conn.close()


def test_budget_multi_month_group_is_one_undo_step() -> None:
    conn = _conn()
    try:
        budget = BudgetModel(conn)
        for month in (1, 2, 3):
            budget.set_amount(2026, month, "Ausgaben", "Miete", 100.0)

        # Baseline nicht mit der eigentlichen Benutzeraktion vermischen.
        conn.execute("DELETE FROM undo_stack")
        conn.execute("DELETE FROM redo_stack")
        conn.commit()

        group_id = budget.undo.new_group_id()
        for month, amount in ((1, 110.0), (2, 120.0), (3, 130.0)):
            budget.set_amount(
                2026, month, "Ausgaben", "Miete", amount, group_id=group_id
            )

        groups = conn.execute(
            "SELECT COUNT(DISTINCT group_id) FROM undo_stack"
        ).fetchone()[0]
        assert groups == 1

        undo = UndoRedoModel(conn)
        assert undo.undo()
        values = [
            conn.execute(
                "SELECT amount FROM budget WHERE year=2026 AND month=? AND typ='Ausgaben' AND category='Miete'",
                (month,),
            ).fetchone()[0]
            for month in (1, 2, 3)
        ]
        assert values == [100.0, 100.0, 100.0]
    finally:
        conn.close()


def test_main_window_history_actions_are_not_disabled_by_stale_state() -> None:
    src = (Path(__file__).resolve().parents[1] / "views" / "main_window.py").read_text(
        encoding="utf-8"
    )
    marker = "def _update_undo_redo_actions"
    start = src.index(marker)
    end = src.index("def _finish_active_editor_before_history", start)
    method = src[start:end]
    assert "self.undo_action.setEnabled(True)" in method
    assert "self.redo_action.setEnabled(True)" in method
    assert "setEnabled(self.undo_redo.can_undo())" not in method
    assert "setEnabled(self.undo_redo.can_redo())" not in method


def test_unified_toolbar_reuses_global_undo_actions() -> None:
    src = (Path(__file__).resolve().parents[1] / "views" / "main_window.py").read_text(
        encoding="utf-8"
    )
    assert "toolbar.addAction(self.undo_action)" in src
    assert "toolbar.addAction(self.redo_action)" in src
