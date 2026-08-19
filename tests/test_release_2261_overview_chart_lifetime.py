"""Regression gates for v2.2.61 overview QtCharts native-abort hotfix."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIDGETS = ROOT / "views" / "tabs" / "overview_widgets.py"


def _compact_chart() -> ast.ClassDef:
    tree = ast.parse(WIDGETS.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "CompactChart":
            return node
    raise AssertionError("CompactChart fehlt")


def _method(cls: ast.ClassDef, name: str) -> ast.FunctionDef:
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} fehlt")


def test_overview_refresh_never_calls_remove_all_series() -> None:
    cls = _compact_chart()
    calls = [
        node
        for node in ast.walk(cls)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "removeAllSeries"
    ]
    assert not calls


def test_chart_is_replaced_atomically_before_old_chart_is_retired() -> None:
    clear_src = ast.unparse(_method(_compact_chart(), "_clear_chart"))
    assert "new_chart = self._new_chart()" in clear_src
    assert "self.setChart(new_chart)" in clear_src
    assert "self._retire_chart(old_chart)" in clear_src
    assert clear_src.index("self.setChart(new_chart)") < clear_src.index(
        "self._retire_chart(old_chart)"
    )


def test_retired_chart_uses_deferred_cpp_deletion_and_strong_reference() -> None:
    cls = _compact_chart()
    init_src = ast.unparse(_method(cls, "__init__"))
    retire_src = ast.unparse(_method(cls, "_retire_chart"))
    assert "self._retired_charts" in init_src
    assert "self._retired_charts[key] = chart" in retire_src
    assert "chart.destroyed.connect" in retire_src
    assert "chart.deleteLater()" in retire_src


def test_all_chart_builders_still_clear_via_safe_swap() -> None:
    cls = _compact_chart()
    for name in (
        "create_pie_chart",
        "create_nested_donut",
        "create_line_chart",
        "create_colored_bar_chart",
        "create_horizontal_bar_chart",
        "create_grouped_bar_chart",
    ):
        src = ast.unparse(_method(cls, name))
        assert "self._clear_chart" in src
