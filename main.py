from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from model.database import open_db
from model.migrations import migrate_all
from views.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    
    # Einstellungen laden
    from settings import Settings
    settings = Settings()
    
    # Datenbank-Pfad (vor open_db prüfen, ob die Datei bereits existierte)
    db_path = Path(settings.database_path).expanduser()
    db_existed_before = db_path.exists()
    
    # Datenbank öffnen (erstellt Datei falls nicht vorhanden)
    conn = open_db(str(db_path))
    
    # Migrations durchführen mit Backup-Ordner aus Einstellungen
    backup_dir = settings.backup_directory
    migration_info = migrate_all(conn, str(db_path), backup_dir)
    
    # Migration-Info anzeigen wenn Änderungen vorgenommen wurden
    if migration_info.get('migrations_applied'):
        from PySide6.QtWidgets import QMessageBox
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Datenbank aktualisiert")
        
        info_text = f"Die Datenbank wurde erfolgreich von Version {migration_info['old_version']} auf Version {migration_info['new_version']} aktualisiert.\n\n"
        info_text += "Durchgeführte Änderungen:\n"
        info_text += "\n".join(f"• {m}" for m in migration_info['migrations_applied'])
        
        if migration_info.get('backup_created'):
            info_text += f"\n\n✓ Sicherheitskopie wurde erstellt."
        
        msg.setText(info_text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()

    win = MainWindow(conn)
    win.show()

    # Setup-Assistent beim Start (wenn aktiviert und noch nicht abgeschlossen)
    # via QTimer, damit das Hauptfenster bereits sichtbar ist
    QTimer.singleShot(0, lambda: win._start_setup_assistant(force=False, db_existed_before=db_existed_before))

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
