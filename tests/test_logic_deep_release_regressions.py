"""Tiefe Release-Regressionen für fachliche Logikverknüpfungen."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_overview_banner_includes_zero_balance_suggestions():
    """Null-Bilanz-Vorschläge dürfen nicht nur im Dialog sichtbar sein."""
    src = (ROOT / "views" / "tabs" / "overview_budget_panel.py").read_text()
    fn_start = src.index("    def _update_suggestions_banner")
    fn_end = src.index("    def _collect_main_cat_data", fn_start)
    body = src[fn_start:fn_end]

    assert "get_balance_suggestions" in body
    assert "balance_suggs" in body
    assert "all_suggs.append(s)" in body


def test_type_suggestions_respect_zero_balance_rule_static():
    """Gesamt-Ersparnisse dürfen die Null-Bilanz-Regel nicht umgehen."""
    src = (ROOT / "model" / "budget_overview_model.py").read_text()
    fn_start = src.index("    def get_type_suggestions")
    fn_end = src.index(
        "    # ------------------------------------------------------------------\n    # Hilfsmethoden",
        fn_start,
    )
    body = src[fn_start:fn_end]

    assert "budget_zero_balance_rule" in body
    assert "zero_balance_enabled and typ == TYP_SAVINGS" in body
    assert 'direction == "surplus"' in body
