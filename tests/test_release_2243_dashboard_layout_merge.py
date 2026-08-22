"""Regression tests for v2.2.43 dashboard/layout merge."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COCKPIT = ROOT / "views/tabs/cockpit_tab.py"
SECTIONS = ROOT / "views/cockpit_sections.py"
THEME = ROOT / "theme_manager.py"
SETTINGS = ROOT / "settings.py"
MAIN = ROOT / "views/main_window.py"


def test_card_constructor_accepts_the_icon_used_by_all_kpis():
    src = COCKPIT.read_text(encoding="utf-8")
    signature = src.split("class _Card", 1)[1].split("super().__init__", 1)[0]
    assert "icon: str" in signature
    for glyph, escaped in (
        ("↑", "\\u2191"),
        ("↓", "\\u2193"),
        ("◆", "\\u25c6"),
        ("∑", "\\u2211"),
    ):
        assert f'icon="{glyph}"' in src or f'icon="{escaped}"' in src


def test_canonical_panel_list_includes_charts_and_action_needed():
    presets = (ROOT / "utils/cockpit_presets.py").read_text(encoding="utf-8")
    block = presets.split("PANEL_KEYS = (", 1)[1].split(")", 1)[0]
    assert '"action_needed"' in block
    assert '"charts"' in block
    src = COCKPIT.read_text(encoding="utf-8")
    assert "PANEL_ORDER_DEFAULTS = list(_cp.PANEL_KEYS)" in src


def test_design_manager_builds_dashboard_qss_without_undefined_border():
    src = THEME.read_text(encoding="utf-8")
    variables = src.split("def build_stylesheet", 1)[1].split("return f", 1)[0]
    assert "border = table_grid" in variables
    assert "positive = p.get(" in variables
    assert "negative = p.get(" in variables


def test_dashboard_does_not_embed_literal_colours_outside_design_manager():
    literal = re.compile(r"#[0-9a-fA-F]{3,8}(?![A-Za-z0-9_-])")
    for path in (COCKPIT, SECTIONS, ROOT / "views/cockpit_charts.py"):
        assert not literal.search(path.read_text(encoding="utf-8")), path


def test_all_dashboard_visual_roles_are_named_for_theme_manager():
    cockpit = COCKPIT.read_text(encoding="utf-8")
    sections = SECTIONS.read_text(encoding="utf-8")
    theme = THEME.read_text(encoding="utf-8")
    names = (
        "cockpitTitle",
        "cockpitSubtitle",
        "cockpitMonthStatus",
        "cockpitNextSteps",
        "cockpitCardIcon",
        "cockpitCardLabel",
        "cockpitCardValue",
        "cockpitCardCaption",
        "cockpitCardTrend",
        "cockpitInnerTitle",
        "cockpitSectionTitle",
        "cockpitSectionGrip",
        "cockpitChartView",
    )
    charts = (ROOT / "views/cockpit_charts.py").read_text(encoding="utf-8")
    combined = cockpit + sections + charts
    for name in names:
        assert f'"{name}"' in combined, name
        assert f"#{name}" in theme, name


def test_trend_colour_is_a_theme_property_not_inline_qss():
    src = COCKPIT.read_text(encoding="utf-8")
    block = src.split("def set_trend", 1)[1].split("def set_values", 1)[0]
    assert 'setProperty("trendState"' in block
    assert "setStyleSheet" not in block
    theme = THEME.read_text(encoding="utf-8")
    assert 'trendState="good"' in theme
    assert 'trendState="bad"' in theme


def test_theme_switch_refreshes_cockpit_charts_and_trends():
    src = MAIN.read_text(encoding="utf-8")
    block = src.split("def _apply_theme", 1)[1].split("def _setup_edit_menu", 1)[0]
    assert 'hasattr(self, "cockpit_tab")' in block
    assert "self.cockpit_tab.refresh()" in block


def test_settings_cover_new_and_legacy_layout_keys():
    src = SETTINGS.read_text(encoding="utf-8")
    for key in (
        "cockpit_layout_mode",
        "cockpit_panel_columns",
        "cockpit_tiles_fixed",
        "cockpit_tile_columns",
    ):
        assert f'"{key}"' in src
    assert '"charts": "right"' in src


def test_empty_charts_follow_the_same_shrink_and_sink_rule():
    src = COCKPIT.read_text(encoding="utf-8")
    assert 'self._update_section_state("charts"' in src or (
        'self._update_section_state(\n                "charts"' in src
    )
    assert '"cockpit.empty_charts"' in src
    assert "automatic=not fixed" in src


def test_chart_view_style_is_owned_by_design_manager():
    charts = (ROOT / "views/cockpit_charts.py").read_text(encoding="utf-8")
    theme = THEME.read_text(encoding="utf-8")
    assert 'setObjectName("cockpitChartView")' in charts
    assert "setStyleSheet" not in charts
    assert "QChartView#cockpitChartView" in theme


def test_current_version_is_valid_semver():
    import re

    from app_info import APP_VERSION

    assert re.fullmatch(r"\d+\.\d+\.\d+", APP_VERSION)
