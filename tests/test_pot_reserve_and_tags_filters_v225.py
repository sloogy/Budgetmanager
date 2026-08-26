from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from model.migrations import migrate_all
from model.pot_reserve_model import PotReserveModel
from model.tags_model import TagsModel
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES
from tests.conftest import verbindung_merken

_OPEN_CONNECTIONS: list[sqlite3.Connection] = []


@pytest.fixture(autouse=True)
def _close_connections_after_test():
    yield
    while _OPEN_CONNECTIONS:
        _OPEN_CONNECTIONS.pop().close()


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate_all(conn)
    _OPEN_CONNECTIONS.append(conn)
    return verbindung_merken(conn)


def _add_pot_category(conn, name="Franchise"):
    conn.execute(
        """
        INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day, forecast_mode)
        VALUES(?,?,?,?,1,'auto')
        """,
        (TYP_EXPENSES, name, 1, 0),
    )


def test_pot_reserve_uses_one_cap_not_monthly_sum():
    conn = _conn()
    _add_pot_category(conn)
    for month in range(1, 7):
        conn.execute(
            "INSERT INTO budget(year, month, typ, category, amount) VALUES(?,?,?,?,?)",
            (2026, month, TYP_EXPENSES, "Franchise", 750.0),
        )
    for month, amount in [(1, 150), (2, 300), (3, 55), (4, 120), (5, 700)]:
        conn.execute(
            "INSERT INTO tracking(date, typ, category, amount, details) VALUES(?,?,?,?,?)",
            (f"2026-{month:02d}-20", TYP_EXPENSES, "Franchise", amount, "test"),
        )

    status = PotReserveModel(conn).status(2026, 7, TYP_EXPENSES, "Franchise")

    assert status is not None
    assert status.cap == 750.0  # nicht 6×750
    assert status.spent == 1325.0
    assert status.rest == -575.0
    assert status.is_overdrawn is True


def test_pot_reserve_reports_tracking_only_without_budget():
    conn = _conn()
    _add_pot_category(conn)
    conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details) VALUES(?,?,?,?,?)",
        ("2026-02-20", TYP_EXPENSES, "Franchise", 300.0, "tracking-only"),
    )

    status = PotReserveModel(conn).status(2026, 7, TYP_EXPENSES, "Franchise")

    assert status is not None
    assert status.has_budget is False
    assert status.cap == 0.0
    assert status.rest == -300.0


def test_tracking_add_returns_id_so_tags_are_assignable():
    conn = _conn()
    conn.execute(
        "INSERT INTO categories(typ, name) VALUES(?,?)", (TYP_EXPENSES, "Lebensmittel")
    )
    tag_id = TagsModel(conn).create("Urlaub", "#abcdef")

    entry_id = TrackingModel(conn).add(
        "2026-01-05", TYP_EXPENSES, "Lebensmittel", 42.0, "Migros"
    )
    TagsModel(conn).set_entry_tags(entry_id, [tag_id])

    names = [t["name"] for t in TagsModel(conn).get_tags_for_entry(entry_id)]
    assert names == ["Urlaub"]


def test_tracking_tag_ui_is_directly_available_static():
    # v2.2.16 (K1): Bearbeiten laeuft ueber den QuickAddDialog (Edit-Modus).
    tracker_dialog = Path("views/quick_add_dialog.py").read_text(encoding="utf-8")
    tracking_tab = Path("views/tabs/tracking_tab.py").read_text(encoding="utf-8")
    quick_add_dialog = Path("views/quick_add_dialog.py").read_text(encoding="utf-8")

    assert "tag_ids" in tracker_dialog
    assert "QListWidget" in tracker_dialog
    assert "self.lst_tags" in tracker_dialog  # Tag-Liste im (Edit-)Dialog vorhanden
    assert 'tr("header.tags")' in quick_add_dialog
    assert (
        "self.tags_model.set_entry_tags(int(new_id), list(tag_ids))" in quick_add_dialog
    )
    assert "QuickAddDialog" in tracking_tab


def test_overview_filter_widgets_emit_refresh_and_preserve_selection_static():
    right_panel = Path("views/tabs/overview_right_panel.py").read_text(encoding="utf-8")
    overview_tab = Path("views/tabs/overview_tab.py").read_text(encoding="utf-8")

    assert "filters_changed = Signal()" in right_panel
    for widget in [
        "category_combo.currentIndexChanged",
        "tag_combo.currentIndexChanged",
        "search_edit.textChanged",
        "min_amount.textChanged",
        "max_amount.textChanged",
        "only_fix.toggled",
        "only_recurring.toggled",
        "limit_spin.valueChanged",
    ]:
        assert widget in right_panel
    assert "previous = self.category_combo.currentText()" in right_panel
    assert "previous = self.tag_combo.currentText()" in right_panel
    assert (
        "self.right_panel.filters_changed.connect(self._delayed_refresh)"
        in overview_tab
    )


def test_franchise_pot_overrun_warns_with_two_active_months_in_three_month_window():
    from model.budget_suggestion_engine import BudgetSuggestionEngine
    from model.budget_warnings_model_extended import BudgetWarningsModelExtended

    conn = _conn()
    _add_pot_category(conn)
    for month in range(1, 7):
        conn.execute(
            "INSERT INTO budget(year, month, typ, category, amount) VALUES(?,?,?,?,?)",
            (2026, month, TYP_EXPENSES, "Franchise", 750.0),
        )
    # April + Mai aktiv, Juni 0: fachlich POT/lumpy, nicht laufende Monatsausgabe.
    for month, amount in [(4, 120.0), (5, 700.0)]:
        conn.execute(
            "INSERT INTO tracking(date, typ, category, amount, details) VALUES(?,?,?,?,?)",
            (f"2026-{month:02d}-20", TYP_EXPENSES, "Franchise", amount, "pot"),
        )

    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        TYP_EXPENSES, "Franchise", 2026, 7, months_back=3
    )
    warnings = BudgetWarningsModelExtended(conn).check_warnings_extended(
        2026, 7, lookback_months=3
    )

    assert res is not None
    assert res.suggested_budget > 750.0
    assert any(
        w.category == "Franchise" and w.suggestion and w.suggestion > 750.0
        for w in warnings
    )
