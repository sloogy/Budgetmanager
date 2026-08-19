"""Regressionstests v2.2.40 – übersichtlicheres Cockpit.

Vier Änderungen: leere Abschnitte schrumpfen, Warnbereiche sind gebündelt,
zwei Spalten auf breiten Fenstern, Abschnitte sind aufklappbar.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COCKPIT = ROOT / "views/tabs/cockpit_tab.py"
SECTIONS = ROOT / "views/cockpit_sections.py"
PRESETS = ROOT / "utils/cockpit_presets.py"
LANGS = ("de", "en", "fr")


def test_tables_no_longer_have_fixed_minimum_height():
    """Vorher kostete jede leere Liste rund 150 px Mindesthöhe."""
    src = COCKPIT.read_text(encoding="utf-8")
    assert "setMinimumHeight(150)" not in src
    assert "fit_table_height(table)" in src


def test_empty_tables_are_hidden_instead_of_showing_a_placeholder_row():
    src = COCKPIT.read_text(encoding="utf-8")
    block = src.split("def _set_table_rows", 1)[1].split("def _stabilize", 1)[0]
    assert "table.setRowCount(0)" in block
    assert "table.setVisible(False)" in block


def test_fit_table_height_is_capped_and_defensive():
    src = SECTIONS.read_text(encoding="utf-8")
    block = src.split("def fit_table_height", 1)[1].split("class ResponsiveColumns", 1)[
        0
    ]
    assert "max_rows" in block
    assert "except Exception" in block, "Höhe darf den Aufbau nie stoppen"


def test_three_warning_panels_merged_into_one_section():
    presets = PRESETS.read_text(encoding="utf-8")
    assert '"action_needed",' in presets
    for old in ('"warnings",', '"budget_warnings",', '"missing",'):
        assert old not in presets.split("PANEL_KEYS = (", 1)[1].split(")", 1)[0]
    src = COCKPIT.read_text(encoding="utf-8")
    assert '_add_panel("action_needed"' in src
    for old in (
        '_add_panel("warnings"',
        '_add_panel("budget_warnings"',
        '_add_panel("missing"',
    ):
        assert old not in src


def test_legacy_panel_config_is_migrated():
    """Alt-Konfigurationen dürfen ihren Zustand nicht verlieren."""
    import sys

    sys.path.insert(0, str(ROOT))
    from utils.cockpit_presets import migrate_panel_keys

    assert migrate_panel_keys({"warnings": True, "missing": False})["action_needed"]
    assert not migrate_panel_keys({"warnings": False, "budget_warnings": False})[
        "action_needed"
    ]
    assert migrate_panel_keys({"kpis": False})["kpis"] is False
    assert migrate_panel_keys({}) == {}
    assert migrate_panel_keys(None) == {}


def test_action_needed_counter_sums_all_three_blocks():
    src = COCKPIT.read_text(encoding="utf-8")
    block = src.split("def _refresh_section_states", 1)[1]
    for table in ("self.tbl_warnings", "self.tbl_budget_warnings", "self.tbl_missing"):
        assert table in block
    assert "action_needed" in block


def test_sections_are_collapsible_with_remembered_state():
    src = COCKPIT.read_text(encoding="utf-8")
    assert "cockpit_collapsed_sections" in src
    assert "DEFAULT_OPEN_PANELS" in src
    assert (
        '"kpis", "action_needed"' in src
    ), "anfangs offen: Kennzahlen und Handlungsbedarf"
    sections = SECTIONS.read_text(encoding="utf-8")
    assert "class CollapsibleSection" in sections
    assert "def set_collapsed" in sections


def test_toggle_arrows_are_plain_glyphs_not_emoji():
    """Gleiche Begründung wie beim Hilfe-'?': ohne Emoji-Schrift sichtbar."""
    sections = SECTIONS.read_text(encoding="utf-8")
    assert 'ARROW_OPEN = "\\u25be"' in sections
    assert 'ARROW_CLOSED = "\\u25b8"' in sections


def test_two_column_layout_has_a_breakpoint_and_falls_back():
    sections = SECTIONS.read_text(encoding="utf-8")
    assert "TWO_COLUMN_BREAKPOINT" in sections
    block = sections.split("class ResponsiveColumns", 1)[1]
    assert "def resizeEvent" in block
    assert "self._left + self._right" in block, "einspaltiger Rückfall fehlt"
    src = COCKPIT.read_text(encoding="utf-8")
    assert 'LEFT_COLUMN_PANELS = ("kpis", "quick_actions")' in src


def test_empty_hints_exist_in_all_languages():
    for lang in LANGS:
        data = json.loads((ROOT / f"locales/{lang}.json").read_text(encoding="utf-8"))
        for flat in (
            "cockpit.panel.action_needed",
            "cockpit.empty_action_needed",
            "cockpit.empty_savings",
        ):
            ns, key = flat.split(".", 1)
            value = data.get(flat) or data.get(ns, {}).get(key)
            assert value and value.strip(), f"{lang}/{flat}"
