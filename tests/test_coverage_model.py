from __future__ import annotations

from dataclasses import dataclass
import sqlite3

import pytest

from model.migrations import migrate_all

from model.coverage_model import coverage_from_tracking_rows, budget_year_coverage
from model.budget_model import BudgetModel
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS


@dataclass(frozen=True)
class Row:
    typ: str
    category: str
    amount: float


@pytest.fixture
def migrated_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_all(conn)
    try:
        yield conn
    finally:
        conn.close()


def test_tracking_coverage_detects_deficit_and_single_savings_suggestion():
    result = coverage_from_tracking_rows(
        [
            Row(TYP_INCOME, "Lohn", 5000),
            Row(TYP_EXPENSES, "Wohnen", 4600),
            Row(TYP_SAVINGS, "Notgroschen", 600),
            Row(TYP_SAVINGS, "Altersvorsorge", 200),
        ]
    )
    assert result.balance == -400
    assert result.deficit == 400
    singles = result.single_savings_suggestions()
    assert singles and singles[0].category == "Notgroschen"


def test_tracking_coverage_combines_savings_when_no_single_category_is_enough():
    result = coverage_from_tracking_rows(
        [
            Row(TYP_INCOME, "Lohn", 1000),
            Row(TYP_EXPENSES, "Ausgaben", 1050),
            Row(TYP_SAVINGS, "A", 30),
            Row(TYP_SAVINGS, "B", 30),
        ]
    )
    assert result.deficit == 110
    assert result.single_savings_suggestions() == []
    assert result.combined_savings_suggestions() == []

    result2 = coverage_from_tracking_rows(
        [
            Row(TYP_INCOME, "Lohn", 1000),
            Row(TYP_EXPENSES, "Ausgaben", 1000),
            Row(TYP_SAVINGS, "A", 60),
            Row(TYP_SAVINGS, "B", 60),
        ]
    )
    assert result2.deficit == 120
    combined = result2.combined_savings_suggestions()
    assert [s.category for s in combined] == ["A", "B"]


def test_budget_year_coverage_finds_negative_month(migrated_conn):
    budget = BudgetModel(migrated_conn)
    for month in range(1, 13):
        budget.set_amount(2026, month, TYP_INCOME, "Lohn", 5000)
        budget.set_amount(2026, month, TYP_EXPENSES, "Ausgaben", 4500)
        budget.set_amount(2026, month, TYP_SAVINGS, "Notgroschen", 200)
    budget.set_amount(2026, 6, TYP_SAVINGS, "Notgroschen", 700)

    report = budget_year_coverage(budget, 2026)
    assert report.negative_months == [6]
    worst = report.worst_month
    assert worst is not None
    month, result = worst
    assert month == 6
    assert result.deficit == 200
    assert result.single_savings_suggestions()[0].category == "Notgroschen"
