"""Cockpit-Diagramme im Stil der Vorlage: Ring mit Mittelwert, Flächenverlauf.

Getrennt von ``views/tabs/overview_widgets.py``, weil dort das interaktive
Übersichts-Diagramm mit Klick-Signal lebt. Hier geht es um zwei stille
Kacheln ohne Interaktion – gemeinsame Basis ist lediglich QtCharts.

Beide Diagramme färben sich nach jedem Aufbau aus dem aktiven Profil. Ohne
das bleiben neue Serien und Achsen bei den Qt-Standardfarben (schwarz auf
weiß) und wirken im dunklen Profil kaputt – dieselbe Falle wie in v2.1.4.
"""

from __future__ import annotations

import logging

from PySide6.QtCharts import (
    QAreaSeries,
    QChart,
    QChartView,
    QLineSeries,
    QPieSeries,
    QValueAxis,
)
from PySide6.QtCore import QMargins, QPointF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen

from views.ui_colors import ui_colors

logger = logging.getLogger(__name__)

#: Mehr Ringsegmente kann niemand mehr auseinanderhalten; der Rest wird
#: zu „Sonstige" zusammengefasst.
MAX_SLICES = 5


class _ThemedChartView(QChartView):
    """Gemeinsame Grundlage: transparenter Hintergrund, keine Animation."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("cockpitChartView")
        self.setRenderHint(QPainter.Antialiasing)
        self.setMinimumHeight(200)
        self.setMaximumHeight(260)
        self._chart = QChart()
        # Animationen aus: eine noch laufende Animation auf einer gerade
        # entfernten Serie hat unter Wayland schon zu Abstürzen geführt.
        self._chart.setAnimationOptions(QChart.NoAnimation)
        self._chart.setMargins(QMargins(4, 4, 4, 4))
        self._chart.setBackgroundVisible(False)
        self._chart.legend().setVisible(False)
        self.setChart(self._chart)


class DonutChart(_ThemedChartView):
    """Ringdiagramm mit Summe in der Mitte."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._center_title = ""

    def set_data(self, items: list[tuple[str, float]], center_label: str) -> None:
        """``items`` sind (Beschriftung, Betrag)-Paare, absteigend sortiert."""
        try:
            colors = ui_colors(self)
            self._chart.removeAllSeries()
            series = QPieSeries()
            series.setHoleSize(0.62)
            palette = [
                colors.accent,
                colors.positive,
                colors.warning,
                colors.negative,
                colors.text_dim,
            ]
            top = sorted(items, key=lambda item: item[1], reverse=True)
            rest = sum(value for _, value in top[MAX_SLICES:])
            top = top[:MAX_SLICES]
            if rest:
                top.append((center_label and "…" or "…", rest))
            for index, (label, value) in enumerate(top):
                if value <= 0:
                    continue
                slice_ = series.append(label, value)
                slice_.setLabelVisible(False)
                slice_.setBorderColor(QColor(colors.bg_panel))
                slice_.setBorderWidth(2)
                slice_.setBrush(QColor(palette[index % len(palette)]))
            self._chart.addSeries(series)
            self._chart.setTitle(center_label)
            self._chart.setTitleBrush(QColor(colors.text))
            font = QFont()
            font.setPointSize(13)
            font.setBold(True)
            self._chart.setTitleFont(font)
        except Exception as exc:  # pragma: no cover - Diagramm ist Beiwerk
            logger.debug("Ringdiagramm nicht aufbaubar: %s", exc)


class TrendAreaChart(_ThemedChartView):
    """Flächenverlauf mit stabiler, dauerhaft gehaltener QtCharts-Struktur.

    ``QAreaSeries`` übernimmt laut Qt-Dokumentation *nicht* das Eigentum an
    ihrer oberen/unteren ``QLineSeries``. Eine nur lokale Python-Referenz kann
    deshalb vom Garbage Collector entfernt werden, obwohl QtCharts intern noch
    darauf zugreift. Das endete unter PySide6 6.10.3 in
    ``AreaChartItem::fixEdgeSeriesDomain`` mit einem nativen Segfault.

    Serien und Achsen werden hier genau einmal erzeugt und als Instanzattribute
    gehalten. Bei einem Cockpit-Refresh ersetzen wir nur noch die Punkte und
    Achsenbereiche. Dadurch gibt es weder ungültige Edge-Series-Zeiger noch
    ``removeAllSeries()`` während eines laufenden Layout-/Paint-Ereignisses.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # QAreaSeries besitzt diese Linie NICHT. Die starke Python-Referenz und
        # der QObject-Parent sind daher beide absichtlich dauerhaft.
        self._upper_series = QLineSeries(self)
        self._area_series = QAreaSeries(self._upper_series)
        self._axis_x = QValueAxis(self)
        self._axis_y = QValueAxis(self)

        self._axis_x.setLabelsVisible(False)
        self._axis_x.setGridLineVisible(False)
        self._axis_x.setLineVisible(False)
        self._axis_y.setLabelFormat("%.0f")
        self._axis_y.setTickCount(5)

        self._chart.addSeries(self._area_series)
        self._chart.addAxis(self._axis_x, Qt.AlignBottom)
        self._chart.addAxis(self._axis_y, Qt.AlignLeft)
        self._area_series.attachAxis(self._axis_x)
        self._area_series.attachAxis(self._axis_y)
        self._area_series.setVisible(False)

    def set_data(self, values: list[float]) -> None:
        try:
            colors = ui_colors(self)
            points = [
                QPointF(index, float(value)) for index, value in enumerate(values)
            ]

            # Ein einzelner replace()-Aufruf verhindert Zwischenzustände, in
            # denen QtCharts während der Geometrieberechnung eine halb geleerte
            # Edge-Series sieht.
            self._upper_series.replace(points)
            self._area_series.setVisible(bool(points))

            accent = QColor(colors.accent)
            pen = QPen(accent)
            pen.setWidth(2)
            self._area_series.setPen(pen)

            gradient = QLinearGradient(0, 0, 0, 1)
            gradient.setCoordinateMode(QLinearGradient.ObjectBoundingMode)
            top_color = QColor(accent)
            top_color.setAlpha(150)
            bottom_color = QColor(accent)
            bottom_color.setAlpha(10)
            gradient.setColorAt(0.0, top_color)
            gradient.setColorAt(1.0, bottom_color)
            self._area_series.setBrush(gradient)

            axis_color = QColor(colors.border)
            self._axis_y.setLabelsColor(QColor(colors.text_dim))
            self._axis_y.setGridLineColor(axis_color)
            self._axis_y.setLinePenColor(axis_color)

            if not points:
                self._axis_x.setRange(0.0, 1.0)
                self._axis_y.setRange(0.0, 1.0)
                return

            x_max = max(1.0, float(len(points) - 1))
            raw_min = min(0.0, *(point.y() for point in points))
            raw_max = max(0.0, *(point.y() for point in points))
            if raw_min == raw_max:
                padding = max(1.0, abs(raw_max) * 0.1)
            else:
                padding = max(1.0, (raw_max - raw_min) * 0.08)
            self._axis_x.setRange(0.0, x_max)
            self._axis_y.setRange(raw_min - padding, raw_max + padding)
        except Exception as exc:  # pragma: no cover - Diagramm ist Beiwerk
            logger.debug("Flächenverlauf nicht aktualisierbar: %s", exc)
