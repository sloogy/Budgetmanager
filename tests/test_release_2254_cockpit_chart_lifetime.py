"""Regression gates for v2.2.54 cockpit QtCharts lifetime hotfix."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHARTS = ROOT / "views" / "cockpit_charts.py"


def _trend_class() -> ast.ClassDef:
    tree = ast.parse(CHARTS.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "TrendAreaChart":
            return node
    raise AssertionError("TrendAreaChart fehlt")


def _method(cls: ast.ClassDef, name: str) -> ast.FunctionDef:
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} fehlt")


def test_area_edge_series_has_a_persistent_python_reference():
    """QAreaSeries owns neither upper nor lower edge series."""
    init_src = ast.unparse(_method(_trend_class(), "__init__"))
    assert "self._upper_series = QLineSeries(self)" in init_src
    assert "self._area_series = QAreaSeries(self._upper_series)" in init_src


def test_refresh_updates_existing_series_in_place():
    set_data_src = ast.unparse(_method(_trend_class(), "set_data"))
    assert "self._upper_series.replace(points)" in set_data_src
    assert "removeAllSeries" not in set_data_src
    assert "createDefaultAxes" not in set_data_src
    assert "QAreaSeries(" not in set_data_src
    assert "QLineSeries(" not in set_data_src


def test_axes_are_persistent_and_not_recreated_during_refresh():
    init_src = ast.unparse(_method(_trend_class(), "__init__"))
    assert "self._axis_x = QValueAxis(self)" in init_src
    assert "self._axis_y = QValueAxis(self)" in init_src
    assert "self._area_series.attachAxis(self._axis_x)" in init_src
    assert "self._area_series.attachAxis(self._axis_y)" in init_src


def test_chart_module_documents_the_native_crash_signature():
    src = CHARTS.read_text(encoding="utf-8")
    assert "AreaChartItem::fixEdgeSeriesDomain" in src
    assert "QAreaSeries besitzt diese Linie NICHT" in src


def test_emergency_switch_can_disable_only_cockpit_charts():
    src = (ROOT / "views" / "tabs" / "cockpit_tab.py").read_text(encoding="utf-8")
    block = src.split("def _refresh_charts", 1)[1].split("def _refresh_kpi_trends", 1)[
        0
    ]
    assert "BM_DISABLE_COCKPIT_CHARTS" in block
    assert "self.chart_donut.setVisible(not disabled)" in block
    assert "self.chart_trend.setVisible(not disabled)" in block
    assert "return" in block
