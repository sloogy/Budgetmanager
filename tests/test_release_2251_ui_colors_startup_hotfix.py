"""Regression fuer den Erststart-Crash aus v2.2.50.

UIColors ist absichtlich frozen. Berechnete Hover-Felder muessen deshalb
explizit deklariert und in __post_init__ via object.__setattr__ gesetzt werden.
Der Laufzeittest arbeitet in einem separaten Python-Prozess, damit Qt-Stubs
keinen globalen Testzustand verunreinigen.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ui_colors_can_be_created_on_first_start() -> None:
    script = r"""
import importlib
import sys
import types
from dataclasses import FrozenInstanceError

try:
    importlib.import_module("PySide6")
except ModuleNotFoundError:
    pyside = types.ModuleType("PySide6")
    qtgui = types.ModuleType("PySide6.QtGui")
    qtwidgets = types.ModuleType("PySide6.QtWidgets")

    class QColor:
        def __init__(self, value=None, *args):
            self.value = value
        def red(self): return 0
        def green(self): return 0
        def blue(self): return 0
        def name(self): return str(self.value or "#000000")

    class QBrush:
        def __init__(self, value=None): self.value = value

    class QWidget:
        pass

    qtgui.QColor = QColor
    qtgui.QBrush = QBrush
    qtwidgets.QWidget = QWidget
    pyside.QtGui = qtgui
    pyside.QtWidgets = qtwidgets
    sys.modules["PySide6"] = pyside
    sys.modules["PySide6.QtGui"] = qtgui
    sys.modules["PySide6.QtWidgets"] = qtwidgets

from views.ui_colors import UIColors

colors = UIColors()
assert colors.accent_hover
assert colors.positive_hover
assert colors.warning_hover
assert colors.negative_hover
assert all(
    name in vars(colors)
    for name in (
        "accent_hover",
        "positive_hover",
        "warning_hover",
        "negative_hover",
    )
)
try:
    colors.accent = "#000000"
except FrozenInstanceError:
    pass
else:
    raise AssertionError("UIColors muss nach der Initialisierung unveraenderlich bleiben")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
