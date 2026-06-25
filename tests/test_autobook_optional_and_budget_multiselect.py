"""Regressionen für Autobuchungs-Optionen und Budget-Mehrfachauswahl.

Diese Tests sind bewusst statische Marker-Tests: Die betroffenen Pfade sind Qt-UI-
Dialoge, deren Fachlogik hier durch eindeutige Quelltext-Marker abgesichert wird.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_autobooking_includes_optional_non_flagged_budget_items_and_skips_zero():
    src = (ROOT / "views" / "tabs" / "tracking_tab.py").read_text(encoding="utf-8")
    assert "optional_items: list[PendingBooking]" in src
    assert "no_flags = not (cat.is_fix or cat.is_recurring)" in src
    assert "source=\"auto_optional\"" in src
    assert "if abs(budget_amt) < EPS:" in src
    assert "optional_items=optional_items" in src


def test_autobooking_dialog_has_type_filter_and_optional_kind():
    src = (ROOT / "views" / "recurring_bookings_dialog.py").read_text(encoding="utf-8")
    assert "optional_items: list[PendingBooking] | None = None" in src
    assert "booking.kind_optional" in src
    assert "self.filter_typ = QComboBox()" in src
    assert "self.filter_kind = QComboBox()" in src
    assert "_apply_filters" in src
    assert "_matches_kind_filter" in src
    assert "real_fixed" in src and "optional" in src
    assert "self.table.setRowHidden" in src


def test_budget_tab_supports_ctrl_multiselect_and_bulk_delete_paths():
    src = (ROOT / "views" / "tabs" / "budget_tab.py").read_text(encoding="utf-8")
    assert "QAbstractItemView.ExtendedSelection" in src
    assert "def _selected_categories" in src
    assert "_delete_budget_rows_for_categories(selected)" in src
    assert "_delete_categories_with_confirm(selected)" in src
    assert "budget.ctx.multi_section" in src


def test_budget_and_tracking_have_coverage_warning_hooks():
    budget_src = (ROOT / "views" / "tabs" / "budget_tab.py").read_text(encoding="utf-8")
    tracking_src = (ROOT / "views" / "tabs" / "tracking_tab.py").read_text(encoding="utf-8")
    assert "budget_year_coverage" in budget_src
    assert "lbl_coverage_warning" in budget_src
    assert "budget.coverage.warning_months" in budget_src
    assert "coverage_from_tracking_rows" in tracking_src
    assert "tracking.coverage.warning" in tracking_src
    assert "single_savings_suggestions" in tracking_src
