from __future__ import annotations

import sys
from pathlib import Path
<<<<<<< Updated upstream
=======

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
>>>>>>> Stashed changes


def _run_updater_mode(argv: list[str]) -> int | None:
    """CLI-Modi für den Updater.

    Wichtig: muss auch im PyInstaller-Fall funktionieren.
    Daher: App/EXE mit Flags starten, statt `python -m ...`.
    """
    if "--check-update" in argv:
        from updater.check_update import main as check_main
        return check_main()
    if "--apply-update" in argv:
        from updater.apply_update import main as apply_main
        return apply_main()
    return None


def main() -> int:
<<<<<<< Updated upstream
    # --- Updater CLI Mode (ohne GUI) ---
    rc = _run_updater_mode(sys.argv)
    if rc is not None:
        return rc
=======
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
>>>>>>> Stashed changes

    import traceback

<<<<<<< Updated upstream
    try:
        from model.app_paths import resolve_in_app
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QMessageBox
        from model.database import open_db
        from model.migrations import migrate_all

        app = QApplication(sys.argv)

        # Einstellungen laden
        from settings import Settings
        settings = Settings()

        # Datenbank-Pfad (vor open_db prüfen, ob die Datei bereits existierte)
        db_path = resolve_in_app(settings.database_path)
        # Portable: sicherstellen, dass ./data existiert
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_existed_before = db_path.exists()

        # Datenbank öffnen (erstellt Datei falls nicht vorhanden)
        conn = open_db(str(db_path))

        # Migrations durchführen mit Backup-Ordner aus Einstellungen
        backup_dir = str(resolve_in_app(settings.backup_directory))
        Path(backup_dir).mkdir(parents=True, exist_ok=True)
        migration_info = migrate_all(conn, str(db_path), backup_dir)

        # Migration-Info anzeigen wenn Änderungen vorgenommen wurden
        if migration_info.get('migrations_applied'):
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

        from views.main_window import MainWindow
        win = MainWindow(conn)
        win.show()

        # Setup-Assistent beim Start (wenn aktiviert und noch nicht abgeschlossen)
        # via QTimer, damit das Hauptfenster bereits sichtbar ist
        QTimer.singleShot(0, lambda: win._start_setup_assistant(force=False, db_existed_before=db_existed_before))

        return app.exec()

    except Exception as exc:
        # Fehler auf Terminal ausgeben
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"FEHLER BEIM STARTEN DES BUDGETMANAGERS", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)

        # Auch als Dialog anzeigen (falls QApplication bereits existiert)
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance():
                QMessageBox.critical(
                    None, "Startfehler",
                    f"Der Budgetmanager konnte nicht gestartet werden:\n\n{exc}\n\n"
                    f"Details siehe Terminal-Ausgabe."
                )
        except Exception:
            pass

        return 1
=======
    # Setup-Assistent beim Start (wenn aktiviert und noch nicht abgeschlossen)
    # via QTimer, damit das Hauptfenster bereits sichtbar ist
    QTimer.singleShot(0, lambda: win._start_setup_assistant(force=False, db_existed_before=db_existed_before))

    return app.exec()
>>>>>>> Stashed changes


if __name__ == "__main__":
    raise SystemExit(main())
