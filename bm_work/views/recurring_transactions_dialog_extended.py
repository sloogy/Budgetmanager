from __future__ import annotations
from datetime import date, datetime
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QSpinBox,
    QDateEdit, QCheckBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QAbstractItemView, QGroupBox
)

from model.recurring_transactions_model import RecurringTransactionsModel, RecurringTransaction
from model.tracking_model import TrackingModel


class RecurringTransactionsDialog(QDialog):
    """Dialog zur Verwaltung wiederkehrender Transaktionen mit Soll-Buchungsdatum"""
    
    def __init__(self, parent, model: RecurringTransactionsModel, categories: dict, preferred_day: int = 1):
        super().__init__(parent)
        self.model = model
        self.categories = categories
        try:
            d = int(preferred_day or 1)
        except Exception:
            d = 1
        if d < 1: d = 1
        if d > 31: d = 31
        self.preferred_day = d
        
        self.setWindowTitle("Wiederkehrende Transaktionen verwalten")
        self.setModal(True)
        self.resize(1000, 600)
        
        self._setup_ui()
        self._load_transactions()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Info-Label
        info_label = QLabel(
            "Hier verwaltest du wiederkehrende Transaktionen (z. B. Abos, Lohn, Sparrate). "
            "Über \"Fällige Buchungen prüfen\" kannst du fällige Positionen anzeigen und mit einem Klick ins Tracking übernehmen."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background-color: #e3f2fd; border-radius: 5px;")
        layout.addWidget(info_label)
        
        # Tabelle
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "ID", "Aktiv", "Typ", "Kategorie", "Betrag (CHF)", 
            "Tag", "Startdatum", "Enddatum", "Details"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.hideColumn(0)  # ID-Spalte ausblenden
        layout.addWidget(self.table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_add = QPushButton("➕ Neu")
        self.btn_edit = QPushButton("✏️ Bearbeiten")
        self.btn_delete = QPushButton("🗑️ Löschen")
        self.btn_toggle = QPushButton("⏸️ Aktivieren/Deaktivieren")
        self.btn_check_pending = QPushButton("🔍 Fällige Buchungen prüfen")
        self.btn_close = QPushButton("Schließen")
        
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_toggle)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_check_pending)
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)
        
        # Signals
        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_toggle.clicked.connect(self._on_toggle)
        self.btn_check_pending.clicked.connect(self._on_check_pending)
        self.btn_close.clicked.connect(self.accept)
        
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self._on_edit)
    
    def _load_transactions(self):
        """Lädt alle wiederkehrenden Transaktionen"""
        self.table.setRowCount(0)
        transactions = self.model.get_all_recurring_transactions()
        
        for trans in transactions:
            self._add_table_row(trans)
        
        self.table.resizeColumnsToContents()
        self._on_selection_changed()
    
    def _add_table_row(self, trans: RecurringTransaction):
        """Fügt eine Zeile zur Tabelle hinzu"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # ID (hidden)
        self.table.setItem(row, 0, QTableWidgetItem(str(trans.id)))
        
        # Aktiv Status
        active_item = QTableWidgetItem("✓" if trans.is_active else "✗")
        active_item.setTextAlignment(Qt.AlignCenter)
        if not trans.is_active:
            active_item.setForeground(Qt.gray)
        self.table.setItem(row, 1, active_item)
        
        # Typ
        self.table.setItem(row, 2, QTableWidgetItem(trans.typ))
        
        # Kategorie
        self.table.setItem(row, 3, QTableWidgetItem(trans.category))
        
        # Betrag
        amount_item = QTableWidgetItem(f"{trans.amount:,.2f}".replace(",", "'"))
        amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 4, amount_item)
        
        # Tag des Monats
        day_item = QTableWidgetItem(f"{trans.day_of_month}.")
        day_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 5, day_item)
        
        # Startdatum
        self.table.setItem(row, 6, QTableWidgetItem(trans.start_date.strftime("%d.%m.%Y")))
        
        # Enddatum
        end_str = trans.end_date.strftime("%d.%m.%Y") if trans.end_date else "Unbegrenzt"
        self.table.setItem(row, 7, QTableWidgetItem(end_str))
        
        # Details
        self.table.setItem(row, 8, QTableWidgetItem(trans.details or ""))
        
        # Gesamte Zeile grau wenn inaktiv
        if not trans.is_active:
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    item.setForeground(Qt.gray)
    
    def _on_selection_changed(self):
        """Aktiviert/Deaktiviert Buttons basierend auf Selektion"""
        has_selection = bool(self.table.selectedItems())
        self.btn_edit.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)
        self.btn_toggle.setEnabled(has_selection)
    
    def _get_selected_transaction_id(self) -> Optional[int]:
        """Gibt die ID der selektierten Transaktion zurück"""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        
        row = selected_rows[0].row()
        id_item = self.table.item(row, 0)
        return int(id_item.text()) if id_item else None
    
    def _on_add(self):
        """Öffnet Dialog zum Hinzufügen"""
        dialog = RecurringTransactionEditDialog(self, None, self.categories, preferred_day=self.preferred_day)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            self.model.create_recurring_transaction(**data)
            self._load_transactions()
    
    def _on_edit(self):
        """Öffnet Dialog zum Bearbeiten"""
        trans_id = self._get_selected_transaction_id()
        if not trans_id:
            return
        
        # Lade Transaktion
        transactions = self.model.get_all_recurring_transactions()
        transaction = next((t for t in transactions if t.id == trans_id), None)
        
        if not transaction:
            return
        
        dialog = RecurringTransactionEditDialog(self, transaction, self.categories, preferred_day=self.preferred_day)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            self.model.update_recurring_transaction(trans_id, **data)
            self._load_transactions()
    
    def _on_delete(self):
        """Löscht die selektierte Transaktion"""
        trans_id = self._get_selected_transaction_id()
        if not trans_id:
            return
        
        reply = QMessageBox.question(
            self,
            "Löschen bestätigen",
            "Möchten Sie diese wiederkehrende Transaktion wirklich löschen?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.model.delete_recurring_transaction(trans_id)
            self._load_transactions()
    
    def _on_toggle(self):
        """Aktiviert/Deaktiviert die selektierte Transaktion"""
        trans_id = self._get_selected_transaction_id()
        if not trans_id:
            return
        
        self.model.toggle_active(trans_id)
        self._load_transactions()
    
    def _on_check_pending(self):
        """Prüft und zeigt fällige Buchungen an"""
        today = date.today()
        pending = self.model.get_pending_bookings(today)
        
        if not pending:
            QMessageBox.information(
                self,
                "Keine fälligen Buchungen",
                "Aktuell gibt es keine fälligen wiederkehrenden Buchungen."
            )
            return
        
        # Zeige Dialog mit fälligen Buchungen
        tracking_model = TrackingModel(self.model.conn)
        dialog = PendingBookingsDialog(self, pending, self.model, tracking_model)
        dialog.exec()
        self._load_transactions()


class RecurringTransactionEditDialog(QDialog):
    """Dialog zum Erstellen/Bearbeiten einer wiederkehrenden Transaktion"""
    
    def __init__(self, parent, transaction: Optional[RecurringTransaction], categories: dict, preferred_day: int = 1):
        super().__init__(parent)
        self.transaction = transaction
        self.categories = categories
        try:
            d = int(preferred_day or 1)
        except Exception:
            d = 1
        if d < 1: d = 1
        if d > 31: d = 31
        self.preferred_day = d
        
        is_edit = transaction is not None
        self.setWindowTitle("Wiederkehrende Transaktion bearbeiten" if is_edit else "Neue wiederkehrende Transaktion")
        self.setModal(True)
        
        self._setup_ui()
        
        if transaction:
            self._load_transaction_data()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Formular
        form = QFormLayout()
        
        # Typ
        self.typ_combo = QComboBox()
        # Wichtig: muss zu den Typen im restlichen Tool passen
        self.typ_combo.addItems(["Ausgaben", "Einkommen", "Ersparnisse"])
        form.addRow("Typ:", self.typ_combo)
        
        # Kategorie
        self.category_combo = QComboBox()
        form.addRow("Kategorie:", self.category_combo)
        
        # Betrag
        self.amount_spin = QLineEdit()
        self.amount_spin.setPlaceholderText("0.00")
        form.addRow("Betrag (CHF):", self.amount_spin)
        
        # Tag des Monats
        self.day_spin = QSpinBox()
        self.day_spin.setRange(1, 31)
        self.day_spin.setSuffix(". des Monats")
        # Standard nur bei "Neu" – bei Edit wird später geladen
        if self.transaction is None:
            self.day_spin.setValue(self.preferred_day)
        form.addRow("Buchungstag:", self.day_spin)
        
        # Details
        self.details_edit = QLineEdit()
        self.details_edit.setPlaceholderText("Optional: Bemerkung")
        form.addRow("Details:", self.details_edit)
        
        # Startdatum
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(date.today())
        form.addRow("Startdatum:", self.start_date)
        
        # Enddatum (optional)
        end_layout = QHBoxLayout()
        self.has_end_date = QCheckBox("Enddatum festlegen")
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(date.today())
        self.end_date.setEnabled(False)
        end_layout.addWidget(self.has_end_date)
        end_layout.addWidget(self.end_date)
        form.addRow("", end_layout)
        
        # Aktiv Status
        self.is_active = QCheckBox("Aktiv")
        self.is_active.setChecked(True)
        form.addRow("Status:", self.is_active)
        
        layout.addLayout(form)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Speichern")
        self.btn_cancel = QPushButton("Abbrechen")
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
        # Signals
        self.typ_combo.currentTextChanged.connect(self._on_typ_changed)
        self.has_end_date.toggled.connect(self.end_date.setEnabled)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_cancel.clicked.connect(self.reject)
        
        # Initial Kategorien laden
        self._on_typ_changed(self.typ_combo.currentText())
    
    def _on_typ_changed(self, typ: str):
        """Aktualisiert Kategorien basierend auf Typ"""
        self.category_combo.clear()
        if typ in self.categories:
            self.category_combo.addItems(sorted(self.categories[typ]))
    
    def _load_transaction_data(self):
        """Lädt Daten einer existierenden Transaktion"""
        if not self.transaction:
            return
        
        self.typ_combo.setCurrentText(self.transaction.typ)
        self.category_combo.setCurrentText(self.transaction.category)
        self.amount_spin.setText(str(self.transaction.amount))
        self.day_spin.setValue(self.transaction.day_of_month)
        self.details_edit.setText(self.transaction.details or "")
        self.start_date.setDate(self.transaction.start_date)
        
        if self.transaction.end_date:
            self.has_end_date.setChecked(True)
            self.end_date.setDate(self.transaction.end_date)
        
        self.is_active.setChecked(self.transaction.is_active)
    
    def _on_save(self):
        """Validiert und speichert die Daten"""
        # Validierung
        try:
            amount = float(self.amount_spin.text().replace("'", "").replace(",", "."))
            if amount <= 0:
                raise ValueError("Betrag muss größer als 0 sein")
        except ValueError as e:
            QMessageBox.warning(self, "Ungültige Eingabe", f"Bitte einen gültigen Betrag eingeben:\n{e}")
            return
        
        if not self.category_combo.currentText():
            QMessageBox.warning(self, "Ungültige Eingabe", "Bitte eine Kategorie auswählen")
            return
        
        self.accept()
    
    def get_data(self) -> dict:
        """Gibt die eingegebenen Daten zurück"""
        amount = float(self.amount_spin.text().replace("'", "").replace(",", "."))
        
        data = {
            'typ': self.typ_combo.currentText(),
            'category': self.category_combo.currentText(),
            'amount': amount,
            'details': self.details_edit.text(),
            'day_of_month': self.day_spin.value(),
            'start_date': self.start_date.date().toPython(),
            'end_date': self.end_date.date().toPython() if self.has_end_date.isChecked() else None,
            'is_active': self.is_active.isChecked()
        }
        
        return data


class PendingBookingsDialog(QDialog):
    """Dialog zur Anzeige und Buchung fälliger Transaktionen"""
    
    def __init__(self, parent, pending: list, model: RecurringTransactionsModel, tracking_model: TrackingModel):
        super().__init__(parent)
        self.pending = pending
        self.model = model
        self.tracking_model = tracking_model
        
        self.setWindowTitle("Fällige wiederkehrende Buchungen")
        self.setModal(True)
        self.resize(800, 400)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        info = QLabel(f"Es gibt {len(self.pending)} fällige wiederkehrende Buchung(en):")
        info.setStyleSheet("font-weight: bold; padding: 10px;")
        layout.addWidget(info)
        
        # Tabelle
        table = QTableWidget(len(self.pending), 6)
        table.setHorizontalHeaderLabels([
            "Soll-Datum", "Typ", "Kategorie", "Betrag (CHF)", "Details", "Buchen"
        ])
        table.horizontalHeader().setStretchLastSection(True)
        
        for row, (trans, booking_date) in enumerate(self.pending):
            table.setItem(row, 0, QTableWidgetItem(booking_date.strftime("%d.%m.%Y")))
            table.setItem(row, 1, QTableWidgetItem(trans.typ))
            table.setItem(row, 2, QTableWidgetItem(trans.category))
            
            amount_item = QTableWidgetItem(f"{trans.amount:,.2f}".replace(",", "'"))
            amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(row, 3, amount_item)
            
            table.setItem(row, 4, QTableWidgetItem(trans.details or ""))
            
            # Checkbox
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked)
            table.setItem(row, 5, chk)
        
        table.resizeColumnsToContents()
        layout.addWidget(table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_book = QPushButton("Ausgewählte buchen")
        btn_close = QPushButton("Schließen")
        btn_layout.addStretch()
        btn_layout.addWidget(btn_book)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
        
        btn_book.clicked.connect(lambda: self._book_selected(table))
        btn_close.clicked.connect(self.reject)
    
    def _book_selected(self, table: QTableWidget):
        """Bucht die ausgewählten Transaktionen"""
        # Buchungslogik: Einträge ins Tracking schreiben und Marker setzen,
        # damit Duplikate zuverlässig erkannt werden.
        booked_count = 0
        for row in range(table.rowCount()):
            chk = table.item(row, 5)
            if chk and chk.checkState() == Qt.Checked:
                trans, booking_date = self.pending[row]

                marker = f"Wiederkehrend (ID: {trans.id})"
                base = (trans.details or "").strip()
                details = base
                if marker not in details:
                    details = f"{base} | {marker}" if base else marker

                # Betrag wird als positiver Wert gespeichert (Saldo-Berechnung erfolgt über Typ)
                self.tracking_model.add(booking_date, trans.typ, trans.category, float(trans.amount), details)

                # Zusätzlich last_booking_date aktualisieren (für UI/Statistik)
                self.model.update_last_booking_date(trans.id, booking_date)
                booked_count += 1
        
        QMessageBox.information(
            self,
            "Buchung erfolgreich",
            f"{booked_count} Transaktion(en) wurden erfolgreich gebucht."
        )
        
        self.accept()
