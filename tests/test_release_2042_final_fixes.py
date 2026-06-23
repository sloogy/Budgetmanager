from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

from model.migrations import migrate_all
from model.savings_goals_model import SavingsGoalsModel
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS

ROOT = Path(__file__).resolve().parents[1]
DB_TYPE_LITERALS = {TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS}


def test_production_code_uses_db_type_constants_instead_of_raw_literals():
    """Release guard: DB-Typwerte dürfen nur zentral als Konstanten definiert werden."""
    ignored_parts = {"tests", "locales", "data", "docs"}
    ignored_files = {ROOT / "model" / "typ_constants.py"}
    offenders: list[str] = []

    for path in ROOT.rglob("*.py"):
        rel_parts = set(path.relative_to(ROOT).parts)
        if rel_parts & ignored_parts or path in ignored_files:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value in DB_TYPE_LITERALS:
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}:{node.value}")

    assert offenders == []


def test_savings_goal_sync_uses_savings_type_parameter_and_does_not_crash():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate_all(conn)
    try:
        model = SavingsGoalsModel(conn)
        goal_id = model.create("Hochzeit", 1_000, current_amount=0, category="Hochzeit")
        conn.execute(
            "INSERT INTO tracking(date, typ, category, amount, details) VALUES (?, ?, ?, ?, ?)",
            ("2026-06-01", TYP_SAVINGS, "Hochzeit", 125.0, "Einzahlung"),
        )
        conn.execute(
            "INSERT INTO tracking(date, typ, category, amount, details) VALUES (?, ?, ?, ?, ?)",
            ("2026-06-02", TYP_SAVINGS, "Hochzeit", -25.0, "Entnahme"),
        )
        conn.commit()

        assert model.sync_with_tracking(goal_id) == 100.0
        row = conn.execute(
            "SELECT current_amount FROM savings_goals WHERE id=?", (goal_id,)
        ).fetchone()
        assert float(row["current_amount"]) == 100.0
    finally:
        conn.close()
