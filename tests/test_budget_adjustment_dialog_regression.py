"""Regression für Budgetwarnungen-Dialog ohne aktuelle Überschreitungen.

Der Dialog kann reine Verlaufsvorschläge anzeigen, bei denen keine
aktuellen Budget-Überschreitungen aus ``check_warnings_extended`` vorliegen.
In v2.0.8 crashte das durch ``max(exceedances)`` mit leerer Liste.
Dieser Test ist bewusst statisch und läuft ohne PySide6.
"""
from pathlib import Path


def test_budget_adjustment_recommendations_do_not_max_empty_exceedances():
    src = Path("views/budget_adjustment_dialog.py").read_text(encoding="utf-8")
    assert "max(exceedances" not in src
    assert "if exceeded_cats else None" in src
