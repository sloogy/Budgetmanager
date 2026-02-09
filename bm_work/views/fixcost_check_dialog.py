"""
Dialog zur Anzeige und Verwaltung fehlender Fixkosten-Buchungen
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QComboBox, QCheckBox, QMessageBox, QProgressBar, QWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from datetime import datetime, date
from typing import List, Dict


class FixcostMissingDialog(QDialog):
    """
    Dialog zur Anzeige fehlender Fixkosten-Buchungen mit Option zum Buchen.
    """
    
    # Signal wenn Buchungen erstellt wurden
    bookings_created = Signal()
    
    def __init__(self, fixcost_model, budget_model, parent=None):
        super().__init__(parent)
        self.fixcost_model = fixcost_model
        self.budget_model = budget_model
        self.missing_fixcosts = []
        self.selected_items = []
        
        self.setWindowTitle("Fehlende Fixkosten-Buchungen")
        self.setMinimumSize(800, 600)
        
        self._setup_ui()
        self._load_current_month()
    
    def _setup_ui(self):
        """Erstellt die Benutzeroberfläche."""
        layout = QVBoxLayout(self)
        
        # Header mit Monatswahl
        header_layout = QHBoxLayout()
        
        header_layout.addWidget(QLabel("Monat:"))
        self.cmb_month = QComboBox()
        self.cmb_month.addItems([
            "Januar", "Februar", "März", "April", "Mai", "Juni",
            "Juli", "August", "September", "Oktober", "November", "Dezember"
        ])
        header_layout.addWidget(self.cmb_month)
        
        header_layout.addWidget(QLabel("Jahr:"))
        self.cmb_year = QComboBox()
        current_year = datetime.now().year
        for year in range(current_year - 2, current_year + 2):
            self.cmb_year.addItem(str(year))
        self.cmb_year.setCurrentText(str(current_year))
        header_layout.addWidget(self.cmb_year)
        
        self.btn_reload = QPushButton("Aktualisieren")
        self.btn_reload.clicked.connect(self._load_month)
        header_layout.addWidget(self.btn_reload)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Status-Übersicht
        self.status_group = self._create_status_widget()
        layout.addWidget(self.status_group)
        
        # Tabelle mit fehlenden Fixkosten
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "✓", "Kategorie", "Typ", "Geschätzter Betrag", 
            "Erwartete Buchungen", "Hinweis"
        ])
        
        # Spaltenbreiten
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.table)
        
        # Buttons unten
        button_layout = QHBoxLayout()
        
        self.cb_select_all = QCheckBox("Alle auswählen")
        self.cb_select_all.stateChanged.connect(self._toggle_select_all)
        button_layout.addWidget(self.cb_select_all)
        
        button_layout.addStretch()
        
        self.btn_create_bookings = QPushButton("Ausgewählte Buchungen erstellen")
        self.btn_create_bookings.clicked.connect(self._create_selected_bookings)
        self.btn_create_bookings.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        button_layout.addWidget(self.btn_create_bookings)
        
        self.btn_close = QPushButton("Schließen")
        self.btn_close.clicked.connect(self.accept)
        button_layout.addWidget(self.btn_close)
        
        layout.addLayout(button_layout)
    
    def _create_status_widget(self) -> QGroupBox:
        """Erstellt das Status-Widget."""
        group = QGroupBox("Übersicht")
        layout = QVBoxLayout(group)
        
        # Labels
        label_layout = QHBoxLayout()
        self.lbl_total = QLabel("Gesamt: 0")
        self.lbl_booked = QLabel("Gebucht: 0")
        self.lbl_missing = QLabel("Fehlend: 0")
        
        label_layout.addWidget(self.lbl_total)
        label_layout.addWidget(QLabel("|"))
        label_layout.addWidget(self.lbl_booked)
        label_layout.addWidget(QLabel("|"))
        label_layout.addWidget(self.lbl_missing)
        label_layout.addStretch()
        
        layout.addLayout(label_layout)
        
        # Fortschrittsbalken
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% abgeschlossen")
        layout.addWidget(self.progress_bar)
        
        return group
    
    def _load_current_month(self):
        """Lädt die Daten für den aktuellen Monat."""
        now = datetime.now()
        self.cmb_month.setCurrentIndex(now.month - 1)
        self.cmb_year.setCurrentText(str(now.year))
        self._load_month()
    
    def _load_month(self):
        """Lädt die Daten für den ausgewählten Monat."""
        month = self.cmb_month.currentIndex() + 1
        year = int(self.cmb_year.currentText())
        
        # Status laden
        status = self.fixcost_model.get_fixcost_status_for_month(year, month)
        
        # Status anzeigen
        self.lbl_total.setText(f"Gesamt: {status['total_fixcosts']}")
        self.lbl_booked.setText(f"Gebucht: {status['booked_count']}")
        self.lbl_missing.setText(f"Fehlend: {status['missing_count']}")
        
        completion = int(status['completion_percentage'])
        self.progress_bar.setValue(completion)
        
        # Farbe des Fortschrittsbalkens anpassen
        if completion >= 100:
            color = "#4CAF50"  # Grün
        elif completion >= 80:
            color = "#FFA500"  # Orange
        else:
            color = "#FF6B6B"  # Rot
        
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {color};
            }}
        """)
        
        # Fehlende Fixkosten laden
        self.missing_fixcosts = status['missing_fixcosts']
        self._populate_table()
        
        # Button aktivieren/deaktivieren
        self.btn_create_bookings.setEnabled(len(self.missing_fixcosts) > 0)
    
    def _populate_table(self):
        """Füllt die Tabelle mit fehlenden Fixkosten."""
        self.table.setRowCount(0)
        
        if not self.missing_fixcosts:
            # Info anzeigen wenn keine fehlen
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            item = QTableWidgetItem("✓ Alle Fixkosten für diesen Monat gebucht!")
            item.setTextAlignment(Qt.AlignCenter)
            item.setForeground(QColor("#4CAF50"))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            
            self.table.setItem(row, 1, item)
            self.table.setSpan(row, 1, 1, 5)
            return
        
        for fixcost in self.missing_fixcosts:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Checkbox
            checkbox = QCheckBox()
            checkbox.setChecked(False)
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, checkbox_widget)
            
            # Kategorie
            item_name = QTableWidgetItem(fixcost['category_name'])
            self.table.setItem(row, 1, item_name)
            
            # Typ
            type_text = "Ausgabe" if fixcost['category_type'] == 'expense' else "Einnahme"
            item_type = QTableWidgetItem(type_text)
            self.table.setItem(row, 2, item_type)
            
            # Geschätzter Betrag
            amount = fixcost['estimated_amount']
            item_amount = QTableWidgetItem(f"{amount:.2f} €")
            item_amount.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 3, item_amount)
            
            # Erwartete Buchungen
            expected = fixcost['expected_bookings']
            item_expected = QTableWidgetItem(str(expected))
            item_expected.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, item_expected)
            
            # Hinweis
            hint = ""
            if amount == 0:
                hint = "⚠ Kein Durchschnittswert verfügbar"
            elif expected > 1:
                hint = f"ℹ Normalerweise {expected}x pro Monat"
            
            item_hint = QTableWidgetItem(hint)
            if amount == 0:
                item_hint.setForeground(QColor("#FFA500"))
            self.table.setItem(row, 5, item_hint)
    
    def _toggle_select_all(self, state):
        """Wählt alle Checkboxen aus oder ab."""
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, 0)
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(state == Qt.Checked)
    
    def _create_selected_bookings(self):
        """Erstellt Buchungen für ausgewählte Fixkosten."""
        selected = []
        
        # Ausgewählte Fixkosten sammeln
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, 0)
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    if row < len(self.missing_fixcosts):
                        selected.append(self.missing_fixcosts[row])
        
        if not selected:
            QMessageBox.information(
                self,
                "Keine Auswahl",
                "Bitte wählen Sie mindestens eine Fixkost aus."
            )
            return
        
        # Bestätigung
        month = self.cmb_month.currentIndex() + 1
        year = int(self.cmb_year.currentText())
        
        msg = f"Möchten Sie {len(selected)} Buchung(en) für {month}/{year} erstellen?\n\n"
        for fixcost in selected:
            amount = fixcost['estimated_amount']
            msg += f"• {fixcost['category_name']}: {amount:.2f} €\n"
        
        reply = QMessageBox.question(
            self,
            "Buchungen erstellen",
            msg,
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._do_create_bookings(selected, year, month)
    
    def _do_create_bookings(self, selected: List[Dict], year: int, month: int):
        """Führt die Erstellung der Buchungen durch."""
        from datetime import date as dt_date
        
        created_count = 0
        
        # Datum: Letzter Tag des Monats oder heute (falls aktueller Monat)
        today = dt_date.today()
        if year == today.year and month == today.month:
            booking_date = today
        else:
            # Letzter Tag des Monats
            if month == 12:
                next_month = dt_date(year + 1, 1, 1)
            else:
                next_month = dt_date(year, month + 1, 1)
            from datetime import timedelta
            booking_date = next_month - timedelta(days=1)
        
        booking_date_str = booking_date.isoformat()
        
        try:
            for fixcost in selected:
                # Buchung erstellen (über budget_model)
                self.budget_model.add_entry(
                    year=year,
                    month=month,
                    category_id=fixcost['category_id'],
                    description=f"Automatisch: {fixcost['category_name']}",
                    amount=fixcost['estimated_amount'],
                    date=booking_date_str,
                    is_fixcost=True
                )
                
                # Als gebucht markieren
                self.fixcost_model.mark_as_booked(
                    category_id=fixcost['category_id'],
                    year=year,
                    month=month,
                    booking_date=booking_date_str,
                    amount=fixcost['estimated_amount']
                )
                
                created_count += 1
            
            QMessageBox.information(
                self,
                "Erfolg",
                f"{created_count} Buchung(en) erfolgreich erstellt!"
            )
            
            # Tabelle aktualisieren
            self._load_month()
            
            # Signal aussenden
            self.bookings_created.emit()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Fehler",
                f"Fehler beim Erstellen der Buchungen:\n{str(e)}"
            )


