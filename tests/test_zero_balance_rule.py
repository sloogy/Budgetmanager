"""Regressionstests für sanfte Null-Bilanz-Vorschläge (v2.0.38)."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.budget_overview_model import BudgetOverviewModel  # noqa: E402
from model.migrations import migrate_all  # noqa: E402
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS  # noqa: E402


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    migrate_all(c)
    yield c
    c.close()


def _add_category(conn, typ: str, name: str, *, is_fix=False, is_recurring=False):
    conn.execute(
        """
        INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day, forecast_mode)
        VALUES(?,?,?,?,1,'auto')
        """,
        (typ, name, 1 if is_fix else 0, 1 if is_recurring else 0),
    )


def _set_budget(conn, year: int, month: int, typ: str, category: str, amount: float):
    conn.execute(
        """
        INSERT OR REPLACE INTO budget(year, month, typ, category, amount)
        VALUES(?,?,?,?,?)
        """,
        (year, month, typ, category, float(amount)),
    )


def _book(conn, year: int, month: int, typ: str, category: str, amount: float):
    conn.execute(
        """
        INSERT INTO tracking(date, typ, category, amount, details)
        VALUES(?,?,?,?,?)
        """,
        (f"{year:04d}-{month:02d}-15", typ, category, float(amount), "balance-test"),
    )


def test_positive_planned_balance_increases_savings(conn):
    _add_category(conn, TYP_INCOME, "Lohn")
    _add_category(conn, TYP_EXPENSES, "Alltag")
    _add_category(conn, TYP_SAVINGS, "Notgroschen")
    _set_budget(conn, 2026, 7, TYP_INCOME, "Lohn", 5000)
    _set_budget(conn, 2026, 7, TYP_EXPENSES, "Alltag", 3000)
    _set_budget(conn, 2026, 7, TYP_SAVINGS, "Notgroschen", 1000)

    res = BudgetOverviewModel(conn).get_balance_suggestions(
        2026, 7, enabled=True, surplus_strategy="savings"
    )

    assert len(res) == 1
    assert res[0].typ == TYP_SAVINGS
    assert res[0].category == "Notgroschen"
    assert res[0].current_budget == 1000
    assert res[0].suggested_amount == 2000


def test_negative_planned_balance_reduces_savings_first(conn):
    _add_category(conn, TYP_INCOME, "Lohn")
    _add_category(conn, TYP_EXPENSES, "Alltag")
    _add_category(conn, TYP_SAVINGS, "Sparen")
    _set_budget(conn, 2026, 7, TYP_INCOME, "Lohn", 5000)
    _set_budget(conn, 2026, 7, TYP_EXPENSES, "Alltag", 4000)
    _set_budget(conn, 2026, 7, TYP_SAVINGS, "Sparen", 1500)

    res = BudgetOverviewModel(conn).get_balance_suggestions(2026, 7, enabled=True)

    assert len(res) == 1
    assert res[0].typ == TYP_SAVINGS
    assert res[0].category == "Sparen"
    assert res[0].current_budget == 1500
    assert res[0].suggested_amount == 1000


def test_negative_balance_never_reduces_fixed_expenses(conn):
    _add_category(conn, TYP_INCOME, "Lohn")
    _add_category(conn, TYP_EXPENSES, "Miete", is_fix=True, is_recurring=True)
    _add_category(conn, TYP_EXPENSES, "Hobby")
    _add_category(conn, TYP_SAVINGS, "Sparen")
    _set_budget(conn, 2026, 7, TYP_INCOME, "Lohn", 5000)
    _set_budget(conn, 2026, 7, TYP_EXPENSES, "Miete", 4500)
    _set_budget(conn, 2026, 7, TYP_EXPENSES, "Hobby", 1000)
    _set_budget(conn, 2026, 7, TYP_SAVINGS, "Sparen", 300)

    res = BudgetOverviewModel(conn).get_balance_suggestions(2026, 7, enabled=True)

    by_cat = {(s.typ, s.category): s for s in res}
    assert (TYP_EXPENSES, "Miete") not in by_cat
    assert by_cat[(TYP_SAVINGS, "Sparen")].suggested_amount == 0
    assert by_cat[(TYP_EXPENSES, "Hobby")].suggested_amount == 500


def test_regular_actual_surplus_can_raise_savings_when_plan_is_balanced(conn):
    _add_category(conn, TYP_INCOME, "Lohn")
    _add_category(conn, TYP_EXPENSES, "Alltag")
    _add_category(conn, TYP_SAVINGS, "Notgroschen")
    # Zielmonat ist bereits planmässig 0: 5000 - (4000 + 1000) = 0
    _set_budget(conn, 2026, 7, TYP_INCOME, "Lohn", 5000)
    _set_budget(conn, 2026, 7, TYP_EXPENSES, "Alltag", 4000)
    _set_budget(conn, 2026, 7, TYP_SAVINGS, "Notgroschen", 1000)

    for m in (4, 5, 6):
        _set_budget(conn, 2026, m, TYP_INCOME, "Lohn", 5000)
        _set_budget(conn, 2026, m, TYP_EXPENSES, "Alltag", 4000)
        _set_budget(conn, 2026, m, TYP_SAVINGS, "Notgroschen", 1000)
        _book(conn, 2026, m, TYP_INCOME, "Lohn", 5200)
        _book(conn, 2026, m, TYP_EXPENSES, "Alltag", 3800)
        _book(conn, 2026, m, TYP_SAVINGS, "Notgroschen", 1000)

    res = BudgetOverviewModel(conn).get_balance_suggestions(
        2026, 7, min_consecutive_months=3, enabled=True
    )

    assert len(res) == 1
    assert res[0].typ == TYP_SAVINGS
    assert res[0].category == "Notgroschen"
    assert res[0].suggested_amount == 1400


def test_zero_balance_rule_can_be_disabled(conn):
    _add_category(conn, TYP_INCOME, "Lohn")
    _add_category(conn, TYP_EXPENSES, "Alltag")
    _add_category(conn, TYP_SAVINGS, "Notgroschen")
    _set_budget(conn, 2026, 7, TYP_INCOME, "Lohn", 5000)
    _set_budget(conn, 2026, 7, TYP_EXPENSES, "Alltag", 3000)
    _set_budget(conn, 2026, 7, TYP_SAVINGS, "Notgroschen", 1000)

    assert BudgetOverviewModel(conn).get_balance_suggestions(2026, 7, enabled=False) == []


def test_zero_balance_rule_suppresses_classic_savings_reduction(conn, monkeypatch):
    import settings as settings_module

    class FakeSettings:
        def get(self, key, default=None):
            values = {
                "budget_zero_balance_rule": True,
                "budget_suggestion_sign_ratio": 0.7,
            }
            return values.get(key, default)

    monkeypatch.setattr(settings_module, "Settings", FakeSettings)

    _add_category(conn, TYP_INCOME, "Lohn")
    _add_category(conn, TYP_EXPENSES, "Alltag")
    _add_category(conn, TYP_SAVINGS, "Sparen")
    for m in (4, 5, 6, 7):
        _set_budget(conn, 2026, m, TYP_INCOME, "Lohn", 5000)
        _set_budget(conn, 2026, m, TYP_EXPENSES, "Alltag", 3000)
        _set_budget(conn, 2026, m, TYP_SAVINGS, "Sparen", 1000)
    # Sparbudget wurde nicht getrackt. Bei aktiver Null-Bilanz darf daraus
    # kein klassischer Senkungsvorschlag entstehen, sonst widerspricht er dem
    # Überschuss-in-Ersparnisse-Prinzip.
    for m in (4, 5, 6):
        _book(conn, 2026, m, TYP_INCOME, "Lohn", 5000)
        _book(conn, 2026, m, TYP_EXPENSES, "Alltag", 3000)

    res = BudgetOverviewModel(conn).get_suggestions(2026, 7, min_consecutive_months=3)
    assert not any(s.typ == TYP_SAVINGS and s.category == "Sparen" and s.direction == "surplus" for s in res)


def test_zero_balance_rule_suppresses_classic_savings_type_reduction(conn, monkeypatch):
    """Typ-Gesamtvorschläge dürfen die Null-Bilanz-Regel nicht umgehen."""
    import settings as settings_module

    class FakeSettings:
        def get(self, key, default=None):
            values = {
                "budget_zero_balance_rule": True,
                "budget_suggestion_sign_ratio": 0.7,
            }
            return values.get(key, default)

    monkeypatch.setattr(settings_module, "Settings", FakeSettings)

    _add_category(conn, TYP_INCOME, "Lohn")
    _add_category(conn, TYP_EXPENSES, "Alltag")
    _add_category(conn, TYP_SAVINGS, "Sparen")
    for m in (4, 5, 6, 7):
        _set_budget(conn, 2026, m, TYP_INCOME, "Lohn", 5000)
        _set_budget(conn, 2026, m, TYP_EXPENSES, "Alltag", 3000)
        _set_budget(conn, 2026, m, TYP_SAVINGS, "Sparen", 1000)
    for m in (4, 5, 6):
        _book(conn, 2026, m, TYP_INCOME, "Lohn", 5000)
        _book(conn, 2026, m, TYP_EXPENSES, "Alltag", 3000)

    res = BudgetOverviewModel(conn).get_type_suggestions(
        2026, 7, min_consecutive_months=3
    )

    assert not any(
        s.typ == TYP_SAVINGS and s.direction == "surplus" for s in res
    )
