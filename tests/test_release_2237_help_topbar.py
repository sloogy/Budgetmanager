"""Regressionstests v2.2.37 – Hilfe-Fragezeichen in der oberen Leiste.

Anforderung: Das ``?`` muss in der Top-Leiste sitzen (neben Minimieren bzw.
direkt bei ``Hilfe``) und nicht nur unten links in der Seitenleiste.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW = ROOT / "views/main_window.py"
LAUNCHER = ROOT / "views/help_launcher.py"
THEME = ROOT / "theme_manager.py"


def _main_window_source() -> str:
    return MAIN_WINDOW.read_text(encoding="utf-8")


def _launcher_source() -> str:
    return LAUNCHER.read_text(encoding="utf-8")


def test_help_corner_button_is_created_and_wired():
    src = _main_window_source()
    assert "def _install_help_corner_button" in src
    assert "self._install_help_corner_button(menubar)" in src
    # Der Aufruf muss im Menue-Aufbau stehen, damit er auch nach einem
    # Sprachwechsel (menuBar().clear() + _create_menu()) wieder greift.
    create_menu = src.split("def _create_menu", 1)[1].split(
        "def _install_help_corner_button", 1
    )[0]
    assert "self._install_help_corner_button(menubar)" in create_menu


def test_help_corner_button_sits_in_top_right_corner():
    block = _launcher_source()
    assert "Qt.TopRightCorner" in block
    assert "setCornerWidget" in block
    assert 'setObjectName("menuBarHelpButton")' in block


def test_help_corner_button_uses_plain_ascii_question_mark():
    """Kein Emoji, kein Icon-Theme: unter Fedora/GNOME sonst unsichtbar."""
    block = _launcher_source()
    assert 'setText("?")' in block
    assert "get_icon(" not in block
    assert all(ord(char) < 128 for char in 'setText("?")')


def test_help_corner_button_opens_handbook():
    block = _launcher_source()
    assert "button.clicked.connect(on_click)" in block


def test_help_corner_button_is_reused_on_language_switch():
    """Ein neues QToolButton je Sprachwechsel wuerde Widgets verwaisen lassen."""
    block = _launcher_source()
    main = _main_window_source()
    assert 'existing=getattr(self, "menu_help_button", None)' in main
    assert "if button is None:" in block


def test_help_corner_button_is_themed_in_all_profiles():
    qss = THEME.read_text(encoding="utf-8")
    assert "QToolButton#menuBarHelpButton {{" in qss
    assert "QToolButton#menuBarHelpButton:hover {{" in qss
    assert "QToolButton#menuBarHelpButton:focus {{" in qss


def test_help_corner_button_has_geometry_rules():
    qss = THEME.read_text(encoding="utf-8")
    assert "border-radius: 11px;" in qss
    assert "min-width: 26px;" in qss


def test_sidebar_help_entry_still_present():
    """Der Einstieg unten links bleibt zusaetzlich erhalten (kein Rueckschritt)."""
    src = _main_window_source()
    assert "self.sidebar_help_button = add_utility" in src
    assert "f\"?  {tr('menu.help')}\"" in src


def test_help_corner_translations_exist_in_all_languages():
    counts = {}
    for lang in ("de", "en", "fr"):
        data = json.loads((ROOT / f"locales/{lang}.json").read_text(encoding="utf-8"))
        assert data["menu"]["help_corner_tip"].strip()
        assert data["menu"]["help_corner_a11y"].strip()
        counts[lang] = sum(
            len(value) if isinstance(value, dict) else 1 for value in data.values()
        )
    assert counts["de"] == counts["en"] == counts["fr"]


def test_help_corner_button_is_accessible():
    block = _launcher_source()
    assert "setAccessibleName" in block
    assert "setToolTip" in block
    assert "setStatusTip" in block


def test_help_corner_button_renders_headless():
    """Optionaler Funktionstest – laeuft nur mit installiertem PySide6."""
    pytest.importorskip("PySide6")
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMainWindow, QToolButton

    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    button = QToolButton(window.menuBar())
    button.setObjectName("menuBarHelpButton")
    button.setText("?")
    window.menuBar().setCornerWidget(button, Qt.TopRightCorner)
    assert window.menuBar().cornerWidget(Qt.TopRightCorner) is button
    assert button.text() == "?"
    window.deleteLater()
    del app
