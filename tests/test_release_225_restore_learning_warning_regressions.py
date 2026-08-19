"""Regressionen v2.2.5: Restore darf Warnungen/Lernen/Onboarding nicht brechen."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.budget_learning import (
    KIND_FIXED_RECURRING,
    apply_learning_budget_kind,
)  # noqa: E402
from model.budget_overview_model import BudgetOverviewModel  # noqa: E402
from model.budget_warnings_model_extended import (
    BudgetWarningsModelExtended,
)  # noqa: E402
from model.migrations import migrate_all  # noqa: E402
from model.typ_constants import TYP_EXPENSES  # noqa: E402
from settings import Settings  # noqa: E402


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    migrate_all(c)
    yield c
    c.close()


@pytest.fixture
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("BUDGETMANAGER_APP_DIR", str(tmp_path))
    return Settings()


def _add_category(conn: sqlite3.Connection, typ: str, name: str) -> None:
    conn.execute(
        "INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day) VALUES(?,?,?,?,1)",
        (typ, name, 0, 0),
    )


def _book(
    conn: sqlite3.Connection, year: int, month: int, category: str, amount: float
) -> None:
    conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details, source) VALUES(?,?,?,?,?,?)",
        (
            f"{year:04d}-{month:02d}-15",
            TYP_EXPENSES,
            category,
            amount,
            "test",
            "manual",
        ),
    )


def test_manual_budget_warnings_are_not_disabled_by_passive_banner_setting(
    conn: sqlite3.Connection,
    isolated_settings: Settings,
) -> None:
    isolated_settings.set("warn_budget_overrun", False)
    isolated_settings.set("auto_generate_budget_warnings", True)
    _add_category(conn, TYP_EXPENSES, "Lebensmittel")
    conn.execute(
        "INSERT INTO budget(year, month, typ, category, amount) VALUES(2026, 7, ?, 'Lebensmittel', 100)",
        (TYP_EXPENSES,),
    )
    _book(conn, 2026, 7, "Lebensmittel", 150)
    conn.commit()

    rows = BudgetWarningsModelExtended(conn).check_warnings_extended(
        2026, 7, lookback_months=3
    )

    assert len(rows) == 1
    assert rows[0].category == "Lebensmittel"
    assert rows[0].percent_used == 150


def test_tracking_learning_reopens_after_stale_ended_state_when_budget_is_empty(
    conn: sqlite3.Connection,
) -> None:
    _add_category(conn, TYP_EXPENSES, "Hobby")
    _book(conn, 2026, 1, "Hobby", 40)
    _book(conn, 2026, 2, "Hobby", 60)
    conn.execute(
        "INSERT INTO tracking_learning_state(typ, category, status, snooze_until, changed_at) "
        "VALUES(?, 'Hobby', 'ended', NULL, '2026-02-01')",
        (TYP_EXPENSES,),
    )
    conn.commit()

    suggestions = BudgetOverviewModel(conn).get_tracking_budget_suggestions(
        year=2026,
        current_month=2,
        enabled=True,
        proposal_months=2,
        stable_months=3,
        include_current_month_projection=False,
        show_in_report=True,
    )

    assert [s.category for s in suggestions] == ["Hobby"]
    assert (
        conn.execute("SELECT COUNT(*) FROM tracking_learning_state").fetchone()[0] == 0
    )


def test_accepted_suggestion_marker_does_not_hide_rows_when_budget_was_not_written(
    conn: sqlite3.Connection,
) -> None:
    conn.execute(
        "INSERT INTO suggestion_accepted(typ, category, year, month) VALUES(?, 'Hobby', 2026, 2)",
        (TYP_EXPENSES,),
    )
    conn.commit()

    assert BudgetWarningsModelExtended(conn).get_accepted_for_month(2026, 2) == set()

    conn.execute(
        "INSERT INTO budget(year, month, typ, category, amount) VALUES(2026, 2, ?, 'Hobby', 50)",
        (TYP_EXPENSES,),
    )
    conn.commit()

    assert BudgetWarningsModelExtended(conn).get_accepted_for_month(2026, 2) == {
        (TYP_EXPENSES, "Hobby")
    }


def test_learning_budget_kind_uses_preferred_recurring_day_from_settings(
    conn: sqlite3.Connection,
    isolated_settings: Settings,
) -> None:
    isolated_settings.set("recurring_preferred_day", 25)

    apply_learning_budget_kind(conn, TYP_EXPENSES, "Miete", KIND_FIXED_RECURRING)

    row = conn.execute(
        "SELECT is_fix, is_recurring, recurring_day FROM categories WHERE typ=? AND name='Miete'",
        (TYP_EXPENSES,),
    ).fetchone()
    assert tuple(row) == (1, 1, 25)


def test_startup_import_marks_existing_database_and_suppresses_onboarding_static() -> (
    None
):
    startup = (ROOT / "views/startup_wizard.py").read_text(encoding="utf-8")
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    setup = (ROOT / "views/setup_assistant_dialog.py").read_text(encoding="utf-8")

    assert "imported_existing_database = True" in startup
    assert "_restore_safe_settings_from_bundle" in startup
    assert 'settings.settings["show_onboarding"] = False' in startup
    assert 'settings.set("show_onboarding", False)' in main
    assert 'self.settings.set("show_onboarding", False)' in setup
