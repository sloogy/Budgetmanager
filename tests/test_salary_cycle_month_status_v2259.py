from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from model.salary_cycle import previous_salary_cycle, resolve_salary_cycle
from model.typ_constants import TYP_INCOME


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE categories(
            typ TEXT NOT NULL,
            name TEXT NOT NULL,
            is_recurring INTEGER NOT NULL DEFAULT 0,
            recurring_day INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE tracking(
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            typ TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE budget(
            year INTEGER,
            month INTEGER,
            typ TEXT,
            category TEXT,
            amount REAL
        )
        """
    )
    return conn


def _salary(
    conn: sqlite3.Connection, *, day: int = 25, name: str = "Lohn (Netto)"
) -> None:
    conn.execute(
        "INSERT INTO categories(typ,name,is_recurring,recurring_day) VALUES(?,?,1,?)",
        (TYP_INCOME, name, day),
    )


def _book_salary(
    conn: sqlite3.Connection,
    booking_date: str,
    amount: float = 6500.0,
    *,
    name: str = "Lohn (Netto)",
) -> None:
    conn.execute(
        "INSERT INTO tracking(date,typ,category,amount) VALUES(?,?,?,?)",
        (booking_date, TYP_INCOME, name, amount),
    )


def test_falls_back_to_calendar_month_without_salary_category():
    conn = _conn()
    cycle = resolve_salary_cycle(conn, on_date=date(2026, 2, 10))
    assert cycle.start == date(2026, 2, 1)
    assert cycle.end_exclusive == date(2026, 3, 1)
    assert (cycle.budget_year, cycle.budget_month) == (2026, 2)
    assert cycle.source == "calendar"


def test_salary_day_25_runs_until_day_before_same_day_next_month():
    conn = _conn()
    _salary(conn, day=25)
    cycle = resolve_salary_cycle(conn, on_date=date(2026, 2, 10))
    assert cycle.start == date(2026, 1, 25)
    assert cycle.end_exclusive == date(2026, 2, 25)
    assert cycle.end_inclusive == date(2026, 2, 24)
    assert (cycle.budget_year, cycle.budget_month) == (2026, 2)
    assert cycle.category == "Lohn (Netto)"
    assert cycle.source == "recurring"


def test_actual_salary_receipt_near_due_day_opens_cycle_immediately():
    conn = _conn()
    _salary(conn, day=25)
    _book_salary(conn, "2026-01-24")
    cycle = resolve_salary_cycle(conn, on_date=date(2026, 2, 10))
    assert cycle.start == date(2026, 1, 24)
    assert cycle.end_exclusive == date(2026, 2, 25)
    assert cycle.source == "actual"


def test_early_current_salary_starts_new_cycle_before_configured_day():
    conn = _conn()
    _salary(conn, day=25)
    _book_salary(conn, "2026-01-24")
    _book_salary(conn, "2026-02-24")
    cycle = resolve_salary_cycle(conn, on_date=date(2026, 2, 24))
    assert cycle.start == date(2026, 2, 24)
    assert cycle.end_exclusive == date(2026, 3, 25)
    assert (cycle.budget_year, cycle.budget_month) == (2026, 3)
    assert cycle.source == "actual"


def test_missing_salary_does_not_extend_old_cycle_beyond_one_month():
    conn = _conn()
    _salary(conn, day=25)
    _book_salary(conn, "2026-01-25")
    cycle = resolve_salary_cycle(conn, on_date=date(2026, 2, 26))
    assert cycle.start == date(2026, 2, 25)
    assert cycle.end_exclusive == date(2026, 3, 25)
    assert cycle.source == "recurring"


def test_day_31_is_clamped_safely_for_short_months():
    conn = _conn()
    _salary(conn, day=31)
    cycle = resolve_salary_cycle(conn, on_date=date(2026, 2, 15))
    assert cycle.start == date(2026, 1, 31)
    assert cycle.end_exclusive == date(2026, 2, 28)
    assert cycle.end_inclusive == date(2026, 2, 27)

    next_cycle = resolve_salary_cycle(conn, on_date=date(2026, 2, 28))
    assert next_cycle.start == date(2026, 2, 28)
    assert next_cycle.end_exclusive == date(2026, 3, 31)


def test_salary_named_category_beats_other_recurring_income():
    conn = _conn()
    conn.execute(
        "INSERT INTO categories(typ,name,is_recurring,recurring_day) VALUES(?,?,1,?)",
        (TYP_INCOME, "Nebeneinkommen", 5),
    )
    _salary(conn, day=25, name="Gehalt")
    _book_salary(conn, "2026-01-25", 6000.0, name="Gehalt")
    cycle = resolve_salary_cycle(conn, on_date=date(2026, 2, 10))
    assert cycle.category == "Gehalt"
    assert cycle.anchor_day == 25


def test_bonus_far_from_salary_day_does_not_shift_cycle():
    conn = _conn()
    _salary(conn, day=25)
    _book_salary(conn, "2026-01-25", 6500.0)
    _book_salary(conn, "2026-02-10", 1000.0)
    cycle = resolve_salary_cycle(conn, on_date=date(2026, 2, 15))
    assert cycle.start == date(2026, 1, 25)
    assert cycle.end_exclusive == date(2026, 2, 25)


def test_previous_cycle_ends_exactly_at_current_salary_receipt():
    conn = _conn()
    _salary(conn, day=25)
    _book_salary(conn, "2026-02-24")
    current = resolve_salary_cycle(conn, on_date=date(2026, 2, 24))
    previous = previous_salary_cycle(current)
    assert previous.start == date(2026, 1, 25)
    assert previous.end_exclusive == date(2026, 2, 24)
    assert (previous.budget_year, previous.budget_month) == (2026, 2)


def test_cockpit_month_status_queries_salary_cycle_bounds_static():
    source = (
        Path(__file__).resolve().parents[1] / "views" / "tabs" / "cockpit_tab.py"
    ).read_text(encoding="utf-8")
    assert "resolve_salary_cycle(self.conn" in source
    assert '"actual_start": cycle.start_iso' in source
    assert '"actual_end": cycle.end_iso' in source
    assert "previous_salary_cycle(cycle)" in source
    assert '"status.salary_cycle_period"' in source
