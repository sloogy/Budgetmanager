from __future__ import annotations
import logging
logger = logging.getLogger(__name__)
import sqlite3
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QDoubleSpinBox, QTextEdit, QDateEdit,
    QComboBox, QMessageBox, QProgressBar, QAbstractItemView, QMenu, QGroupBox
)

from model.savings_goals_model import (
    SavingsGoalsModel, SavingsGoal,
    STATUS_SAVING, STATUS_RELEASED, STATUS_COMPLETED,
    STATUS_LABELS, STATUS_ICONS,
)
from model.category_model import CategoryModel
from utils.money import format_money, get_symbol, currency_header
from views.ui_colors import ui_colors
from utils.i18n import tr, trf, display_typ, db_typ_from_display
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS


class SavingsGoalsDialog(QDialog):
    def __init__(self, parent, conn: sqlite3.Connection, initial_goal_id: int | None = None):
        super().__init__(parent)
        self.conn = conn
        self._initial_goal_id = initial_goal_id
        self.goals_model = SavingsGoalsModel(conn)
        self.cat_model = CategoryModel(conn)
        
        self.setWindowTitle(tr("dlg.savings_goals"))
        self.setModal(True)
        self.resize(1050, 650)
        
        # Buttons
        self.btn_add = QPushButton(tr("btn.btn_new_goal"))
        self.btn_edit = QPushButton("✏️ Bearbeiten")
        self.btn_delete = QPushButton(tr("btn.loeschen_1"))
        self.btn_add_progress = QPushButton("📈 Fortschritt")
        self.btn_sync = QPushButton("🔄 Sync")
        # Lifecycle-Buttons
        self.btn_release = QPushButton(tr("btn.btn_unlock"))
        self.btn_complete = QPushButton("✅ Abschliessen")
        self.btn_reopen = QPushButton(tr("btn.wieder_oeffnen"))
        self.btn_close = QPushButton(tr("btn.close"))
        
        # Tooltips
        self.btn_release.setToolTip(
            "Sparziel freigeben: Der aktuelle Stand wird eingefroren.\n"
            "Ab dann können Ausgaben gegen dieses Ziel gebucht werden."
        )
        self.btn_complete.setToolTip(
            "Sparziel abschliessen: Wird archiviert und als erledigt markiert."
        )
        self.btn_reopen.setToolTip(
            "Sparziel wieder zum Sparen öffnen.\n"
            "Der Freigabe-Status wird zurückgesetzt."
        )
        self.btn_sync.setToolTip(
            tr("tip.sync_tracking")
        )
        
        # Tabelle: 9 Spalten inkl. Status und Verbrauch
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Name", f"Ziel ({currency_header()})", f"Aktuell ({currency_header()})", 
            "Fortschritt", "Restbetrag", "Status",
            "Freigegeben", "Verbraucht", "Frist"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(lambda _: self.edit_goal())
        self.table.itemSelectionChanged.connect(self._update_button_states)
        
        # Layout
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_add_progress)
        btn_layout.addWidget(self.btn_sync)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_release)
        btn_layout.addWidget(self.btn_complete)
        btn_layout.addWidget(self.btn_reopen)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        
        # Info-Label
        info = QLabel(
            "💡 Lebenszyklus: <b>Sparend</b> → <b>Freigegeben</b> (Verbrauch möglich) → <b>Abgeschlossen</b> (Archiv)"
        )
        info.setWordWrap(True)
        _c = ui_colors(self)
        info.setStyleSheet(f"padding: 8px; background-color: {_c.info_bg}; border-radius: 5px; font-size: 11px;")
        
        layout = QVBoxLayout()
        layout.addWidget(info)
        layout.addWidget(self.table)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        # Connections
        self.btn_add.clicked.connect(self.add_goal)
        self.btn_edit.clicked.connect(self.edit_goal)
        self.btn_delete.clicked.connect(self.delete_goal)
        self.btn_add_progress.clicked.connect(self.add_progress)
        self.btn_sync.clicked.connect(self.sync_with_tracking)
        self.btn_release.clicked.connect(self._release_goal)
        self.btn_complete.clicked.connect(self._complete_goal)
        self.btn_reopen.clicked.connect(self._reopen_goal)
        self.btn_close.clicked.connect(self.accept)
        
        self.refresh()
        # Vorauswahl: Wenn ein Sparziel-ID übergeben wurde, entsprechende Zeile selektieren
        if self._initial_goal_id is not None:
            self._select_goal_by_id(self._initial_goal_id)
    
    def _select_goal_by_id(self, goal_id: int) -> None:
        """Selektiert die Zeile mit der angegebenen Sparziel-ID."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.UserRole) == goal_id:
                self.table.selectRow(row)
                self.table.scrollTo(self.table.model().index(row, 0))
                break

    def _show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        self.table.selectRow(row)
        goal = self._selected_goal()
        if not goal:
            return

        menu = QMenu(self)
        act_edit = menu.addAction("✏️ Bearbeiten…")
        act_progress = menu.addAction(tr("btn.fortschritt_hinzufuegen"))
        act_sync = menu.addAction(tr("dlg.sync_mit_tracking"))
        menu.addSeparator()

        # Lifecycle-Aktionen je nach Status
        act_release = act_complete = act_reopen = None
        if goal.is_saving:
            act_release = menu.addAction("🔓 Freigeben…")
        if goal.is_saving or goal.is_released:
            act_complete = menu.addAction("✅ Abschliessen…")
        if goal.is_released or goal.is_completed:
            act_reopen = menu.addAction(tr("btn.wieder_oeffnen_1"))

        menu.addSeparator()
        act_delete = menu.addAction(tr("btn.loeschen_1"))

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == act_edit:
            self.edit_goal()
        elif chosen == act_progress:
            self.add_progress()
        elif chosen == act_sync:
            self.sync_with_tracking()
        elif chosen == act_delete:
            self.delete_goal()
        elif act_release and chosen == act_release:
            self._release_goal()
        elif act_complete and chosen == act_complete:
            self._complete_goal()
        elif act_reopen and chosen == act_reopen:
            self._reopen_goal()

    def _selected_goal(self) -> SavingsGoal | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        goal_id = item.data(Qt.UserRole)
        return self.goals_model.get(goal_id)

    def _update_button_states(self):
        """Aktiviert/deaktiviert Lifecycle-Buttons je nach Status des selektierten Ziels."""
        goal = self._selected_goal()
        has_goal = goal is not None

        self.btn_edit.setEnabled(has_goal)
        self.btn_delete.setEnabled(has_goal)
        self.btn_add_progress.setEnabled(has_goal)
        self.btn_sync.setEnabled(has_goal)

        self.btn_release.setEnabled(has_goal and goal.is_saving)
        self.btn_complete.setEnabled(has_goal and (goal.is_saving or goal.is_released))
        self.btn_reopen.setEnabled(has_goal and (goal.is_released or goal.is_completed))

    def refresh(self):
        goals = self.goals_model.list_all()
        self.table.setRowCount(0)
        
        for goal in goals:
            r = self.table.rowCount()
            self.table.insertRow(r)
            
            # Name
            name_item = QTableWidgetItem(f"{goal.status_icon} {goal.name}")
            name_item.setData(Qt.UserRole, goal.id)
            tooltip_parts = [f"Status: {goal.status_label}"]
            if goal.category:
                tooltip_parts.append(f"Kategorie: {goal.category}")
            if goal.deadline:
                tooltip_parts.append(f"Frist: {goal.deadline}")
            if goal.released_date:
                tooltip_parts.append(f"Freigegeben: {goal.released_date[:10]}")
            if goal.notes:
                tooltip_parts.append(f"Notiz: {goal.notes}")
            name_item.setToolTip("\n".join(tooltip_parts))
            self.table.setItem(r, 0, name_item)
            
            # Ziel
            target_item = QTableWidgetItem(format_money(goal.target_amount))
            target_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 1, target_item)
            
            # Aktuell
            current_item = QTableWidgetItem(format_money(goal.current_amount))
            current_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 2, current_item)
            
            # Fortschritt (Progressbar)
            progress_widget = QProgressBar()
            progress_widget.setRange(0, 100)
            progress_widget.setValue(int(goal.progress_percent))
            progress_widget.setFormat(f"{goal.progress_percent:.1f}%")
            self.table.setCellWidget(r, 3, progress_widget)
            
            # Restbetrag
            remaining_item = QTableWidgetItem(format_money(goal.remaining_amount))
            remaining_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if goal.remaining_amount <= 0:
                c = ui_colors(self); remaining_item.setForeground(QColor(c.ok))
            self.table.setItem(r, 4, remaining_item)
            
            # Status
            status_item = QTableWidgetItem(f"{goal.status_icon} {goal.status_label}")
            status_item.setTextAlignment(Qt.AlignCenter)
            if goal.is_released:
                status_item.setForeground(QColor(ui_colors(self).accent))
            elif goal.is_completed:
                status_item.setForeground(QColor(ui_colors(self).ok))
            self.table.setItem(r, 5, status_item)
            
            # Freigegebener Betrag
            if goal.released_amount > 0:
                rel_item = QTableWidgetItem(format_money(goal.released_amount))
            else:
                rel_item = QTableWidgetItem("-")
            rel_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 6, rel_item)
            
            # Verbraucht (nur bei freigegebenen/abgeschlossenen)
            if goal.is_released or goal.is_completed:
                spent = self.goals_model.get_spent_amount(goal.id)
                if spent > 0:
                    spent_item = QTableWidgetItem(f"-{format_money(spent)}")
                    spent_item.setForeground(QColor(ui_colors(self).negative))
                else:
                    spent_item = QTableWidgetItem(format_money(0))
            else:
                spent_item = QTableWidgetItem("-")
            spent_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 7, spent_item)
            
            # Frist
            deadline_item = QTableWidgetItem(goal.deadline or "-")
            self.table.setItem(r, 8, deadline_item)
            
            # Abgeschlossene Zeilen grau
            if goal.is_completed:
                for col in range(self.table.columnCount()):
                    item = self.table.item(r, col)
                    if item:
                        item.setForeground(QColor(ui_colors(self).text_dim))
        
        self.table.resizeColumnsToContents()
        self._update_button_states()
    
    # ──────────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────────
    def add_goal(self):
        dlg = EditGoalDialog(self, self.conn)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.goals_model.create(
                name=data['name'],
                target_amount=data['target_amount'],
                current_amount=data['current_amount'],
                deadline=data['deadline'],
                category=data['category'],
                notes=data['notes']
            )
            self.refresh()
    
    def edit_goal(self):
        goal = self._selected_goal()
        if not goal:
            QMessageBox.information(self, tr("msg.info"), tr("savings.msg.select_goal"))
            return
        
        dlg = EditGoalDialog(self, self.conn, goal)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.goals_model.update(
                goal_id=goal.id,
                name=data['name'],
                target_amount=data['target_amount'],
                current_amount=data['current_amount'],
                deadline=data['deadline'],
                category=data['category'],
                notes=data['notes']
            )
            self.refresh()
    
    def delete_goal(self):
        goal = self._selected_goal()
        if not goal:
            QMessageBox.information(self, tr("msg.info"), tr("msg.please_select_goal"))
            return
        
        if QMessageBox.question(
            self, tr("common.delete"), 
            f"Sparziel «{goal.name}» wirklich löschen?"
        ) != QMessageBox.Yes:
            return
        
        self.goals_model.delete(goal.id)
        self.refresh()
    
    def add_progress(self):
        goal = self._selected_goal()
        if not goal:
            QMessageBox.information(self, tr("msg.info"), tr("savings.msg.select_goal"))
            return
        
        dlg = AddProgressDialog(self, goal)
        if dlg.exec() == QDialog.Accepted:
            amount = dlg.get_amount()
            self.goals_model.add_progress(goal.id, amount)
            self.refresh()
    
    def sync_with_tracking(self):
        goal = self._selected_goal()
        if not goal:
            QMessageBox.information(self, tr("msg.info"), tr("savings.msg.select_goal"))
            return
        
        if not goal.category:
            QMessageBox.information(
                self, tr("dlg.keine_kategorie"), 
                "Dieses Sparziel ist mit keiner Kategorie verknüpft."
            )
            return
        
        old_amount = goal.current_amount
        new_amount = self.goals_model.sync_with_tracking(goal.id)
        
        QMessageBox.information(
            self, "Synchronisiert",
            f"Sparziel «{goal.name}» wurde mit Tracking synchronisiert.\n\n"
            f"Kategorie: {goal.category}\n"
            f"Vorher: {format_money(old_amount)}\n"
            f"Nachher: {format_money(new_amount)}\n"
            f"Differenz: {format_money(new_amount - old_amount, force_sign=True)}"
        )
        self.refresh()

    # ──────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────
    def _release_goal(self):
        """Sparziel freigeben: Status sparend → freigegeben."""
        goal = self._selected_goal()
        if not goal:
            QMessageBox.information(self, tr("msg.info"), tr("savings.msg.select_goal"))
            return
        if not goal.is_saving:
            QMessageBox.information(self, tr("msg.info"), tr("msg.only_active_goals_releasable"))
            return

        reply = QMessageBox.question(
            self, "Sparziel freigeben",
            f"Sparziel «{goal.name}» freigeben?\n\n"
            f"Aktueller Stand: {format_money(goal.current_amount)}\n"
            f"Ziel: {format_money(goal.target_amount)}\n\n"
            f"Der aktuelle Stand ({format_money(goal.current_amount)}) wird eingefroren.\n"
            f"Ab dann werden negative Buchungen als Verbrauch erfasst.\n\n"
            f"Fortfahren?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        result = self.goals_model.release(goal.id)
        if result:
            QMessageBox.information(
                self, "Freigegeben",
                f"Sparziel «{result.name}» wurde freigegeben.\n\n"
                f"Eingefrorener Betrag: {format_money(result.released_amount)}\n"
                f"Du kannst jetzt Ausgaben gegen dieses Ziel buchen."
            )
        self.refresh()

    def _complete_goal(self):
        """Sparziel abschliessen."""
        goal = self._selected_goal()
        if not goal:
            QMessageBox.information(self, tr("msg.info"), tr("savings.msg.select_goal"))
            return

        extra = ""
        if goal.is_released:
            spent = self.goals_model.get_spent_amount(goal.id)
            extra = f"\nVerbraucht seit Freigabe: {format_money(spent)}\n"

        reply = QMessageBox.question(
            self, "Sparziel abschliessen",
            f"Sparziel «{goal.name}» wirklich abschliessen?\n\nStand: {format_money(goal.current_amount)}\n{extra}"
            f"Das Ziel wird archiviert und kann nicht mehr bebucht werden.\n" +
            tr("btn.wieder_oeffnen_ist_jederzeit"),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.goals_model.complete(goal.id)
        self.refresh()

    def _reopen_goal(self):
        """Sparziel wieder zum Sparen öffnen."""
        goal = self._selected_goal()
        if not goal:
            QMessageBox.information(self, tr("msg.info"), tr("savings.msg.select_goal"))
            return

        reply = QMessageBox.question(
            self, tr("btn.sparziel_wieder_oeffnen"),
            f"Sparziel «{goal.name}» wieder zum Sparen öffnen?\n\n"
            f"Der Freigabe-Status und der eingefrorene Betrag werden zurückgesetzt.\n"
            f"Fortfahren?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.goals_model.reopen(goal.id)
        self.refresh()


class EditGoalDialog(QDialog):
    def __init__(self, parent, conn: sqlite3.Connection, goal: SavingsGoal | None = None):
        super().__init__(parent)
        self.conn = conn
        self.goal = goal
        self.cat_model = CategoryModel(conn)
        
        self.setWindowTitle(tr("dlg.savings_goals"))
        self.setModal(True)
        self.resize(500, 400)
        
        # Felder
        self.name_edit = QLineEdit()
        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(0, 1000000)
        self.target_spin.setDecimals(2)
        self.target_spin.setSuffix(f" {get_symbol()}")
        
        self.current_spin = QDoubleSpinBox()
        self.current_spin.setRange(-1000000, 1000000)
        self.current_spin.setDecimals(2)
        self.current_spin.setSuffix(f" {get_symbol()}")
        
        self.deadline_edit = QDateEdit()
        self.deadline_edit.setCalendarPopup(True)
        self.deadline_edit.setDate(datetime.now().date())
        self.deadline_edit.setSpecialValueText("Kein Datum")
        
        self.category_combo = QComboBox()
        self.category_combo.addItem("(Keine)")
        for typ in [TYP_SAVINGS, TYP_INCOME, TYP_EXPENSES]:
            pairs = []
            if hasattr(self.cat_model, "list_names_tree"):
                try:
                    pairs = self.cat_model.list_names_tree(typ)
                except Exception:
                    pairs = []
            if pairs:
                for label, real in pairs:
                    self.category_combo.addItem(trf("tracking.filter.typ_prefix"), real)
            else:
                for cat in self.cat_model.list_names(typ):
                    self.category_combo.addItem(f"{typ} / {cat}", cat)

        self.notes_edit = QTextEdit()
        
        # Werte setzen
        if goal:
            self.name_edit.setText(goal.name)
            self.target_spin.setValue(goal.target_amount)
            self.current_spin.setValue(goal.current_amount)
            if goal.deadline:
                try:
                    d = datetime.fromisoformat(goal.deadline).date()
                    self.deadline_edit.setDate(d)
                except Exception as e:
                    logger.debug("date parse error: %s", e)
            if goal.category:
                idx = self.category_combo.findData(goal.category)
                if idx >= 0:
                    self.category_combo.setCurrentIndex(idx)
            if goal.notes:
                self.notes_edit.setPlainText(goal.notes)
        
        # Layout
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel(tr("lbl.lbl_goal_name")))
        layout.addWidget(self.name_edit)
        
        layout.addWidget(QLabel(tr("lbl.lbl_target_amount")))
        layout.addWidget(self.target_spin)
        
        layout.addWidget(QLabel(tr("lbl.lbl_current_amount")))
        layout.addWidget(self.current_spin)
        
        layout.addWidget(QLabel(tr("lbl.lbl_deadline")))
        layout.addWidget(self.deadline_edit)
        
        layout.addWidget(QLabel(tr("lbl.category")))
        layout.addWidget(self.category_combo)
        
        sync_hint = QLabel(
            "<i><small>💡 Tipp: Wenn eine Kategorie ausgewählt ist, wird der Fortschritt "
            "automatisch mit Ersparnisse-Buchungen dieser Kategorie synchronisiert.</small></i>"
        )
        sync_hint.setWordWrap(True)
        sync_hint.setStyleSheet(f"color: {ui_colors(self).text_dim}; padding: 5px;")
        layout.addWidget(sync_hint)
        
        layout.addWidget(QLabel(tr("lbl.lbl_notes")))
        layout.addWidget(self.notes_edit)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton(tr("btn.ok"))
        btn_cancel = QPushButton(tr("btn.cancel"))
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
    
    def get_data(self):
        category = self.category_combo.currentData()
        deadline = self.deadline_edit.date().toString("yyyy-MM-dd") if self.deadline_edit.date().isValid() else None
        
        return {
            'name': self.name_edit.text().strip(),
            'target_amount': self.target_spin.value(),
            'current_amount': self.current_spin.value(),
            'deadline': deadline,
            'category': category,
            'notes': self.notes_edit.toPlainText().strip()
        }


class AddProgressDialog(QDialog):
    def __init__(self, parent, goal: SavingsGoal):
        super().__init__(parent)
        self.goal = goal
        
        self.setWindowTitle(trf("btn.fortschritt_hinzufuegen_goalname"))
        self.setModal(True)
        
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(-1000000, 1000000)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSuffix(f" {get_symbol()}")
        self.amount_spin.setValue(0)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"Aktuell: {format_money(goal.current_amount)}"))
        layout.addWidget(QLabel(f"Ziel: {format_money(goal.target_amount)}"))
        layout.addWidget(QLabel(f"Restbetrag: {format_money(goal.remaining_amount)}"))
        if goal.is_released:
            layout.addWidget(QLabel(f"Status: 🔓 Freigegeben (eingef. {format_money(goal.released_amount)})"))
        layout.addSpacing(10)
        layout.addWidget(QLabel(tr("btn.betrag_hinzufuegen")))
        layout.addWidget(self.amount_spin)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton(tr("btn.ok"))
        btn_cancel = QPushButton(tr("btn.cancel"))
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
    
    def get_amount(self):
        return self.amount_spin.value()
