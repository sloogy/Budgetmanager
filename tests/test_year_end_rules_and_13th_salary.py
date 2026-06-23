from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.income_specials import apply_13th_month_salary  # noqa: E402
from model.migrations import migrate_all  # noqa: E402
from model.typ_constants import TYP_EXPENSES, TYP_INCOME  # noqa: E402
from model.year_copy_rules import (  # noqa: E402
    YearCopyOverride,
    apply_year_copy_pattern,
    distribute_like_previous_year,
    list_year_copy_review_rows,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    migrate_all(c)
    yield c
    c.close()


def _cat(conn, typ, name, *, is_fix=False, is_recurring=False, forecast_mode="auto"):
    conn.execute(
        """
        INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day, forecast_mode)
        VALUES(?,?,?,?,25,?)
        """,
        (typ, name, int(is_fix), int(is_recurring), forecast_mode),
    )
    conn.commit()


def _budget(conn, year, month, typ, category, amount):
    conn.execute(
        """
        INSERT INTO budget(year, month, typ, category, amount)
        VALUES(?,?,?,?,?)
        ON CONFLICT(year, month, typ, category) DO UPDATE SET amount=excluded.amount
        """,
        (year, month, typ, category, amount),
    )
    conn.commit()


def _book(conn, year, month, typ, category, amount):
    conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details) VALUES(?,?,?,?,?)",
        (f"{year:04d}-{month:02d}-25", typ, category, amount, "test"),
    )
    conn.commit()


def test_13th_salary_is_one_income_month_only(conn):
    apply_13th_month_salary(conn, year=2027, payout_month=11, amount=5200)

    rows = conn.execute(
        "SELECT month, amount FROM budget WHERE year=2027 AND typ=? AND category='13. Monatslohn' ORDER BY month",
        (TYP_INCOME,),
    ).fetchall()
    assert len(rows) == 12
    assert {int(r["month"]): float(r["amount"]) for r in rows}[11] == 5200
    assert sum(float(r["amount"]) for r in rows) == 5200

    cat = conn.execute(
        "SELECT is_fix, is_recurring, forecast_mode FROM categories WHERE typ=? AND name='13. Monatslohn'",
        (TYP_INCOME,),
    ).fetchone()
    assert bool(cat["is_fix"]) is True
    assert bool(cat["is_recurring"]) is False
    assert cat["forecast_mode"] == "incremental"


def test_distribution_uses_previous_actual_pattern_and_preserves_annual_total():
    out = distribute_like_previous_year(
        budget_months=[100.0] * 12,
        actual_months=[0, 250, 0, 250, 0, 500, 0, 0, 0, 0, 0, 0],
        annual_amount=1200.0,
    )
    assert sum(out) == pytest.approx(1200.0)
    assert out[2 - 1] == pytest.approx(300.0)
    assert out[4 - 1] == pytest.approx(300.0)
    assert out[6 - 1] == pytest.approx(600.0)
    assert sum(v for i, v in enumerate(out, start=1) if i not in {2, 4, 6}) == 0


def test_year_copy_review_lists_only_year_end_relevant_categories(conn):
    _cat(conn, TYP_EXPENSES, "Miete", is_fix=True, is_recurring=True)
    _cat(conn, TYP_EXPENSES, "Lebensmittel")
    _budget(conn, 2026, 1, TYP_EXPENSES, "Miete", 1400)
    _budget(conn, 2026, 1, TYP_EXPENSES, "Lebensmittel", 500)

    rows = list_year_copy_review_rows(conn, 2026)
    assert [r.category for r in rows] == ["Miete"]


def test_apply_year_copy_pattern_can_edit_and_skip_reviewed_items(conn):
    _cat(conn, TYP_EXPENSES, "Versicherung", is_fix=True, is_recurring=False)
    _cat(conn, TYP_EXPENSES, "Abo", is_fix=False, is_recurring=True)
    for m in range(1, 13):
        _budget(conn, 2026, m, TYP_EXPENSES, "Versicherung", 100)
        _budget(conn, 2026, m, TYP_EXPENSES, "Abo", 50)
    _book(conn, 2026, 3, TYP_EXPENSES, "Versicherung", 600)
    _book(conn, 2026, 9, TYP_EXPENSES, "Versicherung", 600)

    apply_year_copy_pattern(
        conn,
        src_year=2026,
        dst_year=2027,
        overrides=[
            YearCopyOverride(TYP_EXPENSES, "Versicherung", 1500, include=True),
            YearCopyOverride(TYP_EXPENSES, "Abo", 600, include=False),
        ],
    )

    vers = conn.execute(
        "SELECT month, amount FROM budget WHERE year=2027 AND typ=? AND category='Versicherung' ORDER BY month",
        (TYP_EXPENSES,),
    ).fetchall()
    assert sum(float(r["amount"]) for r in vers) == pytest.approx(1500)
    assert {int(r["month"]): float(r["amount"]) for r in vers}[3] == pytest.approx(750)
    assert {int(r["month"]): float(r["amount"]) for r in vers}[9] == pytest.approx(750)

    abo_total = conn.execute(
        "SELECT SUM(amount) AS s FROM budget WHERE year=2027 AND typ=? AND category='Abo'",
        (TYP_EXPENSES,),
    ).fetchone()["s"]
    assert float(abo_total or 0.0) == 0.0


def test_13th_salary_rejects_zero_amount(conn):
    with pytest.raises(ValueError, match="greater than zero"):
        apply_13th_month_salary(conn, year=2027, payout_month=11, amount=0)
