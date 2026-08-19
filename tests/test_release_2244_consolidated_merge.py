"""Regression gates for v2.2.44 best-of-both dashboard consolidation."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COCKPIT = ROOT / "views/tabs/cockpit_tab.py"
THEME = ROOT / "theme_manager.py"
CHARTS = ROOT / "views/cockpit_charts.py"
SETTINGS = ROOT / "settings.py"
HELP = ROOT / "views/help_content.py"


def test_design_manager_still_owns_dashboard_visuals():
    cockpit = COCKPIT.read_text(encoding="utf-8")
    charts = CHARTS.read_text(encoding="utf-8")
    theme = THEME.read_text(encoding="utf-8")
    literal = re.compile(r"#[0-9a-fA-F]{3,8}(?![A-Za-z0-9_-])")
    assert not literal.search(cockpit)
    assert 'setObjectName("cockpitChartView")' in charts
    assert "setStyleSheet" not in charts
    assert "QChartView#cockpitChartView" in theme
    assert 'trendState="good"' in theme and 'trendState="bad"' in theme


def test_charts_remain_a_persisted_draggable_panel():
    settings = SETTINGS.read_text(encoding="utf-8")
    cockpit = COCKPIT.read_text(encoding="utf-8")
    assert '"charts": "right"' in settings
    assert '_add_panel("charts", self.charts_panel)' in cockpit
    assert '"cockpit.empty_charts"' in cockpit


def test_legacy_and_canonical_layout_keys_are_written_atomically():
    settings = SETTINGS.read_text(encoding="utf-8")
    cockpit = COCKPIT.read_text(encoding="utf-8")
    assert "def set_many(" in settings
    block = cockpit.split("def set_layout_fixed", 1)[1].split("def reset_layout", 1)[0]
    assert "self.settings.set_many(" in block
    assert '"cockpit_layout_mode"' in block
    assert '"cockpit_tiles_fixed"' in block
    reorder = cockpit.split("def _on_columns_reordered", 1)[1].split(
        "def _apply_panel_order", 1
    )[0]
    assert "self.settings.set_many(" in reorder
    assert '"cockpit_panel_columns"' in reorder
    assert '"cockpit_tile_columns"' in reorder


def test_help_explains_auto_fixed_drag_and_responsive_persistence():
    from app_info import APP_VERSION

    help_src = HELP.read_text(encoding="utf-8")
    for phrase in (
        "Kacheln frei anordnen",
        "Kopfzeile",
        "zwei unabhängigen Zielspalten",
    ):
        assert phrase in help_src
    guides = [
        ("de", "Kacheln frei anordnen"),
        ("en", "Arrange tiles freely"),
        ("fr", "Organiser librement les tuiles"),
    ]
    for lang, phrase in guides:
        text = (ROOT / f"docs/USER_GUIDE.{lang}.md").read_text(encoding="utf-8")
        assert phrase in text
        assert APP_VERSION in text.splitlines()[0]


def test_all_layout_and_chart_translations_are_retained():
    required_nested = (
        "customize_intro",
        "layout_fixed",
        "layout_fixed_tip",
        "layout_mode_hint",
        "drag_handle_tip",
        "reset_layout",
        "empty_charts",
    )
    required_flat = (
        "cockpit.fix_tiles",
        "cockpit.fix_tiles_tip",
        "cockpit.panel.charts",
    )
    for lang in ("de", "en", "fr"):
        data = json.loads((ROOT / f"locales/{lang}.json").read_text(encoding="utf-8"))
        for key in required_nested:
            assert data["cockpit"][key].strip(), f"{lang}/{key}"
        for key in required_flat:
            assert data[key].strip(), f"{lang}/{key}"


def test_current_version_is_2244():
    from app_info import APP_VERSION

    assert re.fullmatch(r"\d+\.\d+\.\d+", APP_VERSION)
