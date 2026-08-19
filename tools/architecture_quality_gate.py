#!/usr/bin/env python3
"""Wartbarkeits-Gate: verhindert neue GUI-Monolithen und Riesenmethoden.

Die zwei historisch grossen Tabs wurden durch Auslagerung von eigenständigen
Dialogen reduziert. Harte Grenzwerte verhindern, dass diese Dateien wieder
unkontrolliert wachsen; neue Funktionalität muss in Module/Controller.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_DIRS = ("model", "updater", "utils", "views")
MAX_FILE_LINES = 3500
MAX_FUNCTION_LINES = 400
LEGACY_FUNCTION_LIMITS = {(Path("main.py"), "main"): 700}


def findings() -> list[str]:
    errors: list[str] = []
    files: list[Path] = []
    for directory in PRODUCT_DIRS:
        files.extend((ROOT / directory).rglob("*.py"))
    files.extend([ROOT / "main.py", ROOT / "settings.py", ROOT / "settings_dialog.py"])
    for path in sorted(set(files)):
        text = path.read_text(encoding="utf-8")
        line_count = len(text.splitlines())
        rel = path.relative_to(ROOT)
        if line_count > MAX_FILE_LINES:
            errors.append(f"{rel}: {line_count} Zeilen > {MAX_FILE_LINES}")
        try:
            tree = ast.parse(text, filename=str(rel))
        except SyntaxError as exc:
            errors.append(f"{rel}: Syntaxfehler: {exc}")
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.end_lineno
            ):
                length = node.end_lineno - node.lineno + 1
                limit = LEGACY_FUNCTION_LIMITS.get((rel, node.name), MAX_FUNCTION_LINES)
                if length > limit:
                    errors.append(
                        f"{rel}:{node.lineno} {node.name}(): {length} Zeilen > {limit}"
                    )
    return errors


def main() -> int:
    errors = findings()
    if errors:
        print("Architektur-Gate FEHLGESCHLAGEN")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        f"Architektur-Gate BESTANDEN: Dateien <= {MAX_FILE_LINES}, "
        f"neue Methoden <= {MAX_FUNCTION_LINES} Zeilen; "
        "explizit budgetierte Legacy-Ausnahmen innerhalb ihrer Obergrenze"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
