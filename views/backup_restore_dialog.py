from __future__ import annotations
import sqlite3
import shutil
import os
from datetime import datetime
from pathlib import Path
from model.app_paths import resolve_in_app

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QMessageBox, QListWidget, QListWidgetItem
)


class BackupRestoreDialog(QDialog):
    def __init__(self, parent, conn: sqlite3.Connection, db_path: str, settings=None):
        super().__init__(parent)
        self.conn = conn
        self.db_path = db_path
        self.settings = settings

        # Wird auf True gesetzt, wenn die aktive DB ersetzt / zurückgesetzt wurde.
        # MainWindow kann dann (optional) einen Neustart verlangen.
        self.db_changed = False
        
        # Backup-Ordner aus Einstellungen oder Standard
        if settings and hasattr(settings, 'backup_directory'):
            self.backup_dir = resolve_in_app(settings.backup_directory)
        else:
            self.backup_dir = Path.home() / "BudgetManager_Backups"
        
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.setWindowTitle("Backup & Wiederherstellung")
        self.setModal(True)
        self.resize(600, 400)
        
        # UI Elemente
        self.btn_create_backup = QPushButton("Backup erstellen")
        self.btn_restore = QPushButton("Backup wiederherstellen")
        self.btn_export = QPushButton("Backup exportieren...")
        self.btn_import = QPushButton("Backup importieren...")
        self.btn_delete = QPushButton("Backup löschen")
        self.btn_reset_db = QPushButton("Datenbank zurücksetzen")
        self.btn_close = QPushButton("Schließen")
        
        # Liste der Backups
        self.backup_list = QListWidget()
        
        # Layout
        info_label = QLabel(f"Backup-Ordner: {self.backup_dir}")
        info_label.setWordWrap(True)
        
        btn_layout1 = QHBoxLayout()
        btn_layout1.addWidget(self.btn_create_backup)
        btn_layout1.addWidget(self.btn_restore)
        btn_layout1.addWidget(self.btn_delete)
        
        btn_layout2 = QHBoxLayout()
        btn_layout2.addWidget(self.btn_export)
        btn_layout2.addWidget(self.btn_import)
        btn_layout2.addStretch()
        btn_layout2.addWidget(self.btn_reset_db)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("<b>Backup & Wiederherstellung</b>"))
        layout.addWidget(info_label)
        layout.addSpacing(10)
        layout.addWidget(QLabel("Verfügbare Backups:"))
        layout.addWidget(self.backup_list)
        layout.addLayout(btn_layout1)
        layout.addLayout(btn_layout2)
        layout.addSpacing(10)
        layout.addWidget(self.btn_close)
        self.setLayout(layout)
        
        # Connections
        self.btn_create_backup.clicked.connect(self.create_backup)
        self.btn_restore.clicked.connect(self.restore_backup)
        self.btn_export.clicked.connect(self.export_backup)
        self.btn_import.clicked.connect(self.import_backup)
        self.btn_delete.clicked.connect(self.delete_backup)
        self.btn_reset_db.clicked.connect(self.reset_database)
        # Schließen bedeutet: keine Änderungen an der aktiven DB → reject()
        self.btn_close.clicked.connect(self.reject)
        
        self.refresh_backup_list()
    
    def refresh_backup_list(self):
        self.backup_list.clear()

        # Alle sinnvollen Backup-Typen anzeigen (nicht nur "budgetmanager_backup_*"),
        # sonst sind z.B. "before_restore"/"pre_migration"/importierte DBs Dead-Ends.
        patterns = [
            "budgetmanager_backup_*.db",
            "budgetmanager_backup_imported_*.db",
            "budgetmanager_before_restore_*.db",
            "budgetmanager_before_reset_*.db",
            "budgetmanager_pre_migration_*.db",
        ]
        seen = set()
        backups = []
        for pat in patterns:
            for p in self.backup_dir.glob(pat):
                if p not in seen:
                    seen.add(p)
                    backups.append(p)

        # Neueste zuerst (mtime)
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        for backup in backups:
            size = backup.stat().st_size / 1024  # KB
            mod_time = datetime.fromtimestamp(backup.stat().st_mtime)
            
            item_text = f"{backup.name} ({size:.1f} KB, {mod_time.strftime('%d.%m.%Y %H:%M')})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, str(backup))
            self.backup_list.addItem(item)
        
        if backups:
            self.backup_list.setCurrentRow(0)
    
    def create_backup(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"budgetmanager_backup_{timestamp}.db"
        backup_path = self.backup_dir / backup_name
        
        try:
            # Datenbank-Verbindung temporär schließen für sauberes Backup
            shutil.copy2(self.db_path, backup_path)
            
            QMessageBox.information(
                self,
                "Erfolg",
                f"Backup erstellt:\n{backup_name}"
            )
            self.refresh_backup_list()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Fehler",
                f"Backup konnte nicht erstellt werden:\n{e}"
            )
    
    def restore_backup(self):
        item = self.backup_list.currentItem()
        if not item:
            QMessageBox.information(self, "Hinweis", "Bitte ein Backup auswählen.")
            return
        
        backup_path = item.data(Qt.UserRole)
        
        reply = QMessageBox.question(
            self,
            "Wiederherstellung",
            "ACHTUNG: Dies ersetzt die aktuelle Datenbank!\n\n"
            "Alle nicht gesicherten Daten gehen verloren.\n"
            "Möchten Sie fortfahren?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            # Aktuelles Backup vor Restore
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            auto_backup = self.backup_dir / f"budgetmanager_before_restore_{timestamp}.db"
            shutil.copy2(self.db_path, auto_backup)
            
            # Restore durchführen
            shutil.copy2(backup_path, self.db_path)

            self.db_changed = True
            
            QMessageBox.information(
                self,
                "Erfolg",
                "Datenbank wurde wiederhergestellt.\n\n"
                "Bitte starten Sie die Anwendung neu."
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Fehler",
                f"Wiederherstellung fehlgeschlagen:\n{e}"
            )
    
    def export_backup(self):
        item = self.backup_list.currentItem()
        if not item:
            QMessageBox.information(self, "Hinweis", "Bitte ein Backup auswählen.")
            return
        
        backup_path = Path(item.data(Qt.UserRole))
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Backup exportieren",
            str(Path.home() / backup_path.name),
            "Datenbank-Dateien (*.db)"
        )
        
        if not file_path:
            return
        
        try:
            shutil.copy2(backup_path, file_path)
            QMessageBox.information(self, "Erfolg", f"Backup exportiert nach:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Export fehlgeschlagen:\n{e}")
    
    def import_backup(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Backup importieren",
            str(Path.home()),
            "Datenbank-Dateien (*.db)"
        )
        
        if not file_path:
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Wichtig: Name muss im Backup-Listing auftauchen.
            # Wenn das Prefix nicht passt, ist die importierte DB ein Dead-End (nicht auswählbar).
            import_name = f"budgetmanager_backup_imported_{timestamp}.db"
            import_path = self.backup_dir / import_name
            
            shutil.copy2(file_path, import_path)
            
            QMessageBox.information(
                self,
                "Erfolg",
                f"Backup importiert als:\n{import_name}"
            )
            self.refresh_backup_list()

            # Importiertes Backup direkt markieren
            for i in range(self.backup_list.count()):
                it = self.backup_list.item(i)
                if it and it.data(Qt.UserRole) == str(import_path):
                    self.backup_list.setCurrentRow(i)
                    break

            # Optional: gleich wiederherstellen
            if QMessageBox.question(
                self,
                "Sofort wiederherstellen?",
                "Möchten Sie das importierte Backup jetzt als aktive Datenbank wiederherstellen?\n\n"
                "(Die Anwendung muss danach neu gestartet werden.)",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            ) == QMessageBox.Yes:
                # reuse restore flow, aber ohne zweite Auswahl
                self._restore_from_path(str(import_path))
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Import fehlgeschlagen:\n{e}")

    def _restore_from_path(self, backup_path: str):
        """Interner Helper: Restore von einem beliebigen Pfad (aus Liste oder import)."""
        try:
            # Aktuelles Backup vor Restore
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            auto_backup = self.backup_dir / f"budgetmanager_before_restore_{timestamp}.db"
            shutil.copy2(self.db_path, auto_backup)

            # Restore durchführen
            shutil.copy2(backup_path, self.db_path)
            self.db_changed = True

            QMessageBox.information(
                self,
                "Erfolg",
                "Datenbank wurde wiederhergestellt.\n\n"
                "Bitte starten Sie die Anwendung neu."
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Wiederherstellung fehlgeschlagen:\n{e}")
    
    def delete_backup(self):
        item = self.backup_list.currentItem()
        if not item:
            QMessageBox.information(self, "Hinweis", "Bitte ein Backup auswählen.")
            return
        
        backup_path = Path(item.data(Qt.UserRole))
        
        if QMessageBox.question(
            self,
            "Löschen",
            f"Backup wirklich löschen?\n{backup_path.name}"
        ) != QMessageBox.Yes:
            return
        
        try:
            backup_path.unlink()
            self.refresh_backup_list()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Löschen fehlgeschlagen:\n{e}")
    
    def reset_database(self):
        reply = QMessageBox.question(
            self,
            "Datenbank zurücksetzen",
            "WARNUNG: Dies löscht ALLE Daten!\n\n"
            "Die Datenbank wird auf Standard zurückgesetzt.\n"
            "Ein automatisches Backup wird erstellt.\n\n"
            "Möchten Sie wirklich fortfahren?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Nochmal nachfragen
        reply2 = QMessageBox.question(
            self,
            "Letzte Warnung",
            "Sind Sie ABSOLUT SICHER?\n\nAlle Kategorien, Budgets und Buchungen werden gelöscht!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply2 != QMessageBox.Yes:
            return
        
        try:
            # Backup erstellen
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"budgetmanager_before_reset_{timestamp}.db"
            backup_path = self.backup_dir / backup_name
            shutil.copy2(self.db_path, backup_path)
            
            # Alle Tabellen löschen
            tables = [
                'tracking', 'budget', 'categories', 'favorites',
                'savings_goals', 'budget_warnings', 'undo_stack',
                'tags', 'category_tags', 'theme_profiles', 'system_flags'
            ]
            
            for table in tables:
                try:
                    self.conn.execute(f"DELETE FROM {table}")
                except:
                    pass
            
            self.conn.commit()

            self.db_changed = True
            
            QMessageBox.information(
                self,
                "Erfolg",
                f"Datenbank wurde zurückgesetzt.\n\n"
                f"Backup erstellt: {backup_name}\n\n"
                f"Bitte starten Sie die Anwendung neu."
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Fehler",
                f"Reset fehlgeschlagen:\n{e}"
            )


from PySide6.QtCore import Qt
