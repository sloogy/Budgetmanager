"""Runtime- und Strukturregressionen für den v2.2.60-QtCharts-Abort."""

from __future__ import annotations

import ast
import inspect
import os
import textwrap

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PySide6.QtWidgets", reason="PySide6 Widgets fehlen")
pytest.importorskip("PySide6.QtCharts", reason="PySide6 QtCharts fehlt")

from PySide6.QtWidgets import QApplication  # noqa: E402

from views.tabs.overview_widgets import CompactChart  # noqa: E402


def _ring_data() -> list[dict]:
    return [
        {
            "pie_size": 0.92,
            "hole_size": 0.66,
            "slices": [
                {
                    "value": 100.0,
                    "label": "Plan",
                    "raw_label": "Plan",
                    "color": "#4caf50",
                },
                {
                    "value": 40.0,
                    "label": "Ist",
                    "raw_label": "Ist",
                    "color": "#f44336",
                },
            ],
        }
    ]


def test_overview_refresh_never_calls_remove_all_series() -> None:
    source = inspect.getsource(CompactChart._clear_chart)
    tree = ast.parse(textwrap.dedent(source))
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "removeAllSeries"
        for node in ast.walk(tree)
    )
    assert "deleteLater" in source
    assert "self.setChart(new_chart)" in source


def test_repeated_nested_donut_refresh_replaces_chart_atomically() -> None:
    app = QApplication.instance() or QApplication([])
    widget = CompactChart()
    previous = widget._chart
    for _ in range(250):
        widget.create_nested_donut(_ring_data())
        assert widget._chart is not previous
        previous = widget._chart
        app.processEvents()
    widget.close()
    app.processEvents()
