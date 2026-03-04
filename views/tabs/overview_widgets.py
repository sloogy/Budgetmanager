"""Gemeinsam genutzte UI-Widgets für die Finanzübersicht.

Enthält die wiederverwendbaren Basiswidgets:
- CompactKPICard
- CompactProgressBar
- CompactChart

Wurde aus overview_tab.py extrahiert (v1.0.5 – Patch C: Aufspaltung).
Alle anderen Overview-Sub-Module importieren aus dieser Datei.
"""
from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt, Signal, QMargins
from PySide6.QtGui import QPainter, QFont, QCursor, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QProgressBar, QSizePolicy,
)
from PySide6.QtCharts import (
    QChart, QChartView, QPieSeries, QPieSlice,
    QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis,
)

from utils.i18n import tr
from utils.money import format_money as format_chf
from views.ui_colors import ui_colors


class CompactKPICard(QFrame):
    """Kompakte KPI-Karte – anklickbar, farbkodiert."""
    clicked = Signal(str)

    def __init__(self, title: str, value: str = "0", icon: str = "💰",
                 color: str = None, parent=None):
        super().__init__(parent)
        self.title = title
        self._color = color or ui_colors(self).accent

        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(90)
        self.setMinimumWidth(150)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        header = QHBoxLayout()
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 16pt;")
        header.addWidget(icon_label)

        title_label = QLabel(title)
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        title_label.setFont(font)
        header.addWidget(title_label)
        header.addStretch()
        layout.addLayout(header)

        self.value_label = QLabel(value)
        font2 = QFont()
        font2.setPointSize(14)
        font2.setBold(True)
        self.value_label.setFont(font2)
        self.value_label.setStyleSheet(f"color: {self._color};")
        layout.addWidget(self.value_label)
        layout.addStretch()

    def update_value(self, value: str, color: str = None) -> None:
        self.value_label.setText(value)
        if color:
            self._color = color
            self.value_label.setStyleSheet(f"color: {color};")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.title)
        super().mousePressEvent(event)


