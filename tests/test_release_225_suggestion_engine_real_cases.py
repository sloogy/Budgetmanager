"""Regressionen v2.2.5: echte Vorschlagsfälle aus der Bedienung.

Abgedeckt:
- Mehrere abgeschlossene Monate über Budget müssen auch dann einen Vorschlag
  liefern, wenn der aktuell geöffnete Zielmonat noch kein Budget hat.
- Lernmodus muss auch automatisch erzeugte Fixkosten-/Monatsanfangs-Buchungen
  berücksichtigen.
- Ein leerer aktueller Monat darf Lernvorschläge nicht künstlich als
  inkrementell/lumpy klassifizieren oder den Betrag senken.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.budget_learning import KIND_FIXED_RECURRING  # noqa: E402
from model.budget_overview_model import BudgetOverviewModel  # noqa: E402
from model.budget_warnings_model_extended import (
    BudgetWarningsModelExtended,
)  # noqa: E402
from model.budget_suggestion_engine import BudgetSuggestionEngine  # noqa: E402
from model.migrations import migrate_all  # noqa: E402
from model.typ_constants import TYP_EXPENSES  # noqa: E402


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    migrate_all(c)
    yield c
    c.close()


def _add_category(
    conn: sqlite3.Connection,
    name: str,
    *,
    is_fix: bool = False,
    is_recurring: bool = False,
) -> None:
    conn.execute(
        "INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day) VALUES(?,?,?,?,1)",
        (TYP_EXPENSES, name, 1 if is_fix else 0, 1 if is_recurring else 0),
    )


def _set_budget(
    conn: sqlite3.Connection, name: str, months: list[int], amount: float
) -> None:
    for month in months:
        conn.execute(
            "INSERT INTO budget(year, month, typ, category, amount) VALUES(?,?,?,?,?)",
            (2026, month, TYP_EXPENSES, name, amount),
        )


def _book(
    conn: sqlite3.Connection,
    name: str,
    month: int,
    amount: float,
    *,
    source: str = "manual",
) -> None:
    conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details, source) VALUES(?,?,?,?,?,?)",
        (f"2026-{month:02d}-15", TYP_EXPENSES, name, amount, "test", source),
    )


def test_overbudget_months_suggest_even_when_target_month_has_no_budget(
    conn: sqlite3.Connection,
) -> None:
    _add_category(conn, "Nahrungsmittel")
    _set_budget(conn, "Nahrungsmittel", [1, 2, 3, 4, 5, 6], 400.0)
    for month in [1, 2, 3, 4, 5, 6]:
        _book(conn, "Nahrungsmittel", month, 450.0)
    conn.commit()

    # Juli hat bewusst KEIN Budget. Früher brach die Engine hier ab, obwohl
    # Jan-Jun klar und stabil über Budget lagen.
    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        typ=TYP_EXPENSES,
        category="Nahrungsmittel",
        year=2026,
        month=7,
        months_back=3,
    )

    assert res is not None
    assert res.direction == "deficit"
    assert res.current_budget == 400.0
    assert res.suggested_budget > 400.0


def test_overview_suggestions_include_overbudget_without_target_month_budget(
    conn: sqlite3.Connection,
) -> None:
    _add_category(conn, "Nahrungsmittel")
    _set_budget(conn, "Nahrungsmittel", [1, 2, 3, 4, 5, 6], 400.0)
    for month in [1, 2, 3, 4, 5, 6]:
        _book(conn, "Nahrungsmittel", month, 450.0)
    conn.commit()

    rows = BudgetOverviewModel(conn).get_suggestions(
        year=2026,
        current_month=7,
        min_consecutive_months=3,
    )

    assert any(
        row.category == "Nahrungsmittel" and row.suggested_amount > 400 for row in rows
    )


def test_learning_uses_auto_booked_fixed_costs_after_restore(
    conn: sqlite3.Connection,
) -> None:
    _add_category(conn, "Miete", is_fix=True, is_recurring=True)
    for month in [1, 2, 3]:
        _book(conn, "Miete", month, 1000.0, source="auto")
    conn.commit()

    rows = BudgetOverviewModel(conn).get_tracking_budget_suggestions(
        year=2026,
        current_month=3,
        enabled=True,
        proposal_months=2,
        stable_months=3,
        include_current_month_projection=False,
        show_in_report=True,
    )

    assert len(rows) == 1
    assert rows[0].category == "Miete"
    assert rows[0].suggested_amount == 1000.0


def test_learning_does_not_treat_empty_current_month_as_zero_gap(
    conn: sqlite3.Connection,
) -> None:
    _add_category(conn, "Abo", is_fix=True, is_recurring=True)
    for month in [1, 2, 3, 4, 5, 6]:
        _book(conn, "Abo", month, 100.0, source="auto")
    conn.commit()

    rows = BudgetOverviewModel(conn).get_tracking_budget_suggestions(
        year=2026,
        current_month=7,
        enabled=True,
        proposal_months=2,
        stable_months=3,
        include_current_month_projection=False,
        show_in_report=True,
    )

    assert len(rows) == 1
    assert rows[0].category == "Abo"
    assert rows[0].budget_kind == KIND_FIXED_RECURRING
    assert rows[0].suggested_amount == 100.0
    assert "07/2026" not in rows[0].tracking_data


def _set_income_budget(
    conn: sqlite3.Connection, months: list[int], amount: float
) -> None:
    for month in months:
        conn.execute(
            "INSERT INTO budget(year, month, typ, category, amount) VALUES(?,?,?,?,?)",
            (2026, month, "Einkommen", "Lohn", amount),
        )


def _set_savings_budget(
    conn: sqlite3.Connection, months: list[int], amount: float
) -> None:
    for month in months:
        conn.execute(
            "INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day) VALUES('Ersparnisse','Notgroschen',0,0,1) "
            "ON CONFLICT(typ, name) DO NOTHING"
        )
        conn.execute(
            "INSERT INTO budget(year, month, typ, category, amount) VALUES(?,?,?,?,?)",
            (2026, month, "Ersparnisse", "Notgroschen", amount),
        )


def test_type_suggestion_uses_latest_budget_basis_when_target_month_empty(
    conn: sqlite3.Connection,
) -> None:
    _add_category(conn, "Nahrungsmittel")
    _set_budget(conn, "Nahrungsmittel", [1, 2, 3, 4, 5, 6], 400.0)
    for month in [1, 2, 3, 4, 5, 6]:
        _book(conn, "Nahrungsmittel", month, 450.0)
    conn.commit()

    rows = BudgetOverviewModel(conn).get_type_suggestions(
        year=2026,
        current_month=7,
        min_consecutive_months=3,
    )

    assert any(
        row.typ == TYP_EXPENSES
        and row.category == "(Gesamt)"
        and row.suggested_amount > 400
        for row in rows
    )


def test_zero_balance_suggestion_uses_latest_budget_basis_when_target_month_empty(
    conn: sqlite3.Connection,
) -> None:
    _set_income_budget(conn, [1, 2, 3, 4, 5, 6], 5000.0)
    _set_budget(conn, "Nahrungsmittel", [1, 2, 3, 4, 5, 6], 3000.0)
    _set_savings_budget(conn, [1, 2, 3, 4, 5, 6], 500.0)
    for month in [1, 2, 3, 4, 5, 6]:
        conn.execute(
            "INSERT INTO tracking(date, typ, category, amount, details, source) VALUES(?,?,?,?,?,?)",
            (f"2026-{month:02d}-15", "Einkommen", "Lohn", 5000.0, "test", "manual"),
        )
        _book(conn, "Nahrungsmittel", month, 3000.0)
        conn.execute(
            "INSERT INTO tracking(date, typ, category, amount, details, source) VALUES(?,?,?,?,?,?)",
            (
                f"2026-{month:02d}-20",
                "Ersparnisse",
                "Notgroschen",
                500.0,
                "test",
                "manual",
            ),
        )
    conn.commit()

    rows = BudgetOverviewModel(conn).get_balance_suggestions(
        year=2026,
        current_month=7,
        min_consecutive_months=3,
        enabled=True,
        surplus_strategy="savings",
    )

    assert any(
        row.typ == "Ersparnisse"
        and row.category == "Notgroschen"
        and row.suggested_amount > 500
        for row in rows
    )


def test_completed_selected_month_is_included_for_warning_suggestions(
    conn: sqlite3.Connection,
) -> None:
    _add_category(conn, "Nahrungsmittel")
    _set_budget(conn, "Nahrungsmittel", [4, 5, 6], 400.0)
    for month in [4, 5, 6]:
        _book(conn, "Nahrungsmittel", month, 450.0)
    conn.commit()

    rows = BudgetWarningsModelExtended(conn).check_warnings_extended(
        year=2026,
        month=6,
        lookback_months=3,
    )

    assert rows
    match = next((row for row in rows if row.category == "Nahrungsmittel"), None)
    assert match is not None
    assert match.exceed_count == 3
    assert match.suggestion is not None
    assert match.suggestion > 400.0


def test_budget_warning_auto_candidates_use_latest_budget_when_target_month_empty(
    conn: sqlite3.Connection,
) -> None:
    _add_category(conn, "Nahrungsmittel")
    _set_budget(conn, "Nahrungsmittel", [4, 5, 6], 400.0)
    for month in [4, 5, 6]:
        _book(conn, "Nahrungsmittel", month, 450.0)
    conn.commit()

    rows = BudgetWarningsModelExtended(conn).check_warnings_extended(
        year=2026,
        month=7,
        lookback_months=3,
    )

    match = next((row for row in rows if row.category == "Nahrungsmittel"), None)
    assert match is not None
    assert match.budget == 400.0
    assert match.spent == 0.0
    assert match.exceed_count == 3
    assert match.suggestion is not None
    assert match.suggestion > 400.0


def test_budget_warning_auto_candidates_cross_year_when_january_target_is_empty(
    conn: sqlite3.Connection,
) -> None:
    _add_category(conn, "Nahrungsmittel")
    for month in [10, 11, 12]:
        conn.execute(
            "INSERT INTO budget(year, month, typ, category, amount) VALUES(?,?,?,?,?)",
            (2025, month, TYP_EXPENSES, "Nahrungsmittel", 400.0),
        )
        conn.execute(
            "INSERT INTO tracking(date, typ, category, amount, details, source) VALUES(?,?,?,?,?,?)",
            (
                f"2025-{month:02d}-15",
                TYP_EXPENSES,
                "Nahrungsmittel",
                450.0,
                "test",
                "manual",
            ),
        )
    conn.commit()

    rows = BudgetWarningsModelExtended(conn).check_warnings_extended(
        year=2026,
        month=1,
        lookback_months=3,
    )

    match = next((row for row in rows if row.category == "Nahrungsmittel"), None)
    assert match is not None
    assert match.budget == 400.0
    assert match.exceed_count == 3
    assert match.suggestion is not None
    assert match.suggestion > 400.0
