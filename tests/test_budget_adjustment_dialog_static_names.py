from __future__ import annotations

import ast
from pathlib import Path


def test_budget_adjustment_dialog_imports_typ_income_for_income_learning_rows():
    """Regression: tracking-only start with only salary created an income-only
    learning suggestion. The dialog then hit ``typ == TYP_INCOME`` but the
    constant was not imported, causing a user-visible NameError.
    """

    source = Path("views/budget_adjustment_dialog.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported = set()
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported.add(alias.asname or alias.name)
        elif isinstance(node, ast.Name):
            if node.id.startswith("TYP_"):
                used.add(node.id)

    assert "TYP_INCOME" in used
    assert "TYP_INCOME" in imported
