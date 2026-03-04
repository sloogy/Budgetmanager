"""
Login-Dialog für den Budgetmanager.

Startlogik:
  0 User:           → Kein Dialog, Setup-Wizard startet
  1 Quick-User:     → Direkt rein (kein Dialog)
  1 Auth-User:      → Direkt PW/PIN-Prompt (kein User-Auswahl)
  2+ Auth-User:     → User-Auswahl + PW/PIN
  Quick + Auth:     → Quick als grosser Button, Auth-Login darunter
"""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QMessageBox, QFrame, QStackedWidget,
    QWidget, QFormLayout, QRadioButton, QButtonGroup, QSpinBox,
    QTextEdit, QCheckBox, QGroupBox, QSizePolicy
)

from model.user_model import (
    UserModel, User,
    SECURITY_QUICK, SECURITY_PIN, SECURITY_PASSWORD,
    SECURITY_LABELS, SECURITY_ICONS,
)
from views.ui_colors import ui_colors
from utils.i18n import tr, trf, display_typ, db_typ_from_display


@dataclass
class LoginResult:
    """Ergebnis des Login-Dialogs."""
    user: User
    db_key: bytes


# ═════════════════════════════════════════════════════════════════
# Benutzer-Erstellen-Wizard
# ═════════════════════════════════════════════════════════════════

