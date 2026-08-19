from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]


def _qt():
    return pytest.importorskip("PySide6.QtWidgets")


def _app():
    qt = _qt()
    return qt.QApplication.instance() or qt.QApplication([])


def test_nested_layout_label_becomes_accessible_name():
    qt = _qt()
    from utils.ui_usability import enhance_widget_tree

    _app()
    dialog = qt.QDialog()
    outer = qt.QVBoxLayout(dialog)
    row = qt.QHBoxLayout()
    row.addWidget(qt.QLabel("Zielbetrag"))
    field = qt.QDoubleSpinBox()
    row.addWidget(field)
    outer.addLayout(row)

    enhance_widget_tree(dialog)

    assert field.accessibleName() == "Zielbetrag"


def test_standard_dialog_buttons_are_localized_to_active_language():
    qt = _qt()
    from utils.i18n import set_language
    from utils.ui_usability import enhance_widget_tree

    _app()
    set_language("de")
    dialog = qt.QDialog()
    box = qt.QDialogButtonBox(
        qt.QDialogButtonBox.Ok | qt.QDialogButtonBox.Cancel, parent=dialog
    )
    enhance_widget_tree(dialog)

    assert box.button(qt.QDialogButtonBox.Ok).text() == "OK"
    assert box.button(qt.QDialogButtonBox.Cancel).text() == "Abbrechen"


def test_tab_order_candidates_stay_in_the_same_window():
    qt = _qt()
    from utils.accessibility import _focus_widgets

    _app()
    dialog = qt.QDialog()
    layout = qt.QVBoxLayout(dialog)
    combo = qt.QComboBox()
    combo.addItems(["A", "B"])
    layout.addWidget(combo)
    layout.addWidget(qt.QPushButton("Weiter"))
    dialog.show()
    combo.showPopup()
    qt.QApplication.processEvents()

    candidates = _focus_widgets(dialog)

    assert candidates
    assert all(widget.window() is dialog for widget in candidates)
    combo.hidePopup()
    dialog.close()


def test_large_dialogs_use_non_focusable_scroll_containers():
    budget = (ROOT / "views" / "budget_fill_dialog.py").read_text(encoding="utf-8")
    setup = (ROOT / "views" / "setup_assistant_dialog.py").read_text(encoding="utf-8")
    assert "self.budget_scroll = QScrollArea()" in budget
    assert "self.budget_scroll.setFocusPolicy(Qt.NoFocus)" in budget
    assert "self.step_scroll = QScrollArea()" in setup
    assert "self.step_scroll.setFocusPolicy(Qt.NoFocus)" in setup


def test_critical_action_targets_have_minimum_size():
    category_manager = (ROOT / "views" / "category_manager_dialog.py").read_text(
        encoding="utf-8"
    )
    budget_entry = (ROOT / "views" / "budget_entry_dialog_extended.py").read_text(
        encoding="utf-8"
    )
    assert "self.btn_apply.setMinimumHeight(36)" in category_manager
    assert "self.btn_manage.setMinimumSize(32, 32)" in budget_entry


def test_killcritic_usability_audit_remains_a_local_tool():
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(
        encoding="utf-8"
    )
    assert "killcritic-usability-audit-10000:" not in workflow
    assert (ROOT / "tools" / "run_killcritic_usability_10000.py").is_file()


def test_isolated_killcritic_worker_smoke(tmp_path):
    _qt()  # Worker-Subprozess nutzt denselben Interpreter → ohne PySide6 sauber skippen.
    output = tmp_path / "audit.json"
    matrix = tmp_path / "audit.csv"
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [
            sys.executable,
            "tools/killcritic_usability_audit_10000.py",
            "--worker",
            "--loops",
            "20",
            "--seed",
            "2226001",
            "--json",
            str(output),
            "--csv",
            str(matrix),
        ],
        cwd=ROOT,
        env=env,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["loops"] == 20
    assert payload["findings"] == 0
    assert matrix.read_text(encoding="utf-8").count("\n") == 21
