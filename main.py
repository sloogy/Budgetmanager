from __future__ import annotations

import faulthandler
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


_crash_log_handle = None


class _SingleInstanceGuard:
    """Robuster, app- und datenordnerspezifischer Single-Instance-Schutz.

    Wichtig: Dieser Guard blockiert NICHT global alle ``python main.py``-Prozesse.
    Er sperrt nur genau den übergebenen Lock-Pfad im BudgetManager-Datenordner.
    Andere Programme wie der Füller-/Sammelmanager dürfen parallel laufen, solange
    sie ihren eigenen App-/Datenordner verwenden.

    Warum nicht nur QLockFile? In einer früheren Variante konnte ein Qt-Stale-
    Timeout eine lange laufende App fälschlich als "stale" betrachten. Dieses
    Lock nutzt atomar ``os.mkdir()`` und prüft bei vorhandenen Locks die gespeicherte
    PID. Alte Crash-Locks werden nur entfernt, wenn der gespeicherte Prozess nicht
    mehr läuft.
    """

    def __init__(self, lock_dir: Path, *, app_id: str = "budgetmanager"):
        self.lock_dir = Path(lock_dir)
        self.app_id = app_id
        self.acquired = False

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        from model.process_utils import is_pid_alive

        return is_pid_alive(pid)

    def _read_pid(self) -> int | None:
        try:
            text = (self.lock_dir / "pid").read_text(encoding="utf-8").strip()
            return int(text)
        except Exception:
            return None

    def acquire(self) -> tuple[bool, str]:
        self.lock_dir.parent.mkdir(parents=True, exist_ok=True)
        for _attempt in range(2):
            try:
                os.mkdir(self.lock_dir)
                metadata = {
                    "app_id": self.app_id,
                    "pid": os.getpid(),
                    "cmdline": sys.argv,
                    "lock_dir": str(self.lock_dir),
                }
                (self.lock_dir / "pid").write_text(str(os.getpid()), encoding="utf-8")
                (self.lock_dir / "owner.json").write_text(
                    json.dumps(metadata, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                # Kompatibilitäts-Datei für schnelle manuelle Diagnose.
                (self.lock_dir / "cmdline").write_text(
                    " ".join(sys.argv), encoding="utf-8"
                )
                self.acquired = True
                return True, ""
            except FileExistsError:
                pid = self._read_pid()
                if pid is not None and self._pid_alive(pid):
                    return False, f"BudgetManager läuft bereits (PID {pid})."
                # Stales Lock: Prozess ist weg oder PID fehlt/kaputt. Entfernen und noch einmal versuchen.
                try:
                    import shutil

                    shutil.rmtree(self.lock_dir)
                    continue
                except Exception as exc:
                    return (
                        False,
                        f"BudgetManager-Lock konnte nicht übernommen werden: {exc}",
                    )
            except Exception as exc:
                return False, f"BudgetManager-Lock konnte nicht erstellt werden: {exc}"
        return False, "BudgetManager-Lock konnte nicht erstellt werden."

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            pid = self._read_pid()
            if pid == os.getpid():
                import shutil

                shutil.rmtree(self.lock_dir)
        except Exception:
            pass
        finally:
            self.acquired = False


def _install_crash_diagnostics() -> None:
    """Aktiviert Low-Level Crash-Dumps (z.B. bei Segmentation Fault)."""
    global _crash_log_handle
    try:
        from model.app_paths import data_dir

        crash_log = data_dir() / "budgetmanager_crash.log"
        crash_log.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Portabler Fallback: OS-Temp-Verzeichnis statt hartkodiertem /tmp
        # (existiert unter Windows nicht). gettempdir() liefert %TEMP% bzw. /tmp.
        import tempfile

        crash_log = Path(tempfile.gettempdir()) / "budgetmanager_crash.log"

    try:
        from datetime import datetime

        from app_info import APP_VERSION

        # Kein Kontextmanager: Der Deskriptor bleibt fuer die gesamte
        # Laufzeit offen, weil faulthandler direkt hineinschreibt.
        # Geschlossen wird er beim Herunterfahren.
        _crash_log_handle = open(crash_log, "a", encoding="utf-8")  # noqa: SIM115
        # Mit Zeit, Version und Prozessnummer: Die Datei sammelt jeden Start,
        # und ohne diese drei Angaben laesst sich ein Absturzdump keinem
        # Programmlauf zuordnen. Im eingesandten Bericht standen zwoelf
        # gleichlautende Zeilen und ein Dump - welcher Start dazugehoerte,
        # war daraus nicht zu erkennen.
        _crash_log_handle.write(
            "\n=== Budgetmanager {version} | Start {zeit} | PID {pid} ===\n".format(
                version=APP_VERSION,
                zeit=datetime.now().astimezone().isoformat(timespec="seconds"),
                pid=os.getpid(),
            )
        )
        _crash_log_handle.flush()
        faulthandler.enable(file=_crash_log_handle, all_threads=True)
        logger.info("Crash-Diagnose aktiv: %s", crash_log)
    except Exception as exc:
        logger.warning("Crash-Diagnose konnte nicht aktiviert werden: %s", exc)


def _configure_qt_platform() -> None:
    """Stabiler Qt-Start unter Linux/Wayland.

    In Qt/PySide kann Wayland beim Schließen kleiner Dialoge oder Kontextmenüs
    mit ``qt.qpa.wayland.textinput ... surface 0x0`` in einen nativen
    Segmentation Fault laufen. Python sieht diesen Fehler nicht mehr, deshalb
    hilft nur ein QPA-Workaround VOR ``QApplication(...)``.

    Best Practice für diese Desktop-App: Unter einer Wayland-Sitzung automatisch
    das XCB/XWayland-Backend verwenden, solange der Nutzer nicht explizit
    ``BM_ALLOW_WAYLAND=1`` setzt. ``BM_FORCE_XCB=1`` bleibt zusätzlich als
    manueller Schalter erhalten.
    """
    force_xcb = os.environ.get("BM_FORCE_XCB", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    allow_wayland = os.environ.get("BM_ALLOW_WAYLAND", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    platform_already_set = bool(os.environ.get("QT_QPA_PLATFORM"))
    is_wayland_session = os.environ.get(
        "XDG_SESSION_TYPE", ""
    ).strip().lower() == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))

    if not platform_already_set and (
        force_xcb or (is_wayland_session and not allow_wayland)
    ):
        os.environ["QT_QPA_PLATFORM"] = "xcb"
        logging.getLogger(__name__).info(
            "Qt-Backend auf xcb gesetzt (Wayland-Stabilitätsfallback). "
            "Native Wayland-Nutzung: BM_ALLOW_WAYLAND=1 setzen."
        )


def _configure_utf8_runtime() -> None:
    """Sorgt dafuer, dass die App und ihre Kindprozesse in UTF-8 arbeiten.

    Auf Windows waehlt Python ohne UTF-8-Modus die ANSI-Codepage - auf einer
    deutschen Installation cp1252 fuer Dateien und cp850 auf der Konsole.
    ``PYTHONUTF8=1`` stand bisher ausschliesslich in den CI-Env-Bloecken und in
    keiner Zeile Produktivcode; beim Nutzer galt es also nie.

    Drei Vorkehrungen, analog zum Wayland-Workaround darueber - erst pruefen,
    dann nur setzen, was noch nicht gesetzt ist:

    1. stdout/stderr auf UTF-8 umstellen. Ohne das stirbt jede Ausgabe mit
       Umlaut oder Emoji auf einer Windows-Konsole an UnicodeEncodeError.
    2. ``PYTHONUTF8`` und ``PYTHONIOENCODING`` in die Umgebung schreiben. Das
       aendert am laufenden Interpreter nichts mehr, wohl aber an jedem
       Kindprozess: Der Updater laeuft als eigener Prozess und gibt ❌, ✓ und
       ⟲ aus, und der Neustart nach einem Update startet die App erneut.
    3. Fehlt der UTF-8-Modus, wird das protokolliert. Der gebaute Stand
       erzwingt ihn ueber ``-X utf8=1`` in BudgetManager.spec; im Quellbetrieb
       ist die Umgebung des Aufrufers zustaendig.
    """
    from updater.common import enable_utf8_console

    enable_utf8_console()
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    if not sys.flags.utf8_mode:
        import locale

        logging.getLogger(__name__).info(
            "Python laeuft nicht im UTF-8-Modus (Vorgabe-Kodierung: %s). "
            "Der gebaute Stand setzt -X utf8=1; im Quellbetrieb hilft PYTHONUTF8=1.",
            locale.getpreferredencoding(False),
        )


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
            "Segoe UI Emoji",  # manchmal via Wine/crossover
            "DejaVu Sans",  # hat zumindest grundlegende Unicode-Symbole
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
                        details=f"{exc_type.__name__}: {exc_value}",
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
    if "--startup-update-check" in argv:
        from updater.startup_check import main as startup_check_main

        return startup_check_main()
    return None


def _apply_application_icon(app) -> None:
    """Setzt das BudgetManager-App-Icon fuer Fenster/Taskbar.

    Funktioniert im Source-Start und im PyInstaller-Onefile-Build:
    - Source/portable Ordner: <app_dir>/resources/icons/...
    - Frozen Onefile: sys._MEIPASS/resources/icons/...
    """
    try:
        from PySide6.QtGui import QIcon

        from model.app_paths import resolve_in_app

        candidates = []
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            base = Path(meipass)
            candidates.extend(
                [
                    base / "resources" / "icons" / "budgetmanager.ico",
                    base / "resources" / "icons" / "budgetmanager.png",
                ]
            )
        candidates.extend(
            [
                resolve_in_app("resources/icons/budgetmanager.ico"),
                resolve_in_app("resources/icons/budgetmanager.png"),
            ]
        )
        for icon_path in candidates:
            if icon_path.exists():
                icon = QIcon(str(icon_path))
                if not icon.isNull():
                    app.setWindowIcon(icon)
                    logging.getLogger(__name__).info("App-Icon gesetzt: %s", icon_path)
                    return
        logging.getLogger(__name__).debug("Kein App-Icon gefunden: %s", candidates)
    except Exception as exc:
        logging.getLogger(__name__).debug(
            "App-Icon konnte nicht gesetzt werden: %s", exc
        )


def main() -> int:
    # Logging initialisieren (vor allem anderen Code)
    from model.app_paths import data_dir
    from model.logging_config import setup_logging

    try:
        log_file = str(data_dir() / "budgetmanager.log")
    except Exception:
        log_file = None
    setup_logging(log_file=log_file)
    _configure_utf8_runtime()
    logger.info("Budgetmanager gestartet")
    _install_crash_diagnostics()

    # Globalen Exception-Handler installieren (fängt Fehler in Qt-Signals)
    _install_excepthook()
    _configure_qt_platform()
    try:
        from utils.ui_scaling import configure_qt_scaling_environment

        configure_qt_scaling_environment()
    except Exception as _scale_exc:
        logger.debug("Qt-Skalierung konnte nicht vorbereitet werden: %s", _scale_exc)
    logger.info(
        "Qt-Umgebung: XDG_SESSION_TYPE=%s, QT_QPA_PLATFORM=%s, WAYLAND_DISPLAY=%s, DISPLAY=%s",
        os.environ.get("XDG_SESSION_TYPE", ""),
        os.environ.get("QT_QPA_PLATFORM", ""),
        os.environ.get("WAYLAND_DISPLAY", ""),
        os.environ.get("DISPLAY", ""),
    )

    # --- Installationsnaher Release-Selbsttest (ohne Login/Produktivdaten) ---
    if "--release-self-test" in sys.argv:
        from utils.release_self_test import run_release_self_test

        return run_release_self_test()

    # --- Isolierter Updater-E2E-Selbsttest (ohne Produktivdaten) ---
    if "--updater-self-test" in sys.argv:
        from utils.updater_self_test import run_updater_self_test

        return run_updater_self_test()

    # --- Updater CLI Mode (ohne GUI) ---
    rc = _run_updater_mode(sys.argv)
    if rc is not None:
        return rc

    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QMessageBox

        from model.app_paths import (
            configured_backups_dir,
            configured_db_path,
            data_dir,
        )
        from model.database import EncryptedSession, open_db
        from model.migrations import migrate_all

        # Single-Instance-Schutz VOR der GUI/User-DB öffnen.
        # Wichtig: Kein 30s-Stale-Timeout mehr. Eine laufende App bleibt gesperrt,
        # bis sie sauber beendet wird; nach einem Crash wird das Lock beim nächsten Start
        # über die PID-Prüfung als stale erkannt und entfernt.
        # Datenordner-spezifisch: blockiert nur eine zweite BudgetManager-Instanz,
        # die auf denselben Datenordner zugreift. Andere Apps mit eigener Ablage
        # (z.B. Füller-/Sammelmanager) bleiben parallel startbar.
        single_lock = _SingleInstanceGuard(
            data_dir() / "budgetmanager.instance.lock", app_id="budgetmanager"
        )
        ok, lock_reason = single_lock.acquire()
        if not ok:
            logger.warning("Zweite Instanz blockiert: %s", lock_reason)
            print(lock_reason)
            return 0

        from app_info import APP_VERSION
        from model.diagnostics import mark_app_exited, mark_app_started

        previous_unclean_state = mark_app_started(version=APP_VERSION, argv=sys.argv)

        def _finish_startup_return(
            code: int, reason: str, *, clean: bool = True
        ) -> int:
            try:
                mark_app_exited(clean=clean, reason=reason, version=APP_VERSION)
            except Exception:
                logger.debug(
                    "Runtime-State konnte vor frühem Exit nicht geschrieben werden",
                    exc_info=True,
                )
            try:
                single_lock.release()
            except Exception:
                pass
            return code

        app = QApplication(sys.argv)
        _setup_emoji_fonts(app)
        _apply_application_icon(app)
        # v2.2.21: zentrale Accessibility- und Fokus-Härtung für alle Views.
        from utils.ui_usability import install_ui_usability

        _ui_usability_filter = install_ui_usability(app)

        # Einstellungen laden
        from settings import Settings

        settings = Settings()

        # Sprache & Währung
        from utils.i18n import (
            set_debug_missing,
            set_language,
            tr,
            trf,
        )
        from utils.money import set_currency, set_number_format

        # i18n Debug (Missing-Key-Warnungen) – aktivierbar via Env:
        #   BM_I18N_DEBUG=1 python main.py
        try:
            if os.environ.get("BM_I18N_DEBUG", "").strip() not in (
                "",
                "0",
                "false",
                "False",
            ):
                set_debug_missing(True)
        except Exception as e:
            logging.getLogger(__name__).debug(
                "BM_I18N_DEBUG-Auswertung fehlgeschlagen: %s", e
            )

        # UserModel früh laden – wird für Language-Check und Login-Flow benötigt
        from model.user_model import UserModel

        user_model = UserModel()

        # Sprache wählen: beim echten Erststart (kein Flag) ODER wenn keine Benutzer
        # vorhanden sind (z.B. nach Reset ohne vollständiges Settings-Löschen)
        if not settings.get("language_selected", False) or not user_model.has_users():
            from views.language_select_dialog import LanguageSelectDialog

            lang_dlg = LanguageSelectDialog(
                current=settings.get("language", "de"),
                current_currency=settings.get("currency", "CHF"),
                current_recurring_day=settings.get("recurring_preferred_day", 25),
                current_number_format=settings.get("number_format", "swiss"),
            )
            lang_dlg.exec()
            settings.set("language", lang_dlg.selected_code)
            settings.set("currency", lang_dlg.selected_currency)
            settings.set("number_format", lang_dlg.selected_number_format)
            settings.set(
                "recurring_preferred_day", int(lang_dlg.selected_recurring_day or 0)
            )
            settings.set("language_selected", True)
            settings.save()

        set_language(settings.language)
        set_currency(settings.currency)
        set_number_format(settings.get("number_format", "swiss"))
        try:
            from utils.qt_translator import apply_number_locale

            apply_number_locale(settings.get("number_format", "swiss"))
        except Exception as _e:
            logging.getLogger(__name__).debug("QLocale-Kopplung fehlgeschlagen: %s", _e)
        # Qt-eigene Übersetzungen (native Kontextmenüs: Kopieren/Einfügen/…)
        try:
            from utils.qt_translator import install_qt_translations

            install_qt_translations(app, settings.language)
        except Exception as _e:
            logging.getLogger(__name__).debug(
                "Qt-Übersetzung nicht installiert: %s", _e
            )

        encrypted_session = None
        conn = None
        db_path = None
        active_user = None

        def _recover_broken_account(broken, reason: str) -> bool:
            """Selbstheilung bei einem defekten/verwaisten Konto.

            Fragt, ob das nicht öffenbare Konto entfernt und die Ersteinrichtung
            erneut gestartet werden soll. Bei Zustimmung wird das Konto inkl. der
            verschlüsselten DB-Datei gelöscht und True zurückgegeben – so muss der
            Nutzer NICHT manuell den data-Ordner leeren, um wieder hineinzukommen
            (z. B. nach einem Erststart-Restore mit falschem Wiederherstellungscode).
            """
            if (
                QMessageBox.question(
                    None,
                    tr("startup.recover_title"),
                    trf("startup.recover_question", reason=reason),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                != QMessageBox.Yes
            ):
                return False
            try:
                user_model.delete_user(broken.username, delete_db=True)
            except Exception as exc:
                logger.warning(
                    "Defektes Konto konnte nicht regulär entfernt werden: %s", exc
                )
            # Sicherstellen, dass keine verwaiste .enc zurückbleibt.
            try:
                if broken.db_path.exists():
                    broken.db_path.unlink()
            except Exception as exc:
                logger.error("Verwaiste DB-Datei konnte nicht entfernt werden: %s", exc)
                return False
            logger.info(
                "Defektes Konto '%s' entfernt – Ersteinrichtung wird erneut angeboten.",
                broken.username,
            )
            return True

        while True:
            if user_model.has_users():
                users = user_model.list_users()

                # Fall: 1 Quick-User → direkt rein (kein Dialog)
                if len(users) == 1 and users[0].is_quick:
                    user = users[0]
                    db_key = user_model.authenticate_quick(user.username)
                    if not db_key:
                        if _recover_broken_account(
                            user, tr("account.quick_login_failed")
                        ):
                            active_user = None
                            continue
                        QMessageBox.critical(
                            None, tr("msg.error"), tr("account.quick_login_failed")
                        )
                        return _finish_startup_return(1, "quick_login_failed")
                    active_user = user
                else:
                    # Login-Dialog anzeigen
                    from views.login_dialog import LoginDialog

                    login_dlg = LoginDialog()
                    if login_dlg.exec() != LoginDialog.Accepted or not login_dlg.result:
                        return _finish_startup_return(
                            0, "login_cancelled"
                        )  # Abgebrochen
                    active_user = login_dlg.result.user
                    db_key = login_dlg.result.db_key

                # Verschlüsselte DB öffnen
                try:
                    encrypted_session = EncryptedSession.open_with_key(
                        str(active_user.db_path), db_key, active_user.salt
                    )
                    conn = encrypted_session.conn
                    logger.info(
                        "DB geöffnet: %s (%s)",
                        active_user.display_name,
                        active_user.db_filename,
                    )
                except Exception as e:
                    # DB nicht öffenbar (defekt/verwaist). Bei einem EINZELNEN
                    # Benutzer ohne öffenbare Daten Selbstheilung anbieten, statt
                    # hart zu beenden (sonst: "komme nicht mehr rein bis data leer").
                    single_user = len(users) == 1
                    if single_user and _recover_broken_account(active_user, str(e)):
                        active_user = None
                        encrypted_session = None
                        conn = None
                        continue
                    QMessageBox.critical(
                        None, tr("msg.error"), trf("msg.db_open_failed", err=str(e))
                    )
                    return _finish_startup_return(1, "db_open_failed")
                break

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
                        if getattr(wiz, "imported_existing_database", False):
                            # Die Settings-Instanz wurde vor dem Wizard geladen.
                            # Nach einem erfolgreichen Import muss auch dieses
                            # Objekt aktualisiert werden, sonst plant main.py im
                            # selben Start trotzdem wieder den Setup-Assistenten.
                            try:
                                settings.set("show_onboarding", False)
                                settings.set("setup_completed", True)
                                settings.set(
                                    "auto_generate_budget_warnings",
                                    bool(
                                        settings.get(
                                            "auto_generate_budget_warnings", True
                                        )
                                    ),
                                )
                                settings.set(
                                    "tracking_budget_learning_enabled",
                                    bool(
                                        settings.get(
                                            "tracking_budget_learning_enabled", True
                                        )
                                    ),
                                )
                                settings.set(
                                    "tracking_budget_learning_show_in_report",
                                    bool(
                                        settings.get(
                                            "tracking_budget_learning_show_in_report",
                                            True,
                                        )
                                    ),
                                )
                            except Exception as _import_settings_exc:
                                logging.getLogger(__name__).warning(
                                    "Import-Settings konnten im Startlauf nicht fixiert werden: %s",
                                    _import_settings_exc,
                                )
                        try:
                            encrypted_session = EncryptedSession.open_with_key(
                                str(active_user.db_path), db_key, active_user.salt
                            )
                            conn = encrypted_session.conn
                        except Exception as e:
                            # Selbst der frisch eingerichtete Benutzer ließ sich nicht
                            # öffnen → entfernen und Einrichtung erneut anbieten.
                            if _recover_broken_account(active_user, str(e)):
                                active_user = None
                                encrypted_session = None
                                conn = None
                                continue
                            QMessageBox.critical(None, tr("msg.error"), str(e))
                            return _finish_startup_return(
                                1, "startup_wizard_db_open_failed"
                            )
                    else:
                        # Abgebrochen → Fallback auf unverschlüsselt
                        pass

                if conn is None:
                    # Fallback: unverschlüsselte DB (wenn kein crypto oder abgebrochen)
                    db_path = configured_db_path(settings.database_path)
                    db_path.parent.mkdir(parents=True, exist_ok=True)
                    db_existed_before = db_path.exists()
                    conn = open_db(str(db_path))
                break

        # ── Migrations ──────────────────────────────
        if db_path:
            backup_dir = str(configured_backups_dir(settings.backup_directory))
            Path(backup_dir).mkdir(parents=True, exist_ok=True)
            migration_info = migrate_all(conn, str(db_path), backup_dir)
        else:
            # Verschlüsselter Modus: Die Migration läuft auf der In-Memory-DB.
            # Falls sie nötig ist, sichern wir VORHER die originale .enc-Datei —
            # geht beim anschließenden verschlüsselten Speichern etwas schief,
            # bleibt der letzte gute Stand erhalten.
            if encrypted_session is not None:
                try:
                    from model.migrations import CURRENT_VERSION, _get_db_version

                    if _get_db_version(conn) < CURRENT_VERSION:
                        import shutil
                        from datetime import datetime as _dt

                        enc_src = Path(encrypted_session.enc_path)
                        if enc_src.exists():
                            backup_dir_p = configured_backups_dir(
                                settings.backup_directory
                            )
                            backup_dir_p.mkdir(parents=True, exist_ok=True)
                            stamp = _dt.now().strftime("%Y%m%d_%H%M%S")
                            enc_backup = backup_dir_p / f"pre_migration_{stamp}.enc"
                            shutil.copy2(str(enc_src), str(enc_backup))
                            logging.getLogger(__name__).info(
                                "Pre-Migration-Backup der verschlüsselten DB: %s",
                                enc_backup,
                            )
                except Exception as e:
                    logging.getLogger(__name__).warning(
                        "Pre-Migration-Backup (.enc) fehlgeschlagen: %s", e
                    )
            migration_info = migrate_all(conn)

        if migration_info.get("migrations_applied"):
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)

            old_v = int(migration_info.get("old_version") or 0)
            new_v = int(migration_info.get("new_version") or 0)
            details = "\n".join(
                f"• {m}" for m in migration_info.get("migrations_applied", [])
            )
            if migration_info.get("backup_created"):
                details += "\n\n✓ " + tr("db.backup_created")

            if old_v <= 0:
                # Erststart: nicht mit technischen v0→v11 Details überfordern.
                msg.setWindowTitle(tr("db.created_title"))
                msg.setText(tr("db.created_body"))
            else:
                msg.setWindowTitle(tr("db.updated_title"))
                msg.setText(tr("db.updated_body"))
                msg.setInformativeText(trf("db.version_line", old=old_v, new=new_v))

            if details:
                msg.setDetailedText(details)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()

            if encrypted_session:
                encrypted_session.save()

        # ── MainWindow ──────────────────────────────
        from views.main_window import MainWindow

        win = MainWindow(conn, active_user=active_user, user_model=user_model)
        try:
            win.setWindowIcon(app.windowIcon())
        except Exception:
            pass
        win._single_instance_lock = single_lock

        if encrypted_session:
            win._encrypted_session = encrypted_session

            # Titel: 🔒 + Username
            icon = active_user.security_icon if active_user else "🔒"
            name = active_user.display_name if active_user else ""
            win.setWindowTitle(
                trf(
                    "auto.main.337_value_0_value_1_value_2_08554ed9",
                    value_0=(win.windowTitle()),
                    value_1=(icon),
                    value_2=(name),
                )
            )

            # Auto-Save Timer (5 Minuten)
            save_timer = QTimer(win)
            save_timer.timeout.connect(encrypted_session.save)
            save_timer.start(5 * 60 * 1000)
            win._save_timer = save_timer

        # Auto-Backup nach Event-Loop-Start prüfen (nicht in __init__,
        # damit _encrypted_session korrekt gesetzt ist).
        #
        # WICHTIG v2.0.16 Hotfix:
        # Beim echten Erststart läuft direkt danach der nicht-modale Setup-Assistent.
        # Auf Fedora/Wayland über XCB kann gleichzeitiges Initialisieren eines
        # Kinddialogs + verschlüsseltes Auto-Backup zu einem nativen Qt/PySide-
        # Segfault führen (kein Python-Traceback). Deshalb wird das erste
        # Auto-Backup bei aktivem Onboarding bis nach dem Assistenten verschoben.
        setup_autostart_requested = bool(
            settings.get("show_onboarding", True)
        ) and not bool(settings.get("setup_completed", False))
        win._defer_startup_auto_backup_until_setup = bool(setup_autostart_requested)
        win._startup_auto_backup_done = False

        if setup_autostart_requested:
            logger.info("Auto-Backup wird bis nach dem Setup-Assistenten verschoben.")
        else:
            # Einheitlicher, parent-gebundener Pfad. Damit laeuft die Pruefung
            # weder aus einem Dialog-Signal noch ueber einen unparented Callback.
            win._schedule_startup_auto_backup(delay_ms=500)

        # Hauptfenster genau einmal anzeigen. MainWindow._restore_window_state()
        # setzt nur Geometrie und merkt sich den gewünschten Zustand.
        if hasattr(win, "show_restored"):
            win.show_restored()
        else:
            win.show()

        # Setup-Assistent
        # WICHTIG: db_existed_before wurde VOR open_db() ermittelt — nach open_db()
        # existiert die Datei immer, wodurch der Setup-Assistent beim Erststart
        # fälschlich unterdrückt wurde.
        if db_path is not None:
            try:
                db_existed = bool(db_existed_before)
            except NameError:
                db_existed = db_path.exists()
        else:
            db_existed = True
        if encrypted_session:
            # Bei verschlüsselter DB: Setup wenn DB leer
            try:
                cnt = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
                if cnt == 0:
                    db_existed = False
            except Exception:
                db_existed = False

        # Setup nicht im selben Event-Loop-Tick wie show() starten. Das gibt Qt
        # Zeit, das Hauptfenster vollständig zu realisieren, bevor der Assistent
        # als Kindfenster angezeigt wird.
        #
        # Windows-Crashfix v2.0.32:
        # Kein unparented QTimer.singleShot(lambda) verwenden. In PyInstaller/Qt
        # kann ein statischer SingleShot mit Python-Lambda während Start/Shutdown
        # noch auf ein bereits zerstörtes Fenster zeigen und als native
        # ``access violation`` enden. Der Timer hängt jetzt als QObject-Kind am
        # MainWindow und wird beim Fenster zuverlässig mitzerstört.
        setup_timer = QTimer(win)
        setup_timer.setSingleShot(True)

        # Das Fenster wird als Vorgabewert gebunden, nicht ueber die Closure
        # geholt: beim Beenden loescht ``del win`` den Namen, und das
        # anschliessende ``app.processEvents()`` kann diesen Timer noch feuern
        # lassen. Dann griff der Rumpf auf eine geleerte Zelle - ein
        # NameError, der beim Beenden wie ein Programmfehler aussah.
        def _start_setup_assistant_safely(win=win) -> None:
            try:
                if QApplication.instance() is None:
                    return
                if getattr(win, "_is_closing", False):
                    return
                win._start_setup_assistant(force=False, db_existed_before=db_existed)
            except RuntimeError:
                logger.debug(
                    "Setup-Assistent übersprungen: MainWindow wurde bereits zerstört."
                )
            except Exception:
                logger.exception(
                    "Setup-Assistent konnte verzögert nicht gestartet werden"
                )
            finally:
                try:
                    setup_timer.deleteLater()
                except Exception:
                    pass

        setup_timer.timeout.connect(_start_setup_assistant_safely)
        setup_timer.start(350)

        try:
            win.schedule_startup_update_check(delay_ms=4000)
        except Exception:
            logger.exception("Startup-Update-Check konnte nicht geplant werden")

        try:
            win.schedule_unclean_shutdown_prompt(previous_unclean_state, delay_ms=1500)
        except Exception:
            logger.exception("Crash-/Diagnosehinweis konnte nicht geplant werden")

        try:
            win.schedule_onedrive_warning(delay_ms=2500)
        except (OSError, RuntimeError, ValueError, TypeError):
            logger.exception("OneDrive-Hinweis konnte nicht geplant werden")

        rc = app.exec()

        # ── Cleanup (Reihenfolge kritisch für PyInstaller!) ────
        # Qt-Objekte müssen vor QApplication zerstört werden,
        # sonst Segfault beim nächsten Start (stale _MEIPASS refs).
        if encrypted_session:
            encrypted_session.close()

        try:
            single_lock.release()
        except Exception:
            pass

        # LRU-Caches mit Qt-Objekten leeren
        try:
            from utils.icons import get_icon

            get_icon.cache_clear()
        except Exception as e:
            logging.getLogger(__name__).debug(
                "Icon-Cache-Clear beim Shutdown fehlgeschlagen: %s", e
            )

        # MainWindow explizit zerstören vor QApplication – aber den normalen
        # closeEvent-Pfad hier NICHT noch einmal auslösen. Wenn app.exec() durch
        # QApplication.quit() beendet wurde (z.B. nach Konto-Restore/Updater),
        # kann ein nachträgliches win.close() sonst nochmals Settings/Bridge/
        # Budget speichern und damit gerade wiederhergestellte Daten mit dem
        # alten In-Memory-Stand überschreiben. Bei einem normalen Fenster-X ist
        # closeEvent bereits vor dem Verlassen der Eventloop gelaufen.
        try:
            win.hide()
            win.deleteLater()
            app.processEvents()
        except RuntimeError:
            logger.debug("MainWindow war beim Shutdown bereits zerstört.")
        del win

        # QApplication sauber beenden
        del app

        import gc

        gc.collect()

        try:
            mark_app_exited(
                clean=(rc == 0), reason=f"qt_exit_{rc}", version=APP_VERSION
            )
        except Exception:
            logger.debug(
                "Runtime-State konnte beim Shutdown nicht geschrieben werden",
                exc_info=True,
            )

        return rc

    except Exception as exc:
        try:
            if "mark_app_exited" in locals():
                mark_app_exited(clean=False, reason=f"startup_error: {exc}")
        except Exception:
            pass
        try:
            if "single_lock" in locals():
                single_lock.release()
        except Exception:
            pass
        logger.critical("FEHLER BEIM STARTEN DES BUDGETMANAGERS", exc_info=True)

        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance():
                QMessageBox.critical(
                    None,
                    tr("auto.main.410_startfehler_1a2ebad1"),
                    trf(
                        "auto.main.411_budgetmanager_konnte_nicht_gestarte_8ae862ce",
                        value_0=(exc),
                    ),
                )
        except Exception as ui_exc:
            logger.critical("Fehler beim Anzeigen des Startfehler-Dialogs: %s", ui_exc)

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