class CreateUserWizard(QDialog):
    """Wizard zum Erstellen eines neuen Benutzers."""

    def __init__(self, parent=None, *, user_model: UserModel,
                 is_first_user: bool = False):
        super().__init__(parent)
        self.user_model = user_model
        self.is_first_user = is_first_user
        self._created_user: User | None = None
        self._db_key: bytes | None = None
        self._restore_key: str = ""

        self.setWindowTitle(tr("dlg.login_create_user"))
        self.setMinimumSize(520, 580)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(25, 20, 25, 20)

        # Header
        h = QLabel(tr("create_user.title"))
        h.setAlignment(Qt.AlignCenter)
        hf = QFont(); hf.setPointSize(16); hf.setBold(True)
        h.setFont(hf)
        layout.addWidget(h)

        if is_first_user:
            info = QLabel(tr("create_user.first_user_info"))
            info.setAlignment(Qt.AlignCenter)
            info.setStyleSheet(f"color: {ui_colors(self).text_dim}; margin-bottom: 8px;")
            layout.addWidget(info)

        self._add_separator(layout)

        # ── Name ──
        layout.addWidget(QLabel(tr("create_user.display_name_label")))
        self.edt_name = QLineEdit()
        self.edt_name.setPlaceholderText(tr("account.zb_christian_kraemer"))
        self.edt_name.setStyleSheet("padding: 8px; font-size: 13px;")
        layout.addWidget(self.edt_name)

        layout.addSpacing(5)

        # ── Sicherheitsstufe ──
        gb = QGroupBox(tr("create_user.security_level"))
        gb_layout = QVBoxLayout(gb)

        self.btn_group = QButtonGroup(self)

        self.rb_quick = QRadioButton(tr("radio.security_quick"))
        self.rb_quick.setToolTip(tr("create_user.quick_tooltip"))
        self.btn_group.addButton(self.rb_quick)
        gb_layout.addWidget(self.rb_quick)

        self.rb_pin = QRadioButton(tr("radio.security_pin"))
        self.rb_pin.setToolTip(tr("create_user.pin_tooltip"))
        self.btn_group.addButton(self.rb_pin)
        gb_layout.addWidget(self.rb_pin)

        self.rb_pw = QRadioButton(tr("radio.security_password"))
        self.rb_pw.setToolTip(tr("create_user.pw_tooltip"))
        self.btn_group.addButton(self.rb_pw)
        gb_layout.addWidget(self.rb_pw)

        self.rb_quick.setChecked(True)
        layout.addWidget(gb)

        # ── Secret-Eingabe (für PIN/PW) ──
        self.secret_frame = QFrame()
        sf_layout = QFormLayout(self.secret_frame)
        sf_layout.setContentsMargins(0, 0, 0, 0)

        self.edt_secret = QLineEdit()
        self.edt_secret.setStyleSheet("padding: 6px;")
        self.lbl_secret = QLabel("PIN:")
        sf_layout.addRow(self.lbl_secret, self.edt_secret)

        self.edt_secret2 = QLineEdit()
        self.edt_secret2.setStyleSheet("padding: 6px;")
        self.lbl_secret2 = QLabel("Wiederholen:")
        sf_layout.addRow(self.lbl_secret2, self.edt_secret2)

        layout.addWidget(self.secret_frame)
        self.secret_frame.setVisible(False)

        # Warn-Label
        self.lbl_warn = QLabel()
        self.lbl_warn.setWordWrap(True)
        self.lbl_warn.setStyleSheet(f"color: {ui_colors(self).negative}; font-size: 11px; padding: 5px;")
        layout.addWidget(self.lbl_warn)
        self.lbl_warn.setVisible(False)

        layout.addStretch()

        # ── Buttons ──
        btn_layout = QHBoxLayout()
        if not is_first_user:
            btn_cancel = QPushButton(tr("btn.cancel"))
            btn_cancel.clicked.connect(self.reject)
            btn_layout.addWidget(btn_cancel)

        btn_layout.addStretch()

        self.btn_create = QPushButton(tr("create_user.btn_create"))
        self.btn_create.setStyleSheet("""
            QPushButton {
                padding: 10px 24px; background: #27ae60; color: white;
                border: none; border-radius: 5px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background: #219a52; }
        """)
        self.btn_create.clicked.connect(self._on_create)
        btn_layout.addWidget(self.btn_create)

        layout.addLayout(btn_layout)

        # Signals
        self.btn_group.buttonToggled.connect(self._on_security_changed)
        self._on_security_changed()

    def _add_separator(self, layout):
        line = QFrame(); line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {ui_colors(self).border};")
        layout.addWidget(line)

    def _on_security_changed(self):
        is_quick = self.rb_quick.isChecked()
        is_pin = self.rb_pin.isChecked()
        self.secret_frame.setVisible(not is_quick)

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
            self.lbl_warn.setVisible(True)
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
            self.lbl_warn.setVisible(True)
        else:
            self.lbl_warn.setText(tr("account.schuetzt_vor_versehenneugier_nicht"))
            self.lbl_warn.setStyleSheet(f"color: {ui_colors(self).text_dim}; font-size: 11px; padding: 5px;")
            self.lbl_warn.setVisible(True)

    def _on_create(self):
        name = self.edt_name.text().strip()
        if not name:
            QMessageBox.warning(self, tr("msg.info"), tr("account.bitte_einen_namen_eingeben"))
            return

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

        self._created_user = user
        self._db_key = user.get_db_key(secret)
        self._restore_key = restore_key

        # Restore-Key anzeigen (nur bei PIN/PW)
        if restore_key:
            self._show_restore_key(restore_key)
        else:
            self.accept()

    def _show_restore_key(self, key: str):
        """Zeigt den Restore-Key und verlangt Bestätigung."""
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("dlg.restore_key_note"))
        dlg.setMinimumSize(480, 380)
        layout = QVBoxLayout(dlg)

        c = ui_colors(dlg)
        layout.addWidget(QLabel(
            trf("dlg.restore_key_intro", color=c.negative)
        ))

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

        layout.addWidget(QLabel(
            tr("dlg.restore_key_copy_note")
        ))

        chk = QCheckBox(tr("chk.restore_key_noted"))
        chk.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(chk)

        btn_ok = QPushButton(tr("btn.continue"))
        btn_ok.setEnabled(False)
        btn_ok.setStyleSheet(f"""
            QPushButton {{ padding: 10px; background: {c.ok}; color: white;
                           border: none; border-radius: 5px; font-weight: bold; }}
            QPushButton:hover {{ background: {c.ok}; opacity: 0.9; }}
            QPushButton:disabled {{ background: {c.border}; color: {c.text_dim}; }}
        """)
        chk.toggled.connect(btn_ok.setEnabled)
        btn_ok.clicked.connect(dlg.accept)
        layout.addWidget(btn_ok)

        if dlg.exec() == QDialog.Accepted:
            self.user_model._users[self._created_user.username].restore_key_offered = True
            self.user_model._save()
            self.accept()

    @property
    def created_user(self) -> User | None:
        return self._created_user

    @property
    def db_key(self) -> bytes | None:
        return self._db_key


# ═════════════════════════════════════════════════════════════════
# Restore-Key Dialog
# ═════════════════════════════════════════════════════════════════

