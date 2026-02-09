"""
Database Management Dialog - Neu
Version 2.3.0.1

Features:
- Datenbank-Reset (komplett oder nur Budget/Kategorien)
- Datenbank-Bereinigung
- Statistiken anzeigen
- Backup vor Reset
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QTextEdit, QCheckBox, QMessageBox, QProgressDialog,
    QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from model.database_management_model import DatabaseManagementModel


class DatabaseManagementDialog(QDialog):
    """Dialog für Datenbank-Verwaltung."""
    
    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.model = DatabaseManagementModel(db_path)
        
        self.setWindowTitle("Datenbank-Verwaltung")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        self._init_ui()
        self._load_statistics()
    
    def _init_ui(self):
        """Initialisiert die Benutzeroberfläche."""
        layout = QVBoxLayout(self)
        
        # Titel
        title = QLabel("🗄️ Datenbank-Verwaltung")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Statistiken
        stats_group = QGroupBox("Datenbank-Statistiken")
        stats_layout = QVBoxLayout()
        
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(150)
        stats_layout.addWidget(self.stats_text)
        
        refresh_btn = QPushButton("🔄 Aktualisieren")
        refresh_btn.clicked.connect(self._load_statistics)
        stats_layout.addWidget(refresh_btn)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Bereinigung
        cleanup_group = QGroupBox("Datenbank-Bereinigung")
        cleanup_layout = QVBoxLayout()
        
        cleanup_info = QLabel(
            "Entfernt verwaiste Einträge, ungültige Daten und optimiert die Datenbank.\n"
            "Diese Operation ist sicher und löscht keine wichtigen Daten."
        )
        cleanup_info.setWordWrap(True)
        cleanup_layout.addWidget(cleanup_info)
        
        cleanup_btn = QPushButton("🧹 Datenbank bereinigen")
        cleanup_btn.clicked.connect(self._cleanup_database)
        cleanup_layout.addWidget(cleanup_btn)
        
        cleanup_group.setLayout(cleanup_layout)
        layout.addWidget(cleanup_group)
        
        # Reset
        reset_group = QGroupBox("⚠️ Datenbank zurücksetzen")
        reset_layout = QVBoxLayout()
        
        reset_warning = QLabel(
            "<b>ACHTUNG:</b> Diese Aktion löscht Daten!\n"
            "Es wird automatisch ein Backup erstellt."
        )
        reset_warning.setStyleSheet("color: #e74c3c;")
        reset_warning.setWordWrap(True)
        reset_layout.addWidget(reset_warning)
        
        # Reset-Optionen
        self.radio_group = QButtonGroup()
        
        self.radio_full = QRadioButton("Kompletter Reset (alle Daten löschen)")
        self.radio_full.setChecked(True)
        self.radio_group.addButton(self.radio_full)
        reset_layout.addWidget(self.radio_full)
        
        self.radio_partial = QRadioButton(
            "Budget & Kategorien zurücksetzen (Buchungen behalten)"
        )
        self.radio_group.addButton(self.radio_partial)
        reset_layout.addWidget(self.radio_partial)
        
        self.chk_backup = QCheckBox("Backup vor Reset erstellen (empfohlen)")
        self.chk_backup.setChecked(True)
        reset_layout.addWidget(self.chk_backup)
        
        reset_btn = QPushButton("🔄 Datenbank zurücksetzen")
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        reset_btn.clicked.connect(self._reset_database)
        reset_layout.addWidget(reset_btn)
        
        reset_group.setLayout(reset_layout)
        layout.addWidget(reset_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _load_statistics(self):
        """Lädt und zeigt Datenbank-Statistiken."""
        stats = self.model.get_database_statistics()
        
        text = "📊 <b>Aktuelle Statistiken:</b><br><br>"
        
        for key, value in stats.items():
            text += f"<b>{key}:</b> {value}<br>"
        
        self.stats_text.setHtml(text)
    
    def _cleanup_database(self):
        """Führt Datenbank-Bereinigung durch."""
        reply = QMessageBox.question(
            self,
            "Bereinigung bestätigen",
            "Möchten Sie die Datenbank bereinigen?\n\n"
            "Dies entfernt:\n"
            "• Verwaiste Budget-Einträge\n"
            "• Fehlerhafte System-Kategorien (BUDGET-SALDO)\n"
            "• Ungültige Tags\n"
            "• Einträge mit ungültigen Daten\n\n"
            "Die Datenbank wird anschließend optimiert.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            progress = QProgressDialog(
                "Bereinige Datenbank...", None, 0, 0, self
            )
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            success, message, stats = self.model.cleanup_database()
            
            progress.close()
            
            if success:
                details = "\n".join([
                    f"• {key.replace('deleted_', '').replace('_', ' ').title()}: {value}"
                    for key, value in stats.items() if value > 0
                ])
                
                QMessageBox.information(
                    self,
                    "Bereinigung erfolgreich",
                    f"{message}\n\nDetails:\n{details}"
                )
                self._load_statistics()
            else:
                QMessageBox.critical(
                    self,
                    "Fehler",
                    message
                )
    
    def _reset_database(self):
        """Führt Datenbank-Reset durch."""
        keep_tracking = self.radio_partial.isChecked()
        create_backup = self.chk_backup.isChecked()
        
        reset_type = "Budget und Kategorien" if keep_tracking else "alle Daten"
        
        reply = QMessageBox.warning(
            self,
            "⚠️ Datenbank zurücksetzen",
            f"<b>ACHTUNG: Diese Aktion löscht {reset_type}!</b><br><br>"
            f"Möchten Sie wirklich fortfahren?<br><br>"
            f"{'✅ Ein Backup wird erstellt<br>' if create_backup else '❌ KEIN Backup wird erstellt<br>'}"
            f"{'✅ Buchungen bleiben erhalten<br>' if keep_tracking else '❌ Alle Buchungen werden gelöscht<br>'}"
            "<br><b>Diese Aktion kann nicht rückgängig gemacht werden!</b>",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Zweite Bestätigung für kompletten Reset
        if not keep_tracking:
            reply2 = QMessageBox.warning(
                self,
                "Letzte Warnung",
                "Sie sind dabei, <b>ALLE DATEN</b> zu löschen!\n\n"
                "Sind Sie ABSOLUT SICHER?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply2 != QMessageBox.Yes:
                return
        
        progress = QProgressDialog(
            "Setze Datenbank zurück...", None, 0, 0, self
        )
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        success, message = self.model.reset_database(
            create_backup=create_backup,
            keep_user_data=keep_tracking
        )
        
        progress.close()
        
        if success:
            QMessageBox.information(
                self,
                "Reset erfolgreich",
                f"{message}\n\n"
                "Die Datenbank wurde zurückgesetzt.\n"
                "Standard-Kategorien wurden erstellt.\n\n"
                "Bitte starten Sie die Anwendung neu."
            )
            self._load_statistics()
        else:
            QMessageBox.critical(
                self,
                "Fehler",
                f"Fehler beim Reset:\n{message}"
            )


if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    dialog = DatabaseManagementDialog('budgetmanager.db')
    dialog.show()
    sys.exit(app.exec())
