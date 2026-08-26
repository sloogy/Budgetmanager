from __future__ import annotations

import logging
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from model.app_paths import configured_backups_dir
from model.file_permissions import secure_dir, secure_file
from utils.accessibility import configure_dialog_tab_order
from utils.icons import get_icon
from utils.notifications import show_info, show_warning

logger = logging.getLogger(__name__)


BMR_EXT = ".bmr"  # BudgetManager Restore Bundle (zip)


class BackupRestoreDialog(QDialog):
    def __init__(
        self,
        parent,
        conn: sqlite3.Connection,
        db_path: str | None,
        settings=None,
        encrypted_session=None,
        *,
        active_user=None,
    ):
        super().__init__(parent)
        self.conn = conn
        self.db_path = db_path  # unverschlüsselte File-DB (legacy)
        self.settings = settings
        self.encrypted_session = encrypted_session  # EncryptedSession oder None
        self.active_user = active_user  # User-Objekt (oder None)

        # Re-Authentifizierung für Export/Import/Restore: einmal pro Dialog.
        # Bleibt bei Quick-Konten wirkungslos (dort wird nie gefragt).
        self._auth_ok = False

        # Wird auf True gesetzt, wenn die aktive DB ersetzt / zurückgesetzt wurde.
        # MainWindow kann dann (optional) einen Neustart verlangen.
        self.db_changed = False

        # Wird True, wenn wir den User direkt zum Neustart führen und die App beenden.
        # MainWindow kann dann sein eigenes "Bitte neu starten"-Popup überspringen.
        self.exit_requested = False

        # Backup-Ordner aus Einstellungen oder Standard
        if settings and hasattr(settings, "backup_directory"):
            self.backup_dir = configured_backups_dir(settings.backup_directory)
        else:
            from model.app_paths import backups_dir

            self.backup_dir = backups_dir()

        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self.setWindowTitle(tr("dlg.backup_restore"))
        self.setModal(True)
        self.resize(600, 400)

        # UI Elemente
        self.btn_create_backup = QPushButton(tr("btn.create_backup"))
        self.btn_create_backup.setIcon(get_icon("💾"))
        self.btn_restore = QPushButton(tr("backup.btn_restore"))
        self.btn_restore.setIcon(get_icon("📥"))
        self.btn_export = QPushButton(tr("backup.btn_export"))
        self.btn_export.setIcon(get_icon("📤"))
        self.btn_import = QPushButton(tr("backup.btn_import"))
        self.btn_import.setIcon(get_icon("📁"))
        self.btn_delete = QPushButton(tr("btn.backup_loeschen"))
        self.btn_delete.setIcon(get_icon("🗑"))
        self.btn_close = QPushButton(tr("btn.close"))
        self.btn_close.setIcon(get_icon("✗"))

        # Liste der Backups
        self.backup_list = QListWidget()

        # Layout
        info_label = QLabel(
            trf(
                "auto.views_backup_restore_dialog.80_value_0_value_1_e0475ff7",
                value_0=(tr("backup.backup_folder")),
                value_1=(self.backup_dir),
            )
        )
        info_label.setWordWrap(True)

        # Aktiven Benutzer + DB anzeigen (damit klar ist, WAS ersetzt wird)
        if self.encrypted_session is not None:
            active_db_path = Path(self.encrypted_session.enc_path)
        else:
            active_db_path = Path(self.db_path) if self.db_path else Path("(unbekannt)")

        if self.active_user is not None:
            user_txt = f"{tr('backup.active_user')}: {getattr(self.active_user, 'display_name', '')} ({display_security_label(getattr(self.active_user, 'security', ''))})"
        else:
            user_txt = f"{tr('backup.active_user')}: {tr('backup.unencrypted')}"

        active_label = QLabel(
            trf(
                "auto.views_backup_restore_dialog.94_value_0_value_1_value_2_fd084554",
                value_0=(user_txt),
                value_1=(tr("backup.active_db")),
                value_2=(active_db_path),
            )
        )
        active_label.setWordWrap(True)

        btn_layout1 = QHBoxLayout()
        btn_layout1.addWidget(self.btn_create_backup)
        btn_layout1.addWidget(self.btn_restore)
        btn_layout1.addWidget(self.btn_delete)

        btn_layout2 = QHBoxLayout()
        btn_layout2.addWidget(self.btn_export)
        btn_layout2.addWidget(self.btn_import)
        btn_layout2.addStretch()

        layout = QVBoxLayout()
        layout.addWidget(QLabel(tr("backup.title")))
        layout.addWidget(info_label)
        layout.addWidget(active_label)
        layout.addSpacing(10)
        layout.addWidget(QLabel(tr("dlg.verfuegbare_backups")))
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
        # Schließen bedeutet: keine Änderungen an der aktiven DB → reject()
        self.btn_close.clicked.connect(self.reject)

        self.refresh_backup_list()
        configure_dialog_tab_order(self)

    def refresh_backup_list(self):
        self.backup_list.clear()

        # Alle sinnvollen Backup-Typen anzeigen (nicht nur "budgetmanager_backup_*"),
        # sonst sind z.B. "before_restore"/"pre_migration"/importierte DBs Dead-Ends.
        # In verschlüsseltem Modus sichern wir .enc, sonst .db
        if self.encrypted_session is not None:
            patterns = [
                "budgetmanager_backup_*.bmr",
                "budgetmanager_backup_*.enc",
                "budgetmanager_backup_imported_*.enc",
                "budgetmanager_backup_imported_*.db",  # Import kann auch unverschlüsselt sein
                "budgetmanager_backup_imported_*.bmr",
                "budgetmanager_before_restore_*.enc",
                "budgetmanager_before_reset_*.enc",
                "budgetmanager_pre_migration_*.enc",
            ]
        else:
            patterns = [
                "budgetmanager_backup_*.bmr",
                "budgetmanager_backup_*.db",
                "budgetmanager_backup_imported_*.db",
                "budgetmanager_backup_imported_*.bmr",
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

            item_text = (
                f"{backup.name} ({size:.1f} KB, {mod_time.strftime('%d.%m.%Y %H:%M')})"
            )
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, str(backup))
            self.backup_list.addItem(item)

        if backups:
            self.backup_list.setCurrentRow(0)

    def _require_auth(self, action: str) -> bool:
        """Code-Abfrage vor Export/Import/Restore (v2.2.10), gemeinsame
        Implementierung seit v2.2.16 (K4) in views.reauth. Eine erfolgreiche
        Eingabe gilt fuer die restliche Lebensdauer dieses Dialogs."""
        if getattr(self, "_auth_ok", False):
            return True
        from views.reauth import require_reauth

        if require_reauth(self, self.active_user, action):
            self._auth_ok = True
            return True
        return False

    def create_backup(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Ab v0.4.0: immer als Restore-Bundle (.bmr), damit es 1-Klick wiederherstellbar ist.
        backup_name = f"budgetmanager_backup_{timestamp}.bmr"
        backup_path = self.backup_dir / backup_name

        try:
            from app_info import APP_NAME, APP_VERSION
            from model.restore_bundle import create_bundle

            if self.encrypted_session is not None:
                try:
                    self.encrypted_session.save()
                except Exception as e:
                    logger.debug("%s", e)
                src = Path(self.encrypted_session.enc_path)
            else:
                src = Path(self.db_path)

            # Settings- und Benutzerdatei ermitteln. users.json gehört zum
            # Vollbackup, wird beim Restore aber nur nach ausdrücklicher Wahl
            # übernommen.
            from model.app_paths import settings_path as get_settings_path
            from model.user_model import _users_file_path

            s_path = get_settings_path()
            u_path = _users_file_path()

            create_bundle(
                source_db=src,
                out_path=backup_path,
                app=APP_NAME,
                app_version=APP_VERSION,
                note=tr("backup.manual_note"),
                settings_path=s_path if s_path.exists() else None,
                users_json_path=u_path if u_path.exists() else None,
            )

            from model.restore_bundle import bundle_has_settings, bundle_has_users

            # Nicht die Quelldatei, sondern den tatsächlichen Bundle-Inhalt
            # anzeigen. Bei Mehrbenutzer-Installationen kann users.json bewusst
            # ausgelassen werden, wenn kein eindeutig passendes Konto existiert.
            has_settings = bundle_has_settings(backup_path)
            has_users = bundle_has_users(backup_path)
            show_info(
                self,
                tr("dlg.backup_erfolg"),
                f"{tr('dlg.backup_erstellt')}\n{backup_name}"
                + (f"\n\n✓ {tr('dlg.settings_included')}" if has_settings else "")
                + (f"\n✓ {tr('dlg.users_included')}" if has_users else ""),
            )
            self.refresh_backup_list()
            # Silent cleanup for manual backups: enforce configured keep limit.
            try:
                keep_n = int(self.settings.get("auto_backup_keep", 10) or 10)
            except Exception:
                keep_n = 10
            keep_n = max(3, min(200, keep_n))

            backups = sorted(
                self.backup_dir.glob("budgetmanager_backup_*.bmr"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for old_backup in backups[keep_n:]:
                try:
                    old_backup.unlink()
                    logger.debug("Deleted old backup (manual cleanup): %s", old_backup)
                except Exception as cleanup_err:
                    logger.debug(
                        "Could not delete old backup during manual cleanup (%s): %s",
                        old_backup,
                        cleanup_err,
                    )
        except Exception as e:
            QMessageBox.critical(
                self, tr("msg.error"), trf("backup.backup_error", error=e)
            )

    def restore_backup(self):
        item = self.backup_list.currentItem()
        if not item:
            show_info(self, tr("msg.info"), tr("backup.select_backup"))
            return

        backup_path = Path(item.data(Qt.UserRole))
        self.restore_external_path(backup_path)

    def _ask_restore_options(self, backup_path: Path) -> tuple[bool, bool] | None:
        """Fragt Restore-Bestätigung und optionale Zusatzdaten ab.

        Returns:
            (restore_settings, restore_users) oder None bei Abbruch.
        """
        backup_path = Path(backup_path)
        from model.restore_bundle import bundle_has_settings, bundle_has_users

        is_bmr = backup_path.suffix.lower() == ".bmr"
        backup_has_settings = is_bmr and bundle_has_settings(backup_path)
        backup_has_users = is_bmr and bundle_has_users(backup_path)

        hints = ""
        if backup_has_settings:
            hints += f"\n\n⚙️ {tr('dlg.backup_includes_settings')}"
        if backup_has_users:
            hints += f"\n\n👤 {tr('dlg.backup_includes_users')}\n{tr('backup.users_not_restored_security_note')}"

        reply = QMessageBox.question(
            self,
            tr("dlg.restore_title"),
            tr("dlg.restore_warning") + hints,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return None

        restore_settings = False
        if backup_has_settings:
            sr = QMessageBox.question(
                self,
                tr("dlg.restore_settings_title"),
                tr("dlg.restore_settings_question"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            restore_settings = sr == QMessageBox.Yes

        restore_users = False
        if backup_has_users:
            from model.restore_bundle import bundle_user_security_modes

            modes = bundle_user_security_modes(backup_path)
            mode_note = ""
            if "quick" in modes:
                mode_note = "\n\n" + tr("dlg.restore_users_quick_warning")
            elif "pin" in modes:
                mode_note = "\n\n" + tr("dlg.restore_users_pin_warning")
            elif "password" in modes:
                mode_note = "\n\n" + tr("dlg.restore_users_password_note")

            ur = QMessageBox.question(
                self,
                tr("dlg.restore_users_title"),
                tr("dlg.restore_users_question") + mode_note,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            restore_users = ur == QMessageBox.Yes

        return restore_settings, restore_users

    def restore_external_path(self, backup_path: str | Path) -> bool:
        """Restore eines direkt ausgewählten Backups.

        Wird u.a. vom geführten Setup-Assistenten verwendet. Der Dialog muss dafür
        nicht erst als Backup-Liste geöffnet werden. Gibt True zurück, wenn die DB
        ersetzt wurde.
        """
        backup_path = Path(backup_path)
        # Restore überschreibt die aktive Datenbank → Code abfragen.
        if not self._require_auth("restore"):
            return False
        opts = self._ask_restore_options(backup_path)
        if opts is None:
            return False
        restore_settings, restore_users = opts
        before = self.db_changed
        self._restore_from_path(
            str(backup_path),
            restore_settings=restore_settings,
            restore_users=restore_users,
        )
        return bool(self.db_changed and not before or self.db_changed)

    def export_backup(self):
        item = self.backup_list.currentItem()
        if not item:
            show_info(self, tr("msg.info"), tr("backup.select_backup"))
            return

        # Export schreibt die DB (und ggf. users.json) nach aussen → Code abfragen.
        if not self._require_auth("export"):
            return

        backup_path = Path(item.data(Qt.UserRole))

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("backup.backup_export_title"),
            str(Path.home() / backup_path.name),
            tr("backup.backup_filter"),
        )

        if not file_path:
            return

        try:
            shutil.copy2(backup_path, file_path)
            show_info(
                self,
                tr("backup.import_success_title"),
                trf("msg.backup_exportiert", file_path=str(file_path)),
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("msg.error"),
                trf(
                    "auto.views_backup_restore_dialog.415_export_fehlgeschlagen_value_0_208f6ca9",
                    value_0=(e),
                ),
            )

    def import_backup(self):
        # Import kann anschliessend die aktive DB ersetzen → Code abfragen.
        if not self._require_auth("import"):
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("backup.backup_import_title"),
            str(Path.home()),
            tr("backup.backup_filter"),
        )

        if not file_path:
            return

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Standard: importierte Backups werden IMMER als .bmr abgelegt
            # (egal ob .bmr/.enc/.db), damit Restore/Export konsistent ist.
            src = Path(file_path)
            import_name = f"budgetmanager_backup_imported_{timestamp}.bmr"
            import_path = self.backup_dir / import_name

            # Wenn bereits .bmr: 1:1 kopieren, sonst in .bmr verpacken.
            if src.suffix.lower() == BMR_EXT:
                shutil.copy2(file_path, import_path)
                secure_file(import_path)
            else:
                from app_info import APP_NAME, APP_VERSION
                from model.restore_bundle import create_bundle

                create_bundle(
                    source_db=src,
                    out_path=import_path,
                    app=APP_NAME,
                    app_version=APP_VERSION,
                    note="Imported Backup",
                )

            show_info(
                self,
                tr("backup.import_success_title"),
                trf("backup.import_success", name=import_name),
            )
            self.refresh_backup_list()

            # Importiertes Backup direkt markieren
            for i in range(self.backup_list.count()):
                it = self.backup_list.item(i)
                if it and it.data(Qt.UserRole) == str(import_path):
                    self.backup_list.setCurrentRow(i)
                    break

            # Optional: gleich wiederherstellen
            if (
                QMessageBox.question(
                    self,
                    tr("backup.restore_now_title"),
                    tr("backup.restore_now_text")
                    + "\n\n"
                    + tr("dlg.die_anwendung_muss_danach"),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                == QMessageBox.Yes
            ):
                # Den normalen Restore-Flow verwenden, damit Settings-/Konto-Optionen
                # und Sicherheitswarnungen auch bei importierten Backups gelten.
                self.restore_external_path(import_path)
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("msg.error"),
                trf(
                    "auto.views_backup_restore_dialog.468_import_fehlgeschlagen_value_0_fabf2450",
                    value_0=(e),
                ),
            )

    def _restore_from_path(
        self,
        backup_path: str,
        *,
        restore_settings: bool = False,
        restore_users: bool = False,
    ) -> None:
        """Interner Helper: Restore von einem beliebigen Pfad (aus Liste, Import oder Setup)."""
        backup_path_obj = Path(backup_path)
        try:
            # Ein .bmr genau einmal vor allen schreibenden Schritten prüfen.
            # Bei bestätigten Legacy-Bundles zeigt dies auf die neu erzeugte,
            # vollständig gehashte Kopie. Dadurch werden DB, Einstellungen und
            # Konto-Metadaten garantiert aus demselben verifizierten Archiv gelesen.
            if backup_path_obj.suffix.lower() == BMR_EXT:
                backup_path_obj, _verified_db_member = self._prepare_verified_bundle(
                    backup_path_obj
                )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._create_bmr_backup(
                prefix=f"budgetmanager_before_restore_{timestamp}",
                note="Before Restore",
            )
            self._cleanup_safety_backups("budgetmanager_before_restore_*.bmr")

            if self.encrypted_session is None:
                try:
                    # Verbindung offen lassen (Restore via Backup-API),
                    # nur offene Transaktion beenden.
                    self.conn.rollback()
                except Exception as e:
                    logger.debug("self.conn.rollback(): %s", e)
            else:
                try:
                    self.encrypted_session.freeze()
                except Exception as e:
                    logger.debug("%s", e)

            if restore_users and backup_path_obj.suffix.lower() == BMR_EXT:
                self._restore_full_account_bundle(backup_path_obj)
            else:
                self._restore_to_active(str(backup_path_obj))
            self.db_changed = True

            # Optionale Zusatzdaten aus .bmr wiederherstellen.
            if backup_path_obj.suffix.lower() == BMR_EXT:
                if restore_settings:
                    from model.app_paths import settings_path as get_settings_path
                    from model.restore_bundle import extract_settings

                    if extract_settings(backup_path_obj, get_settings_path()):
                        logger.info("Settings aus Backup wiederhergestellt")
                    else:
                        logger.warning("Settings-Restore fehlgeschlagen")

                if restore_users:
                    logger.info(
                        "users.json wurde als vollständige Konto-Wiederherstellung übernommen"
                    )

            self._post_restore_prompt()
            self.accept()
        except ValueError as e:
            # Restore abgebrochen (z.B. kein/falscher Restore-Key) → Session wieder entsperren
            if self.encrypted_session is not None:
                try:
                    self.encrypted_session.unfreeze()
                except Exception as _ue:
                    logger.debug("unfreeze after error failed: %s", _ue)
            show_warning(
                self,
                tr("backup.restore_aborted_title"),
                trf("backup.restore_aborted", error=e),
            )
        except Exception as e:
            if self.encrypted_session is not None:
                try:
                    self.encrypted_session.unfreeze()
                except Exception as _ue:
                    logger.debug("unfreeze after error failed: %s", _ue)
            QMessageBox.critical(
                self, tr("msg.error"), trf("backup_restore.restore_failed", err=str(e))
            )

    def _ask_restore_key(self) -> str | None:
        """Fragt den Nutzer nach dem Restore-Key (Wiederherstellungscode).

        Wird gebraucht, wenn ein importiertes .enc nicht mit dem aktuellen Benutzer-Key
        geöffnet werden kann (z.B. Backup stammt von anderem Konto / anderer Installation).
        """
        msg = tr("backup.restore_key_text")
        key, ok = QInputDialog.getText(self, tr("backup.restore_key_dialog_title"), msg)
        if not ok:
            return None
        key = (key or "").strip()
        return key or None

    def _prepare_verified_bundle(self, bundle_path: Path) -> tuple[Path, str]:
        """Prüft Backups fail-closed und migriert bestätigte Legacy-Bundles."""
        from model.restore_bundle import (
            LegacyBundleIntegrityError,
            upgrade_legacy_bundle,
            verify_bundle,
        )

        bundle_path = Path(bundle_path)
        try:
            return bundle_path, verify_bundle(bundle_path)
        except LegacyBundleIntegrityError:
            answer = QMessageBox.warning(
                self,
                tr("backup.legacy_integrity_title"),
                tr("backup.legacy_integrity_text"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                raise LegacyBundleIntegrityError(tr("backup.legacy_integrity_rejected"))

            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            verified_copy = self.backup_dir / f"{bundle_path.stem}_verified_{stamp}.bmr"
            upgrade_legacy_bundle(bundle_path, verified_copy)
            show_info(
                self,
                tr("backup.legacy_integrity_title"),
                trf("backup.legacy_integrity_upgraded", path=verified_copy),
            )
            return verified_copy, verify_bundle(verified_copy)

    def _restore_full_account_bundle(self, bundle_path: Path) -> None:
        """Stellt DB-Datei + users.json als Konto-Backup wieder her.

        Dieser Pfad ist absichtlich getrennt vom normalen Datenbank-Restore:
        Beim normalen Restore wird eine fremde verschlüsselte DB per Restore-Key in
        den aktuell angemeldeten Benutzer re-verschlüsselt. Wenn aber users.json
        übernommen wird, muss die DB-Datei zum wiederhergestellten Benutzerkonto
        passen. Deshalb wird die DB aus dem Bundle unter ihrem ursprünglichen
        Dateinamen abgelegt und users.json erst danach atomar ersetzt.
        """
        import json
        import zipfile

        from model.app_paths import data_dir
        from model.restore_bundle import (
            MAX_DB_BYTES,
            MAX_USERS_BYTES,
            BundleIntegrityError,
            copy_member_limited,
            merge_user_snapshot_bytes,
            read_manifest_from_zip,
            read_member_limited,
            verify_open_bundle,
        )
        from model.user_model import _users_file_path

        bundle_path = Path(bundle_path)
        # SICHERHEIT (v2.2.11): Struktur, Grössen und SHA256 prüfen, BEVOR
        # users.json und die DB die aktive Installation ersetzen.
        try:
            bundle_path, verified_db_file = self._prepare_verified_bundle(bundle_path)
        except BundleIntegrityError as e:
            raise ValueError(str(e)) from e

        with zipfile.ZipFile(bundle_path, "r") as zf:
            # Nochmals auf genau dem Handle prüfen, aus dem anschliessend gelesen
            # wird. Dadurch kann ein ausgetauschtes Archiv nicht zwischen
            # Vorprüfung und Installation durchrutschen.
            db_file = verify_open_bundle(zf)
            names = set(zf.namelist())
            if "users.json" not in names:
                raise ValueError(tr("dlg.ungueltiges_bmr_usersjson_fehlt"))
            if "manifest.json" not in names:
                raise ValueError(tr("dlg.ungueltiges_bmr_manifestjson_fehlt"))

            manifest = read_manifest_from_zip(zf)
            if db_file != verified_db_file:
                raise ValueError(tr("backup_restore.bundle_changed_during_restore"))

            users_bytes = read_member_limited(zf, "users.json", MAX_USERS_BYTES)
            users_raw = json.loads(users_bytes.decode("utf-8"))
            source_name = str(manifest.get("source_db_name") or "").strip()
            if not source_name:
                users = (
                    users_raw.get("users", []) if isinstance(users_raw, dict) else []
                )
                if len(users) == 1:
                    source_name = str(dict(users[0]).get("db_filename", "")).strip()
            if not source_name:
                source_name = (
                    "budgetmanager_restored.enc"
                    if str(db_file).endswith(".enc")
                    else "budgetmanager_restored.db"
                )

            # Ein Bundle enthaelt genau eine Datenbank und darf deshalb beim
            # Konto-Restore auch genau einen passenden Benutzer aktivieren.
            users = users_raw.get("users", []) if isinstance(users_raw, dict) else []
            if not isinstance(users, list):
                raise ValueError(tr("dlg.ungueltiges_bmr_usersjson_fehlt"))
            source_basename = Path(source_name).name
            source_key = source_basename.casefold()
            matching_users = [
                entry
                for entry in users
                if isinstance(entry, dict)
                and Path(str(entry.get("db_filename") or "")).name.casefold()
                == source_key
            ]
            if len(matching_users) != 1:
                raise ValueError(tr("backup_restore.account_bundle_user_mismatch"))
            # Pfad-Sicherheit: kein Pfad aus dem Backup darf aus data_dir ausbrechen.
            source_name = Path(source_name).name
            # SICHERHEIT (v2.2.11): Der Name stammt aus dem Backup. Ohne
            # Endungs-Zwang könnte ein präpariertes Bundle die DB-Bytes über
            # users.json oder settings.json schreiben.
            expected_suffix = ".enc" if str(db_file).endswith(".enc") else ".db"
            if not source_name.lower().endswith(expected_suffix):
                source_name = f"{Path(source_name).stem or 'budgetmanager_restored'}{expected_suffix}"

            dest_db = data_dir() / source_name
            dest_users = _users_file_path()
            if dest_db.resolve() == dest_users.resolve():
                raise ValueError(tr("dlg.ungueltiges_bmr_keine_datenbankdatei"))
            dest_db.parent.mkdir(parents=True, exist_ok=True)
            dest_users.parent.mkdir(parents=True, exist_ok=True)

            # Bestehende lokale Konten erhalten. Nur ein exakt identisches Konto
            # (Benutzername + DB-Datei) wird durch seinen Backup-Stand ersetzt.
            existing_users_bytes = None
            if dest_users.exists():
                if dest_users.stat().st_size > MAX_USERS_BYTES:
                    raise ValueError(tr("backup_restore.local_users_too_large"))
                existing_users_bytes = dest_users.read_bytes()
            try:
                users_bytes = merge_user_snapshot_bytes(
                    existing_users_bytes,
                    users_bytes,
                    source_db_name=source_name,
                )
            except ValueError as exc:
                logger.warning(
                    "Konto-Snapshot konnte nicht zusammengeführt werden: %s", exc
                )
                raise ValueError(
                    tr("backup_restore.account_bundle_merge_failed")
                ) from exc

            tmp_db = dest_db.with_suffix(dest_db.suffix + ".restore_tmp")
            tmp_users = dest_users.with_suffix(".restore_tmp")
            rollback_db = dest_db.with_suffix(dest_db.suffix + ".restore_rollback")
            rollback_users = dest_users.with_suffix(
                dest_users.suffix + ".restore_rollback"
            )
            db_had_old = dest_db.exists()
            users_had_old = dest_users.exists()
            db_installed = False
            users_installed = False
            try:
                copy_member_limited(zf, db_file, tmp_db, MAX_DB_BYTES)
                tmp_users.write_bytes(users_bytes)
                secure_file(tmp_db)
                secure_file(tmp_users)

                rollback_db.unlink(missing_ok=True)
                rollback_users.unlink(missing_ok=True)
                if db_had_old:
                    os.replace(str(dest_db), str(rollback_db))
                if users_had_old:
                    os.replace(str(dest_users), str(rollback_users))
                try:
                    os.replace(str(tmp_db), str(dest_db))
                    db_installed = True
                    os.replace(str(tmp_users), str(dest_users))
                    users_installed = True
                    secure_file(dest_db)
                    secure_file(dest_users)
                except Exception:
                    # Beide Dateien als untrennbare Einheit zurückrollen.
                    if users_installed:
                        dest_users.unlink(missing_ok=True)
                    if db_installed:
                        dest_db.unlink(missing_ok=True)
                    if db_had_old and rollback_db.exists():
                        os.replace(str(rollback_db), str(dest_db))
                    if users_had_old and rollback_users.exists():
                        os.replace(str(rollback_users), str(dest_users))
                    raise

                rollback_db.unlink(missing_ok=True)
                rollback_users.unlink(missing_ok=True)
                self._full_account_restore = True
                logger.info(
                    "Vollständiges Konto-Backup transaktional wiederhergestellt: %s + users.json",
                    dest_db,
                )
            finally:
                tmp_db.unlink(missing_ok=True)
                tmp_users.unlink(missing_ok=True)
                # Rollback-Dateien nur entfernen, wenn die aktiven Ziele vorhanden sind.
                if dest_db.exists() and dest_users.exists():
                    rollback_db.unlink(missing_ok=True)
                    rollback_users.unlink(missing_ok=True)

    def _restore_to_active(self, backup_path: str) -> None:
        """Kopiert/konvertiert ein Backup in die aktive DB.

        - Legacy: .db wird direkt nach self.db_path kopiert
        - Encrypted: .enc wird nach enc_path kopiert
        - Encrypted + Import .db: .db wird in Memory geladen und als .enc neu verschlüsselt gespeichert
        """
        src = Path(backup_path)

        # Restore-Bundle (.bmr) → DB-Datei extrahieren und dann normal weiter.
        if src.suffix.lower() == BMR_EXT:
            extracted = self._extract_bmr_to_temp(src)
            try:
                return self._restore_to_active(str(extracted))
            finally:
                try:
                    extracted.unlink(missing_ok=True)
                except Exception as e:
                    logger.debug("%s", e)
        if self.encrypted_session is None:
            # Legacy: Backup über die SQLite-Backup-API direkt in die LIVE-Connection
            # zurückspielen. Vorteile gegenüber dem früheren File-Copy:
            #   1. Die Haupt-Connection der App bleibt gültig (vorher: geschlossene
            #      Connection → "Cannot operate on a closed database" bei jedem Klick,
            #      wenn der Nutzer den Neustart ablehnte).
            #   2. WAL wird korrekt behandelt — beim File-Copy konnten zurückgebliebene
            #      -wal/-shm Dateien beim nächsten Start ALTE Daten über die
            #      wiederhergestellte DB spielen (Datenkorruption).
            #   3. Atomar auf Seitenebene, kein Zeitfenster mit halber Datei.
            import sqlite3 as _sqlite3

            try:
                # Der Pfad muss prozentkodiert werden, bevor er in eine URI
                # geht: Ein #, ? oder % im Namen aendert sonst die Bedeutung -
                # alles ab # gilt als Fragment, alles ab ? als Abfrage, und
                # ein % leitet eine Escape-Sequenz ein. read_only_uri erledigt
                # zugleich die Windows-Umsetzung von C:\... nach ///C:/...
                from utils.sqlite_uri import read_only_uri

                src_conn = _sqlite3.connect(read_only_uri(src), uri=True)
            except Exception:
                src_conn = _sqlite3.connect(str(src))
            try:
                src_conn.backup(self.conn)
            finally:
                src_conn.close()
            return

        # encrypted mode
        dest_enc = Path(self.encrypted_session.enc_path)
        if src.suffix.lower() == ".enc":
            # Falls das Backup von *diesem* User stammt, passt der Key → 1:1 Copy.
            # Wenn nicht, fragen wir nach dem Restore-Key und re-verschlüsseln.
            from model.crypto import (
                decrypt_db_from_file,
                encrypt_db_to_file,
                restore_key_to_db_key,
            )

            try:
                test_conn = decrypt_db_from_file(src, self.encrypted_session.db_key)
                test_conn.close()
                self._atomic_copy(src, dest_enc)
                return
            except Exception:
                # anderer Key → Restore-Key nötig
                last_exc: Exception | None = None
                for attempt in range(3):
                    restore_key = self._ask_restore_key()
                    if not restore_key:
                        raise ValueError(tr("backup.restore_cancelled"))
                    try:
                        other_key = restore_key_to_db_key(restore_key)
                        tmp_conn = decrypt_db_from_file(src, other_key)
                        try:
                            # in das aktive User-Format re-verschlüsseln
                            encrypt_db_to_file(
                                tmp_conn,
                                dest_enc,
                                self.encrypted_session.db_key,
                                self.encrypted_session.salt,
                            )
                        finally:
                            tmp_conn.close()
                        return
                    except Exception as exc:
                        last_exc = exc
                        if attempt < 2:
                            show_warning(
                                self,
                                tr("dlg.restorekey_ungueltig"),
                                "Der Restore-Key konnte nicht verwendet werden.\n\n"
                                f"{exc}\n\n" + tr("dlg.bitte_erneut_versuchen"),
                            )
                        else:
                            break
                raise ValueError(
                    trf(
                        "dlg.entschluesselung_mit_restorekey_fehlgeschlagen",
                        last_exc=str(last_exc),
                    )
                )

        if src.suffix.lower() == ".db":
            # unverschlüsselte DB importieren → verschlüsselt speichern (ersetzt aktive)
            import sqlite3

            from model.crypto import encrypt_db_to_file

            # Quelle öffnen (read-only, wenn möglich). Pfad prozentkodieren:
            # ein #, ? oder % im Namen aendert sonst die Bedeutung der URI.
            try:
                from utils.sqlite_uri import read_only_uri

                src_conn = sqlite3.connect(read_only_uri(src), uri=True)
            except Exception:
                src_conn = sqlite3.connect(str(src))

            try:
                dump_sql = "\n".join(src_conn.iterdump())
            finally:
                src_conn.close()

            mem_conn = sqlite3.connect(":memory:")
            mem_conn.row_factory = sqlite3.Row
            mem_conn.executescript(dump_sql)
            mem_conn.execute("PRAGMA foreign_keys = ON;")
            mem_conn.execute("PRAGMA busy_timeout = 10000;")

            try:
                encrypt_db_to_file(
                    mem_conn,
                    dest_enc,
                    self.encrypted_session.db_key,
                    self.encrypted_session.salt,
                )
            finally:
                mem_conn.close()
            return

        raise ValueError(f"Unbekanntes Backup-Format: {src.name}")

    def _extract_bmr_to_temp(self, bundle_path: Path) -> Path:
        """Extrahiert database.{db|enc} aus einem .bmr (zip) in eine temp-Datei.

        SICHERHEIT (v2.2.11): Vorher wird das Bundle vollständig verifiziert –
        Struktur, Grössenlimits und SHA256 gegen das Manifest. Ein manipuliertes
        oder halb übertragenes Backup darf niemals über die aktive DB laufen.
        """
        import zipfile

        from model.restore_bundle import (
            MAX_DB_BYTES,
            BundleIntegrityError,
            copy_member_limited,
            verify_open_bundle,
        )

        tmp_dir = self.backup_dir / "_tmp_restore"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        secure_dir(tmp_dir)

        try:
            bundle_path, db_file = self._prepare_verified_bundle(bundle_path)
        except BundleIntegrityError as e:
            raise ValueError(str(e)) from e

        with zipfile.ZipFile(bundle_path, "r") as zf:
            opened_db_file = verify_open_bundle(zf)
            if opened_db_file != db_file:
                raise ValueError(tr("backup_restore.bundle_changed_during_restore"))
            suffix = ".enc" if db_file.endswith(".enc") else ".db"
            out = (
                tmp_dir
                / f"restore_tmp_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{suffix}"
            )
            copy_member_limited(zf, db_file, out, MAX_DB_BYTES)
            secure_file(out)
        return out

    def _atomic_copy(self, src: Path, dest: Path) -> None:
        """Kopiert eine Datei geprüft und atomar, ohne das alte Ziel vorab zu löschen."""
        from model.restore_bundle import atomic_copy_verified

        atomic_copy_verified(Path(src), Path(dest))

    def _post_restore_prompt(self) -> None:
        """Nach erfolgreichem Restore: klar führen (Exit/Restart)."""
        if self.encrypted_session is not None:
            target = Path(self.encrypted_session.enc_path)
        else:
            target = Path(self.db_path) if self.db_path else Path("(unbekannt)")

        if self.active_user is not None:
            user_line = trf(
                "backup_restore.user_line.active",
                name=getattr(self.active_user, "display_name", ""),
                security=display_security_label(
                    getattr(self.active_user, "security", "")
                ),
            )
        else:
            user_line = tr("backup_restore.user_line.plain")

        if getattr(self, "_full_account_restore", False):
            show_info(
                self,
                tr(
                    "auto.views_backup_restore_dialog.722_neustart_erforderlich_5f2fbae8"
                ),
                tr("backup_restore.full_account_restart_required"),
            )
            self.exit_requested = True
            QApplication.quit()
            return

        if self.encrypted_session is None:
            # Legacy: Restore erfolgte direkt in die Live-Connection → kein Neustart nötig.
            show_info(
                self,
                tr("database.msg.restore_success"),
                trf(
                    "auto.views_backup_restore_dialog.706_datenbank_wurde_wiederhergestellt_v_442b01cf",
                    value_0=(user_line),
                    value_1=(target),
                ),
            )
            return

        msg = trf(
            "backup_restore.msg.restore_restart_prompt",
            user_line=user_line,
            target=target,
        )
        if (
            QMessageBox.question(
                self,
                tr(
                    "auto.views_backup_restore_dialog.722_neustart_erforderlich_5f2fbae8"
                ),
                msg,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            == QMessageBox.Yes
        ):
            self.exit_requested = True
            QApplication.quit()

    def delete_backup(self):
        item = self.backup_list.currentItem()
        if not item:
            show_info(self, tr("msg.info"), tr("backup.select_backup"))
            return

        backup_path = Path(item.data(Qt.UserRole))

        if (
            QMessageBox.question(
                self,
                tr("common.delete"),
                trf("backup_restore.delete_confirm", name=backup_path.name),
            )
            != QMessageBox.Yes
        ):
            return

        try:
            backup_path.unlink()
            self.refresh_backup_list()
        except Exception as e:
            QMessageBox.critical(
                self, tr("msg.error"), trf("msg.delete_failed_with_error", err=str(e))
            )

    # v2.2.16 (K4): Der Datenbank-Reset lebt nur noch im
    # DatabaseManagementDialog – ein Ort, eine Sicherheitsabfrage.

    # v2.2.20 (Audit-Fix A): Der 'Notfall-Reset' aus v2.2.18/19 ist entfernt.
    # Er loeschte ALLE Tabellen OHNE die Sicherheitsabfrage aus v2.2.10/16
    # ('funktioniert auch ohne Passwort'), brach damit die K4-Regel 'Reset an
    # genau EINEM Ort' und seine Tabellenliste vergass suggestion_accepted und
    # tracking_learning_state (verwaiste Lernzustaende). Der reguläre Reset im
    # DatabaseManagementDialog ist conn-basiert, funktioniert auch im
    # verschluesselten Modus und laeuft IMMER hinter require_reauth.

    def _create_bmr_backup(self, *, prefix: str, note: str) -> Path:
        """Erstellt ein restorefähiges Vollbackup (.bmr) des aktuellen Zustands.

        prefix: Dateiname ohne Endung (im backup_dir)
        Schließt automatisch settings.json und users.json ein. users.json wird
        beim Restore aber nur nach ausdrücklicher Konto-Wiederherstellung übernommen.
        """
        from app_info import APP_NAME, APP_VERSION
        from model.app_paths import settings_path as get_settings_path
        from model.restore_bundle import create_bundle
        from model.user_model import _users_file_path

        out = self.backup_dir / f"{prefix}.bmr"
        if self.encrypted_session is not None:
            try:
                self.encrypted_session.save()
            except Exception as e:
                logger.debug("%s", e)
            src = Path(self.encrypted_session.enc_path)
        else:
            src = Path(self.db_path)

        s_path = get_settings_path()
        u_path = _users_file_path()
        return create_bundle(
            source_db=src,
            out_path=out,
            app=APP_NAME,
            app_version=APP_VERSION,
            note=note,
            settings_path=s_path if s_path.exists() else None,
            users_json_path=u_path if u_path.exists() else None,
        )

    def _cleanup_safety_backups(self, pattern: str, keep: int = 3) -> None:
        """Löscht alte Safety-Backups und behält nur die neuesten `keep` Dateien."""
        try:
            files = sorted(
                self.backup_dir.glob(pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except Exception as e:
            logger.debug("Safety-Backup-Scan fehlgeschlagen (%s): %s", pattern, e)
            return

        for old_file in files[keep:]:
            try:
                old_file.unlink()
                logger.debug("Altes Safety-Backup gelöscht: %s", old_file)
            except Exception as e:
                logger.debug("Konnte Safety-Backup nicht löschen (%s): %s", old_file, e)


from utils.i18n import display_security_label, tr, trf
