"""Regression v2.2.5: Vorschläge-Button darf Lern-/Forecast-Vorschläge nicht blockieren."""
from __future__ import annotations

from pathlib import Path


def test_overview_suggestions_button_does_not_gate_on_warnings_only() -> None:
    src = Path("views/tabs/overview_tab.py").read_text(encoding="utf-8")
    start = src.index("    def _show_budget_suggestions_dialog")
    end = src.index("    def _show_overrun_details", start)
    body = src[start:end]

    assert "BudgetAdjustmentDialog" in body
    assert "check_warnings_extended" not in body
    assert "Lernvorschläge" in body
    assert "data_changed" in body
    assert "_refresh_all_tabs" in body


def test_budget_adjustment_dialog_marks_data_changed_after_apply() -> None:
    src = Path("views/budget_adjustment_dialog.py").read_text(encoding="utf-8")
    assert "self.data_changed = False" in src
    assert "self.data_changed = True" in src


def test_manual_budget_adjustment_dialog_forces_learning_visibility() -> None:
    src = Path("views/budget_adjustment_dialog.py").read_text(encoding="utf-8")
    start = src.index("    def _load_exceedances")
    end = src.index("    def _apply_stable_column_widths", start)
    body = src[start:end]
    assert "get_tracking_budget_suggestions" in body
    assert "show_in_report=True" in body
    assert "explicit_learning" in body
