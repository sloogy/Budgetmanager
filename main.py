from __future__ import annotations

import faulthandler
import logging
logger = logging.getLogger(__name__)
import os
import sys
from pathlib import Path


_crash_log_handle = None


def _install_crash_diagnostics() -> None:
    """Aktiviert Low-Level Crash-Dumps (z.B. bei Segmentation Fault)."""
    global _crash_log_handle
    try:
        from model.app_paths import data_dir
        crash_log = data_dir() / "budgetmanager_crash.log"
        crash_log.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        crash_log = Path("/tmp/budgetmanager_crash.log")

    try:
        _crash_log_handle = open(crash_log, "a", encoding="utf-8")
        _crash_log_handle.write("\n=== Budgetmanager Crash Diagnostics Enabled ===\n")
        _crash_log_handle.flush()
        faulthandler.enable(file=_crash_log_handle, all_threads=True)
        logger.info("Crash-Diagnose aktiv: %s", crash_log)
    except Exception as exc:
        logger.warning("Crash-Diagnose konnte nicht aktiviert werden: %s", exc)


def _configure_qt_platform() -> None:
    """Optionaler Workaround für Wayland-TextInput-Crashes."""
    force_xcb = os.environ.get("BM_FORCE_XCB", "").strip().lower() in {"1", "true", "yes"}
    if force_xcb and not os.environ.get("QT_QPA_PLATFORM"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def _setup_emoji_fonts(app) -> None:
    """Stellt auf Linux sicher dass Emojis (als Icons verwendet) korrekt gerendert werden.

    Die App nutzt Unicode-Emojis als Icons (keine Bilddateien). Qt auf Linux
    rendert Emojis ohne explizite Emoji-Schrift als leere Kästchen.

    Wir fügen die erste verfügbare Emoji-Schrift als Fallback zur App-Schrift hinzu.
    Da theme_manager.py nur setPointSize() aufruft (nicht setFamilies),
    bleibt dieser Fix nach Themewechseln erhalten.

    Schriften installieren falls nötig:
      Fedora:  sudo dnf install google-noto-emoji-color-fonts
      Ubuntu:  sudo apt install fonts-noto-color-emoji
    """
    import platform
    if platform.system() != "Linux":
        return
    try:
        from PySide6.QtGui import QFontDatabase
        available = set(QFontDatabase.families())
        # In Prioritätsreihenfolge: Farb-Emoji bevorzugt vor Monochrom
        candidates = [
            "Noto Color Emoji",
            "Noto Emoji",
            "Symbola",
            "Segoe UI Emoji",   # manchmal via Wine/crossover
            "DejaVu Sans",      # hat zumindest grundlegende Unicode-Symbole
        ]
        emoji_families = [f for f in candidates if f in available]
        if not emoji_families:
            logger.warning(
                "Keine Emoji-Schrift gefunden – Emojis erscheinen möglicherweise als Kästchen. "
                "Bitte 'Noto Color Emoji' installieren."
            )
            return
        font = app.font()
        base = font.family()
        families = ([base] if base else []) + emoji_families
        font.setFamilies(families)
        app.setFont(font)
        logger.info("Emoji-Schrift gesetzt: %s", emoji_families[0])
    except Exception as e:
        logger.warning("_setup_emoji_fonts fehlgeschlagen: %s", e)


def _install_excepthook() -> None:
    """Globaler Exception-Handler für nicht abgefangene Fehler in Qt-Signals.

    Ohne diesen Handler sterben Fehler in Qt-Callbacks lautlos.
    Mit diesem Handler erscheint ein Fehler-Dialog und der Fehler wird geloggt.
    """
    import traceback as _tb

    def _handler(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        msg = "".join(_tb.format_exception(exc_type, exc_value, exc_tb))
        logger.critical("Unbehandelter Fehler:\n%s", msg)

        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            from utils.i18n import tr, trf
            if QApplication.instance():
                box = QMessageBox()
                box.setIcon(QMessageBox.Critical)
                box.setWindowTitle(tr("msg.unexpected_error_title"))
                box.setText(
                    trf(
                        "msg.unexpected_error_body",
                        details=f"{exc_type.__name__}: {exc_value}"
                    )
                )
                box.setDetailedText(msg)
                box.exec()
        except Exception as _dlg_err:
            logger.critical("Fehler beim Anzeigen des Fehler-Dialogs: %s", _dlg_err)

    sys.excepthook = _handler


def _run_updater_mode(argv: list[str]) -> int | None:
    """CLI-Modi für den Updater."""
    if "--check-update" in argv:
        from updater.check_update import main as check_main
        return check_main()
    if "--apply-update" in argv:
        from updater.apply_update import main as apply_main
        return apply_main()
    return None


def main() -> int:
    # Logging initialisieren (vor allem anderen Code)
    from model.logging_config import setup_logging
    from model.app_paths import data_dir
    try:
        log_file = str(data_dir() / "budgetmanager.log")
    except Exception:
        log_file = None
    setup_logging(log_file=log_file)
    logger.info("Budgetmanager gestartet")
    _install_crash_diagnostics()

    # Globalen Exception-Handler installieren (fängt Fehler in Qt-Signals)
    _install_excepthook()
    _configure_qt_platform()
    logger.info(
        "Qt-Umgebung: XDG_SESSION_TYPE=%s, QT_QPA_PLATFORM=%s, WAYLAND_DISPLAY=%s, DISPLAY=%s",
        os.environ.get("XDG_SESSION_TYPE", ""),
        os.environ.get("QT_QPA_PLATFORM", ""),
        os.environ.get("WAYLAND_DISPLAY", ""),
        os.environ.get("DISPLAY", ""),
    )

    # --- Updater CLI Mode (ohne GUI) ---
    rc = _run_updater_mode(sys.argv)
    if rc is not None:
        return rc

    import traceback

    try:
        from model.app_paths import resolve_in_app, data_dir
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QMessageBox
        from model.database import open_db, EncryptedSession
        from model.migrations import migrate_all

        app = QApplication(sys.argv)
        _setup_emoji_fonts(app)

        # Einstellungen laden
        from settings import Settings
        settings = Settings()

        # Sprache & Währung
        from utils.i18n import set_language, available_languages, tr, trf, set_debug_missing
        from utils.money import set_currency

        # i18n Debug (Missing-Key-Warnungen) – aktivierbar via Env:
        #   BM_I18N_DEBUG=1 python main.py
        try:
            if os.environ.get("BM_I18N_DEBUG", "").strip() not in ("", "0", "false", "False"):
                set_debug_missing(True)
        except Exception:
            pass

        # UserModel früh laden – wird für Language-Check und Login-Flow benötigt
        from model.user_model import UserModel
        user_model = UserModel()

        # Sprache wählen: beim echten Erststart (kein Flag) ODER wenn keine Benutzer
        # vorhanden sind (z.B. nach Reset ohne vollständiges Settings-Löschen)
        if not settings.get("language_selected", False) or not user_model.has_users():
            from views.language_select_dialog import LanguageSelectDialog
            lang_dlg = LanguageSelectDialog(current=settings.get("language", "de"))
            lang_dlg.exec()
            settings.set("language", lang_dlg.selected_code)
            settings.set("language_selected", True)
            settings.save()

        set_language(settings.language)
        set_currency(settings.currency)

        encrypted_session = None
        conn = None
        db_path = None
        active_user = None

        if user_model.has_users():
            users = user_model.list_users()

            # Fall: 1 Quick-User → direkt rein (kein Dialog)
            if len(users) == 1 and users[0].is_quick:
                user = users[0]
                db_key = user_model.authenticate_quick(user.username)
                if not db_key:
                    QMessageBox.critical(None, tr("msg.error"), tr("account.quick_login_failed"))
                    return 1
                active_user = user
            else:
                # Login-Dialog anzeigen
                from views.login_dialog import LoginDialog
                login_dlg = LoginDialog()
                if login_dlg.exec() != LoginDialog.Accepted or not login_dlg.result:
                    return 0  # Abgebrochen
                active_user = login_dlg.result.user
                db_key = login_dlg.result.db_key

            # Verschlüsselte DB öffnen
            try:
                encrypted_session = EncryptedSession.open_with_key(
                    str(active_user.db_path), db_key, active_user.salt
                )
                conn = encrypted_session.conn
                logger.info("DB geöffnet: %s (%s)",
                            active_user.display_name, active_user.db_filename)
            except Exception as e:
                QMessageBox.critical(
                    None, tr("msg.error"),
                    trf("msg.db_open_failed", err=str(e))
                )
                return 1

        else:
            # Keine Benutzer → Erstbenutzer-Wizard ODER direkt starten
            from model.crypto import is_crypto_available

            if is_crypto_available():
                # Erststart-Assistent: User erstellen ODER Daten importieren
                from views.startup_wizard import StartupWizard
                wiz = StartupWizard(user_model=user_model)
                if wiz.exec() == StartupWizard.Accepted and wiz.result:
                    active_user = wiz.result.user
                    db_key = wiz.result.db_key
                    try:
                        encrypted_session = EncryptedSession.open_with_key(
                            str(active_user.db_path), db_key, active_user.salt
                        )
                        conn = encrypted_session.conn
                    except Exception as e:
                        QMessageBox.critical(None, tr("msg.error"), str(e))
                        return 1
                else:
                    # Abgebrochen → Fallback auf unverschlüsselt
                    pass

            if conn is None:
                # Fallback: unverschlüsselte DB (wenn kein crypto oder abgebrochen)
                db_path = resolve_in_app(settings.database_path)
                db_path.parent.mkdir(parents=True, exist_ok=True)
                db_existed_before = db_path.exists()
                conn = open_db(str(db_path))

        # ── Migrations ──────────────────────────────
        if db_path:
            backup_dir = str(resolve_in_app(settings.backup_directory))
            Path(backup_dir).mkdir(parents=True, exist_ok=True)
            migration_info = migrate_all(conn, str(db_path), backup_dir)
        else:
            migration_info = migrate_all(conn)

        if migration_info.get('migrations_applied'):
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Datenbank aktualisiert")
            info_text = (
                f"Datenbank von Version {migration_info['old_version']} "
                f"auf {migration_info['new_version']} aktualisiert.\n\n"
            )
            info_text += "\n".join(f"• {m}" for m in migration_info['migrations_applied'])
            if migration_info.get('backup_created'):
                info_text += "\n\n✓ Sicherheitskopie erstellt."
            msg.setText(info_text)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()

            if encrypted_session:
                encrypted_session.save()

        # ── MainWindow ──────────────────────────────
        from views.main_window import MainWindow
        win = MainWindow(conn, active_user=active_user, user_model=user_model)

        if encrypted_session:
            win._encrypted_session = encrypted_session

            # Titel: 🔒 + Username
            icon = active_user.security_icon if active_user else "🔒"
            name = active_user.display_name if active_user else ""
            win.setWindowTitle(f"{win.windowTitle()} — {icon} {name}")

            # Auto-Save Timer (5 Minuten)
            save_timer = QTimer(win)
            save_timer.timeout.connect(encrypted_session.save)
            save_timer.start(5 * 60 * 1000)
            win._save_timer = save_timer

        # Auto-Backup nach Event-Loop-Start prüfen (nicht in __init__,
        # damit _encrypted_session korrekt gesetzt ist und kein Access Violation entsteht)
        QTimer.singleShot(500, win._check_auto_backup)

        win.show()

        # Setup-Assistent
        db_existed = db_path is not None and db_path.exists() if db_path else True
        if encrypted_session:
            # Bei verschlüsselter DB: Setup wenn DB leer
            try:
                cnt = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
                if cnt == 0:
                    db_existed = False
            except Exception:
                db_existed = False

        QTimer.singleShot(0, lambda: win._start_setup_assistant(
            force=False, db_existed_before=db_existed
        ))

        rc = app.exec()

        # ── Cleanup (Reihenfolge kritisch für PyInstaller!) ────
        # Qt-Objekte müssen vor QApplication zerstört werden,
        # sonst Segfault beim nächsten Start (stale _MEIPASS refs).
        if encrypted_session:
            encrypted_session.close()

        # LRU-Caches mit Qt-Objekten leeren
        try:
            from utils.icons import get_icon
            get_icon.cache_clear()
        except Exception:
            pass

        # MainWindow explizit zerstören vor QApplication
        win.close()
        del win

        # QApplication sauber beenden
        app.processEvents()
        del app

        import gc
        gc.collect()

        return rc

    except Exception as exc:
        logger.critical("FEHLER BEIM STARTEN DES BUDGETMANAGERS", exc_info=True)

        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance():
                QMessageBox.critical(
                    None, "Startfehler",
                    f"Budgetmanager konnte nicht gestartet werden:\n\n{exc}\n\n"
                    "Details siehe budgetmanager.log."
                )
        except Exception as ui_exc:
            logger.critical("Fehler beim Anzeigen des Startfehler-Dialogs: %s", ui_exc)

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
