"""
Erweiterte Fixkosten-Prüfung Dialog
Version 2.3.0.1

Neu:
- Prüft ob Fixkosten bereits im aktuellen Monat gebucht wurden
- Zeigt fehlende Buchungen an
- Ermöglicht direktes Buchen aus Liste
- Optionale Erinnerung beim Start
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QGroupBox, QComboBox,
    QMessageBox, QCheckBox, QHeaderView, QSpinBox, QDateEdit
)
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QFont, QColor

from datetime import datetime, date
from model.fixcost_check_model import FixcostCheckModel
from model.tracking_model import TrackingModel


class FixcostCheckDialog(QDialog):
    """
    Dialog zur Prüfung und Verwaltung von Fixkosten-Buchungen.
    Zeigt fehlende Buchungen an und ermöglicht direktes Buchen.
    """
    
    # Signal wenn Buchungen erstellt wurden
    bookings_created = Signal()
    
    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.fixcost_model = FixcostCheckModel(db_path)
        self.tracking_model = TrackingModel(db_path)
        
        self.setWindowTitle("Fixkosten-Prüfung")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        
        self._init_ui()
        self._load_missing_fixcosts()
    
    def _init_ui(self):
        """Initialisiert die Benutzeroberfläche."""
        layout = QVBoxLayout(self)
        
        # Titel
        title = QLabel("💰 Fixkosten-Prüfung")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Zeitraum-Auswahl
        period_group = QGroupBox("Prüfzeitraum")
        period_layout = QHBoxLayout()
        
        period_layout.addWidget(QLabel("Jahr:"))
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2100)
        self.year_spin.setValue(datetime.now().year)
        self.year_spin.valueChanged.connect(self._load_missing_fixcosts)
        period_layout.addWidget(self.year_spin)
        
        period_layout.addWidget(QLabel("Monat:"))
        self.month_combo = QComboBox()
        months = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
                 "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
        self.month_combo.addItems(months)
        self.month_combo.setCurrentIndex(datetime.now().month - 1)
        self.month_combo.currentIndexChanged.connect(self._load_missing_fixcosts)
        period_layout.addWidget(self.month_combo)
        
        refresh_btn = QPushButton("🔄 Aktualisieren")
        refresh_btn.clicked.connect(self._load_missing_fixcosts)
        period_layout.addWidget(refresh_btn)
        
        period_layout.addStretch()
        period_group.setLayout(period_layout)
        layout.addWidget(period_group)
        
        # Status-Übersicht
        self.status_label = QLabel()
        self.status_label.setStyleSheet("""
            QLabel {
                padding: 10px;
                border-radius: 5px;
                background-color: #ecf0f1;
            }
        """)
        layout.addWidget(self.status_label)
        
        # Tabelle mit fehlenden Fixkosten
        table_group = QGroupBox("Fehlende Fixkosten")
        table_layout = QVBoxLayout()
        
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Auswahl", "Kategorie", "Typ", "Geschätzter Betrag",
            "Letztes Jahr", "Durchschnitt", "Buchungsdatum"
        ])
        
        # Spaltenbreiten
        self.table.setColumnWidth(0, 80)   # Auswahl
        self.table.setColumnWidth(1, 200)  # Kategorie
        self.table.setColumnWidth(2, 100)  # Typ
        self.table.setColumnWidth(3, 120)  # Geschätzt
        self.table.setColumnWidth(4, 100)  # Letztes Jahr
        self.table.setColumnWidth(5, 100)  # Durchschnitt
        self.table.setColumnWidth(6, 150)  # Datum
        
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        table_layout.addWidget(self.table)
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)
        
        # Optionen
        options_layout = QHBoxLayout()
        
        self.chk_auto_date = QCheckBox("Buchungsdatum automatisch setzen (heute)")
        self.chk_auto_date.setChecked(True)
        options_layout.addWidget(self.chk_auto_date)
        
        options_layout.addStretch()
        
        select_all_btn = QPushButton("Alle auswählen")
        select_all_btn.clicked.connect(self._select_all)
        options_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Alle abwählen")
        deselect_all_btn.clicked.connect(self._deselect_all)
        options_layout.addWidget(deselect_all_btn)
        
        layout.addLayout(options_layout)
        
        # Action-Buttons
        button_layout = QHBoxLayout()
        
        book_btn = QPushButton("✅ Ausgewählte buchen")
        book_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        book_btn.clicked.connect(self._book_selected)
        button_layout.addWidget(book_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _load_missing_fixcosts(self):
        """Lädt und zeigt fehlende Fixkosten."""
        year = self.year_spin.value()
        month = self.month_combo.currentIndex() + 1
        
        # Status holen
        status = self.fixcost_model.get_fixcost_status_for_month(year, month)
        
        # Status-Label aktualisieren
        total = status['total_fixcosts']
        booked = status['booked_count']
        missing = status['missing_count']
        percent = status['completion_percentage']
        
        if missing == 0:
            status_color = "#27ae60"  # Grün
            status_icon = "✅"
            status_text = f"{status_icon} Alle Fixkosten gebucht!"
        elif percent >= 50:
            status_color = "#f39c12"  # Orange
            status_icon = "⚠️"
            status_text = f"{status_icon} {booked}/{total} Fixkosten gebucht ({percent:.0f}%)"
        else:
            status_color = "#e74c3c"  # Rot
            status_icon = "❌"
            status_text = f"{status_icon} {missing} Fixkosten fehlen noch!"
        
        self.status_label.setText(
            f"<b style='font-size: 12pt; color: {status_color};'>{status_text}</b>"
        )
        
        # Tabelle füllen
        self.table.setRowCount(0)
        missing_list = status['missing_fixcosts']
        
        for item in missing_list:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Checkbox
            chk = QCheckBox()
            chk.setChecked(True)
            cell = QWidget()
            layout = QHBoxLayout(cell)
            layout.addWidget(chk)
            layout.setAlignment(Qt.AlignCenter)
            layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, cell)
            
            # Kategorie
            self.table.setItem(row, 1, QTableWidgetItem(item['category_name']))
            
            # Typ
            typ_item = QTableWidgetItem(item['category_type'])
            typ_color = self._get_type_color(item['category_type'])
            typ_item.setForeground(QColor(typ_color))
            self.table.setItem(row, 2, typ_item)
            
            # Geschätzter Betrag
            estimated = item['estimated_amount']
            est_item = QTableWidgetItem(f"{estimated:.2f} CHF")
            est_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 3, est_item)
            
            # Letztes Jahr - gleicher Monat
            last_year_amount = self._get_last_year_amount(
                item['category_id'], year - 1, month
            )
            last_item = QTableWidgetItem(
                f"{last_year_amount:.2f} CHF" if last_year_amount else "-"
            )
            last_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 4, last_item)
            
            # Durchschnitt (letzte 12 Monate)
            avg = self._get_average_amount(item['category_id'], 12)
            avg_item = QTableWidgetItem(f"{avg:.2f} CHF" if avg else "-")
            avg_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 5, avg_item)
            
            # Buchungsdatum
            date_edit = QDateEdit()
            date_edit.setDate(QDate.currentDate())
            date_edit.setCalendarPopup(True)
            self.table.setCellWidget(row, 6, date_edit)
            
            # User-Data speichern
            self.table.item(row, 1).setData(Qt.UserRole, item)
    
    def _get_type_color(self, typ: str) -> str:
        """Gibt Farbe für Typ zurück."""
        colors = {
            "Einkommen": "#27ae60",
            "Ausgaben": "#e74c3c",
            "Ersparnisse": "#3498db"
        }
        return colors.get(typ, "#95a5a6")
    
    def _get_last_year_amount(self, category_id: int, year: int, month: int) -> float:
        """Gibt Betrag vom gleichen Monat letztes Jahr zurück."""
        try:
            start_date = date(year, month, 1)
            # Letzter Tag des Monats
            if month == 12:
                end_date = date(year, 12, 31)
            else:
                end_date = date(year, month + 1, 1)
            
            entries = self.tracking_model.get_entries_in_range(start_date, end_date)
            total = sum(
                abs(e.amount) for e in entries 
                if e.category_id == category_id
            )
            return total
        except:
            return 0.0
    
    def _get_average_amount(self, category_id: int, months: int) -> float:
        """Berechnet Durchschnitt der letzten N Monate."""
        try:
            history = self.fixcost_model.get_booking_history(category_id, months)
            if not history:
                return 0.0
            amounts = [h['total_amount'] for h in history]
            return sum(amounts) / len(amounts) if amounts else 0.0
        except:
            return 0.0
    
    def _select_all(self):
        """Wählt alle Checkboxen aus."""
        for row in range(self.table.rowCount()):
            cell = self.table.cellWidget(row, 0)
            chk = cell.findChild(QCheckBox)
            if chk:
                chk.setChecked(True)
    
    def _deselect_all(self):
        """Wählt alle Checkboxen ab."""
        for row in range(self.table.rowCount()):
            cell = self.table.cellWidget(row, 0)
            chk = cell.findChild(QCheckBox)
            if chk:
                chk.setChecked(False)
    
    def _book_selected(self):
        """Bucht ausgewählte Fixkosten."""
        selected_items = []
        
        for row in range(self.table.rowCount()):
            # Checkbox prüfen
            cell = self.table.cellWidget(row, 0)
            chk = cell.findChild(QCheckBox)
            
            if chk and chk.isChecked():
                item_data = self.table.item(row, 1).data(Qt.UserRole)
                date_edit = self.table.cellWidget(row, 6)
                booking_date = date_edit.date().toPython()
                
                selected_items.append((item_data, booking_date))
        
        if not selected_items:
            QMessageBox.warning(
                self,
                "Keine Auswahl",
                "Bitte wählen Sie mindestens eine Fixkost zum Buchen aus."
            )
            return
        
        # Bestätigung
        reply = QMessageBox.question(
            self,
            "Buchungen erstellen",
            f"Möchten Sie {len(selected_items)} Fixkosten buchen?\n\n"
            "Die Beträge werden automatisch aus der Schätzung übernommen.\n"
            "Sie können diese später noch anpassen.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            success_count = 0
            error_count = 0
            
            for item_data, booking_date in selected_items:
                try:
                    # Tracking-Eintrag erstellen
                    self.tracking_model.add_entry(
                        date=booking_date,
                        typ=item_data['category_type'],
                        category=item_data['category_name'],
                        amount=item_data['estimated_amount'],
                        description=f"Fixkost - {item_data['category_name']}"
                    )
                    
                    # Als gebucht markieren
                    self.fixcost_model.mark_as_booked(
                        category_id=item_data['category_id'],
                        year=item_data['year'],
                        month=item_data['month'],
                        booking_date=booking_date.isoformat(),
                        amount=item_data['estimated_amount']
                    )
                    
                    success_count += 1
                except Exception as e:
                    print(f"Fehler beim Buchen: {e}")
                    error_count += 1
            
            # Ergebnis anzeigen
            if error_count == 0:
                QMessageBox.information(
                    self,
                    "Erfolgreich",
                    f"✅ {success_count} Fixkosten wurden erfolgreich gebucht!"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Teilweise erfolgreich",
                    f"✅ {success_count} erfolgreich gebucht\n"
                    f"❌ {error_count} Fehler"
                )
            
            # Signal senden und neu laden
            self.bookings_created.emit()
            self._load_missing_fixcosts()


if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    dialog = FixcostCheckDialog('budgetmanager.db')
    dialog.show()
    sys.exit(app.exec())
