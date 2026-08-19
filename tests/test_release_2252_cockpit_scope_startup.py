"""Regressionstest fuer den Cockpit-Klassen-Scope beim Modulimport.

Python fuehrt Comprehensions in Klassenkoerpern in einem eigenen Scope aus.
Ein unqualifizierter Zugriff auf ein zuvor gesetztes Klassenattribut loest daher
bereits beim Import von ``views.tabs.cockpit_tab`` einen ``NameError`` aus.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COCKPIT = ROOT / "views" / "tabs" / "cockpit_tab.py"


def _assigned_names(statement: ast.stmt) -> set[str]:
    if isinstance(statement, ast.Assign):
        return {
            target.id for target in statement.targets if isinstance(target, ast.Name)
        }
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
        return {statement.target.id}
    return set()


def test_class_comprehensions_do_not_read_prior_cockpit_class_attributes() -> None:
    tree = ast.parse(COCKPIT.read_text(encoding="utf-8"))
    cockpit = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "CockpitTab"
    )

    prior_class_attributes: set[str] = set()
    found_default_columns = False
    for statement in cockpit.body:
        value = None
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            value = statement.value

        if isinstance(
            value,
            (ast.DictComp, ast.ListComp, ast.SetComp, ast.GeneratorExp),
        ):
            loaded_names = {
                node.id
                for node in ast.walk(value)
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
            }
            unsafe = loaded_names & prior_class_attributes
            assert not unsafe, (
                "Klassen-Comprehension liest vorherige Klassenattribute und kann "
                f"beim Import mit NameError abbrechen: {sorted(unsafe)}"
            )
        if "DEFAULT_PANEL_COLUMNS" in _assigned_names(statement):
            found_default_columns = True

        prior_class_attributes.update(_assigned_names(statement))

    assert found_default_columns
