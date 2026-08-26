from __future__ import annotations

import inspect
import sqlite3
from datetime import date

from model.migrations import migrate_all
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES, TYP_INCOME
from tests.conftest import verbindung_merken


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate_all(conn)
    return verbindung_merken(conn)


def test_performance_indexes_created_by_current_migration():
    conn = _conn()
    try:
        indexes = {
            str(row["name"])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_tracking_date_typ_category" in indexes
        assert "idx_tracking_typ_category_date" in indexes
        assert "idx_savings_goals_category_status" in indexes
        assert "idx_budget_warnings_year_month_enabled" in indexes
        assert "idx_categories_flags" in indexes
    finally:
        conn.close()


def test_tracking_month_checks_are_boundary_correct_and_index_friendly():
    conn = _conn()
    try:
        model = TrackingModel(conn)
        model.add(date(2026, 1, 31), TYP_EXPENSES, "Miete", 100)
        model.add(date(2026, 2, 1), TYP_EXPENSES, "Miete", 200)

        assert model.exists_in_month(
            year=2026, month=1, typ=TYP_EXPENSES, category="Miete"
        )
        assert model.exists_in_month(
            year=2026, month=2, typ=TYP_EXPENSES, category="Miete"
        )
        assert not model.exists_in_month(
            year=2026, month=3, typ=TYP_EXPENSES, category="Miete"
        )

        src = inspect.getsource(TrackingModel.exists_in_month)
        assert "substr(date" not in src
        assert "date >= ?" in src and "date < ?" in src
    finally:
        conn.close()


def test_tracking_year_month_aggregates_keep_semantics_without_year_substr_filter():
    conn = _conn()
    try:
        model = TrackingModel(conn)
        model.add(date(2025, 12, 31), TYP_INCOME, "Lohn", 1000)
        model.add(date(2026, 1, 1), TYP_INCOME, "Lohn", 2000)
        model.add(date(2026, 1, 31), TYP_EXPENSES, "Miete", 500)
        model.add(date(2026, 2, 1), TYP_EXPENSES, "Miete", 700)

        assert model.sum_by_typ(year=2026, month=1) == {
            TYP_INCOME: 2000.0,
            TYP_EXPENSES: 500.0,
        }
        assert model.sum_by_category(TYP_EXPENSES, year=2026, month=1) == {
            "Miete": 500.0
        }
        by_month = model.sum_by_month(2026, TYP_EXPENSES)
        assert by_month[1] == 500.0
        assert by_month[2] == 700.0
        assert by_month[12] == 0.0

        assert "substr(date,1,4)" not in inspect.getsource(TrackingModel.sum_by_typ)
        assert "substr(date,1,4)" not in inspect.getsource(
            TrackingModel.sum_by_category
        )
        assert "substr(date,1,4)" not in inspect.getsource(TrackingModel.sum_by_month)
    finally:
        conn.close()


def test_tracking_column_lookup_is_cached_for_hot_add_path():
    class CountingConnection(sqlite3.Connection):
        pragma_calls = 0

        def execute(self, sql, parameters=(), /):
            if str(sql).startswith("PRAGMA table_info(tracking)"):
                self.pragma_calls += 1
            return super().execute(sql, parameters)

    conn = sqlite3.connect(":memory:", factory=CountingConnection)
    conn.row_factory = sqlite3.Row
    try:
        migrate_all(conn)
        conn.pragma_calls = 0
        model = TrackingModel(conn)

        assert model._has_source_col()
        assert model._has_source_col()
        assert model._has_source_col()
        assert conn.pragma_calls == 1
    finally:
        conn.close()
