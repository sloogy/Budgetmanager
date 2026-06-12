"""Sparziele-Panel der Finanzübersicht.

Extrahiert aus overview_tab.py (v1.0.5 – Patch C: Aufspaltung).
Verantwortlich für:
- Aufbau der Sparziele-Tabelle
- Laden und Anzeigen der Sparzieldaten
- Doppelklick → SavingsGoalsDialog mit Vorauswahl

Schnittstelle zu OverviewTab:
    panel = OverviewSavingsPanel(conn, parent=self)
    panel.refresh()   # Daten neu laden
"""
from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QSizePolicy,
)

from model.savings_goals_model import SavingsGoalsModel
from utils.i18n import tr, trf
from utils.money import format_money as format_chf
from views.ui_colors import ui_colors


class OverviewSavingsPanel(QWidget):
    """Sparziele-Panel – eigenständiges Widget für den Savings-Tab."""

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.savings = SavingsGoalsModel(conn)
        self._setup_ui()

    # ── Aufbau ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Header: Anzahl + Verwaltungs-Button
        header_layout = QHBoxLayout()
        self.lbl_count = QLabel(trf("overview.count.savings_goals", n=0))
        self.lbl_count.setStyleSheet("font-weight: bold; padding: 4px;")
        header_layout.addWidget(self.lbl_count)
        header_layout.addStretch()

        self.btn_manage = QPushButton(tr("overview.savings.btn_manage"))
        self.btn_manage.setToolTip(tr("btn.sparzieledialog_oeffnen"))
        self.btn_manage.clicked.connect(lambda: self._open_savings_dialog())
        header_layout.addWidget(self.btn_manage)
        layout.addLayout(header_layout)

        # Tabelle
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            tr("dlg.savings_goals"),
            tr("lbl.savings_goal_target"),
            tr("lbl.savings_goal_current"),
            tr("lbl.savings_goal_remaining"),
            tr("lbl.savings_goal_progress"),
            tr("lbl.status"),
            tr("lbl.savings_goal_released"),
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)           # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Ziel
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Aktuell
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Rest
        header.setSectionResizeMode(4, QHeaderView.Stretch)           # Fortschritt
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Status
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Freigegeben
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(55)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(160)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)

        # Zusammenfassung
        self.lbl_summary = QLabel()
        self.lbl_summary.setTextFormat(Qt.RichText)
        self.lbl_summary.setStyleSheet("padding: 4px; font-size: 12px;")
        layout.addWidget(self.lbl_summary)

    # ── Daten laden ─────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Sparzieldaten neu laden und Tabelle aktualisieren."""
        try:
            goals = self.savings.list_all()
        except Exception:
            goals = []

        c = ui_colors(self)
        self.table.setRowCount(0)

        n_goals = len(goals)
        count_key = "lbl.savings_goal_count_one" if n_goals == 1 else "lbl.savings_goal_count_many"
        self.lbl_count.setText(trf(count_key, n=n_goals))

        if not goals:
            self.lbl_summary.setText(tr("overview.savings.empty"))
            return

        total_target = 0.0
        total_current = 0.0

        for goal in goals:
            row = self.table.rowCount()
            self.table.insertRow(row)

            total_target += goal.target_amount
            total_current += goal.current_amount

            status_icon = getattr(goal, "status_icon", "")
            status_label = getattr(goal, "status_label", tr("lbl.saving"))
            is_released = getattr(goal, "is_released", False)
            is_completed = getattr(goal, "is_completed", False)

            # Spalte 0: Name + Tooltip
            name_item = QTableWidgetItem(f"{status_icon} {goal.name}".strip())
            name_item.setData(Qt.UserRole, goal.id)
            tooltip_parts = [f"{tr('tooltip.status')}: {status_label}"]
            if goal.category:
                tooltip_parts.append(f"{tr('tooltip.category')}: {goal.category}")
            if goal.deadline:
                tooltip_parts.append(f"{tr('tooltip.deadline')}: {goal.deadline}")
            if getattr(goal, "released_date", None):
                tooltip_parts.append(f"{tr('tooltip.released')}: {goal.released_date[:10]}")
            if goal.notes:
                tooltip_parts.append(f"{tr('tooltip.note')}: {goal.notes}")
            name_item.setToolTip("\n".join(tooltip_parts))
            self.table.setItem(row, 0, name_item)

            # Spalte 1: Ziel
            t = QTableWidgetItem(format_chf(goal.target_amount))
            t.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 1, t)

            # Spalte 2: Aktuell
            cur = QTableWidgetItem(format_chf(goal.current_amount))
            cur.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, cur)

            # Spalte 3: Rest
            remaining = goal.remaining_amount
            rest_item = QTableWidgetItem(format_chf(remaining))
            rest_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if remaining <= 0:
                rest_item.setForeground(QColor(c.ok))
            self.table.setItem(row, 3, rest_item)

            # Spalte 4: Fortschrittsbalken (als CellWidget)
            progress = int(goal.progress_percent)
            pw = QWidget()
            pl = QHBoxLayout(pw)
            pl.setContentsMargins(4, 4, 4, 4)
            bar = QProgressBar()
            bar.setMinimum(0)
            bar.setMaximum(100)
            bar.setValue(min(progress, 100))
            bar.setFormat(f"{progress}%")
            bar.setFixedHeight(20)

            if progress >= 100:
                pcolor = c.ok
            elif progress >= 75:
                pcolor = c.accent
            elif progress >= 40:
                pcolor = c.warning
            else:
                pcolor = c.negative
            bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid {c.border};
                    border-radius: 4px;
                    text-align: center;
                    background: {c.bg_panel};
                }}
                QProgressBar::chunk {{
                    background-color: {pcolor};
                    border-radius: 3px;
                }}
            """)
            pl.addWidget(bar)
            self.table.setCellWidget(row, 4, pw)

            # Spalte 5: Status
            st_item = QTableWidgetItem(f"{status_icon} {status_label}")
            st_item.setTextAlignment(Qt.AlignCenter)
            if is_released:
                st_item.setForeground(QColor(c.accent))
            elif is_completed:
                st_item.setForeground(QColor(c.ok))
            self.table.setItem(row, 5, st_item)

            # Spalte 6: Freigegeben/Verbraucht
            if is_released or is_completed:
                try:
                    spent = self.savings.get_spent_amount(goal.id)
                    released_amt = getattr(goal, "released_amount", 0) or 0
                    if spent > 0:
                        sp_item = QTableWidgetItem(f"-{format_chf(spent)}")
                        sp_item.setForeground(QColor(c.negative))
                        sp_item.setToolTip(
                            trf(
                                "overview.savings.released_tooltip",
                                released=format_chf(released_amt),
                                spent=format_chf(spent),
                                available=format_chf(max(0, released_amt - spent)),
                            )
                        )
                    else:
                        sp_item = QTableWidgetItem(format_chf(0))
                except Exception:
                    sp_item = QTableWidgetItem("-")
            else:
                sp_item = QTableWidgetItem("-")
            sp_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 6, sp_item)

            # Abgeschlossene Zeilen grau darstellen
            if is_completed:
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        item.setForeground(QColor(c.text_dim))

        # Zusammenfassung
        total_remaining = total_target - total_current
        overall_pct = (total_current / total_target * 100) if total_target > 0 else 0
        summary = trf("lbl.savings_summary_of",
            current=format_chf(total_current), target=format_chf(total_target), pct=overall_pct)
        if total_remaining <= 0:
            summary += trf("lbl.all_goals_reached", color=c.ok)
        else:
            summary += trf("lbl.savings_remaining", amount=format_chf(total_remaining))
        self.lbl_summary.setText(summary)
        self.table.resizeRowsToContents()

    # ── Interaktion ─────────────────────────────────────────────────────────

    def _on_double_click(self, index) -> None:
        goal_id = None
        try:
            model = index.model()
            if model:
                goal_id = model.index(index.row(), 0).data(Qt.UserRole)
        except Exception as e:
            logger.debug("_on_double_click goal_id: %s", e)
        self._open_savings_dialog(initial_goal_id=goal_id)

    def _open_savings_dialog(self, initial_goal_id: int | None = None) -> None:
        from views.savings_goals_dialog import SavingsGoalsDialog
        dialog = SavingsGoalsDialog(self.window(), self.conn, initial_goal_id=initial_goal_id)
        dialog.exec()
        self.refresh()
