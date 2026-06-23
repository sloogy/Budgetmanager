from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cockpit_does_not_launch_processes() -> None:
    source = (ROOT / "views" / "tabs" / "cockpit_tab.py").read_text(encoding="utf-8")
    forbidden = [
        "QProcess",
        "subprocess",
        "Popen",
        "startDetached",
        "sys.executable",
        "main.py",
    ]
    for token in forbidden:
        assert token not in source


def test_update_dialog_source_mode_does_not_restart_main_py() -> None:
    source = (ROOT / "views" / "update_dialog.py").read_text(encoding="utf-8")
    assert 'root / "main.py"' not in source
    assert '"-m", mod' in source


def test_restore_window_state_does_not_show_window_inside_constructor() -> None:
    source = (ROOT / "views" / "main_window.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    main_window = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow"
    )
    fn = next(
        node
        for node in main_window.body
        if isinstance(node, ast.FunctionDef) and node.name == "_restore_window_state"
    )
    forbidden_calls = {"show", "showMaximized", "showFullScreen"}
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_calls
    assert "def show_restored" in source


def test_cockpit_card_hint_label_is_not_orphaned() -> None:
    """Regression: KPI hint labels must be layout children, otherwise Qt may
    show them as separate top-level windows when setVisible(True) is called.
    """
    source = (ROOT / "views" / "tabs" / "cockpit_tab.py").read_text(encoding="utf-8")
    assert "self.lbl_hint = QLabel(hint, self)" in source
    assert "lay.addWidget(self.lbl_hint)" in source
    assert "if hint:\n            lay.addWidget(self.lbl_hint)" not in source
