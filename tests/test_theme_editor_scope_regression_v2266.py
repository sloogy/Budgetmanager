from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME_EDITOR = ROOT / "views" / "theme_editor_dialog.py"


def _class_method(tree: ast.AST, class_name: str, method_name: str) -> ast.FunctionDef:
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return item
    raise AssertionError(f"{class_name}.{method_name} nicht gefunden")


def test_theme_editor_close_bar_stays_in_setup_layout_scope() -> None:
    """Regression: v2.2.66 durfte beim Öffnen nicht auf lokales `outer` aus anderem Scope zugreifen."""
    tree = ast.parse(THEME_EDITOR.read_text(encoding="utf-8"))
    init = _class_method(tree, "ThemeEditorDialog", "__init__")
    setup = _class_method(tree, "ThemeEditorDialog", "_setup_ui")

    init_names = {n.id for n in ast.walk(init) if isinstance(n, ast.Name)}
    setup_names = {n.id for n in ast.walk(setup) if isinstance(n, ast.Name)}

    assert (
        "outer" not in init_names
    ), "__init__ greift wieder auf die lokale Layout-Variable `outer` zu"
    assert "outer" in setup_names, "_setup_ui muss das Hauptlayout weiterhin besitzen"

    setup_source = (
        ast.get_source_segment(THEME_EDITOR.read_text(encoding="utf-8"), setup) or ""
    )
    assert "buttons.rejected.connect(self.reject)" in setup_source
    assert "outer.addWidget(buttons)" in setup_source
