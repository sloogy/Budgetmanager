from __future__ import annotations
import sqlite3
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QDoubleSpinBox, QTextEdit, QDateEdit,
    QComboBox, QMessageBox, QProgressBar, QAbstractItemView
)

from model.savings_goals_model import SavingsGoalsModel, SavingsGoal
from model.category_model import CategoryModel


class SavingsGoalsDialog(QDialog):
    def __init__(self, parent, conn: sqlite3.Connection):
        super().__init__(parent)
        self.conn = conn
        self.goals_model = SavingsGoalsModel(conn)
        self.cat_model = CategoryModel(conn)
        
        self.setWindowTitle("Sparziele")
        self.setModal(True)
        self.resize(900, 600)
        
        # Buttons
        self.btn_add = QPushButton("Neues Ziel")
        self.btn_edit = QPushButton("Bearbeiten")
        self.btn_delete = QPushButton("Löschen")
        self.btn_add_progress = QPushButton("Fortschritt hinzufügen")
        self.btn_sync = QPushButton("Mit Tracking synchronisieren")
        self.btn_close = QPushButton("Schließen")
        
        # Tabelle
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Name", "Ziel (CHF)", "Aktuell (CHF)", "Fortschritt", 
            "Restbetrag", "Frist", "Kategorie"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        # Layout
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_add_progress)
        btn_layout.addWidget(self.btn_sync)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Sparziele verwalten"))
        layout.addWidget(self.table)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        # Connections
        self.btn_add.clicked.connect(self.add_goal)
        self.btn_edit.clicked.connect(self.edit_goal)
        self.btn_delete.clicked.connect(self.delete_goal)
        self.btn_add_progress.clicked.connect(self.add_progress)
        self.btn_sync.clicked.connect(self.sync_with_tracking)
        self.btn_close.clicked.connect(self.accept)
        
        self.refresh()
    
    def refresh(self):
        goals = self.goals_model.list_all()
        self.table.setRowCount(0)
        
        for goal in goals:
            r = self.table.rowCount()
            self.table.insertRow(r)
            
            # Name
            name_item = QTableWidgetItem(goal.name)
            name_item.setData(Qt.UserRole, goal.id)
            self.table.setItem(r, 0, name_item)
            
            # Ziel
            target_item = QTableWidgetItem(f"{goal.target_amount:.2f}")
            target_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 1, target_item)
            
            # Aktuell
            current_item = QTableWidgetItem(f"{goal.current_amount:.2f}")
            current_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 2, current_item)
            
            # Fortschritt (Progressbar)
            progress_widget = QProgressBar()
            progress_widget.setRange(0, 100)
            progress_widget.setValue(int(goal.progress_percent))
            progress_widget.setFormat(f"{goal.progress_percent:.1f}%")
            self.table.setCellWidget(r, 3, progress_widget)
            
            # Restbetrag
            remaining_item = QTableWidgetItem(f"{goal.remaining_amount:.2f}")
            remaining_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 4, remaining_item)
            
            # Frist
            deadline_item = QTableWidgetItem(goal.deadline or "-")
            self.table.setItem(r, 5, deadline_item)
            
            # Kategorie
            category_item = QTableWidgetItem(goal.category or "-")
            self.table.setItem(r, 6, category_item)
        
        self.table.resizeColumnsToContents()
    
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
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Hinweis", "Bitte ein Ziel auswählen.")
            return
        
        goal_id = self.table.item(row, 0).data(Qt.UserRole)
        goal = self.goals_model.get(goal_id)
        if not goal:
            return
        
        dlg = EditGoalDialog(self, self.conn, goal)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.goals_model.update(
                goal_id=goal_id,
                name=data['name'],
                target_amount=data['target_amount'],
                current_amount=data['current_amount'],
                deadline=data['deadline'],
                category=data['category'],
                notes=data['notes']
            )
            self.refresh()
    
    def delete_goal(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Hinweis", "Bitte ein Ziel auswählen.")
            return
        
        goal_id = self.table.item(row, 0).data(Qt.UserRole)
        name = self.table.item(row, 0).text()
        
        if QMessageBox.question(
            self, "Löschen", 
            f"Sparziel '{name}' wirklich löschen?"
        ) != QMessageBox.Yes:
            return
        
        self.goals_model.delete(goal_id)
        self.refresh()
    
    def add_progress(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Hinweis", "Bitte ein Ziel auswählen.")
            return
        
        goal_id = self.table.item(row, 0).data(Qt.UserRole)
        goal = self.goals_model.get(goal_id)
        if not goal:
            return
        
        dlg = AddProgressDialog(self, goal)
        if dlg.exec() == QDialog.Accepted:
            amount = dlg.get_amount()
            self.goals_model.add_progress(goal_id, amount)
            self.refresh()
    
    def sync_with_tracking(self):
        """Synchronisiert ausgewähltes Sparziel mit Tracking-Buchungen"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Hinweis", "Bitte ein Ziel auswählen.")
            return
        
        goal_id = self.table.item(row, 0).data(Qt.UserRole)
        goal = self.goals_model.get(goal_id)
        if not goal:
            return
        
        if not goal.category:
            QMessageBox.information(
                self, 
                "Keine Kategorie", 
                "Dieses Sparziel ist mit keiner Kategorie verknüpft.\n\n"
                "Um die automatische Synchronisation zu nutzen, bearbeiten Sie "
                "das Ziel und wählen Sie eine Kategorie aus."
            )
            return
        
        old_amount = goal.current_amount
        new_amount = self.goals_model.sync_with_tracking(goal_id)
        
        QMessageBox.information(
            self,
            "Synchronisiert",
            f"Sparziel '{goal.name}' wurde mit Tracking synchronisiert.\n\n"
            f"Kategorie: {goal.category}\n"
            f"Vorher: {old_amount:.2f} CHF\n"
            f"Nachher: {new_amount:.2f} CHF\n"
            f"Differenz: {new_amount - old_amount:+.2f} CHF\n\n"
            f"Der neue Betrag basiert auf allen 'Ersparnisse'-Buchungen\n"
            f"in der Kategorie '{goal.category}'."
        )
        
        self.refresh()


class EditGoalDialog(QDialog):
    def __init__(self, parent, conn: sqlite3.Connection, goal: SavingsGoal | None = None):
        super().__init__(parent)
        self.conn = conn
        self.goal = goal
        self.cat_model = CategoryModel(conn)
        
        self.setWindowTitle("Sparziel bearbeiten" if goal else "Neues Sparziel")
        self.setModal(True)
        self.resize(500, 400)
        
        # Felder
        self.name_edit = QLineEdit()
        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(0, 1000000)
        self.target_spin.setDecimals(2)
        self.target_spin.setSuffix(" CHF")
        
        self.current_spin = QDoubleSpinBox()
        self.current_spin.setRange(0, 1000000)
        self.current_spin.setDecimals(2)
        self.current_spin.setSuffix(" CHF")
        
        self.deadline_edit = QDateEdit()
        self.deadline_edit.setCalendarPopup(True)
        self.deadline_edit.setDate(datetime.now().date())
        self.deadline_edit.setSpecialValueText("Kein Datum")
        
        self.category_combo = QComboBox()
        self.category_combo.addItem("(Keine)")
        for typ in ["Ersparnisse", "Einkommen", "Ausgaben"]:
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
                    date = datetime.fromisoformat(goal.deadline).date()
                    self.deadline_edit.setDate(date)
                except:
                    pass
            if goal.category:
                idx = self.category_combo.findData(goal.category)
                if idx >= 0:
                    self.category_combo.setCurrentIndex(idx)
            if goal.notes:
                self.notes_edit.setPlainText(goal.notes)
        
        # Layout
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Name:"))
        layout.addWidget(self.name_edit)
        
        layout.addWidget(QLabel("Zielbetrag:"))
        layout.addWidget(self.target_spin)
        
        layout.addWidget(QLabel("Aktueller Betrag:"))
        layout.addWidget(self.current_spin)
        
        layout.addWidget(QLabel("Frist:"))
        layout.addWidget(self.deadline_edit)
        
        layout.addWidget(QLabel("Kategorie:"))
        layout.addWidget(self.category_combo)
        
        # Hinweis zur automatischen Synchronisation
        sync_hint = QLabel(
            "<i><small>💡 Tipp: Wenn eine Kategorie ausgewählt ist, wird der Fortschritt "
            "automatisch mit 'Ersparnisse'-Buchungen dieser Kategorie synchronisiert.</small></i>"
        )
        sync_hint.setWordWrap(True)
        sync_hint.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(sync_hint)
        
        layout.addWidget(QLabel("Notizen:"))
        layout.addWidget(self.notes_edit)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Abbrechen")
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
        
        self.setWindowTitle(f"Fortschritt hinzufügen: {goal.name}")
        self.setModal(True)
        
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(-1000000, 1000000)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSuffix(" CHF")
        self.amount_spin.setValue(0)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"Aktuell: {goal.current_amount:.2f} CHF"))
        layout.addWidget(QLabel(f"Ziel: {goal.target_amount:.2f} CHF"))
        layout.addWidget(QLabel(f"Restbetrag: {goal.remaining_amount:.2f} CHF"))
        layout.addSpacing(10)
        layout.addWidget(QLabel("Betrag hinzufügen:"))
        layout.addWidget(self.amount_spin)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Abbrechen")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
    
    def get_amount(self):
        return self.amount_spin.value()
