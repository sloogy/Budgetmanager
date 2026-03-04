from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

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
from views.ui_colors import ui_colors
from utils.i18n import tr, trf, tr_msg, display_typ, db_typ_from_display


class DatabaseManagementDialog(QDialog):
    """Dialog für Datenbank-Verwaltung."""
    
    def __init__(self, db_path: str, parent=None, conn=None):
        super().__init__(parent)
        self.db_path = db_path
        self.model = DatabaseManagementModel(db_path, conn=conn)
        self.data_changed = False  # Wird True nach Reset/Bereinigung → main_window refresht Tabs

        self.setWindowTitle(tr("dlg.db_management"))
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
        stats_group = QGroupBox(tr("grp.db_stats"))
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
        cleanup_group = QGroupBox(tr("grp.db_cleanup"))
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
        reset_group = QGroupBox(tr("dlg.datenbank_zuruecksetzen_1"))
        reset_layout = QVBoxLayout()
        
        reset_warning = QLabel(
            "<b>ACHTUNG:</b> Diese Aktion löscht Daten!\n"
            "Es wird automatisch ein Backup erstellt."
        )
        _c = ui_colors(self)
        reset_warning.setStyleSheet(f"color: {_c.negative};")
        reset_warning.setWordWrap(True)
        reset_layout.addWidget(reset_warning)
        
        # Reset-Optionen
        self.radio_group = QButtonGroup()
        
        self.radio_full = QRadioButton(tr("radio.full_reset"))
        self.radio_full.setChecked(True)
        self.radio_group.addButton(self.radio_full)
        reset_layout.addWidget(self.radio_full)
        
        self.radio_partial = QRadioButton(
            "Budget & Kategorien zurücksetzen (Buchungen behalten)"
        )
        self.radio_group.addButton(self.radio_partial)
        reset_layout.addWidget(self.radio_partial)
        
        self.chk_backup = QCheckBox(tr("chk.backup_before_reset"))
        self.chk_backup.setChecked(True)
        reset_layout.addWidget(self.chk_backup)
        
        reset_btn = QPushButton(tr("dlg.datenbank_zuruecksetzen_2"))
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_c.negative};
                color: white;
                padding: 8px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        reset_btn.clicked.connect(self._reset_database)
        reset_layout.addWidget(reset_btn)
        
        reset_group.setLayout(reset_layout)
        layout.addWidget(reset_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton(tr("btn.close"))
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _load_statistics(self):
        """Lädt und zeigt Datenbank-Statistiken."""
        stats = self.model.get_database_statistics()
        
        text = tr("dbmgmt.stats_header")
        
        for key, value in stats.items():
            text += f"<b>{key}:</b> {value}<br>"
        
        self.stats_text.setHtml(text)
    
    def _cleanup_database(self):
        """Führt Datenbank-Bereinigung durch."""
        reply = QMessageBox.question(
            self,
            tr("msg.confirm_cleanup"),
            trf("dbmgmt.cleanup_confirm_body", extra=tr("btn.die_datenbank_wird_anschliessend")),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            progress = QProgressDialog(
                tr("dbmgmt.cleanup_progress"), None, 0, 0, self
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
                    tr("msg.cleanup_success"),
                    f"{message}\n\nDetails:\n{details}"
                )
                self._load_statistics()
            else:
                QMessageBox.critical(
                    self,
                    tr("msg.error"),
                    tr_msg(message)
                )
    
    def _reset_database(self):
        """Führt Datenbank-Reset durch."""
        keep_tracking = self.radio_partial.isChecked()
        create_backup = self.chk_backup.isChecked()
        
        reset_type = tr("dbmgmt.reset_type_partial") if keep_tracking else tr("dbmgmt.reset_type_full")

        backup_line = tr("dbmgmt.reset_line_backup_yes") if create_backup else tr("dbmgmt.reset_line_backup_no")
        tracking_line = tr("dbmgmt.reset_line_keep_tracking") if keep_tracking else tr("dbmgmt.reset_line_delete_tracking")
        
        reply = QMessageBox.warning(
            self,
            tr("dlg.datenbank_zuruecksetzen_1"),
            trf(
                "dbmgmt.reset_warning_body",
                reset_type=reset_type,
                backup_line=backup_line,
                tracking_line=tracking_line,
                extra=tr("dlg.brbdiese_aktion_kann_nicht"),
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Zweite Bestätigung für kompletten Reset
        if not keep_tracking:
            reply2 = QMessageBox.warning(
                self,
                tr("dbmgmt.last_warning_title"),
                tr("dbmgmt.last_warning_body"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply2 != QMessageBox.Yes:
                return
        
        progress = QProgressDialog(
            tr("dlg.setze_datenbank_zurueck"), None, 0, 0, self
        )
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        success, message = self.model.reset_database(
            create_backup=create_backup,
            keep_user_data=keep_tracking
        )
        
        progress.close()
        
        if success:
            self.data_changed = True

            # Bei vollem Reset: users.json + Settings löschen
            if not keep_tracking:
                extra_errors = []
                try:
                    from model.user_model import _users_file_path
                    users_file = _users_file_path()
                    if users_file.exists():
                        users_file.unlink()
                        logger.info("users.json gelöscht (Full-Reset)")
                except Exception as e:
                    extra_errors.append(f"users.json: {e}")
                try:
                    from model.app_paths import settings_path
                    sf = settings_path()
                    if sf.exists():
                        sf.unlink()
                        logger.info("Settings-Datei gelöscht (Full-Reset)")
                except Exception as e:
                    extra_errors.append(f"settings: {e}")
                if extra_errors:
                    logger.warning("Full-Reset Zusatz-Fehler: %s", extra_errors)

            QMessageBox.information(
                self,
                tr("database.reset_success_title"),
                trf("dbmgmt.reset_success_body", message=tr_msg(message))
            )
            self._load_statistics()
        else:
            QMessageBox.critical(
                self,
                tr("msg.error"),
                trf("dbmgmt.reset_failed_body", message=tr_msg(message))
            )


if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    dialog = DatabaseManagementDialog('budgetmanager.db')
    dialog.show()
    sys.exit(app.exec())
