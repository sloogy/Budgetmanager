"""Regression tests v2.2.41 – automatic and fixed cockpit tile layout."""

from __future__ import annotations

import json
import re
from pathlib import Path

from utils.cockpit_layout import (
    LAYOUT_AUTO,
    LAYOUT_FIXED,
    arrange_columns,
    columns_from_lists,
    normalize_columns,
    normalize_mode,
    normalize_order,
)

ROOT = Path(__file__).resolve().parents[1]
COCKPIT = ROOT / "views" / "tabs" / "cockpit_tab.py"
SECTIONS = ROOT / "views" / "cockpit_sections.py"
MAIN = ROOT / "views" / "main_window.py"
SETTINGS = ROOT / "settings.py"
LANGS = ("de", "en", "fr")
KEYS = (
    "kpis",
    "quick_actions",
    "action_needed",
    "charts",
    "favorites",
    "savings",
    "recent",
)
LEFT = ("kpis", "quick_actions")
LEGACY = {
    "warnings": "action_needed",
    "budget_warnings": "action_needed",
    "missing": "action_needed",
}


def test_layout_mode_is_fail_safe():
    assert normalize_mode(None) == LAYOUT_AUTO
    assert normalize_mode("fixed") == LAYOUT_FIXED
    assert normalize_mode("UNKNOWN") == LAYOUT_AUTO


def test_legacy_warning_order_migrates_to_action_needed_once():
    order = normalize_order(
        KEYS,
        ["kpis", "warnings", "missing", "favorites", "recent"],
        legacy_map=LEGACY,
    )
    assert order == [
        "kpis",
        "action_needed",
        "favorites",
        "recent",
        "quick_actions",
        "charts",
        "savings",
    ]
    assert order.count("action_needed") == 1


def test_automatic_mode_moves_empty_sections_down_in_their_column():
    left, right = arrange_columns(
        KEYS,
        list(KEYS),
        {},
        default_left=LEFT,
        empty_keys={"action_needed", "favorites"},
        automatic=True,
        legacy_map=LEGACY,
    )
    assert left == ["kpis", "quick_actions"]
    assert right == ["charts", "savings", "recent", "action_needed", "favorites"]


def test_fixed_mode_keeps_exact_order_and_user_columns():
    order = [
        "recent",
        "kpis",
        "favorites",
        "quick_actions",
        "action_needed",
        "charts",
        "savings",
    ]
    columns = {
        "recent": "left",
        "kpis": "right",
        "favorites": "left",
        "quick_actions": "right",
        "action_needed": "right",
        "charts": "right",
        "savings": "left",
    }
    left, right = arrange_columns(
        KEYS,
        order,
        columns,
        default_left=LEFT,
        empty_keys={"recent", "favorites"},
        automatic=False,
    )
    assert left == ["recent", "favorites", "savings"]
    assert right == ["kpis", "quick_actions", "action_needed", "charts"]


def test_drag_result_persists_both_columns():
    mapping = columns_from_lists(
        KEYS,
        ["quick_actions", "favorites", "kpis"],
        ["action_needed", "charts", "savings", "recent"],
    )
    assert mapping["favorites"] == "left"
    assert mapping["kpis"] == "left"
    assert mapping["recent"] == "right"
    assert normalize_columns(KEYS, mapping, default_left=LEFT) == mapping


def test_source_has_handle_only_in_fixed_mode_and_real_drop_support():
    sections = SECTIONS.read_text(encoding="utf-8")
    assert "COCKPIT_MIME_TYPE" in sections
    assert "class _SectionDragHandle" in sections
    assert "def dropEvent" in sections
    assert "layout_changed.emit" in sections
    assert "self.btn_drag.setVisible(bool(enabled))" in sections
    assert 'DRAG_HANDLE = "\\u2261"' in sections


def test_cockpit_applies_auto_sort_after_empty_state_refresh():
    source = COCKPIT.read_text(encoding="utf-8")
    block = source.split("def _refresh_section_states", 1)[1].split(
        "def _refresh_next_steps", 1
    )[0]
    assert "self._apply_panel_order()" in block
    assert "empty_keys" in source
    assert "automatic=not fixed" in source
    assert "cockpit_panel_columns" in source


def test_empty_savings_section_is_not_silently_hidden_anymore():
    source = COCKPIT.read_text(encoding="utf-8")
    block = source.split("def _apply_panel_visibility", 1)[1].split(
        "def _show_customize_menu", 1
    )[0]
    assert "SavingsGoalsModel" not in block
    assert "widget.setVisible(bool(cfg.get(key, True)))" in block


def test_view_menu_exposes_fixed_layout_and_reset():
    source = MAIN.read_text(encoding="utf-8")
    assert 'tr("menu.cockpit_layout")' in source
    assert 'tr("cockpit.layout_fixed")' in source
    assert "fixed_layout.setCheckable(True)" in source
    assert "fixed_layout.toggled.connect(self.cockpit_tab.set_layout_fixed)" in source
    assert "reset_layout.triggered.connect(self.cockpit_tab.reset_layout)" in source


def test_settings_define_auto_default_current_keys_and_columns():
    source = SETTINGS.read_text(encoding="utf-8")
    assert '"cockpit_layout_mode": "auto"' in source
    assert '"cockpit_panel_columns": {' in source
    order_block = source.split('"cockpit_panel_order": [', 1)[1].split("]", 1)[0]
    assert '"action_needed"' in order_block
    for legacy in ('"warnings"', '"budget_warnings"', '"missing"'):
        assert legacy not in order_block


def test_layout_texts_exist_in_all_languages():
    for lang in LANGS:
        data = json.loads((ROOT / f"locales/{lang}.json").read_text(encoding="utf-8"))
        for key in (
            "layout_fixed",
            "layout_fixed_tip",
            "layout_mode_hint",
            "drag_handle_tip",
            "reset_layout",
        ):
            assert data["cockpit"][key].strip(), f"{lang}/cockpit.{key}"
        assert data["menu"]["cockpit_layout"].strip()


def test_current_version_is_2244():
    from app_info import APP_VERSION

    assert re.fullmatch(r"\d+\.\d+\.\d+", APP_VERSION)
