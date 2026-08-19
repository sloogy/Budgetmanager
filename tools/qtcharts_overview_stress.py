#!/usr/bin/env python3
"""Realer QtCharts-Stresstest für den Overview-Hotfix v2.2.61.

Auf einem System mit GUI aus dem Projektroot ausführen:
    ./.venv/bin/python tools/qtcharts_overview_stress.py --iterations 1000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from views.tabs.overview_widgets import CompactChart


def _rings(seed: int) -> list[dict]:
    base = float((seed % 97) + 1)
    return [
        {
            "pie_size": 0.92,
            "hole_size": 0.68,
            "slices": [
                {"label": "Budget", "value": 1000.0 + base, "color": "#808080"},
                {"label": "Ist", "value": 700.0 + base, "color": "#404040"},
            ],
        },
        {
            "pie_size": 0.65,
            "hole_size": 0.42,
            "slices": [
                {"label": "Offen", "value": 300.0 + base, "color": "#909090"},
                {"label": "Gebucht", "value": 200.0 + base, "color": "#303030"},
            ],
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=1000)
    args = parser.parse_args()

    app = QApplication.instance() or QApplication(sys.argv[:1])
    chart = CompactChart()
    chart.resize(900, 420)
    chart.show()
    app.processEvents()

    for i in range(max(1, args.iterations)):
        mode = i % 6
        if mode == 0:
            chart.create_nested_donut(_rings(i))
        elif mode == 1:
            chart.create_pie_chart({"A": 100 + i, "B": 50 + i}, "Pie")
        elif mode == 2:
            chart.create_line_chart(
                ["Jan", "Feb", "Mrz"],
                [{"label": "Ist", "values": [10 + i, 20 + i, 15 + i]}],
                "Linie",
            )
        elif mode == 3:
            chart.create_colored_bar_chart(
                [
                    {"label": "A", "value": 100 + i, "color": "#808080"},
                    {"label": "B", "value": 50 + i, "color": "#404040"},
                ],
                "Balken",
            )
        elif mode == 4:
            chart.create_horizontal_bar_chart(
                [
                    {"label": "A", "value": 100 + i, "color": "#808080"},
                    {"label": "B", "value": 50 + i, "color": "#404040"},
                ],
                "Horizontal",
            )
        else:
            chart.create_grouped_bar_chart(
                ["Jan", "Feb"],
                [
                    {"label": "Budget", "values": [100 + i, 120 + i]},
                    {"label": "Ist", "values": [80 + i, 90 + i]},
                ],
                "Gruppiert",
            )
        app.processEvents()

    chart.close()
    chart.deleteLater()
    app.processEvents()
    print(f"OK: {args.iterations} Overview-Chart-Refreshes beendet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
