from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QRadioButton, QButtonGroup, QGroupBox, QFrame,
    QFormLayout, QFileDialog, QMessageBox, QInputDialog,
    QStackedWidget, QTextEdit, QCheckBox,
)

from model.user_model import (
    UserModel, User,
    SECURITY_QUICK, SECURITY_PIN, SECURITY_PASSWORD,
)
from views.ui_colors import ui_colors
from utils.i18n import tr, trf


@dataclass
class StartupResult:
    user: User
    db_key: bytes


class StartupWizard(QDialog):
    """Erststart-Assistent – dreistufig.

    Reihenfolge:
      1. Kontoname eingeben
      2. Neu anlegen ODER Daten importieren
      3. Kontotyp (Sicherheitsstufe) wählen → Konto erstellen
    """

    _PAGE_NAME = 0
    _PAGE_CHOICE = 1
    _PAGE_SECURITY = 2

    def __init__(self, parent=None, *, user_model: UserModel):
        super().__init__(parent)
        self.user_model = user_model
        self.result: StartupResult | None = None
        self._import_src_path: str | None = None

        self.setWindowTitle(tr("dlg.setup_assistant"))
        self.setMinimumSize(560, 400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Title ──
        title = QLabel(tr("startup.welcome_title"))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: 700; padding: 16px 24px 8px 24px;")
        root.addWidget(title)

        # ── Stacked pages ──
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.stack.addWidget(self._build_page_name())
        self.stack.addWidget(self._build_page_choice())
        self.stack.addWidget(self._build_page_security())

        # ── Navigation bar ──
        nav = QHBoxLayout()
        nav.setContentsMargins(24, 8, 24, 16)
        nav.setSpacing(8)

        self.btn_back = QPushButton(f"◀ {tr('btn.back_step')}")
        self.btn_back.setVisible(False)
        self.btn_back.clicked.connect(self._go_back)
        nav.addWidget(self.btn_back)

        nav.addStretch(1)

        self.btn_cancel = QPushButton(tr("btn.cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        nav.addWidget(self.btn_cancel)

        self.btn_next = QPushButton(f"{tr('btn.continue')} ▶")
        self.btn_next.setDefault(True)
        self.btn_next.setMinimumWidth(110)
        self.btn_next.clicked.connect(self._go_next)
        nav.addWidget(self.btn_next)

        root.addLayout(nav)

        self._goto(self._PAGE_NAME)

    # ──────────────────────────────────────────────
    # Page builders
    # ──────────────────────────────────────────────

    def _build_page_name(self) -> QFrame:
        w = QFrame()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 8, 24, 8)
        lay.setSpacing(10)

        desc = QLabel(tr("startup.name_step_desc"))
        desc.setWordWrap(True)
        lay.addWidget(desc)

        lay.addSpacing(6)

        lay.addWidget(QLabel(tr("create_user.display_name_label")))
        self.edt_name = QLineEdit()
        self.edt_name.setPlaceholderText(tr("account.zb_christian_kraemer"))
        self.edt_name.setStyleSheet("padding: 8px; font-size: 13px;")
        self.edt_name.returnPressed.connect(self._go_next)
        lay.addWidget(self.edt_name)

        lay.addStretch(1)
        return w

    def _build_page_choice(self) -> QFrame:
        w = QFrame()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 8, 24, 8)
        lay.setSpacing(12)

        desc = QLabel(tr("startup.choice_step_desc"))
        desc.setWordWrap(True)
        lay.addWidget(desc)

        lay.addSpacing(6)

        self.btn_choose_new = QPushButton(tr("startup.btn_create_user"))
        self.btn_choose_new.setMinimumHeight(48)
        self.btn_choose_new.setStyleSheet(
            "QPushButton { font-size: 13px; font-weight: bold; }"
        )
        self.btn_choose_new.clicked.connect(self._choose_new)
        lay.addWidget(self.btn_choose_new)

        self.btn_choose_import = QPushButton(tr("lbl.daten_uebernehmen_importrestore"))
        self.btn_choose_import.setMinimumHeight(48)
        self.btn_choose_import.setStyleSheet("QPushButton { font-size: 13px; }")
        self.btn_choose_import.clicked.connect(self._choose_import)
        lay.addWidget(self.btn_choose_import)

        lay.addStretch(1)
        return w

    def _build_page_security(self) -> QFrame:
        w = QFrame()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 8, 24, 8)
        lay.setSpacing(10)

        desc = QLabel(tr("startup.security_step_desc"))
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # Security group
        gb = QGroupBox(tr("create_user.security_level"))
        gb_lay = QVBoxLayout(gb)
        self.btn_group = QButtonGroup(self)

        self.rb_quick = QRadioButton(tr("radio.security_quick"))
        self.rb_quick.setToolTip(tr("create_user.quick_tooltip"))
        self.btn_group.addButton(self.rb_quick)
        gb_lay.addWidget(self.rb_quick)

        self.rb_pin = QRadioButton(tr("radio.security_pin"))
        self.rb_pin.setToolTip(tr("create_user.pin_tooltip"))
        self.btn_group.addButton(self.rb_pin)
        gb_lay.addWidget(self.rb_pin)

        self.rb_pw = QRadioButton(tr("radio.security_password"))
        self.rb_pw.setToolTip(tr("create_user.pw_tooltip"))
        self.btn_group.addButton(self.rb_pw)
        gb_lay.addWidget(self.rb_pw)

        self.rb_quick.setChecked(True)
        lay.addWidget(gb)

        # Secret input (shown for PIN / Password)
        self.secret_frame = QFrame()
        sf_lay = QFormLayout(self.secret_frame)
        sf_lay.setContentsMargins(0, 0, 0, 0)

        self.edt_secret = QLineEdit()
        self.edt_secret.setStyleSheet("padding: 6px;")
        self.lbl_secret = QLabel("PIN:")
        sf_lay.addRow(self.lbl_secret, self.edt_secret)

        self.edt_secret2 = QLineEdit()
        self.edt_secret2.setStyleSheet("padding: 6px;")
        self.lbl_secret2 = QLabel(tr("create_user.pin_repeat_label"))
        sf_lay.addRow(self.lbl_secret2, self.edt_secret2)

        self.secret_frame.setVisible(False)
        lay.addWidget(self.secret_frame)

        # Warning label
        self.lbl_warn = QLabel()
        self.lbl_warn.setWordWrap(True)
        self.lbl_warn.setStyleSheet("font-size: 11px; padding: 5px;")
        lay.addWidget(self.lbl_warn)

        lay.addStretch(1)

        self.btn_group.buttonToggled.connect(self._on_security_changed)
        self._on_security_changed()
        return w

    # ──────────────────────────────────────────────
    # Navigation
    # ──────────────────────────────────────────────

    def _goto(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        self.btn_back.setVisible(idx > self._PAGE_NAME)

        if idx == self._PAGE_CHOICE:
            # Choice page: "Next" is hidden – user must click one of the two choice buttons
            self.btn_next.setVisible(False)
        elif idx == self._PAGE_SECURITY:
            self.btn_next.setText(tr("btn.finish"))
            self.btn_next.setVisible(True)
        else:
            self.btn_next.setText(f"{tr('btn.continue')} ▶")
            self.btn_next.setVisible(True)

    def _go_next(self) -> None:
        page = self.stack.currentIndex()
        if page == self._PAGE_NAME:
            if not self.edt_name.text().strip():
                QMessageBox.warning(self, tr("msg.info"), tr("account.bitte_einen_namen_eingeben"))
                self.edt_name.setFocus()
                return
            self._goto(self._PAGE_CHOICE)
        elif page == self._PAGE_SECURITY:
            self._finish()

    def _go_back(self) -> None:
        page = self.stack.currentIndex()
        if page == self._PAGE_CHOICE:
            self._goto(self._PAGE_NAME)
        elif page == self._PAGE_SECURITY:
            self._import_src_path = None
            self._goto(self._PAGE_CHOICE)

    # ──────────────────────────────────────────────
    # Choice handlers
    # ──────────────────────────────────────────────

    def _choose_new(self) -> None:
        self._import_src_path = None
        self._goto(self._PAGE_SECURITY)

    def _choose_import(self) -> None:
        src_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("lbl.backup_auswaehlen"),
            str(Path.home()),
            "Budgetmanager Backups (*.bmr *.enc *.db)"
        )
        if not src_path:
            return

        name = self.edt_name.text().strip()

        # Quick-Account mit eingegebenem Namen erstellen (kein Passwort)
        try:
            user, _ = self.user_model.create_user(name, SECURITY_QUICK, "")
        except (ValueError, ImportError) as e:
            QMessageBox.critical(self, tr("msg.error"), str(e))
            return

        db_key = user.get_db_key("")

        # Daten aus Backup einspielen (fragt ggf. nach Restore-Key)
        try:
            self._restore_into_user(Path(src_path), user, db_key)
        except Exception as exc:
            QMessageBox.critical(self, tr("msg.error"), trf("startup.import_failed", exc=str(exc)))
            return

        QMessageBox.information(self, tr("startup.import_title"), tr("startup.import_success"))
        self.result = StartupResult(user=user, db_key=db_key)
        self.accept()

    # ──────────────────────────────────────────────
    # Security section
    # ──────────────────────────────────────────────

    def _on_security_changed(self) -> None:
        is_quick = self.rb_quick.isChecked()
        is_pin = self.rb_pin.isChecked()
        self.secret_frame.setVisible(not is_quick)

        c = ui_colors(self)
        if is_pin:
            self.lbl_secret.setText(tr("create_user.pin_label"))
            self.edt_secret.setEchoMode(QLineEdit.Password)
            self.edt_secret.setPlaceholderText(tr("create_user.pin_placeholder"))
            self.edt_secret.setMaxLength(8)
            self.lbl_secret2.setText(tr("create_user.pin_repeat_label"))
            self.edt_secret2.setEchoMode(QLineEdit.Password)
            self.edt_secret2.setPlaceholderText(tr("create_user.pin_repeat_placeholder"))
            self.edt_secret2.setMaxLength(8)
            self.lbl_warn.setText(tr("account.pin_oder_restorekey_verlieren"))
            self.lbl_warn.setStyleSheet(f"color: {c.negative}; font-size: 11px; padding: 5px;")
        elif not is_quick:
            self.lbl_secret.setText(tr("create_user.password_label"))
            self.edt_secret.setEchoMode(QLineEdit.Password)
            self.edt_secret.setPlaceholderText(tr("create_user.password_placeholder"))
            self.edt_secret.setMaxLength(128)
            self.lbl_secret2.setText(tr("create_user.repeat_label"))
            self.edt_secret2.setEchoMode(QLineEdit.Password)
            self.edt_secret2.setPlaceholderText(tr("create_user.password_repeat_placeholder"))
            self.edt_secret2.setMaxLength(128)
            self.lbl_warn.setText(tr("account.passwort_oder_restorekey_verlieren"))
            self.lbl_warn.setStyleSheet(f"color: {c.negative}; font-size: 11px; padding: 5px;")
        else:
            self.lbl_warn.setText(tr("account.schuetzt_vor_versehenneugier_nicht"))
            self.lbl_warn.setStyleSheet(f"color: {c.text_dim}; font-size: 11px; padding: 5px;")

    # ──────────────────────────────────────────────
    # Final step: create user (+ optional import)
    # ──────────────────────────────────────────────

    def _finish(self) -> None:
        name = self.edt_name.text().strip()

        if self.rb_quick.isChecked():
            security = SECURITY_QUICK
            secret = ""
        elif self.rb_pin.isChecked():
            security = SECURITY_PIN
            secret = self.edt_secret.text()
            if not secret.isdigit() or not (4 <= len(secret) <= 8):
                QMessageBox.warning(self, tr("msg.info"), tr("account.pin_length"))
                return
            if secret != self.edt_secret2.text():
                QMessageBox.warning(self, tr("msg.info"), tr("account.pins_stimmen_nicht_ueberein"))
                return
        else:
            security = SECURITY_PASSWORD
            secret = self.edt_secret.text()
            if len(secret) < 4:
                QMessageBox.warning(self, tr("msg.info"), tr("account.password_min_length"))
                return
            if secret != self.edt_secret2.text():
                QMessageBox.warning(self, tr("msg.info"), tr("account.passwoerter_stimmen_nicht_ueberein"))
                return

        try:
            user, restore_key = self.user_model.create_user(name, security, secret)
        except (ValueError, ImportError) as e:
            QMessageBox.critical(self, tr("msg.error"), str(e))
            return

        db_key = user.get_db_key(secret)

        # Show restore key dialog (only for PIN / Password)
        if restore_key:
            if not self._show_restore_key(restore_key, user):
                return  # user closed dialog without confirming

        # Import / Restore if requested
        if self._import_src_path:
            try:
                self._restore_into_user(Path(self._import_src_path), user, db_key)
            except Exception as exc:
                QMessageBox.critical(self, tr("msg.error"), trf("startup.import_failed", exc=str(exc)))
                return
            QMessageBox.information(self, tr("startup.import_title"), tr("startup.import_success"))

        self.result = StartupResult(user=user, db_key=db_key)
        self.accept()

    def _show_restore_key(self, key: str, user: User) -> bool:
        """Zeigt den Restore-Key und verlangt Bestätigung. Gibt True zurück wenn bestätigt."""
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("dlg.restore_key_note"))
        dlg.setMinimumSize(480, 380)
        layout = QVBoxLayout(dlg)

        c = ui_colors(dlg)
        layout.addWidget(QLabel(trf("dlg.restore_key_intro", color=c.negative)))

        key_box = QTextEdit()
        key_box.setPlainText(key)
        key_box.setReadOnly(True)
        key_box.setStyleSheet(
            f"font-family: 'Consolas', 'Courier New', monospace; "
            f"font-size: 14px; padding: 10px; background: {c.bg_panel}; "
            f"border: 2px solid {c.negative}; letter-spacing: 1px;"
        )
        key_box.setMaximumHeight(80)
        key_box.selectAll()
        layout.addWidget(key_box)

        layout.addWidget(QLabel(tr("dlg.restore_key_copy_note")))

        chk = QCheckBox(tr("chk.restore_key_noted"))
        chk.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(chk)

        btn_ok = QPushButton(tr("btn.continue"))
        btn_ok.setEnabled(False)
        btn_ok.setStyleSheet(f"""
            QPushButton {{ padding: 10px; background: {c.ok}; color: white;
                           border: none; border-radius: 5px; font-weight: bold; }}
            QPushButton:disabled {{ background: {c.border}; color: {c.text_dim}; }}
        """)
        chk.toggled.connect(btn_ok.setEnabled)
        btn_ok.clicked.connect(dlg.accept)
        layout.addWidget(btn_ok)

        accepted = dlg.exec() == QDialog.Accepted
        if accepted:
            try:
                self.user_model._users[user.username].restore_key_offered = True
                self.user_model._save()
            except Exception as e:
                logger.warning("restore_key_offered konnte nicht gesetzt werden: %s", e)
        return accepted

    # ──────────────────────────────────────────────
    # Import / Restore helpers (unchanged)
    # ──────────────────────────────────────────────

    def _restore_into_user(self, src: Path, user: User, db_key: bytes) -> None:
        """Schreibt ein Backup in die DB-Datei des neu angelegten Users."""
        src = Path(src)
        if not src.exists():
            raise FileNotFoundError(str(src))

        # .bmr extrahieren
        if src.suffix.lower() == ".bmr":
            src = self._extract_bmr_to_temp(src)

        dest_enc = user.db_path
        dest_enc.parent.mkdir(parents=True, exist_ok=True)

        if src.suffix.lower() == ".db":
            self._import_db_to_enc(src, dest_enc, db_key, user.salt)
            return

        if src.suffix.lower() == ".enc":
            from model.crypto import decrypt_db_from_file, encrypt_db_to_file, restore_key_to_db_key

            try:
                test = decrypt_db_from_file(src, db_key)
                test.close()
                dest_enc.write_bytes(src.read_bytes())
                return
            except Exception as e:
                logger.warning("DB-Kopie im StartupWizard fehlgeschlagen: %s", e)

            last_exc: Exception | None = None
            for attempt in range(3):
                restore_key = self._ask_restore_key()
                if not restore_key:
                    raise ValueError(tr("startup.restore_aborted_no_key"))
                try:
                    other_key = restore_key_to_db_key(restore_key)
                    tmp_conn = decrypt_db_from_file(src, other_key)
                    try:
                        encrypt_db_to_file(tmp_conn, dest_enc, db_key, user.salt)
                    finally:
                        tmp_conn.close()
                    return
                except Exception as exc:
                    last_exc = exc
                    if attempt < 2:
                        QMessageBox.warning(self, tr("msg.info"), f"Bitte erneut versuchen.\n\n{exc}")
            raise ValueError(trf("dlg.entschluesselung_mit_restorekey_fehlgeschlagen"))

        raise ValueError(f"Unbekanntes Format: {src.name}")

    def _import_db_to_enc(self, src_db: Path, dest_enc: Path, db_key: bytes, salt: bytes) -> None:
        import sqlite3
        from model.crypto import encrypt_db_to_file

        try:
            ro_uri = f"file:{src_db.as_posix()}?mode=ro"
            src_conn = sqlite3.connect(ro_uri, uri=True)
        except Exception:
            src_conn = sqlite3.connect(str(src_db))

        try:
            dump_sql = "\n".join(src_conn.iterdump())
        finally:
            src_conn.close()

        mem_conn = sqlite3.connect(":memory:")
        mem_conn.executescript(dump_sql)
        mem_conn.execute("PRAGMA foreign_keys = ON;")
        mem_conn.execute("PRAGMA busy_timeout = 5000;")

        try:
            encrypt_db_to_file(mem_conn, dest_enc, db_key, salt)
        finally:
            mem_conn.close()

    def _ask_restore_key(self) -> str | None:
        msg = tr("startup.restore_key_prompt")
        key, ok = QInputDialog.getText(self, tr("startup.restore_key_title"), msg)
        if not ok:
            return None
        key = (key or "").strip()
        return key or None

    def _extract_bmr_to_temp(self, bundle_path: Path) -> Path:
        import json
        import zipfile
        tmp_dir = Path(bundle_path).parent / "_tmp_restore"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(bundle_path, "r") as zf:
            names = set(zf.namelist())
            if "manifest.json" not in names:
                raise ValueError(tr("dlg.ungueltiges_bmr_manifestjson_fehlt"))
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            db_file = manifest.get("db_file")
            if not db_file or db_file not in names:
                if "database.enc" in names:
                    db_file = "database.enc"
                elif "database.db" in names:
                    db_file = "database.db"
                else:
                    raise ValueError(tr("dlg.ungueltiges_bmr_keine_datenbankdatei"))

            suffix = ".enc" if db_file.endswith(".enc") else ".db"
            out = tmp_dir / f"startup_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}"
            with open(out, "wb") as f:
                f.write(zf.read(db_file))
        return out
