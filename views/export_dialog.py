from __future__ import annotations
import sqlite3
import csv
from datetime import date, datetime
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QGroupBox, QPushButton, QFileDialog,
    QDialogButtonBox, QMessageBox, QSpinBox, QRadioButton,
    QButtonGroup, QProgressBar
)
from PySide6.QtCore import Qt

from model.budget_model import BudgetModel
from model.tracking_model import TrackingModel


class ExportDialog(QDialog):
    """Export-Dialog für Daten (CSV, PDF)"""
    
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.budget = BudgetModel(conn)
        self.tracking = TrackingModel(conn)
        
        self.setWindowTitle("📤 Daten exportieren")
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        
        # === FORMAT ===
        format_group = QGroupBox("Export-Format")
        format_layout = QVBoxLayout()
        
        self.format_group = QButtonGroup(self)
        self.radio_csv = QRadioButton("📊 CSV (Excel-kompatibel)")
        self.radio_csv.setChecked(True)
        self.format_group.addButton(self.radio_csv, 0)
        format_layout.addWidget(self.radio_csv)
        
        self.radio_txt = QRadioButton("📝 Text (Tabulator-getrennt)")
        self.format_group.addButton(self.radio_txt, 1)
        format_layout.addWidget(self.radio_txt)
        
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)
        
        # === DATENAUSWAHL ===
        data_group = QGroupBox("Zu exportierende Daten")
        data_layout = QVBoxLayout()
        
        self.chk_tracking = QCheckBox("📊 Tracking-Daten (Transaktionen)")
        self.chk_tracking.setChecked(True)
        data_layout.addWidget(self.chk_tracking)
        
        self.chk_budget = QCheckBox("💰 Budget-Daten")
        self.chk_budget.setChecked(True)
        data_layout.addWidget(self.chk_budget)
        
        self.chk_categories = QCheckBox("📁 Kategorien")
        data_layout.addWidget(self.chk_categories)
        
        data_group.setLayout(data_layout)
        layout.addWidget(data_group)
        
        # === ZEITRAUM ===
        period_group = QGroupBox("Zeitraum")
        period_layout = QVBoxLayout()
        
        year_row = QHBoxLayout()
        year_row.addWidget(QLabel("Jahr:"))
        self.year_combo = QComboBox()
        self.year_combo.addItem("Alle Jahre")
        years = sorted(set(self.budget.years()) | set(self.tracking.years()))
        for y in years:
            self.year_combo.addItem(str(y))
        # Aktuelles Jahr vorauswählen
        current_year = str(date.today().year)
        idx = self.year_combo.findText(current_year)
        if idx >= 0:
            self.year_combo.setCurrentIndex(idx)
        year_row.addWidget(self.year_combo, 1)
        period_layout.addLayout(year_row)
        
        period_group.setLayout(period_layout)
        layout.addWidget(period_group)
        
        # === OPTIONEN ===
        options_group = QGroupBox("Optionen")
        options_layout = QVBoxLayout()
        
        self.chk_include_header = QCheckBox("Spaltenüberschriften einfügen")
        self.chk_include_header.setChecked(True)
        options_layout.addWidget(self.chk_include_header)
        
        self.chk_utf8_bom = QCheckBox("UTF-8 BOM (für Excel)")
        self.chk_utf8_bom.setChecked(True)
        options_layout.addWidget(self.chk_utf8_bom)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # === BUTTONS ===
        btn_layout = QHBoxLayout()
        
        self.btn_export = QPushButton("📤 Exportieren...")
        self.btn_export.clicked.connect(self._do_export)
        btn_layout.addWidget(self.btn_export)
        
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def _do_export(self):
        """Führt den Export durch"""
        if not (self.chk_tracking.isChecked() or self.chk_budget.isChecked() or self.chk_categories.isChecked()):
            QMessageBox.warning(self, "Fehler", "Bitte mindestens einen Datentyp auswählen.")
            return
        
        # Dateiname vorschlagen
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        year_text = self.year_combo.currentText().replace(" ", "_")
        default_name = f"budgetmanager_export_{year_text}_{timestamp}"
        
        # Format bestimmen
        if self.radio_csv.isChecked():
            ext = "csv"
            filter_str = "CSV-Dateien (*.csv)"
        else:
            ext = "txt"
            filter_str = "Text-Dateien (*.txt)"
        
        # Speicherort wählen
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export speichern unter",
            f"{default_name}.{ext}",
            filter_str
        )
        
        if not file_path:
            return
        
        try:
            self._export_to_file(file_path)
            QMessageBox.information(
                self, 
                "Export erfolgreich", 
                f"Daten wurden erfolgreich exportiert:\n{file_path}"
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Export-Fehler", f"Fehler beim Export:\n{str(e)}")
    
    def _export_to_file(self, file_path: str):
        """Exportiert die Daten in eine Datei"""
        delimiter = ',' if self.radio_csv.isChecked() else '\t'
        year_filter = None
        if self.year_combo.currentText() != "Alle Jahre":
            year_filter = int(self.year_combo.currentText())
        
        # Encoding
        encoding = 'utf-8-sig' if self.chk_utf8_bom.isChecked() else 'utf-8'
        
        with open(file_path, 'w', newline='', encoding=encoding) as f:
            writer = csv.writer(f, delimiter=delimiter)
            
            # === TRACKING ===
            if self.chk_tracking.isChecked():
                if self.chk_include_header.isChecked():
                    writer.writerow(["=== TRACKING-DATEN ==="])
                    writer.writerow(["Datum", "Typ", "Kategorie", "Betrag", "Details"])
                
                rows = self.tracking.list_filtered(
                    year=year_filter if year_filter else None
                )
                for r in rows:
                    writer.writerow([
                        r.d.strftime("%d.%m.%Y"),
                        r.typ,
                        r.category,
                        f"{r.amount:.2f}",
                        r.details
                    ])
                writer.writerow([])  # Leerzeile
            
            # === BUDGET ===
            if self.chk_budget.isChecked():
                if self.chk_include_header.isChecked():
                    writer.writerow(["=== BUDGET-DATEN ==="])
                    writer.writerow(["Jahr", "Monat", "Typ", "Kategorie", "Betrag"])
                
                years = [year_filter] if year_filter else self.budget.years()
                for year in years:
                    for typ in ["Ausgaben", "Einkommen", "Ersparnisse"]:
                        matrix = self.budget.get_matrix(year, typ)
                        for cat, months in matrix.items():
                            for month, amount in months.items():
                                if abs(float(amount)) > 0.01:
                                    writer.writerow([
                                        year,
                                        month,
                                        typ,
                                        cat,
                                        f"{amount:.2f}"
                                    ])
                writer.writerow([])
            
            # === KATEGORIEN ===
            if self.chk_categories.isChecked():
                if self.chk_include_header.isChecked():
                    writer.writerow(["=== KATEGORIEN ==="])
                    writer.writerow(["Typ", "Name", "Fixkosten", "Wiederkehrend"])
                
                from model.category_model import CategoryModel
                cats = CategoryModel(self.conn)
                for typ in ["Ausgaben", "Einkommen", "Ersparnisse"]:
                    for c in cats.list(typ):
                        writer.writerow([
                            typ,
                            c.name,
                            "Ja" if c.is_fix else "Nein",
                            "Ja" if c.is_recurring else "Nein"
                        ])
