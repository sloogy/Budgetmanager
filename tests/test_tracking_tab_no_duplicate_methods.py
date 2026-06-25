"""Regression: ``TrackingTab`` darf keine doppelt definierten Methoden enthalten.

In v2.0.18 hatte ein Patch-Lauf den i18n-Helferblock (``_current_filter_typ_db`` /
``_is_all_typ``) und ``set_recent_days`` mehrfach in die Klasse eingefügt. In Python
gewinnt jeweils die letzte Definition – der Rest war toter, irreführender Code und
blähte die Datei auf. Dieser Test stellt sicher, dass jede Methode genau einmal
definiert ist.

Läuft ohne Qt/PySide6 (reine AST-Analyse).
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _method_counts(path: Path, class_name: str) -> dict[str, int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    counts[item.name] = counts.get(item.name, 0) + 1
    return counts


def test_tracking_tab_has_no_duplicate_methods():
    path = ROOT / "views" / "tabs" / "tracking_tab.py"
    counts = _method_counts(path, "TrackingTab")
    assert counts, "TrackingTab nicht gefunden"
    dupes = {name: n for name, n in counts.items() if n > 1}
    assert not dupes, f"Doppelt definierte Methoden in TrackingTab: {dupes}"


if __name__ == "__main__":
    test_tracking_tab_has_no_duplicate_methods()
    print("OK")
