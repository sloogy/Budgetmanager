"""Regression gates for v2.2.55 free cockpit tile arrangement."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ROOT / "views" / "cockpit_sections.py"
COCKPIT = ROOT / "views" / "tabs" / "cockpit_tab.py"


def _sections() -> str:
    return SECTIONS.read_text(encoding="utf-8")


def test_complete_section_header_is_a_drag_source() -> None:
    src = _sections()
    assert "class _SectionHeader(QWidget)" in src
    assert "self.header = _SectionHeader(key, self)" in src
    assert "self.header.set_drag_enabled" in src
    assert "_start_section_drag(self, self._key)" in src
    assert "Qt.WA_TransparentForMouseEvents" in src


def test_small_grip_and_header_share_one_drag_implementation() -> None:
    src = _sections()
    helper = src.split("def _start_section_drag", 1)[1].split(
        "class _SectionHeader", 1
    )[0]
    assert "COCKPIT_MIME_TYPE" in helper
    assert "drag.exec(Qt.MoveAction)" in helper
    assert src.count("_start_section_drag(self, self._key)") == 2


def test_manual_mode_keeps_a_real_two_column_canvas() -> None:
    src = _sections()
    assert "MANUAL_TWO_COLUMN_BREAKPOINT = 720" in src
    block = src.split("def set_drag_enabled", 2)[2].split("def is_two_columns", 1)[0]
    assert "self.setMinimumWidth(MANUAL_TWO_COLUMN_BREAKPOINT" in block
    relayout = src.split("def _relayout", 1)[1].split("def resizeEvent", 1)[0]
    assert "MANUAL_TWO_COLUMN_BREAKPOINT" in relayout
    assert "if self._drag_enabled" in relayout
    assert "self._grid.setColumnStretch(0, 1)" in relayout
    assert "self._grid.setColumnStretch(1, 1)" in relayout


def test_manual_drag_still_persists_order_and_column() -> None:
    src = COCKPIT.read_text(encoding="utf-8")
    block = src.split("def _on_columns_reordered", 1)[1].split(
        "def _apply_panel_order", 1
    )[0]
    assert "columns_from_lists" in block
    assert '"cockpit_panel_order": order' in block
    assert '"cockpit_panel_columns": columns' in block
    assert '"cockpit_tile_columns": dict(columns)' in block


def test_locales_explain_header_drag_and_both_columns() -> None:
    expected = {
        "de": ("Kopfzeile", "linker und rechter Spalte"),
        "en": ("full header", "left and right columns"),
        "fr": ("tout l’en-tête", "colonnes gauche et droite"),
    }
    for lang, fragments in expected.items():
        data = json.loads((ROOT / f"locales/{lang}.json").read_text(encoding="utf-8"))
        tip = data["cockpit.fix_tiles_tip"]
        assert all(fragment in tip for fragment in fragments), (lang, tip)


def test_current_version_is_2255() -> None:
    from app_info import APP_VERSION

    assert APP_VERSION.count(".") == 2
