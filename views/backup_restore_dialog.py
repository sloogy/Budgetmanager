from __future__ import annotations

import logging
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QMessageBox, QListWidget, QListWidgetItem, QInputDialog, QApplication
)

from model.app_paths import resolve_in_app
from utils.icons import get_icon

logger = logging.getLogger(__name__)


BMR_EXT = ".bmr"  # BudgetManager Restore Bundle (zip)


class BackupRestoreDialog(QDialog):
    def __init__(self, parent, conn: sqlite3.Connection, db_path: str | None,
                 settings=None, encrypted_session=None, *, active_user=None):
        super().__init__(parent)
        self.conn = conn
        self.db_path = db_path  # unverschlüsselte File-DB (legacy)
        self.settings = settings
        self.encrypted_session = encrypted_session  # EncryptedSession oder None
        self.active_user = active_user  # User-Objekt (oder None)

        # Wird auf True gesetzt, wenn die aktive DB ersetzt / zurückgesetzt wurde.
        # MainWindow kann dann (optional) einen Neustart verlangen.
        self.db_changed = False

        # Wird True, wenn wir den User direkt zum Neustart führen und die App beenden.
        # MainWindow kann dann sein eigenes "Bitte neu starten"-Popup überspringen.
        self.exit_requested = False
        
        # Backup-Ordner aus Einstellungen oder Standard
        if settings and hasattr(settings, 'backup_directory'):
            self.backup_dir = resolve_in_app(settings.backup_directory)
        else:
            self.backup_dir = Path.home() / "BudgetManager_Backups"
        
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
        self.btn_reset_db = QPushButton(tr("dlg.datenbank_zuruecksetzen"))
        self.btn_reset_db.setIcon(get_icon("🔄"))
        self.btn_emergency_reset = QPushButton(tr("backup.btn_emergency_reset"))
        self.btn_emergency_reset.setToolTip(
            tr("backup.emergency_tooltip")
        )
        self.btn_emergency_reset.setStyleSheet(f"color: {ui_colors(self).negative}; font-weight: bold;")
        self.btn_close = QPushButton(tr("btn.close"))
        self.btn_close.setIcon(get_icon("✗"))
        
        # Liste der Backups
        self.backup_list = QListWidget()
        
        # Layout
        info_label = QLabel(f"{tr('backup.backup_folder')}: {self.backup_dir}")
        info_label.setWordWrap(True)

        # Aktiven Benutzer + DB anzeigen (damit klar ist, WAS ersetzt wird)
        if self.encrypted_session is not None:
            active_db_path = Path(self.encrypted_session.enc_path)
        else:
            active_db_path = Path(self.db_path) if self.db_path else Path("(unbekannt)")

        if self.active_user is not None:
            user_txt = f"{tr('backup.active_user')}: {getattr(self.active_user, 'display_name', '')} ({getattr(self.active_user, 'security_label', getattr(self.active_user, 'security', ''))})"
        else:
            user_txt = f"{tr('backup.active_user')}: {tr('backup.unencrypted')}"

        active_label = QLabel(f"{user_txt}\n{tr('backup.active_db')}: {active_db_path}")
        active_label.setWordWrap(True)
        
        btn_layout1 = QHBoxLayout()
        btn_layout1.addWidget(self.btn_create_backup)
        btn_layout1.addWidget(self.btn_restore)
        btn_layout1.addWidget(self.btn_delete)
        
        btn_layout2 = QHBoxLayout()
        btn_layout2.addWidget(self.btn_export)
        btn_layout2.addWidget(self.btn_import)
        btn_layout2.addStretch()
        btn_layout2.addWidget(self.btn_reset_db)
        btn_layout2.addWidget(self.btn_emergency_reset)
        
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
        self.btn_reset_db.clicked.connect(self.reset_database)
        self.btn_emergency_reset.clicked.connect(self.emergency_reset)
        # Schließen bedeutet: keine Änderungen an der aktiven DB → reject()
        self.btn_close.clicked.connect(self.reject)
        
        self.refresh_backup_list()

        # In verschlüsseltem Modus ist "Reset" aktuell nicht unterstützt,
        # weil die DB nur in-memory existiert und wir sauber migrieren müssten.
        if self.encrypted_session is not None:
            self.btn_reset_db.setEnabled(False)
            self.btn_reset_db.setToolTip(tr("dlg.im_verschluesselten_benutzermodus_aktuell"))
    
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
            
            item_text = f"{backup.name} ({size:.1f} KB, {mod_time.strftime('%d.%m.%Y %H:%M')})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, str(backup))
            self.backup_list.addItem(item)
        
        if backups:
            self.backup_list.setCurrentRow(0)
    
    def create_backup(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Ab v0.4.0: immer als Restore-Bundle (.bmr), damit es 1-Klick wiederherstellbar ist.
        backup_name = f"budgetmanager_backup_{timestamp}.bmr"
        backup_path = self.backup_dir / backup_name
        
        try:
            from model.restore_bundle import create_bundle
            from app_info import APP_NAME, APP_VERSION

            if self.encrypted_session is not None:
                try:
                    self.encrypted_session.save()
                except Exception as e:
                    logger.debug("%s", e)
                src = Path(self.encrypted_session.enc_path)
            else:
                src = Path(self.db_path)

            # Settings-Pfad ermitteln
            from model.app_paths import settings_path as get_settings_path
            from model.user_model import _users_file_path
            s_path = get_settings_path()
            u_path = _users_file_path()
            users_json_path = u_path if u_path.exists() else None

            create_bundle(
                source_db=src,
                out_path=backup_path,
                app=APP_NAME,
                app_version=APP_VERSION,
                note=tr("backup.manual_note"),
                settings_path=s_path if s_path.exists() else None,
                users_json_path=users_json_path,
            )

            has_settings = s_path.exists()
            QMessageBox.information(
                self,
                tr("dlg.backup_erfolg"),
                f"{tr('dlg.backup_erstellt')}\n{backup_name}"
                + (f"\n\n✓ {tr('dlg.settings_included')}" if has_settings else ""),
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
                self,
                tr("msg.error"), trf("backup.backup_error", error=e)
            )
    
    def restore_backup(self):
        item = self.backup_list.currentItem()
        if not item:
            QMessageBox.information(self, tr("msg.info"), tr("backup.select_backup"))
            return
        
        backup_path = Path(item.data(Qt.UserRole))

        # Prüfen ob das Bundle Settings / users.json enthält
        from model.restore_bundle import (
            bundle_has_settings, extract_settings,
            bundle_has_users, extract_users,
        )
        is_bmr = backup_path.suffix.lower() == ".bmr"
        backup_has_settings = is_bmr and bundle_has_settings(backup_path)
        backup_has_users = is_bmr and bundle_has_users(backup_path)

        hints = ""
        if backup_has_settings:
            hints += f"\n\n⚙️ {tr('dlg.backup_includes_settings')}"
        if backup_has_users:
            hints += f"\n\n👤 {tr('dlg.backup_includes_users')}"

        reply = QMessageBox.question(
            self,
            tr("dlg.restore_title"),
            tr("dlg.restore_warning") + hints,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Settings ebenfalls wiederherstellen?
        restore_settings = False
        if backup_has_settings:
            sr = QMessageBox.question(
                self,
                tr("dlg.restore_settings_title"),
                tr("dlg.restore_settings_question"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            restore_settings = (sr == QMessageBox.Yes)

        # users.json ebenfalls wiederherstellen?
        restore_users = False
        if backup_has_users:
            ur = QMessageBox.question(
                self,
                tr("dlg.restore_users_title"),
                tr("dlg.restore_users_question"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            restore_users = (ur == QMessageBox.Yes)

        try:
            # Aktuelles Backup vor Restore (immer als .bmr, damit restorefähig)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._create_bmr_backup(prefix=f"budgetmanager_before_restore_{timestamp}", note="Before Restore")
            self._cleanup_safety_backups("budgetmanager_before_restore_*.bmr")
            
            # Legacy (File-DB): Connection schliessen, damit SQLite die Datei freigibt
            # Encrypted (In-Memory): NICHT conn.close() – das würde die ganze App-DB killen.
            if self.encrypted_session is None:
                try:
                    self.conn.close()
                except Exception as e:
                    logger.debug("self.conn.close(): %s", e)
            else:
                # Nach Restore darf Auto-Save die neue .enc nicht wieder überschreiben.
                try:
                    self.encrypted_session.freeze()
                except Exception as e:
                    logger.debug("%s", e)

            # Restore durchführen
            self._restore_to_active(str(backup_path))

            self.db_changed = True

            # Settings wiederherstellen (wenn gewünscht)
            if restore_settings and backup_has_settings:
                from model.app_paths import settings_path as get_settings_path
                settings_restored = extract_settings(backup_path, get_settings_path())
                if settings_restored:
                    logger.info("Settings aus Backup wiederhergestellt")
                else:
                    logger.warning("Settings-Restore fehlgeschlagen")

            # users.json wiederherstellen (wenn gewünscht)
            if restore_users and backup_has_users:
                from model.user_model import _users_file_path
                users_restored = extract_users(backup_path, _users_file_path())
                if users_restored:
                    logger.info("users.json aus Backup wiederhergestellt")
                else:
                    logger.warning("users.json-Restore fehlgeschlagen")

            # Klarer Flow: Neustart anbieten
            self._post_restore_prompt()
            self.accept()
        except ValueError as e:
            # Restore abgebrochen (z.B. kein/falscher Restore-Key) → Session wieder entsperren
            if self.encrypted_session is not None:
                try:
                    self.encrypted_session.unfreeze()
                except Exception as _ue:
                    logger.debug("unfreeze after error failed: %s", _ue)
            QMessageBox.warning(
                self, tr("backup.restore_aborted_title"), trf("backup.restore_aborted", error=e)
            )
        except Exception as e:
            if self.encrypted_session is not None:
                try:
                    self.encrypted_session.unfreeze()
                except Exception as _ue:
                    logger.debug("unfreeze after error failed: %s", _ue)
            QMessageBox.critical(
                self,
                tr("msg.error"), trf("backup.restore_failed", error=e)
            )
    
    def export_backup(self):
        item = self.backup_list.currentItem()
        if not item:
            QMessageBox.information(self, tr("msg.info"), tr("backup.select_backup"))
            return
        
        backup_path = Path(item.data(Qt.UserRole))
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("backup.backup_export_title"),
            str(Path.home() / backup_path.name),
            tr("backup.backup_filter")
        )
        
        if not file_path:
            return
        
        try:
            shutil.copy2(backup_path, file_path)
            QMessageBox.information(self, tr("backup.import_success_title"), trf("msg.backup_exportiert"))
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), f"Export fehlgeschlagen:\n{e}")
    
    def import_backup(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("backup.backup_import_title"),
            str(Path.home()),
            tr("backup.backup_filter")
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
            else:
                from model.restore_bundle import create_bundle
                from app_info import APP_NAME, APP_VERSION
                create_bundle(source_db=src, out_path=import_path, app=APP_NAME, app_version=APP_VERSION, note="Imported Backup")
            
            QMessageBox.information(
                self,
                tr("backup.import_success_title"), trf("backup.import_success", name=import_name)
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
                tr("backup.restore_now_title"), tr("backup.restore_now_text") + "\n\n" +
                tr("dlg.die_anwendung_muss_danach"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            ) == QMessageBox.Yes:
                # reuse restore flow, aber ohne zweite Auswahl
                self._restore_from_path(str(import_path))
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), f"Import fehlgeschlagen:\n{e}")

    def _restore_from_path(self, backup_path: str):
        """Interner Helper: Restore von einem beliebigen Pfad (aus Liste oder import)."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._create_bmr_backup(prefix=f"budgetmanager_before_restore_{timestamp}", note="Before Restore")
            self._cleanup_safety_backups("budgetmanager_before_restore_*.bmr")

            if self.encrypted_session is None:
                try:
                    self.conn.close()
                except Exception as e:
                    logger.debug("self.conn.close(): %s", e)
            else:
                try:
                    self.encrypted_session.freeze()
                except Exception as e:
                    logger.debug("%s", e)

            self._restore_to_active(str(backup_path))
            self.db_changed = True
            self._post_restore_prompt()
            self.accept()
        except ValueError as e:
            # Restore abgebrochen (z.B. kein/falscher Restore-Key) → Session wieder entsperren
            if self.encrypted_session is not None:
                try:
                    self.encrypted_session.unfreeze()
                except Exception as _ue:
                    logger.debug("unfreeze after error failed: %s", _ue)
            QMessageBox.warning(
                self, tr("backup.restore_aborted_title"), trf("backup.restore_aborted", error=e)
            )
        except Exception as e:
            if self.encrypted_session is not None:
                try:
                    self.encrypted_session.unfreeze()
                except Exception as _ue:
                    logger.debug("unfreeze after error failed: %s", _ue)
            QMessageBox.critical(self, tr("msg.error"), trf("backup_restore.restore_failed", err=str(e)))
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
            # legacy: 1:1 copy
            shutil.copy2(str(src), str(self.db_path))
            return

        # encrypted mode
        dest_enc = Path(self.encrypted_session.enc_path)
        if src.suffix.lower() == ".enc":
            # Falls das Backup von *diesem* User stammt, passt der Key → 1:1 Copy.
            # Wenn nicht, fragen wir nach dem Restore-Key und re-verschlüsseln.
            from model.crypto import decrypt_db_from_file, encrypt_db_to_file, restore_key_to_db_key

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
                            QMessageBox.warning(
                                self,
                                tr("dlg.restorekey_ungueltig"),
                                "Der Restore-Key konnte nicht verwendet werden.\n\n"
                                f"{exc}\n\n" +
                                tr("dlg.bitte_erneut_versuchen"),
                            )
                        else:
                            break
                raise ValueError(trf("dlg.entschluesselung_mit_restorekey_fehlgeschlagen"))

        if src.suffix.lower() == ".db":
            # unverschlüsselte DB importieren → verschlüsselt speichern (ersetzt aktive)
            import sqlite3
            from model.crypto import encrypt_db_to_file

            # Quelle öffnen (read-only, wenn möglich)
            try:
                ro_uri = f"file:{src.as_posix()}?mode=ro"
                src_conn = sqlite3.connect(ro_uri, uri=True)
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
            mem_conn.execute("PRAGMA busy_timeout = 5000;")

            try:
                encrypt_db_to_file(mem_conn, dest_enc, self.encrypted_session.db_key, self.encrypted_session.salt)
            finally:
                mem_conn.close()
            return

        raise ValueError(f"Unbekanntes Backup-Format: {src.name}")

    def _extract_bmr_to_temp(self, bundle_path: Path) -> Path:
        """Extrahiert database.{db|enc} aus einem .bmr (zip) in eine temp-Datei."""
        import json
        import zipfile
        tmp_dir = self.backup_dir / "_tmp_restore"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(bundle_path, "r") as zf:
            names = set(zf.namelist())
            if "manifest.json" not in names:
                raise ValueError(tr("dlg.ungueltiges_bmr_manifestjson_fehlt"))
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            db_file = manifest.get("db_file")
            if not db_file or db_file not in names:
                # Fallback: suche bekannte Namen
                if "database.enc" in names:
                    db_file = "database.enc"
                elif "database.db" in names:
                    db_file = "database.db"
                else:
                    raise ValueError(tr("dlg.ungueltiges_bmr_keine_datenbankdatei"))

            suffix = ".enc" if db_file.endswith(".enc") else ".db"
            out = tmp_dir / f"restore_tmp_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}"
            with open(out, "wb") as f:
                f.write(zf.read(db_file))
        return out

    def _atomic_copy(self, src: Path, dest: Path) -> None:
        """Kopiert eine Datei atomar (tmp → os.replace).

        Damit ist sichergestellt, dass die aktive DB-Datei *wirklich* ersetzt wird.
        """
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".restore_tmp")
        try:
            shutil.copy2(str(src), str(tmp))
            os.replace(str(tmp), str(dest))
        finally:
            try:
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
            except Exception as e:
                logger.debug("%s", e)

    def _post_restore_prompt(self) -> None:
        """Nach erfolgreichem Restore: klar führen (Exit/Restart)."""
        if self.encrypted_session is not None:
            target = Path(self.encrypted_session.enc_path)
        else:
            target = Path(self.db_path) if self.db_path else Path("(unbekannt)")

        if self.active_user is not None:
            user_line = f"Aktiver Benutzer: {getattr(self.active_user, 'display_name', '')} ({getattr(self.active_user, 'security_label', getattr(self.active_user, 'security', ''))})\n"
        else:
            user_line = "Aktiver Benutzer: (unverschlüsselte DB / kein User-Modus)\n"

        msg = (
            "Datenbank wurde wiederhergestellt.\n\n"
            f"{user_line}"
            f"Aktive DB wurde ersetzt:\n{target}\n\n"
            "WICHTIG: Damit die App die neue DB lädt, ist ein Neustart nötig.\n\n"
            "Jetzt Anwendung beenden?"
        )
        if QMessageBox.question(
            self,
            "Neustart erforderlich",
            msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        ) == QMessageBox.Yes:
            self.exit_requested = True
            QApplication.quit()
    
    def delete_backup(self):
        item = self.backup_list.currentItem()
        if not item:
            QMessageBox.information(self, tr("msg.info"), tr("backup.select_backup"))
            return
        
        backup_path = Path(item.data(Qt.UserRole))
        
        if QMessageBox.question(
            self,
            tr("common.delete"),
            trf("backup_restore.delete_confirm", name=backup_path.name)
        ) != QMessageBox.Yes:
            return
        
        try:
            backup_path.unlink()
            self.refresh_backup_list()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.delete_failed_with_error", err=str(e)))
    
    def reset_database(self):
        reply = QMessageBox.question(
            self,
            tr("dlg.datenbank_zuruecksetzen"),
            "WARNUNG: Dies löscht ALLE Daten!\n\n"
            "Die Datenbank wird auf Standard zurückgesetzt.\n"
            "Ein automatisches Backup wird erstellt.\n\n" +
            tr("dlg.moechten_sie_wirklich_fortfahren"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Nochmal nachfragen
        reply2 = QMessageBox.question(
            self,
            "Letzte Warnung",
            tr("msg.reset_bestaetigung"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply2 != QMessageBox.Yes:
            return
        
        try:
            # Backup erstellen (immer als .bmr)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._create_bmr_backup(prefix=f"budgetmanager_before_reset_{timestamp}", note="Before Reset")
            self._cleanup_safety_backups("budgetmanager_before_reset_*.bmr")
            
            # Alle Tabellen löschen (Whitelist verhindert SQL-Injection)
            # Vollständige Whitelist aller DB-Tabellen (bei Schema-Änderungen mitziehen!)
            _RESET_TABLE_WHITELIST = {
                'budget', 'budget_warnings', 'categories', 'category_tags',
                'entry_tags', 'favorites', 'fixcost_tracking',
                'recurring_transactions', 'redo_stack', 'savings_goals',
                'system_flags', 'tags', 'theme_profiles', 'tracking',
                'undo_stack',
            }
            tables = list(_RESET_TABLE_WHITELIST)
            
            for table in tables:
                if table not in _RESET_TABLE_WHITELIST:
                    logger.warning(tr("dlg.delete_uebersprungen_tabellenname_nicht"), table)
                    continue
                try:
                    self.conn.execute(f"DELETE FROM {table}")
                except Exception as e:
                    logger.debug("DELETE FROM %s: %s", table, e)
            
            self.conn.commit()

            self.db_changed = True
            
            QMessageBox.information(
                self,
                "Erfolg",
                f"Datenbank wurde zurückgesetzt.\n\n"
                f"Backup erstellt: budgetmanager_before_reset_{timestamp}.bmr\n\n"
                f"Bitte starten Sie die Anwendung neu."
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Fehler",
                f"Reset fehlgeschlagen:\n{e}"
            )

    def emergency_reset(self):
        """Notfall-Reset: Löscht ALLE Daten in der aktiven DB (Connection), funktioniert auch
        im verschlüsselten Modus, da wir direkt auf self.conn arbeiten.
        Ein Backup wird versucht, ist aber nicht zwingend.
        """
        reply = QMessageBox.critical(
            self,
            "🆘 NOTFALL-RESET",
            "WARNUNG: Dies löscht ALLE Daten (Buchungen, Budget, Kategorien, ...)!\n\n"
            "Verwende dies nur, wenn du nicht mehr auf ein Backup zugreifen kannst.\n\n"
            "Die Anwendung wird danach neu gestartet.\n\nWirklich fortfahren?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        reply2 = QMessageBox.question(
            self,
            "Letzte Bestätigung",
            "Alle Daten werden UNWIDERRUFLICH gelöscht.\nWirklich?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply2 != QMessageBox.Yes:
            return

        # Backup versuchen (optional – kann fehlschlagen wenn Session eingefroren)
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_prefix = f"budgetmanager_emergency_reset_{timestamp}"
            self._create_bmr_backup(prefix=backup_prefix, note="Emergency Reset")
            if backup_prefix.startswith("budgetmanager_before_restore_"):
                self._cleanup_safety_backups("budgetmanager_before_restore_*.bmr")
            elif backup_prefix.startswith("budgetmanager_before_reset_"):
                self._cleanup_safety_backups("budgetmanager_before_reset_*.bmr")
        except Exception as e:
            logger.warning("Notfall-Backup fehlgeschlagen (nicht kritisch): %s", e)

        # Falls Session eingefroren: wieder auftauen damit conn wieder schreibt
        if self.encrypted_session is not None:
            try:
                self.encrypted_session.unfreeze()
            except Exception as _ue:
                logger.debug("unfreeze before reset failed: %s", _ue)

        # Alle Tabellen leeren
        _RESET_TABLES = {
            "budget", "budget_warnings", "categories", "category_tags",
            "entry_tags", "favorites", "fixcost_tracking",
            "recurring_transactions", "redo_stack", "savings_goals",
            "system_flags", "tags", "theme_profiles", "tracking",
            "undo_stack",
        }
        conn = self.conn if self.encrypted_session is None else self.encrypted_session.conn
        errors = []
        for table in _RESET_TABLES:
            try:
                conn.execute(f"DELETE FROM {table}")
            except Exception as e:
                errors.append(f"{table}: {e}")
        try:
            conn.commit()
        except Exception as e:
            errors.append(f"COMMIT: {e}")

        # Bei verschlüsseltem Modus: sofort auf Disk speichern
        if self.encrypted_session is not None:
            try:
                self.encrypted_session.save()
            except Exception as e:
                errors.append(f"Save: {e}")

        # users.json löschen
        try:
            from model.user_model import _users_file_path
            users_file = _users_file_path()
            if users_file.exists():
                users_file.unlink()
                logger.info("users.json gelöscht (Notfall-Reset)")
        except Exception as e:
            errors.append(f"users.json: {e}")

        # Settings auf Standard zurücksetzen
        try:
            from model.app_paths import settings_path
            sf = settings_path()
            if sf.exists():
                sf.unlink()
                logger.info("Settings-Datei gelöscht (Notfall-Reset)")
        except Exception as e:
            errors.append(f"settings: {e}")

        self.db_changed = True
        self.exit_requested = True

        msg = "Notfall-Reset abgeschlossen. Die Anwendung wird jetzt beendet."
        if errors:
            msg += "\n\n" + tr("backup_restore.hints_title") + ":\n" + "\n".join(errors)
        QMessageBox.information(self, "Notfall-Reset", msg)
        QApplication.quit()

    def _create_bmr_backup(self, *, prefix: str, note: str) -> Path:
        """Erstellt ein restorefähiges Backup (.bmr) des aktuellen Zustands.

        prefix: Dateiname ohne Endung (im backup_dir)
        Schließt automatisch settings.json und users.json mit ein.
        """
        from model.restore_bundle import create_bundle
        from model.app_paths import settings_path as get_settings_path
        from model.user_model import _users_file_path
        from app_info import APP_NAME, APP_VERSION

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


from PySide6.QtCore import Qt
from utils.i18n import tr, trf, display_typ, db_typ_from_display
from views.ui_colors import ui_colors