class RestoreKeyDialog(QDialog):
    """Dialog zur Eingabe des Restore-Keys."""

    def __init__(self, parent=None, *, user: User, user_model: UserModel):
        super().__init__(parent)
        self.user = user
        self.user_model = user_model
        self._db_key: bytes | None = None

        self.setWindowTitle(tr("dlg.restore_key_enter"))
        self.setMinimumSize(460, 220)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(trf("account.restorekey_fuer_buserdisplay_nameb")))

        self.edt_key = QLineEdit()
        self.edt_key.setPlaceholderText("XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX")
        self.edt_key.setStyleSheet(
            "font-family: 'Consolas', monospace; font-size: 13px; padding: 8px;"
        )
        layout.addWidget(self.edt_key)

        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton(tr("btn.cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addStretch()

        btn_ok = QPushButton(tr("account.entschluesseln"))
        btn_ok.setStyleSheet("""
            QPushButton { padding: 8px 20px; background: #e67e22; color: white;
                          border: none; border-radius: 5px; font-weight: bold; }
            QPushButton:hover { background: #d35400; }
        """)
        btn_ok.clicked.connect(self._on_restore)
        btn_layout.addWidget(btn_ok)

        layout.addLayout(btn_layout)

    def _on_restore(self):
        key_text = self.edt_key.text().strip()
        if not key_text:
            QMessageBox.warning(self, tr("msg.info"), tr("account.bitte_restorekey_eingeben"))
            return

        db_key = self.user_model.authenticate_restore(self.user.username, key_text)
        if db_key:
            self._db_key = db_key
            self.accept()
        else:
            QMessageBox.warning(self, tr("msg.info"), tr("account.ungueltiger_restorekey"))

    @property
    def db_key(self) -> bytes | None:
        return self._db_key


# ═════════════════════════════════════════════════════════════════
# Haupt-Login-Dialog
# ═════════════════════════════════════════════════════════════════

class LoginDialog(QDialog):
    """Haupt-Login-Dialog mit smartem Verhalten je nach Benutzerkonfiguration."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.user_model = UserModel()
        self.result: LoginResult | None = None

        self.setWindowTitle(tr("dlg.login"))
        self.setMinimumSize(460, 440)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(30, 20, 30, 20)

        # Header
        header = QLabel("💰 Budgetmanager")
        header.setAlignment(Qt.AlignCenter)
        hf = QFont(); hf.setPointSize(18); hf.setBold(True)
        header.setFont(hf)
        main_layout.addWidget(header)

        sub = QLabel("Deine Finanzen. Deine Kontrolle.")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"color: {ui_colors(self).text_dim}; font-size: 11px; margin-bottom: 5px;")
        main_layout.addWidget(sub)

        self._add_separator(main_layout)

        # Content area
        self.content = QVBoxLayout()
        main_layout.addLayout(self.content)

        main_layout.addStretch()

        # Footer: Benutzer hinzufügen
        self._add_separator(main_layout)
        foot = QHBoxLayout()
        btn_add = QPushButton(tr("account.benutzer_hinzufuegen"))
        btn_add.setFlat(True)
        btn_add.setStyleSheet(f"color: {ui_colors(self).accent}; font-size: 11px;")
        btn_add.clicked.connect(self._on_add_user)
        foot.addWidget(btn_add)

        foot.addStretch()

        btn_manage = QPushButton("⚙️ Verwalten")
        btn_manage.setFlat(True)
        btn_manage.setStyleSheet(f"color: {ui_colors(self).text_dim}; font-size: 11px;")
        btn_manage.clicked.connect(self._on_manage)
        foot.addWidget(btn_manage)

        main_layout.addLayout(foot)

        # Info
        info = QLabel(tr("account.alle_daten_werden_verschluesselt"))
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet(f"color: {ui_colors(self).text_dim}; font-size: 10px;")
        main_layout.addWidget(info)

        # Build UI based on current users
        self._build_content()

    def _add_separator(self, layout):
        line = QFrame(); line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {ui_colors(self).border};")
        layout.addWidget(line)

    def _clear_content(self):
        while self.content.count():
            item = self.content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

    def _build_content(self):
        self._clear_content()
        users = self.user_model.list_users()
        quick_users = self.user_model.get_quick_users()
        auth_users = self.user_model.get_auth_users()

        if len(users) == 0:
            self._build_no_users()
        elif len(users) == 1:
            self._build_single_user(users[0])
        elif quick_users and auth_users:
            self._build_mixed(quick_users, auth_users)
        else:
            self._build_multi_user(users)

    # ── Fall 0: Keine Benutzer ───────────────────
    def _build_no_users(self):
        lbl = QLabel(
            "Noch kein Benutzer eingerichtet.\n\n"
            "Erstelle einen Benutzer, um loszulegen."
        )
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"font-size: 12px; padding: 20px; color: {ui_colors(self).text_dim};")
        self.content.addWidget(lbl)

        btn = QPushButton(tr("dlg.login_create_user"))
        btn.setStyleSheet("""
            QPushButton { padding: 12px; background: #2196F3; color: white;
                          border: none; border-radius: 5px; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background: #1976D2; }
        """)
        btn.clicked.connect(self._on_first_user)
        self.content.addWidget(btn)

    # ── Fall 1: Ein einzelner Benutzer ───────────
    def _build_single_user(self, user: User):
        name_lbl = QLabel(f"{user.security_icon} {user.display_name}")
        name_lbl.setAlignment(Qt.AlignCenter)
        nf = QFont(); nf.setPointSize(14); nf.setBold(True)
        name_lbl.setFont(nf)
        self.content.addWidget(name_lbl)
        self.content.addSpacing(10)

        if user.is_quick:
            btn = QPushButton("⚡ Starten")
            btn.setStyleSheet("""
                QPushButton { padding: 14px; background: #27ae60; color: white;
                              border: none; border-radius: 5px; font-size: 15px; font-weight: bold; }
                QPushButton:hover { background: #219a52; }
            """)
            btn.clicked.connect(lambda: self._login_quick(user))
            self.content.addWidget(btn)
        else:
            prompt = "PIN:" if user.is_pin else "Passwort:"
            self.content.addWidget(QLabel(prompt))
            self.edt_single = QLineEdit()
            self.edt_single.setEchoMode(QLineEdit.Password)
            ph = "4–8 Ziffern" if user.is_pin else "Passwort eingeben…"
            self.edt_single.setPlaceholderText(ph)
            self.edt_single.setStyleSheet("padding: 10px; font-size: 13px;")
            self.edt_single.returnPressed.connect(lambda: self._login_auth(user, self.edt_single))
            self.content.addWidget(self.edt_single)

            self.content.addSpacing(8)
            btn = QPushButton("🔓 Anmelden")
            btn.setStyleSheet("""
                QPushButton { padding: 10px; background: #2196F3; color: white;
                              border: none; border-radius: 5px; font-size: 14px; font-weight: bold; }
                QPushButton:hover { background: #1976D2; }
            """)
            btn.clicked.connect(lambda: self._login_auth(user, self.edt_single))
            self.content.addWidget(btn)

            # Restore-Key Link
            btn_restore = QPushButton("🔑 Restore-Key verwenden")
            btn_restore.setFlat(True)
            btn_restore.setStyleSheet(f"color: {ui_colors(self).warning}; font-size: 11px;")
            btn_restore.clicked.connect(lambda: self._on_restore(user))
            self.content.addWidget(btn_restore)

    # ── Fall 2: Mehrere gleichartige Benutzer ────
    def _build_multi_user(self, users: list[User]):
        self.content.addWidget(QLabel(tr("account.benutzer_auswaehlen")))
        self.cmb_users = QComboBox()
        for u in users:
            self.cmb_users.addItem(f"{u.security_icon} {u.display_name}", u.username)
        self.cmb_users.setStyleSheet("padding: 6px; font-size: 13px;")
        self.cmb_users.currentIndexChanged.connect(self._on_user_selection_changed)
        self.content.addWidget(self.cmb_users)

        self.content.addSpacing(5)

        # Secret-Eingabe (wird je nach User-Typ angezeigt)
        self.multi_secret_frame = QFrame()
        sf_layout = QVBoxLayout(self.multi_secret_frame)
        sf_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_multi_prompt = QLabel("Passwort:")
        sf_layout.addWidget(self.lbl_multi_prompt)

        self.edt_multi = QLineEdit()
        self.edt_multi.setEchoMode(QLineEdit.Password)
        self.edt_multi.setStyleSheet("padding: 8px; font-size: 13px;")
        self.edt_multi.returnPressed.connect(self._on_multi_login)
        sf_layout.addWidget(self.edt_multi)

        self.content.addWidget(self.multi_secret_frame)

        self.content.addSpacing(8)

        self.btn_multi_login = QPushButton("🔓 Anmelden")
        self.btn_multi_login.setStyleSheet("""
            QPushButton { padding: 10px; background: #2196F3; color: white;
                          border: none; border-radius: 5px; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background: #1976D2; }
        """)
        self.btn_multi_login.clicked.connect(self._on_multi_login)
        self.content.addWidget(self.btn_multi_login)

        # Restore-Key Link
        self.btn_multi_restore = QPushButton("🔑 Restore-Key verwenden")
        self.btn_multi_restore.setFlat(True)
        self.btn_multi_restore.setStyleSheet(f"color: {ui_colors(self).warning}; font-size: 11px;")
        self.btn_multi_restore.clicked.connect(self._on_multi_restore)
        self.content.addWidget(self.btn_multi_restore)

        # Initial update
        self._on_user_selection_changed()

    def _on_user_selection_changed(self):
        if not hasattr(self, 'cmb_users'):
            return
        username = self.cmb_users.currentData()
        user = self.user_model.get(username)
        if not user:
            return

        if user.is_quick:
            self.multi_secret_frame.setVisible(False)
            self.btn_multi_login.setText("⚡ Starten")
            self.btn_multi_restore.setVisible(False)
        else:
            self.multi_secret_frame.setVisible(True)
            self.lbl_multi_prompt.setText("PIN:" if user.is_pin else "Passwort:")
            ph = "4–8 Ziffern" if user.is_pin else "Passwort eingeben…"
            self.edt_multi.setPlaceholderText(ph)
            self.edt_multi.clear()
            self.btn_multi_login.setText("🔓 Anmelden")
            self.btn_multi_restore.setVisible(True)

    # ── Fall 3: Quick + Auth gemischt ────────────
    def _build_mixed(self, quick_users: list[User], auth_users: list[User]):
        # Quick-Benutzer als grosse Buttons
        for u in quick_users:
            btn = QPushButton(f"⚡ {u.display_name}")
            btn.setStyleSheet("""
                QPushButton { padding: 14px; background: #27ae60; color: white;
                              border: none; border-radius: 5px; font-size: 14px; font-weight: bold; }
                QPushButton:hover { background: #219a52; }
            """)
            btn.clicked.connect(lambda checked, user=u: self._login_quick(user))
            self.content.addWidget(btn)

        self.content.addSpacing(10)
        self._add_separator(self.content)
        self.content.addSpacing(5)

        # Auth-Benutzer: Login-Bereich
        if len(auth_users) == 1:
            u = auth_users[0]
            lbl = QLabel(f"{u.security_icon} {u.display_name}")
            lbl.setStyleSheet("font-weight: bold;")
            self.content.addWidget(lbl)

            prompt = "PIN:" if u.is_pin else "Passwort:"
            self.content.addWidget(QLabel(prompt))
            self.edt_mixed = QLineEdit()
            self.edt_mixed.setEchoMode(QLineEdit.Password)
            self.edt_mixed.setStyleSheet("padding: 8px;")
            self.edt_mixed.returnPressed.connect(lambda: self._login_auth(u, self.edt_mixed))
            self.content.addWidget(self.edt_mixed)

            btn = QPushButton("🔓 Anmelden")
            btn.setStyleSheet("""
                QPushButton { padding: 8px; background: #2196F3; color: white;
                              border: none; border-radius: 5px; font-weight: bold; }
                QPushButton:hover { background: #1976D2; }
            """)
            btn.clicked.connect(lambda: self._login_auth(u, self.edt_mixed))
            self.content.addWidget(btn)
        else:
            # Mehrere Auth-User: Dropdown
            self._build_multi_user(auth_users)

    # ── Login-Aktionen ───────────────────────────

    def _login_quick(self, user: User):
        db_key = self.user_model.authenticate_quick(user.username)
        if db_key:
            self.result = LoginResult(user=user, db_key=db_key)
            self.accept()
        else:
            QMessageBox.critical(self, tr("msg.error"), tr("account.quick_login_failed"))

    def _login_auth(self, user: User, edt: QLineEdit):
        secret = edt.text()
        if not secret:
            QMessageBox.warning(self, "Hinweis",
                                "PIN eingeben." if user.is_pin else "Passwort eingeben.")
            return

        db_key = self.user_model.authenticate(user.username, secret)
        if db_key:
            self.result = LoginResult(user=user, db_key=db_key)
            self.accept()
        else:
            QMessageBox.warning(self, tr("msg.login_failed"),
                                "Falsche PIN." if user.is_pin else "Falsches Passwort.")
            edt.clear()
            edt.setFocus()

    def _on_multi_login(self):
        if not hasattr(self, 'cmb_users'):
            return
        username = self.cmb_users.currentData()
        user = self.user_model.get(username)
        if not user:
            return

        if user.is_quick:
            self._login_quick(user)
        else:
            self._login_auth(user, self.edt_multi)

    def _on_restore(self, user: User):
        dlg = RestoreKeyDialog(self, user=user, user_model=self.user_model)
        if dlg.exec() == QDialog.Accepted and dlg.db_key:
            self.result = LoginResult(user=user, db_key=dlg.db_key)
            self.accept()

    def _on_multi_restore(self):
        if not hasattr(self, 'cmb_users'):
            return
        username = self.cmb_users.currentData()
        user = self.user_model.get(username)
        if user and user.needs_auth:
            self._on_restore(user)

    # ── Benutzer hinzufügen ──────────────────────

    def _on_first_user(self):
        wizard = CreateUserWizard(self, user_model=self.user_model, is_first_user=True)
        if wizard.exec() == QDialog.Accepted and wizard.created_user:
            self.result = LoginResult(user=wizard.created_user, db_key=wizard.db_key)
            self.accept()

    def _on_add_user(self):
        wizard = CreateUserWizard(self, user_model=self.user_model)
        if wizard.exec() == QDialog.Accepted and wizard.created_user:
            # Nach Erstellen: direkt einloggen
            self.result = LoginResult(user=wizard.created_user, db_key=wizard.db_key)
            self.accept()

    def _on_manage(self):
        """Zeigt Sicherheits-Checkliste / Benutzerverwaltung."""
        report = self.user_model.get_security_report()
        if not report:
            QMessageBox.information(self, "Info", tr("account.keine_benutzer_vorhanden"))
            return

        lines = ["<b>Sicherheits-Checkliste</b><br>"]
        for r in report:
            icon = r["security_icon"]
            name = r["display_name"]
            mode = r["security_label"]
            protect = "✅" if r["needs_auth"] else "❌ (kein Schutz bei Verlust)"
            restore = "✅" if r["restore_offered"] else "—"
            db = "✅" if r["db_exists"] else "❌"
            lines.append(
                f"<b>{icon} {name}</b><br>"
                f"  Modus: {mode}<br>"
                f"  Verlustschutz: {protect}<br>"
                f"  Restore-Key: {restore}<br>"
                f"  DB vorhanden: {db}<br>"
            )

        msg = QMessageBox(self)
        msg.setWindowTitle(tr("dlg.account_mgmt"))
        msg.setTextFormat(Qt.RichText)
        msg.setText("<br>".join(lines))

        btn_delete = msg.addButton(tr("account.benutzer_loeschen"), QMessageBox.DestructiveRole)
        msg.addButton(QMessageBox.Close)
        msg.exec()

        if msg.clickedButton() == btn_delete:
            self._on_delete_user()

    def _on_delete_user(self):
        users = self.user_model.list_users()
        if not users:
            return

        from PySide6.QtWidgets import QInputDialog
        names = [f"{u.security_icon} {u.display_name} ({u.username})" for u in users]
        choice, ok = QInputDialog.getItem(
            self, tr("msg.delete_user"), tr("account.welchen_benutzer_loeschen"), names, 0, False
        )
        if not ok:
            return

        idx = names.index(choice)
        user = users[idx]

        reply = QMessageBox.warning(
            self, tr("msg.delete_user"),
            f"«{user.display_name}» wirklich löschen?\n\n"
            f"⚠️ Die verschlüsselte Datenbank ({user.db_filename}) wird gelöscht!\n" +
            tr("account.diese_aktion_kann_nicht"),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.user_model.delete_user(user.username, delete_db=True)
            QMessageBox.information(self, tr("account.geloescht"), trf("account.userdisplay_name_wurde_geloescht"))
            self.user_model = UserModel()
            self._build_content()
