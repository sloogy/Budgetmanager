"""Regression tests for the merged v2.2.41/v2.2.42 cockpit layout."""

from __future__ import annotations

import json
from pathlib import Path

from utils.cockpit_layout import arrange_columns

ROOT = Path(__file__).resolve().parents[1]
COCKPIT = ROOT / "views/tabs/cockpit_tab.py"
SECTIONS = ROOT / "views/cockpit_sections.py"
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


def _cockpit() -> str:
    return COCKPIT.read_text(encoding="utf-8")


def _sections() -> str:
    return SECTIONS.read_text(encoding="utf-8")


def test_empty_tiles_sink_stably_in_automatic_mode():
    left, right = arrange_columns(
        KEYS,
        list(KEYS),
        {},
        default_left=("kpis", "quick_actions"),
        empty_keys=("action_needed", "favorites"),
        automatic=True,
    )
    assert left == ["kpis", "quick_actions"]
    assert right == ["charts", "savings", "recent", "action_needed", "favorites"]


def test_fix_button_and_both_settings_schemas_are_supported():
    src = _cockpit()
    assert "self.btn_fix_tiles.setCheckable(True)" in src
    assert "self.settings.set_many(" in src
    assert '"cockpit_layout_mode": mode' in src
    assert '"cockpit_tiles_fixed": fixed' in src
    assert 'self.settings.get("cockpit_tile_columns", None)' in src
    assert '"cockpit_panel_columns": columns' in src
    assert '"cockpit_tile_columns": dict(columns)' in src


def test_dragging_uses_a_dedicated_handle_and_private_mime_type():
    sections = _sections()
    assert 'DRAG_HANDLE = "≡"' in sections or 'DRAG_HANDLE = "\\u2261"' in sections
    assert (
        'COCKPIT_MIME_TYPE = "application/x-budgetmanager-cockpit-section"' in sections
    )
    assert "class _SectionDragHandle" in sections
    assert "QApplication.startDragDistance()" in sections
    assert "self.btn_drag.setVisible(bool(enabled))" in sections
    assert "if not self._drag_enabled" in sections


def test_one_column_drop_preserves_underlying_two_column_assignment():
    sections = _sections()
    block = sections.split("def _column_for_point", 1)[1].split(
        "def _remove_widget", 1
    )[0]
    assert "if self._two_columns:" in block
    assert "widget.geometry().contains(point)" in block
    assert 'return "left" if source in self._left else "right"' in block


def test_drop_reports_both_columns_and_cockpit_persists_them():
    sections = _sections()
    assert "layout_changed = Signal(object, object)" in sections
    assert "self.layout_changed.emit(" in sections
    src = _cockpit()
    assert "self.columns.layout_changed.connect(self._on_columns_reordered)" in src
    block = src.split("def _on_columns_reordered", 1)[1].split(
        "def _apply_panel_order", 1
    )[0]
    assert "columns_from_lists" in block
    assert "cockpit_panel_columns" in block
    assert "cockpit_tile_columns" in block


def test_charts_are_part_of_the_canonical_panel_order():
    src = _cockpit()
    assert "PANEL_DEFAULTS = {key: True for key in _cp.PANEL_KEYS}" in src
    assert '"charts": "cockpit.panel.charts"' in src
    assert '_add_panel("charts", self.charts_panel)' in src


def test_pin_and_layout_labels_exist_in_all_languages():
    for lang in LANGS:
        data = json.loads((ROOT / f"locales/{lang}.json").read_text(encoding="utf-8"))
        cockpit = data["cockpit"]
        for key in (
            "layout_fixed",
            "layout_fixed_tip",
            "layout_mode_hint",
            "drag_handle_tip",
            "reset_layout",
        ):
            assert cockpit[key].strip(), f"{lang}/cockpit.{key}"
        for key in (
            "cockpit.fix_tiles",
            "cockpit.fix_tiles_tip",
            "cockpit.panel.charts",
        ):
            assert data.get(key, "").strip(), f"{lang}/{key}"


def test_historical_version_references_are_locked():
    lock = json.loads(
        (ROOT / "docs/version_references.lock.json").read_text(encoding="utf-8")
    )
    assert "2.2.38" in lock["docs/USER_GUIDE.de.md"]
    audit = (ROOT / "tools/dau_enterprise_audit.py").read_text(encoding="utf-8")
    assert "def audit_version_references(" in audit
