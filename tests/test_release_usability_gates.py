"""Regression-Gates für nicht-modale Rückmeldungen und Tastaturführung."""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _ui_files() -> list[Path]:
    return list((ROOT / "views").rglob("*.py")) + [ROOT / "settings_dialog.py"]


def test_no_modal_information_or_passive_warning_calls() -> None:
    modal_information: list[str] = []
    passive_warnings: list[str] = []
    for path in _ui_files():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(
                node.func, ast.Attribute
            ):
                continue
            if (
                not isinstance(node.func.value, ast.Name)
                or node.func.value.id != "QMessageBox"
            ):
                continue
            location = f"{path.relative_to(ROOT)}:{node.lineno}"
            if node.func.attr == "information":
                modal_information.append(location)
            if node.func.attr == "warning" and isinstance(parents.get(node), ast.Expr):
                passive_warnings.append(location)
    assert not modal_information, modal_information
    assert not passive_warnings, passive_warnings


def test_all_complex_dialog_files_configure_tab_order() -> None:
    missing: list[str] = []
    found = 0
    for path in _ui_files():
        source = path.read_text(encoding="utf-8")
        if (
            re.search(r"^class .*\(QDialog\)", source, re.MULTILINE)
            and source.count("QPushButton(") >= 5
        ):
            found += 1
            if "configure_dialog_tab_order(self)" not in source:
                missing.append(str(path.relative_to(ROOT)))
    # Die genaue Anzahl wächst mit neuen Dialogen. Das Gate soll sicherstellen,
    # dass jeder erkannte komplexe Dialog eine Tastaturreihenfolge besitzt,
    # nicht künftige Dialoge durch eine veraltete Zählkonstante blockieren.
    assert found > 0
    assert not missing, missing


QtWidgets = pytest.importorskip("PySide6.QtWidgets", reason="PySide6 fehlt")
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from utils.accessibility import configure_dialog_tab_order
from utils.notifications import show_info, show_warning


def test_notification_toast_is_non_modal_and_accessible() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = QDialog()
    dialog.resize(500, 300)
    dialog.show()
    show_info(dialog, "Gespeichert", "Die Änderung wurde übernommen.")
    app.processEvents()
    toast = getattr(dialog, "_budgetmanager_notification_toast", None)
    assert toast is not None
    assert toast.isVisible()
    assert toast.focusPolicy().name == "NoFocus"
    assert toast.accessibleName() == "Gespeichert"
    assert "übernommen" in toast.accessibleDescription()
    show_warning(dialog, "Eingabe prüfen", "Bitte eine Kategorie auswählen.")
    app.processEvents()
    replacement = getattr(dialog, "_budgetmanager_notification_toast", None)
    assert replacement is not None and replacement is not toast
    assert replacement.isVisible()
    dialog.close()


def test_tab_order_helper_builds_focus_chain() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = QDialog()
    layout = QVBoxLayout(dialog)
    first = QLineEdit()
    second = QLineEdit()
    save = QPushButton("Speichern")
    layout.addWidget(first)
    layout.addWidget(second)
    layout.addWidget(save)
    configure_dialog_tab_order(dialog)
    dialog.show()
    app.processEvents()
    assert dialog.property("budgetManagerTabOrderConfigured") is True
    assert int(dialog.property("budgetManagerTabOrderCount")) >= 3
    assert first.nextInFocusChain() is second
    assert second.nextInFocusChain() is save
    dialog.close()
