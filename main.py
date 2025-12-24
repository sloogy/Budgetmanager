from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication

from model.database import open_db
from model.migrations import migrate_all
from views.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    
    # Einstellungen laden
    from settings import Settings
    settings = Settings()
    
    # Datenbank aus Einstellungen öffnen
    db_path = settings.database_path
    conn = open_db(db_path)
    
    # Migrations durchführen mit Backup-Ordner aus Einstellungen
    backup_dir = settings.backup_directory
    migration_info = migrate_all(conn, db_path, backup_dir)
    
    # Migration-Info anzeigen wenn Änderungen vorgenommen wurden
    if migration_info['migrations_applied']:
        from PySide6.QtWidgets import QMessageBox
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Datenbank aktualisiert")
        
        info_text = f"Die Datenbank wurde erfolgreich von Version {migration_info['old_version']} auf Version {migration_info['new_version']} aktualisiert.\n\n"
        info_text += "Durchgeführte Änderungen:\n"
        info_text += "\n".join(f"• {m}" for m in migration_info['migrations_applied'])
        
        if migration_info['backup_created']:
            info_text += f"\n\n✓ Sicherheitskopie wurde erstellt."
        
        msg.setText(info_text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()

    win = MainWindow(conn)
    win.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
