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
    QBarSeries, QStackedBarSeries, QBarSet, QBarCategoryAxis, QValueAxis,
    QLineSeries,
)

from utils.icons import get_icon
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
        icon_label = QLabel("")
        icon_obj = get_icon(icon)
        if not icon_obj.isNull():
            icon_label.setPixmap(icon_obj.pixmap(20, 20))
            icon_label.setFixedSize(20, 20)
        else:
            icon_label.setText(icon)
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
    """Kompakter Fortschrittsbalken mit Beschriftung.

    Standard bleibt eine Ampel-Farbe. Für Typ-Balken (Einnahmen/Ausgaben/
    Ersparnisse) kann ``typ_key`` gesetzt werden; dann verwendet der Balken
    immer die Kontofarbe aus dem aktiven Theme statt Grün/Gelb/Rot.
    """
    def __init__(self, label: str, max_value: float = 100, parent=None, *, typ_key: str | None = None, bar_color: str | None = None):
        super().__init__(parent)
        self.max_value = max_value
        self.current_value = 0.0
        self.typ_key = typ_key
        self._bar_color = bar_color

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
        if self.typ_key:
            color = c.type_color(self.typ_key)
        else:
            color = self._bar_color or c.progress_color(percent)
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
        # Animationen bewusst AUS: SeriesAnimations + removeAllSeries() beim
        # Neuzeichnen konnten unter Wayland/Linux eine noch animierte Serie
        # freigeben -> "double free or corruption". Ohne Animation ist das
        # Umzeichnen (z.B. nach einer Budgetanpassung) sicher.
        self._chart.setAnimationOptions(QChart.NoAnimation)
        self._chart.setMargins(QMargins(0, 0, 0, 0))
        self.setChart(self._chart)

    def _clear_chart(self, *, keep_legend: bool = False) -> None:
        """Entfernt Serien und Achsen, damit Pie/Line/Bar sauber umschalten.

        Ohne Achsen-Cleanup bleiben nach einem Wechsel von Linien-/Balken-
        Diagrammen zu Kreisdiagrammen gelegentlich alte Achsen im Chart hängen.
        """
        self._chart.removeAllSeries()
        for axis in list(self._chart.axes()):
            self._chart.removeAxis(axis)
        self._chart.legend().setVisible(bool(keep_legend))

    def create_pie_chart(self, data: dict[str, float], title: str = "", color_map: dict[str, str] | None = None) -> None:
        self._clear_chart(keep_legend=False)
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
        self._clear_chart(keep_legend=False)
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

    def create_line_chart(
        self,
        categories: list[str],
        series_data: list[dict],
        title: str = "",
    ) -> None:
        """Zeichnet einen kompakten Liniengraphen für Monats-/Trenddaten.

        ``series_data``: [{"label": str, "values": [float], "color": "#rrggbb"?}]
        Die X-Achse nutzt die übergebenen Kategorien direkt als Monatslabels.
        """
        self._clear_chart(keep_legend=True)

        if not categories or not series_data:
            self._chart.setTitle(title + tr("tab_ui.keine_daten"))
            return

        all_values: list[float] = []
        for sd in series_data:
            values = [float(v or 0.0) for v in sd.get("values", [])]
            if not values:
                continue
            series = QLineSeries()
            series.setName(sd.get("label", ""))
            for i, val in enumerate(values[:len(categories)]):
                series.append(i, val)
                all_values.append(val)
            if sd.get("color"):
                series.setColor(QColor(sd.get("color")))
            self._chart.addSeries(series)

        if not self._chart.series():
            self._chart.setTitle(title + tr("tab_ui.keine_daten"))
            return

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        self._chart.addAxis(axis_x, Qt.AlignBottom)

        if all_values:
            min_val = min(0.0, min(all_values))
            max_val = max(0.0, max(all_values))
        else:
            min_val, max_val = 0.0, 100.0
        if abs(max_val - min_val) < 0.01:
            max_val += 1.0
            min_val -= 1.0 if min_val < 0 else 0.0
        pad = max(abs(max_val - min_val) * 0.12, 1.0)

        axis_y = QValueAxis()
        axis_y.setRange(min_val - pad if min_val < 0 else 0.0, max_val + pad)
        axis_y.setLabelFormat("%.0f")
        self._chart.addAxis(axis_y, Qt.AlignLeft)

        for series in self._chart.series():
            series.attachAxis(axis_x)
            series.attachAxis(axis_y)

        self._chart.setTitle(title)


    def create_colored_bar_chart(self, bars: list[dict], title: str = "") -> None:
        """Balkendiagramm mit individueller Farbe je Balken.

        ``bars``: [{"label": str, "value": float, "color": "#rrggbb"}]
        Technisch wird eine StackedBarSeries mit je einem Set pro Balken
        verwendet. Dadurch bleibt pro Kategorie genau ein farbiger Balken sichtbar.
        """
        self._clear_chart(keep_legend=False)
        bars = [b for b in bars if float(b.get("value", 0.0) or 0.0) > 0.0]
        if not bars:
            self._chart.setTitle(title + tr("tab_ui.keine_daten"))
            return

        labels = [str(b.get("label", "")) for b in bars]
        series = QStackedBarSeries()
        for idx, b in enumerate(bars):
            bar_set = QBarSet(str(b.get("label", "")))
            for j in range(len(bars)):
                bar_set.append(float(b.get("value", 0.0)) if j == idx else 0.0)
            bar_set.setColor(QColor(str(b.get("color") or ui_colors(self).accent)))
            series.append(bar_set)

        self._chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(labels)
        self._chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        max_val = max(float(b.get("value", 0.0) or 0.0) for b in bars)
        axis_y.setRange(0, max_val * 1.15 if max_val > 0 else 1)
        axis_y.setLabelFormat("%.0f")
        self._chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)

        self._chart.setTitle(title)
        self._chart.legend().setVisible(False)

    def create_grouped_bar_chart(
        self,
        categories: list[str],
        series_data: list[dict],
        title: str = "",
    ) -> None:
        self._clear_chart(keep_legend=True)

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
