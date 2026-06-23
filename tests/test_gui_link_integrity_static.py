from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW = ROOT / "views" / "main_window.py"
SHORTCUTS = ROOT / "model" / "shortcuts_config.py"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _shortcut_defs() -> list[str]:
    tree = _parse(SHORTCUTS)
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        else:
            continue
        if not any(
            isinstance(t, ast.Name) and t.id == "SHORTCUT_DEFS" for t in targets
        ):
            continue
        result: list[str] = []
        for item in value.elts:
            if (
                isinstance(item, ast.Tuple)
                and item.elts
                and isinstance(item.elts[0], ast.Constant)
            ):
                result.append(str(item.elts[0].value))
        return result
    raise AssertionError("SHORTCUT_DEFS not found")


def _main_window_shortcut_bindings() -> set[str]:
    tree = _parse(MAIN_WINDOW)
    bindings: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (
            isinstance(node.func, ast.Attribute) and node.func.attr == "_apply_shortcut"
        ):
            continue
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            bindings.add(str(node.args[1].value))
    return bindings


def test_all_configurable_shortcuts_are_bound_to_mainwindow_actions():
    defined = set(_shortcut_defs())
    bound = _main_window_shortcut_bindings()
    assert (
        defined <= bound
    ), f"Shortcut definitions without QAction binding: {sorted(defined - bound)}"


def test_mainwindow_has_no_hardcoded_qaction_shortcuts_outside_shortcut_helper():
    tree = _parse(MAIN_WINDOW)
    helper_ranges = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_apply_shortcut":
            helper_ranges.append((node.lineno, node.end_lineno or node.lineno))

    offenders: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in {"setShortcut", "setShortcuts"}
        ):
            continue
        if any(start <= node.lineno <= end for start, end in helper_ranges):
            continue
        offenders.append((node.lineno, ast.unparse(node)))
    assert not offenders, f"Hardcoded QAction shortcut calls: {offenders}"


def test_expert_categories_tab_is_reachable_when_enabled():
    src = MAIN_WINDOW.read_text(encoding="utf-8")
    assert '1: (self.categories_tab, tr("tab.categories"))' in src
    assert '1: "categories"' in src
    assert 'self._apply_shortcut(self.goto_categories_action, "tab_categories")' in src
    assert "def _goto_categories_or_manager" in src