class FixcostManagementDialog(QDialog):
    """
    Dialog zur Verwaltung von Fixkosten-Kategorien.
    """
    
    def __init__(self, fixcost_model, category_model, parent=None):
        super().__init__(parent)
        self.fixcost_model = fixcost_model
        self.category_model = category_model
        
        self.setWindowTitle("Fixkosten-Verwaltung")
        self.setMinimumSize(700, 500)
        
        self._setup_ui()
        self._load_categories()
    
    def _setup_ui(self):
        """Erstellt die Benutzeroberfläche."""
        layout = QVBoxLayout(self)
        
        # Info-Text
        info = QLabel(
            "Hier können Sie festlegen, welche Kategorien als Fixkosten behandelt werden sollen.\n"
            "Fixkosten werden monatlich auf fehlende Buchungen überprüft."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Tabelle
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Kategorie", "Typ", "Als Fixkost", "Erwartete Buchungen/Monat"
        ])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.btn_auto_detect = QPushButton("Automatisch erkennen")
        self.btn_auto_detect.clicked.connect(self._auto_detect)
        button_layout.addWidget(self.btn_auto_detect)
        
        button_layout.addStretch()
        
        self.btn_save = QPushButton("Speichern")
        self.btn_save.clicked.connect(self._save)
        button_layout.addWidget(self.btn_save)
        
        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(button_layout)
    
    def _load_categories(self):
        """Lädt alle Kategorien."""
        categories = self.category_model.get_all_categories()
        self.table.setRowCount(0)
        
        for cat in categories:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Kategorie-Name
            item_name = QTableWidgetItem(cat['name'])
            item_name.setData(Qt.UserRole, cat['id'])
            self.table.setItem(row, 0, item_name)
            
            # Typ
            type_text = "Ausgabe" if cat['type'] == 'expense' else "Einnahme"
            item_type = QTableWidgetItem(type_text)
            self.table.setItem(row, 1, item_type)
            
            # Checkbox Fixkost
            checkbox = QCheckBox()
            checkbox.setChecked(cat.get('is_fixcost', False))
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 2, checkbox_widget)
            
            # Erwartete Buchungen (nur editierbar wenn Fixkost)
            spinbox = QComboBox()
            spinbox.addItems(["1", "2", "3", "4"])
            expected = cat.get('expected_monthly_bookings', 1)
            spinbox.setCurrentText(str(expected))
            spinbox.setEnabled(checkbox.isChecked())
            
            # Spinbox aktivieren/deaktivieren mit Checkbox
            checkbox.toggled.connect(lambda checked, sb=spinbox: sb.setEnabled(checked))
            
            self.table.setCellWidget(row, 3, spinbox)
    
    def _auto_detect(self):
        """Erkennt automatisch potenzielle Fixkosten."""
        potential_ids = self.fixcost_model.auto_detect_fixcosts(min_months=6)
        
        if not potential_ids:
            QMessageBox.information(
                self,
                "Automatische Erkennung",
                "Keine regelmäßigen Buchungen gefunden."
            )
            return
        
        # Checkboxen setzen
        marked = 0
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                cat_id = item.data(Qt.UserRole)
                if cat_id in potential_ids:
                    widget = self.table.cellWidget(row, 2)
                    if widget:
                        checkbox = widget.findChild(QCheckBox)
                        if checkbox and not checkbox.isChecked():
                            checkbox.setChecked(True)
                            marked += 1
        
        QMessageBox.information(
            self,
            "Automatische Erkennung",
            f"{marked} Kategorie(n) als potenzielle Fixkosten markiert."
        )
    
    def _save(self):
        """Speichert die Einstellungen."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if not item:
                continue
            
            cat_id = item.data(Qt.UserRole)
            
            # Checkbox-Status
            widget = self.table.cellWidget(row, 2)
            is_fixcost = False
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox:
                    is_fixcost = checkbox.isChecked()
            
            # Erwartete Buchungen
            spinbox = self.table.cellWidget(row, 3)
            expected = 1
            if spinbox:
                expected = int(spinbox.currentText())
            
            # Speichern
            self.fixcost_model.set_category_as_fixcost(
                category_id=cat_id,
                is_fixcost=is_fixcost,
                expected_bookings=expected
            )
        
        QMessageBox.information(
            self,
            "Gespeichert",
            "Fixkosten-Einstellungen wurden gespeichert."
        )
        
        self.accept()


if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # Dummy-Modelle für Test
    class DummyFixcostModel:
        def get_fixcost_status_for_month(self, year, month):
            return {
                'year': year,
                'month': month,
                'total_fixcosts': 5,
                'booked_count': 3,
                'missing_count': 2,
                'completion_percentage': 60,
                'missing_fixcosts': [
                    {
                        'category_id': 1,
                        'category_name': 'Miete',
                        'category_type': 'expense',
                        'expected_bookings': 1,
                        'estimated_amount': 850.00,
                        'year': year,
                        'month': month
                    },
                    {
                        'category_id': 2,
                        'category_name': 'Internet',
                        'category_type': 'expense',
                        'expected_bookings': 1,
                        'estimated_amount': 39.99,
                        'year': year,
                        'month': month
                    }
                ]
            }
    
    class DummyBudgetModel:
        def add_entry(self, **kwargs):
            print(f"Buchung erstellt: {kwargs}")
    
    dialog = FixcostMissingDialog(DummyFixcostModel(), DummyBudgetModel())
    dialog.show()
    
    sys.exit(app.exec())