class CompactProgressBar(QWidget):
    """Kompakter Fortschrittsbalken mit Beschriftung."""
    def __init__(self, label: str, max_value: float = 100, parent=None):
        super().__init__(parent)
        self.max_value = max_value
        self.current_value = 0.0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.label = QLabel(label)
        self.label.setFixedWidth(80)
        layout.addWidget(self.label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(True)
        self.progress.setFixedHeight(20)
        layout.addWidget(self.progress)

    def set_values(self, current: float, maximum: float) -> None:
        self.current_value = float(current)
        self.max_value = float(maximum)

        if maximum <= 0:
            # Kein Budget definiert: Fortschritt auf 0 setzen, Hinweis anzeigen
            self.progress.setValue(0)
            self.progress.setFormat(f"{format_chf(current)} / –")
            self.progress.setStyleSheet("")
            return

        percent = min(int((abs(self.current_value) / self.max_value) * 100), 200)
        self.progress.setValue(min(percent, 100))
        self.progress.setFormat(
            f"{percent}% ({format_chf(self.current_value)} / {format_chf(self.max_value)})"
        )

        c = ui_colors(self)
        color = c.progress_color(percent)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {c.border};
                border-radius: 3px;
                text-align: center;
                background: {c.bg_panel};
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 2px;
            }}
        """)


class CompactChart(QChartView):
    """Kompaktes Diagramm mit Click-Signal."""
    slice_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setMinimumHeight(180)
        self.setMaximumHeight(300)
        self._chart = QChart()
        self._chart.setAnimationOptions(QChart.SeriesAnimations)
        self._chart.setAnimationDuration(400)
        self._chart.setMargins(QMargins(0, 0, 0, 0))
        self.setChart(self._chart)

    def create_pie_chart(self, data: dict[str, float], title: str = "", color_map: dict[str, str] | None = None) -> None:
        self._chart.removeAllSeries()
        if not data:
            self._chart.setTitle(title + tr("tab_ui.keine_daten"))
            return

        series = QPieSeries()
        series.setHoleSize(0.4)
        sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
        c = ui_colors(self)
        colors = c.chart_palette(10)

        for i, (label, value) in enumerate(sorted_data):
            v = float(value)
            if v <= 0:
                continue
            s = series.append(f"{label}: {format_chf(v)}", v)
            s.setProperty("raw_label", label)
            s.setLabelVisible(True)
            s.setLabelPosition(QPieSlice.LabelPosition.LabelOutside)
            if color_map and label in color_map:
                s.setColor(QColor(color_map[label]))
            elif i < len(colors):
                s.setColor(colors[i])

        try:
            series.clicked.connect(
                lambda sl: self.slice_clicked.emit(str(sl.property("raw_label") or ""))
            )
        except Exception as e:
            logger.debug("series.clicked connect: %s", e)

        self._chart.addSeries(series)
        self._chart.setTitle(title)
        self._chart.legend().setVisible(False)

    def create_nested_donut(self, ring_data: list[dict]) -> None:
        self._chart.removeAllSeries()
        self._chart.legend().setVisible(False)
        self._chart.setTitle("")

        if not ring_data:
            self._chart.setTitle(tr("dlg.no_data"))
            return

        for ring in ring_data:
            series = QPieSeries()
            series.setPieSize(ring.get("pie_size", 0.9))
            series.setHoleSize(ring.get("hole_size", 0.7))

            for sl_def in ring.get("slices", []):
                val = float(sl_def.get("value", 0))
                if val < 0.01:
                    continue
                sl = series.append(sl_def.get("label", ""), val)
                sl.setColor(QColor(sl_def.get("color", ui_colors(self).text_dim)))
                sl.setProperty("raw_label", sl_def.get("raw_label", ""))
                sl.setLabelVisible(True)
                sl.setLabelPosition(QPieSlice.LabelPosition.LabelOutside)
                try:
                    sl.setBorderWidth(1)
                    sl.setBorderColor(QColor(ui_colors(self).bg_app))
                except Exception as e:
                    logger.debug("sl.setBorderWidth: %s", e)
                try:
                    sl.hovered.connect(lambda state, s=sl: self._on_slice_hover(state, s))
                except Exception as e:
                    logger.debug("sl.hovered connect: %s", e)

            try:
                series.clicked.connect(
                    lambda sl: self.slice_clicked.emit(str(sl.property("raw_label") or ""))
                )
            except Exception as e:
                logger.debug("series.clicked connect: %s", e)

            self._chart.addSeries(series)

    def _on_slice_hover(self, state: bool, sl: QPieSlice) -> None:
        try:
            if state:
                sl.setExploded(True)
                sl.setExplodeDistanceFactor(0.05)
                font = sl.labelFont()
                font.setBold(True)
                sl.setLabelFont(font)
            else:
                sl.setExploded(False)
                font = sl.labelFont()
                font.setBold(False)
                sl.setLabelFont(font)
        except Exception as e:
            logger.debug("_on_slice_hover: %s", e)

    def create_grouped_bar_chart(
        self,
        categories: list[str],
        series_data: list[dict],
        title: str = "",
    ) -> None:
        self._chart.removeAllSeries()
        for ax in self._chart.axes():
            self._chart.removeAxis(ax)
        self._chart.legend().setVisible(True)

        if not categories or not series_data:
            self._chart.setTitle(title + tr("tab_ui.keine_daten"))
            return

        bar_series = QBarSeries()
        for sd in series_data:
            bar_set = QBarSet(sd.get("label", ""))
            for v in sd.get("values", []):
                bar_set.append(float(v))
            bar_set.setColor(QColor(sd.get("color", ui_colors(self).accent)))
            bar_series.append(bar_set)

        self._chart.addSeries(bar_series)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        self._chart.addAxis(axis_x, Qt.AlignBottom)
        bar_series.attachAxis(axis_x)

        axis_y = QValueAxis()
        all_vals = [v for sd in series_data for v in sd.get("values", [])]
        max_val = max(all_vals) if all_vals else 1000
        axis_y.setRange(0, max_val * 1.15)
        axis_y.setLabelFormat("%.0f")
        self._chart.addAxis(axis_y, Qt.AlignLeft)
        bar_series.attachAxis(axis_y)

        self._chart.setTitle(title)
