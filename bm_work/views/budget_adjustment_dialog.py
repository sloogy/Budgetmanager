from __future__ import annotations
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QAbstractItemView, QGroupBox,
    QTextEdit
)
from PySide6.QtGui import QColor

from model.budget_warnings_model_extended import BudgetWarningsModelExtended, BudgetExceedance


class BudgetAdjustmentDialog(QDialog):
    """
    Dialog zur Anzeige von Budget-Überschreitungen mit Anpassungsvorschlägen
    
    Zeigt:
    - Kategorien mit häufigen Überschreitungen
    - Historische Daten (wie oft überschritten)
    - Intelligente Budget-Vorschläge
    - Option zur direkten Anpassung
    """
    
    def __init__(self, parent, warnings_model: BudgetWarningsModelExtended, 
                 budget_model, year: int, month: int):
        super().__init__(parent)
        self.warnings_model = warnings_model
        self.budget_model = budget_model
        self.year = year
        self.month = month
        
        self.setWindowTitle("Budget-Anpassungsvorschläge")
        self.setModal(True)
        self.resize(1000, 700)
        
        self._setup_ui()
        self._load_exceedances()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Titel und Info
        title = QLabel(f"Budget-Überschreitungen für {self.month:02d}/{self.year}")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)
        
        info = QLabel(
            "⚠️ Die folgenden Kategorien haben ihr Budget überschritten. "
            "Basierend auf historischen Daten werden Anpassungen vorgeschlagen."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            "padding: 10px; background-color: #fff3cd; border-left: 4px solid #ffc107; "
            "border-radius: 4px; color: #856404;"
        )
        layout.addWidget(info)
        
        # Tabelle für Überschreitungen
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Typ",
            "Kategorie", 
            "Budget",
            "Ausgegeben",
            "Differenz",
            "Überschritten (%)",
            "Häufigkeit (6M)",
            "Vorschlag",
            "Anpassen"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(7, 120)
        layout.addWidget(self.table)
        
        # Statistik-Bereich
        stats_group = QGroupBox("Empfehlungen")
        stats_layout = QVBoxLayout(stats_group)
        
        self.recommendation_text = QTextEdit()
        self.recommendation_text.setReadOnly(True)
        self.recommendation_text.setMaximumHeight(150)
        stats_layout.addWidget(self.recommendation_text)
        
        layout.addWidget(stats_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_select_all = QPushButton("Alle auswählen")
        self.btn_deselect_all = QPushButton("Alle abwählen")
        self.btn_apply = QPushButton("✓ Ausgewählte anwenden")
        self.btn_apply.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; padding: 8px 16px; "
            "font-weight: bold; } QPushButton:hover { background-color: #218838; }"
        )
        self.btn_close = QPushButton("Schließen")
        
        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addWidget(self.btn_deselect_all)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)
        
        # Signals
        self.btn_select_all.clicked.connect(lambda: self._toggle_all(True))
        self.btn_deselect_all.clicked.connect(lambda: self._toggle_all(False))
        self.btn_apply.clicked.connect(self._on_apply_adjustments)
        self.btn_close.clicked.connect(self.reject)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
    
    def _load_exceedances(self):
        """Lädt alle Budget-Überschreitungen mit erweiterten Infos"""
        self.table.setRowCount(0)
        
        # Hole Überschreitungen
        exceedances = self.warnings_model.check_warnings_extended(
            self.year, self.month, lookback_months=6
        )
        
        if not exceedances:
            self.recommendation_text.setHtml(
                "<p style='color: green; font-weight: bold;'>✓ Keine Budget-Überschreitungen! "
                "Alle Budgets werden eingehalten.</p>"
            )
            return
        
        # Sortiere nach Überschreitungshäufigkeit (häufigste zuerst)
        exceedances.sort(key=lambda x: x.exceed_count, reverse=True)
        
        total_adjustment = 0
        chronic_categories = []
        
        for exc in exceedances:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Typ
            self.table.setItem(row, 0, QTableWidgetItem(exc.typ))
            
            # Kategorie
            cat_item = QTableWidgetItem(exc.category)
            if exc.exceed_count >= 3:
                cat_item.setBackground(QColor("#ffebee"))  # Rot für chronische Überschreiter
                chronic_categories.append(exc.category)
            self.table.setItem(row, 1, cat_item)
            
            # Budget
            budget_item = QTableWidgetItem(f"{exc.budget:,.2f}".replace(",", "'"))
            budget_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, budget_item)
            
            # Ausgegeben
            spent_item = QTableWidgetItem(f"{exc.spent:,.2f}".replace(",", "'"))
            spent_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            spent_item.setForeground(QColor("#d32f2f"))
            self.table.setItem(row, 3, spent_item)
            
            # Differenz
            diff = exc.spent - exc.budget
            diff_item = QTableWidgetItem(f"+{diff:,.2f}".replace(",", "'"))
            diff_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            diff_item.setForeground(QColor("#d32f2f"))
            diff_item.setBackground(QColor("#ffebee"))
            self.table.setItem(row, 4, diff_item)
            
            # Überschritten (%)
            percent_item = QTableWidgetItem(f"{exc.percent_used:.1f}%")
            percent_item.setTextAlignment(Qt.AlignCenter)
            if exc.percent_used >= 150:
                percent_item.setBackground(QColor("#ffcdd2"))
            elif exc.percent_used >= 120:
                percent_item.setBackground(QColor("#ffebee"))
            self.table.setItem(row, 5, percent_item)
            
            # Häufigkeit
            freq_text = f"{exc.exceed_count}/6"
            freq_item = QTableWidgetItem(freq_text)
            freq_item.setTextAlignment(Qt.AlignCenter)
            if exc.exceed_count >= 4:
                freq_item.setBackground(QColor("#ffcdd2"))
                freq_item.setForeground(QColor("#b71c1c"))
            elif exc.exceed_count >= 2:
                freq_item.setBackground(QColor("#ffebee"))
            self.table.setItem(row, 6, freq_item)
            
            # Vorschlag
            suggestion = exc.suggestion or exc.spent * 1.1
            sugg_item = QTableWidgetItem(f"{suggestion:,.2f}".replace(",", "'"))
            sugg_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            sugg_item.setBackground(QColor("#e8f5e9"))
            sugg_item.setForeground(QColor("#2e7d32"))
            self.table.setItem(row, 7, sugg_item)
            
            # Checkbox zum Anwenden
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            # Automatisch auswählen wenn oft überschritten
            chk.setCheckState(Qt.Checked if exc.exceed_count >= 3 else Qt.Unchecked)
            self.table.setItem(row, 8, chk)
            
            if exc.exceed_count >= 3:
                total_adjustment += (suggestion - exc.budget)
        
        self.table.resizeColumnsToContents()
        
        # Generiere Empfehlungtext
        self._generate_recommendations(exceedances, chronic_categories, total_adjustment)
    
    def _generate_recommendations(self, exceedances: list, chronic_categories: list, 
                                  total_adjustment: float):
        """Generiert Empfehlungstext basierend auf den Daten"""
        html = "<div style='font-family: Arial; font-size: 12px;'>"
        
        # Überschrift
        html += f"<h3 style='color: #d32f2f; margin-top: 0;'>⚠️ {len(exceedances)} Kategorie(n) überschritten</h3>"
        
        # Chronische Überschreiter
        if chronic_categories:
            html += f"<p><strong>Chronische Überschreiter (≥3 Monate):</strong> "
            html += ", ".join(chronic_categories)
            html += "<br/>💡 <em>Diese Kategorien sollten definitiv angepasst werden.</em></p>"
        
        # Gesamtanpassung
        if total_adjustment > 0:
            html += f"<p><strong>Empfohlene Gesamt-Budget-Erhöhung:</strong> "
            html += f"<span style='color: #2e7d32; font-weight: bold;'>"
            html += f"+{total_adjustment:,.2f} CHF".replace(",", "'")
            html += "</span></p>"
        
        # Allgemeine Tipps
        html += "<hr/><p><strong>Allgemeine Empfehlungen:</strong></p><ul>"
        
        avg_exceed_count = sum(e.exceed_count for e in exceedances) / len(exceedances)
        
        if avg_exceed_count >= 3:
            html += "<li>🔴 <strong>Kritisch:</strong> Mehrere Kategorien werden regelmäßig überschritten. "
            html += "Eine systematische Budget-Überprüfung ist dringend empfohlen.</li>"
        elif avg_exceed_count >= 2:
            html += "<li>🟠 <strong>Achtung:</strong> Budgets sollten angepasst werden, um realistischere Ziele zu setzen.</li>"
        else:
            html += "<li>🟡 <strong>Hinweis:</strong> Gelegentliche Überschreitungen sind normal. "
            html += "Prüfen Sie, ob strukturelle Änderungen nötig sind.</li>"
        
        # Spezifische Tipps basierend auf Kategorien
        max_exceedance = max(exceedances, key=lambda x: x.percent_used)
        if max_exceedance.percent_used >= 150:
            html += f"<li>💰 Die Kategorie <strong>{max_exceedance.category}</strong> wurde um "
            html += f"{max_exceedance.percent_used:.0f}% überschritten. "
            html += "Überprüfen Sie, ob hier unerwartete Ausgaben aufgetreten sind.</li>"
        
        html += "</ul>"
        html += "</div>"
        
        self.recommendation_text.setHtml(html)
    
    def _toggle_all(self, checked: bool):
        """Wählt alle/keine Checkboxen aus"""
        state = Qt.Checked if checked else Qt.Unchecked
        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 8)
            if chk:
                chk.setCheckState(state)
    
    def _on_selection_changed(self):
        """Reagiert auf Selektion in der Tabelle"""
        pass
    
    def _on_apply_adjustments(self):
        """Wendet die ausgewählten Budget-Anpassungen an"""
        # Zähle ausgewählte Einträge
        selected_rows = []
        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 8)
            if chk and chk.checkState() == Qt.Checked:
                selected_rows.append(row)
        
        if not selected_rows:
            QMessageBox.information(
                self,
                "Keine Auswahl",
                "Bitte wählen Sie mindestens ein Budget zur Anpassung aus."
            )
            return
        
        # Frage: Nur diesen Monat oder restliche Monate?
        remaining_months_count = 12 - self.month + 1
        
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Anpassung anwenden")
        msg.setText(
            f"Für welchen Zeitraum soll die Anpassung gelten?\n\n"
            f"• Nur {self.month:02d}/{self.year}: Anpassung gilt nur für diesen Monat\n"
            f"• Restliche Monate: Anpassung gilt für {self.month:02d}–12/{self.year} "
            f"({remaining_months_count} Monate)"
        )
        
        btn_this_month = msg.addButton(
            f"Nur {self.month:02d}/{self.year}", QMessageBox.AcceptRole
        )
        btn_remaining = msg.addButton(
            f"Restliche Monate ({remaining_months_count})", QMessageBox.AcceptRole
        )
        btn_cancel = msg.addButton("Abbrechen", QMessageBox.RejectRole)
        
        msg.setDefaultButton(btn_this_month)
        msg.exec()
        
        clicked = msg.clickedButton()
        if clicked == btn_cancel:
            return
        
        apply_remaining = (clicked == btn_remaining)
        
        applied_count = 0
        total_increase = 0
        total_months_affected = 0
        
        for row in selected_rows:
            typ = self.table.item(row, 0).text()
            category = self.table.item(row, 1).text()
            new_budget_str = self.table.item(row, 7).text().replace("'", "")
            new_budget = float(new_budget_str)
            
            old_budget_str = self.table.item(row, 2).text().replace("'", "")
            old_budget = float(old_budget_str)
            
            # Budget anwenden
            months_affected = self.warnings_model.apply_budget_suggestion(
                typ, category, self.year, self.month, new_budget,
                remaining_months=apply_remaining
            )
            
            applied_count += 1
            total_increase += (new_budget - old_budget)
            total_months_affected += months_affected
        
        if applied_count > 0:
            scope_text = (
                f"für {self.month:02d}–12/{self.year} ({total_months_affected} Monatswerte)"
                if apply_remaining
                else f"für {self.month:02d}/{self.year}"
            )
            QMessageBox.information(
                self,
                "Budgets angepasst",
                f"✓ {applied_count} Budget(s) wurden erfolgreich angepasst {scope_text}.\n\n"
                f"Erhöhung pro Monat: +{total_increase:,.2f} CHF".replace(",", "'") + "\n\n"
                f"Die neuen Budgets sind sofort wirksam."
            )
            self.accept()
    
    @staticmethod
    def check_and_show_if_needed(parent, warnings_model: BudgetWarningsModelExtended,
                                  budget_model, year: int, month: int,
                                  auto_show_threshold: int = 2) -> bool:
        """
        Prüft ob Budget-Anpassungen nötig sind und zeigt Dialog ggf. automatisch
        
        Args:
            auto_show_threshold: Ab wie vielen Überschreitungen Dialog automatisch zeigen
            
        Returns:
            True wenn Dialog gezeigt wurde
        """
        exceedances = warnings_model.check_warnings_extended(year, month)
        
        # Zähle chronische Überschreiter (≥ threshold)
        chronic_count = sum(1 for exc in exceedances if exc.exceed_count >= auto_show_threshold)
        
        if chronic_count > 0:
            dialog = BudgetAdjustmentDialog(parent, warnings_model, budget_model, year, month)
            dialog.exec()
            return True
        
        return False
