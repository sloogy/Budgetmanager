"""
Kontoverwaltungs-Dialog für den Budgetmanager.

Funktionen:
  - Anzeigenamen bearbeiten
  - Passwort / PIN ändern
  - Sicherheitsstufe wechseln (Quick ↔ PIN ↔ Passwort)

v0.3.9.0
"""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFrame, QFormLayout,
    QRadioButton, QButtonGroup, QGroupBox, QTabWidget,
    QWidget, QTextEdit, QSizePolicy,
)

from model.user_model import (
    UserModel, User,
    SECURITY_QUICK, SECURITY_PIN, SECURITY_PASSWORD,
    SECURITY_LABELS, SECURITY_ICONS,
)
from views.ui_colors import ui_colors
from utils.icons import get_icon
from utils.i18n import tr, trf, display_typ, db_typ_from_display


class AccountManagementDialog(QDialog):
    """Dialog zur Verwaltung des eigenen Benutzerkontos."""

    # Signal: wird emittiert wenn sich der Anzeigename geändert hat
    display_name_changed = Signal(str)
    # Signal: wird emittiert wenn sich die Sicherheitsstufe geändert hat
    security_changed = Signal(str)

    def __init__(self, parent=None, *, user: User, user_model: UserModel,
                 db_key: bytes | None = None):
        super().__init__(parent)
        self.user = user
        self.user_model = user_model
        self.db_key = db_key

        self.setWindowTitle(tr("dlg.account_mgmt"))
        self.setMinimumSize(520, 520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 15, 20, 15)

        # ── Header ──
        header = QLabel(f"👤 {self.user.display_name}")
        header.setAlignment(Qt.AlignCenter)
        hf = QFont(); hf.setPointSize(15); hf.setBold(True)
        header.setFont(hf)
        layout.addWidget(header)
        self._header_label = header

        # Status-Zeile
        sec_info = (f"{self.user.security_icon} {self.user.security_label}  •  "
                    f"Erstellt: {self.user.created[:10]}")
        status = QLabel(sec_info)
        status.setAlignment(Qt.AlignCenter)
        status.setStyleSheet(f"color: {ui_colors(self).text_dim}; font-size: 11px; margin-bottom: 6px;")
        layout.addWidget(status)
        self._status_label = status

        self._add_separator(layout)

        # ── Tabs ──
        tabs = QTabWidget()
        tabs.addTab(self._build_profile_tab(), "Profil")
        tabs.setTabIcon(0, get_icon("✏️"))
        tabs.addTab(self._build_secret_tab(), "Passwort / PIN")
        tabs.setTabIcon(1, get_icon("🔑"))
        tabs.addTab(self._build_security_tab(), "Sicherheitsstufe")
        tabs.setTabIcon(2, get_icon("🔒"))
        layout.addWidget(tabs)

        # ── Schließen ──
        btn_close = QPushButton(tr("btn.close"))
        btn_close.setStyleSheet("padding: 8px 20px;")
        btn_close.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    # ═══════════════════════════════════════════════
    # Tab 1: Profil (Anzeigename bearbeiten)
    # ═══════════════════════════════════════════════

    def _build_profile_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        layout.addWidget(QLabel(tr("account.hier_kannst_du_deinen")))
        layout.addSpacing(5)

        form = QFormLayout()
        form.setSpacing(8)

        self.edt_display_name = QLineEdit(self.user.display_name)
        self.edt_display_name.setStyleSheet("padding: 8px; font-size: 13px;")
        self.edt_display_name.setMaxLength(60)
        form.addRow("Anzeigename:", self.edt_display_name)

        lbl_username = QLabel(self.user.username)
        lbl_username.setStyleSheet(f"color: {ui_colors(self).text_dim}; font-size: 11px;")
        form.addRow("Benutzername:", lbl_username)

        layout.addLayout(form)
        layout.addSpacing(10)

        btn_save_name = QPushButton("Namen speichern")
        btn_save_name.setIcon(get_icon("💾"))
        btn_save_name.setStyleSheet("""
            QPushButton {
                padding: 10px 20px; background: #2196F3; color: white;
                border: none; border-radius: 5px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background: #1976D2; }
        """)
        btn_save_name.clicked.connect(self._on_save_display_name)
        layout.addWidget(btn_save_name)

        layout.addStretch()
        return w

    def _on_save_display_name(self):
        new_name = self.edt_display_name.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Hinweis", tr("account.bitte_einen_namen_eingeben"))
            return

        if new_name == self.user.display_name:
            QMessageBox.information(self, "Info", tr("account.der_name_ist_unveraendert"))
            return

        ok = self.user_model.change_display_name(self.user.username, new_name)
        if ok:
            self.user.display_name = new_name
            self._header_label.setText(f"👤 {new_name}")
            self.display_name_changed.emit(new_name)
            QMessageBox.information(self, "Gespeichert",
                                   trf("account.anzeigename_geaendert_zu_new_name"))
        else:
            QMessageBox.critical(self, tr("msg.error"),
                                tr("account.name_konnte_nicht_gespeichert"))

    # ═══════════════════════════════════════════════
    # Tab 2: Passwort / PIN ändern
    # ═══════════════════════════════════════════════

    def _build_secret_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Info-Text je nach aktuellem Modus
        if self.user.is_quick:
            info = QLabel(
                "⚡ Dein Konto hat aktuell <b>keinen Passwortschutz</b>.\n\n"
                "Um ein Passwort oder eine PIN zu setzen, wechsle zuerst\n"
                "die Sicherheitsstufe im Tab «🔒 Sicherheitsstufe».\n\n"
                "<b>Wichtig:</b> Auch ohne Passwort gibt es einen <b>Restore-Key</b>. "
                "Damit kannst du ein verschlüsseltes Backup wieder öffnen."
            )
            info.setWordWrap(True)
            info.setStyleSheet(f"padding: 15px; background: {ui_colors(self).warning_bg}; border-radius: 5px;")
            layout.addWidget(info)

            # Restore-Key anzeigen (auch im Quick-Modus!)
            gb = QGroupBox("Restore-Key")
            v = QVBoxLayout(gb)
            lbl = QLabel(
                "⚠️ <b>Nur an einem sicheren Ort speichern.</b>\n"
                "PIN oder Restore-Key verlieren = Datenbank kann nicht mehr entschlüsselt werden."
            )
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color:{ui_colors(self).negative};")
            v.addWidget(lbl)

            self.txt_restore_key = QTextEdit()
            self.txt_restore_key.setReadOnly(True)
            self.txt_restore_key.setMaximumHeight(70)
            if self.db_key:
                # Restore-Key ist NICHT einfach db_key.hex().
                # Wir verwenden das etablierte, userfreundliche Format (8er Gruppen mit Bindestrich),
                # identisch zum „Restore-Key — JETZT NOTIEREN!“ Dialog.
                try:
                    from model.crypto import db_key_to_restore_key
                    self.txt_restore_key.setPlainText(db_key_to_restore_key(self.db_key))
                except Exception:
                    # Fallback: wenigstens etwas anzeigen, falls Import/Formatierung fehlschlägt
                    self.txt_restore_key.setPlainText(self.db_key.hex())
            else:
                self.txt_restore_key.setPlainText(tr("account.restorekey_nicht_verfuegbar"))
            v.addWidget(self.txt_restore_key)

            btns = QHBoxLayout()
            btn_copy = QPushButton("Kopieren")
            btn_copy.setIcon(get_icon("📋"))
            btn_copy.clicked.connect(lambda: self._copy_restore_key())
            btns.addWidget(btn_copy)
            btns.addStretch()
            v.addLayout(btns)

            layout.addWidget(gb)
            layout.addStretch()
            self._secret_form_frame = None
            return w

        is_pin = self.user.is_pin
        mode_label = "PIN" if is_pin else "Passwort"

        layout.addWidget(QLabel(trf("account.aendere_dein_aktuelles_mode_label")))
        layout.addSpacing(5)

        self._secret_form_frame = QFrame()
        form = QFormLayout(self._secret_form_frame)
        form.setSpacing(8)

        # Altes Secret
        self.edt_old_secret = QLineEdit()
        self.edt_old_secret.setEchoMode(QLineEdit.Password)
        self.edt_old_secret.setStyleSheet("padding: 6px;")
        self.edt_old_secret.setPlaceholderText(f"Aktuelles {mode_label} eingeben")
        if is_pin:
            self.edt_old_secret.setMaxLength(8)
        form.addRow(f"Aktuelles {mode_label}:", self.edt_old_secret)

        # Neues Secret
        self.edt_new_secret = QLineEdit()
        self.edt_new_secret.setEchoMode(QLineEdit.Password)
        self.edt_new_secret.setStyleSheet("padding: 6px;")
        if is_pin:
            self.edt_new_secret.setPlaceholderText("4–8 Ziffern")
            self.edt_new_secret.setMaxLength(8)
        else:
            self.edt_new_secret.setPlaceholderText("Mindestens 4 Zeichen")
        form.addRow(f"Neues {mode_label}:", self.edt_new_secret)

        # Wiederholung
        self.edt_new_secret2 = QLineEdit()
        self.edt_new_secret2.setEchoMode(QLineEdit.Password)
        self.edt_new_secret2.setStyleSheet("padding: 6px;")
        self.edt_new_secret2.setPlaceholderText(f"{mode_label} wiederholen")
        if is_pin:
            self.edt_new_secret2.setMaxLength(8)
        form.addRow("Wiederholen:", self.edt_new_secret2)

        layout.addWidget(self._secret_form_frame)
        layout.addSpacing(10)

        btn_change = QPushButton(trf("account.mode_label_aendern"))
        btn_change.setStyleSheet("""
            QPushButton {
                padding: 10px 20px; background: #e67e22; color: white;
                border: none; border-radius: 5px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background: #d35400; }
        """)
        btn_change.clicked.connect(self._on_change_secret)
        layout.addWidget(btn_change)

        layout.addStretch()
        return w

    def _copy_restore_key(self) -> None:
        """Kopiert den Restore-Key in die Zwischenablage."""
        try:
            key = ""
            if hasattr(self, "txt_restore_key"):
                key = (self.txt_restore_key.toPlainText() or "").strip()
            if not key or key.startswith("("):
                QMessageBox.warning(self, "Restore-Key", tr("account.kein_restorekey_verfuegbar"))
                return
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(key)
            QMessageBox.information(self, "Restore-Key", tr("account.restorekey_wurde_kopiert"))
        except Exception:
            QMessageBox.warning(self, "Restore-Key", tr("account.kopieren_nicht_moeglich"))

    def _on_change_secret(self):
        old_secret = self.edt_old_secret.text()
        new_secret = self.edt_new_secret.text()
        new_secret2 = self.edt_new_secret2.text()
        is_pin = self.user.is_pin
        mode_label = "PIN" if is_pin else "Passwort"

        if not old_secret:
            QMessageBox.warning(self, "Hinweis",
                               trf("account.bitte_das_aktuelle_mode_label"))
            return

        if not new_secret:
            QMessageBox.warning(self, "Hinweis",
                               trf("account.bitte_ein_neues_mode_label"))
            return

        if new_secret != new_secret2:
            QMessageBox.warning(self, "Hinweis",
                               trf("account.die_mode_labeleingaben_stimmen_nicht"))
            return

        if is_pin:
            if not new_secret.isdigit() or not (4 <= len(new_secret) <= 8):
                QMessageBox.warning(self, "Hinweis",
                                   "PIN muss 4–8 Ziffern lang sein.")
                return
        else:
            if len(new_secret) < 4:
                QMessageBox.warning(self, "Hinweis",
                                   "Passwort muss mindestens 4 Zeichen lang sein.")
                return

        # Passwort/PIN ändern (gleiche Sicherheitsstufe beibehalten)
        success, restore_key = self.user_model.change_secret(
            self.user.username, old_secret, new_secret
        )

        if success:
            # Felder leeren
            self.edt_old_secret.clear()
            self.edt_new_secret.clear()
            self.edt_new_secret2.clear()

            if restore_key:
                self._show_restore_key(restore_key, mode_label)
            else:
                QMessageBox.information(self, "Erfolg",
                                       trf("account.mode_label_wurde_erfolgreich_geaendert"))
        else:
            QMessageBox.critical(self, tr("msg.error"),
                                trf("account.das_aktuelle_mode_label_ist"))
            self.edt_old_secret.clear()
            self.edt_old_secret.setFocus()

    # ═══════════════════════════════════════════════
    # Tab 3: Sicherheitsstufe wechseln
    # ═══════════════════════════════════════════════

    def _build_security_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        layout.addWidget(QLabel(
            "Wechsle die Sicherheitsstufe deines Kontos.\n"
            "Die Datenbank bleibt dabei erhalten."
        ))
        layout.addSpacing(5)

        # Aktuelle Stufe anzeigen
        current_box = QGroupBox(tr("grp.current_level"))
        cb_layout = QVBoxLayout(current_box)
        self._lbl_current_security = QLabel(
            f"{self.user.security_icon} {self.user.security_label}"
        )
        self._lbl_current_security.setStyleSheet(
            "font-size: 14px; font-weight: bold; padding: 5px;"
        )
        cb_layout.addWidget(self._lbl_current_security)
        layout.addWidget(current_box)

        # Neue Stufe wählen
        new_box = QGroupBox("Neue Sicherheitsstufe")
        nb_layout = QVBoxLayout(new_box)

        self.sec_btn_group = QButtonGroup(self)

        self.rb_sec_quick = QRadioButton(tr("radio.security_quick"))
        self.rb_sec_quick.setToolTip(
            "Schneller Zugriff ohne Eingabe.\n"
            "Schützt vor Versehen — nicht bei USB-Verlust."
        )
        self.sec_btn_group.addButton(self.rb_sec_quick)
        nb_layout.addWidget(self.rb_sec_quick)

        self.rb_sec_pin = QRadioButton(tr("radio.security_pin"))
        self.rb_sec_pin.setToolTip(tr("account.schneller_schutz_mit_kurzer"))
        self.sec_btn_group.addButton(self.rb_sec_pin)
        nb_layout.addWidget(self.rb_sec_pin)

        self.rb_sec_pw = QRadioButton(tr("radio.security_password"))
        self.rb_sec_pw.setToolTip(tr("account.maximaler_schutz_mit_passwort"))
        self.sec_btn_group.addButton(self.rb_sec_pw)
        nb_layout.addWidget(self.rb_sec_pw)

        layout.addWidget(new_box)

        # Secret-Eingabe für den Wechsel
        self.sec_change_frame = QFrame()
        scf_layout = QVBoxLayout(self.sec_change_frame)
        scf_layout.setContentsMargins(0, 0, 0, 0)

        # Altes Secret (nur bei PIN/PW → andere Stufe)
        self.sec_old_frame = QFrame()
        sof_layout = QFormLayout(self.sec_old_frame)
        sof_layout.setContentsMargins(0, 0, 0, 0)
        self.edt_sec_old = QLineEdit()
        self.edt_sec_old.setEchoMode(QLineEdit.Password)
        self.edt_sec_old.setStyleSheet("padding: 6px;")
        self._lbl_sec_old = QLabel("Aktuelles Passwort:")
        sof_layout.addRow(self._lbl_sec_old, self.edt_sec_old)
        scf_layout.addWidget(self.sec_old_frame)

        # Neues Secret (nur bei Wechsel zu PIN/PW)
        self.sec_new_frame = QFrame()
        snf_layout = QFormLayout(self.sec_new_frame)
        snf_layout.setContentsMargins(0, 0, 0, 0)

        self.edt_sec_new = QLineEdit()
        self.edt_sec_new.setEchoMode(QLineEdit.Password)
        self.edt_sec_new.setStyleSheet("padding: 6px;")
        self._lbl_sec_new = QLabel("Neues Passwort:")
        snf_layout.addRow(self._lbl_sec_new, self.edt_sec_new)

        self.edt_sec_new2 = QLineEdit()
        self.edt_sec_new2.setEchoMode(QLineEdit.Password)
        self.edt_sec_new2.setStyleSheet("padding: 6px;")
        self._lbl_sec_new2 = QLabel("Wiederholen:")
        snf_layout.addRow(self._lbl_sec_new2, self.edt_sec_new2)

        scf_layout.addWidget(self.sec_new_frame)

        # Warn-Label
        self.lbl_sec_warn = QLabel()
        self.lbl_sec_warn.setWordWrap(True)
        self.lbl_sec_warn.setStyleSheet(
            f"color: {ui_colors(self).negative}; font-size: 11px; padding: 5px;"
        )
        scf_layout.addWidget(self.lbl_sec_warn)

        layout.addWidget(self.sec_change_frame)

        # Button
        self.btn_sec_apply = QPushButton(tr("account.sicherheitsstufe_aendern"))
        self.btn_sec_apply.setStyleSheet("""
            QPushButton {
                padding: 10px 20px; background: #8e44ad; color: white;
                border: none; border-radius: 5px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background: #7d3c98; }
        """)
        self.btn_sec_apply.clicked.connect(self._on_change_security)
        layout.addWidget(self.btn_sec_apply)

        layout.addStretch()

        # Aktuelle Stufe vorselektieren
        if self.user.is_quick:
            self.rb_sec_quick.setChecked(True)
        elif self.user.is_pin:
            self.rb_sec_pin.setChecked(True)
        else:
            self.rb_sec_pw.setChecked(True)

        # Signal verbinden
        self.sec_btn_group.buttonToggled.connect(self._on_security_selection_changed)
        self._on_security_selection_changed()

        return w

    def _on_security_selection_changed(self):
        """Aktualisiert die Eingabefelder basierend auf der gewählten Stufe."""
        target = self._get_selected_security()
        current = self.user.security

        same_level = (target == current)

        # Altes Secret: nur nötig wenn aktuell PIN oder PW
        needs_old = self.user.needs_auth
        self.sec_old_frame.setVisible(needs_old)
        if needs_old:
            old_label = "Aktuelle PIN:" if self.user.is_pin else "Aktuelles Passwort:"
            self._lbl_sec_old.setText(old_label)
            ph = "4–8 Ziffern" if self.user.is_pin else "Passwort eingeben"
            self.edt_sec_old.setPlaceholderText(ph)
            self.edt_sec_old.setMaxLength(8 if self.user.is_pin else 128)

        # Neues Secret: nur nötig wenn Ziel PIN oder PW ist
        needs_new = (target != SECURITY_QUICK)
        self.sec_new_frame.setVisible(needs_new)
        if needs_new:
            is_pin_target = (target == SECURITY_PIN)
            new_label = "Neue PIN:" if is_pin_target else "Neues Passwort:"
            self._lbl_sec_new.setText(new_label)
            ph = "4–8 Ziffern" if is_pin_target else "Mindestens 4 Zeichen"
            self.edt_sec_new.setPlaceholderText(ph)
            self.edt_sec_new.setMaxLength(8 if is_pin_target else 128)
            self._lbl_sec_new2.setText("Wiederholen:")
            self.edt_sec_new2.setPlaceholderText(
                "PIN wiederholen" if is_pin_target else "Passwort wiederholen"
            )
            self.edt_sec_new2.setMaxLength(8 if is_pin_target else 128)

        # Warnhinweis
        if target == SECURITY_QUICK:
            if current != SECURITY_QUICK:
                self.lbl_sec_warn.setText(
                    "⚠️ Quick-Modus entfernt den Passwortschutz!\n"
                    "Jeder mit Zugriff auf deine Dateien kann die Daten öffnen."
                )
                self.lbl_sec_warn.setStyleSheet(
                    f"color: {ui_colors(self).negative}; font-size: 11px; padding: 5px;"
                )
                self.lbl_sec_warn.setVisible(True)
            else:
                self.lbl_sec_warn.setVisible(False)
        elif target in (SECURITY_PIN, SECURITY_PASSWORD):
            kind = "PIN" if target == SECURITY_PIN else "Passwort"
            self.lbl_sec_warn.setText(
                f"⚠️ {kind} oder Restore-Key verlieren = "
                f"Datenbank unwiederbringlich verloren!"
            )
            self.lbl_sec_warn.setStyleSheet(
                f"color: {ui_colors(self).negative}; font-size: 11px; padding: 5px;"
            )
            self.lbl_sec_warn.setVisible(True)
        else:
            self.lbl_sec_warn.setVisible(False)

        # Button nur aktiv wenn Stufe wirklich wechselt
        self.btn_sec_apply.setEnabled(not same_level)
        if same_level:
            self.btn_sec_apply.setText("(Aktuelle Stufe)")
            self.btn_sec_apply.setIcon(QIcon())
        else:
            target_label = SECURITY_LABELS.get(target, target)
            self.btn_sec_apply.setText(f"Wechseln zu: {target_label}")
            self.btn_sec_apply.setIcon(get_icon("🔒"))

    def _get_selected_security(self) -> str:
        if self.rb_sec_quick.isChecked():
            return SECURITY_QUICK
        elif self.rb_sec_pin.isChecked():
            return SECURITY_PIN
        else:
            return SECURITY_PASSWORD

    def _on_change_security(self):
        target = self._get_selected_security()
        current = self.user.security

        if target == current:
            QMessageBox.information(self, "Info",
                                   tr("account.die_sicherheitsstufe_ist_bereits"))
            return

        # Validierung
        old_secret = ""
        new_secret = ""

        # Altes Secret prüfen wenn nötig
        if self.user.needs_auth:
            old_secret = self.edt_sec_old.text()
            if not old_secret:
                mode = "PIN" if self.user.is_pin else "Passwort"
                QMessageBox.warning(self, "Hinweis",
                                   trf("account.bitte_das_aktuelle_mode"))
                return

        # Neues Secret prüfen wenn Ziel nicht Quick
        if target != SECURITY_QUICK:
            new_secret = self.edt_sec_new.text()
            new_secret2 = self.edt_sec_new2.text()

            if not new_secret:
                kind = "PIN" if target == SECURITY_PIN else "Passwort"
                QMessageBox.warning(self, "Hinweis",
                                   trf("account.bitte_ein_neues_kind"))
                return

            if new_secret != new_secret2:
                kind = "PIN" if target == SECURITY_PIN else "Passwort"
                QMessageBox.warning(self, "Hinweis",
                                   trf("account.die_kindeingaben_stimmen_nicht"))
                return

            if target == SECURITY_PIN:
                if not new_secret.isdigit() or not (4 <= len(new_secret) <= 8):
                    QMessageBox.warning(self, "Hinweis",
                                       "PIN muss 4–8 Ziffern lang sein.")
                    return
            else:
                if len(new_secret) < 4:
                    QMessageBox.warning(self, "Hinweis",
                                       "Passwort muss mindestens 4 Zeichen lang sein.")
                    return

        # Bestätigung bei Downgrade zu Quick
        if target == SECURITY_QUICK:
            reply = QMessageBox.warning(
                self, "Schutz entfernen",
                "Willst du wirklich den Passwortschutz entfernen?\n\n" +
                tr("account.jeder_mit_zugriff_auf"),
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        # Änderung durchführen
        success, restore_key = self.user_model.change_secret(
            self.user.username, old_secret, new_secret, target
        )

        if success:
            # User-Objekt aktualisieren (neu laden)
            updated = self.user_model.get(self.user.username)
            if updated:
                self.user.security = updated.security
                self.user.salt_hex = updated.salt_hex
                self.user.db_key_b64 = updated.db_key_b64
                self.user.wrapped_db_key_b64 = updated.wrapped_db_key_b64
                self.user.pw_hash = updated.pw_hash

            # UI aktualisieren
            self._lbl_current_security.setText(
                f"{self.user.security_icon} {self.user.security_label}"
            )
            self._status_label.setText(
                f"{self.user.security_icon} {self.user.security_label}  •  "
                f"Erstellt: {self.user.created[:10]}"
            )
            self.security_changed.emit(target)

            # Felder leeren
            self.edt_sec_old.clear()
            self.edt_sec_new.clear()
            self.edt_sec_new2.clear()

            # Eingabefelder-Sichtbarkeit aktualisieren
            self._on_security_selection_changed()

            target_label = SECURITY_LABELS.get(target, target)
            if restore_key:
                self._show_restore_key(restore_key, target_label)
            else:
                QMessageBox.information(
                    self, "Erfolg",
                    f"Sicherheitsstufe geändert zu «{target_label}»."
                )
        else:
            if self.user.needs_auth:
                mode = "PIN" if self.user.is_pin else "Passwort"
                QMessageBox.critical(self, tr("msg.error"),
                                    trf("account.das_aktuelle_mode_ist"))
                self.edt_sec_old.clear()
                self.edt_sec_old.setFocus()
            else:
                QMessageBox.critical(self, tr("msg.error"),
                                    tr("account.sicherheitsstufe_konnte_nicht_geaendert"))

    # ═══════════════════════════════════════════════
    # Hilfsfunktionen
    # ═══════════════════════════════════════════════

    def _add_separator(self, layout):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {ui_colors(self).border};")
        layout.addWidget(line)

    def _show_restore_key(self, restore_key: str, context: str = ""):
        """Zeigt den neuen Restore-Key in einem Dialog an."""
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("dlg.restore_key_new"))
        dlg.setMinimumWidth(480)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 15, 20, 15)

        header = QLabel(trf("account.context_erfolgreich_geaendert"))
        hf = QFont(); hf.setPointSize(13); hf.setBold(True)
        header.setFont(hf)
        header.setStyleSheet(f"color: {ui_colors(self).ok};")
        layout.addWidget(header)

        warn = QLabel(
            "⚠️ <b>WICHTIG:</b> Dein Restore-Key hat sich geändert!<br>"
            "Notiere diesen Key sicher — er ist dein Notfall-Zugang.<br>"
            "Ohne diesen Key und ohne Passwort/PIN sind deine Daten <b>verloren</b>!"
        )
        warn.setWordWrap(True)
        warn.setTextFormat(Qt.RichText)
        warn.setStyleSheet(
            "background: #fff3cd; padding: 10px; border-radius: 5px; "
            f"color: {ui_colors(self).warning_text};"
        )
        layout.addWidget(warn)

        layout.addSpacing(5)
        layout.addWidget(QLabel("Dein neuer Restore-Key:"))

        key_edit = QTextEdit()
        key_edit.setPlainText(restore_key)
        key_edit.setReadOnly(True)
        key_edit.setMaximumHeight(80)
        key_edit.setStyleSheet(
            "font-family: Consolas, 'Courier New', monospace; "
            "font-size: 13px; padding: 8px; background: #f8f9fa; "
            "border: 2px solid #dee2e6; border-radius: 4px;"
        )
        layout.addWidget(key_edit)

        # Kopier-Button
        btn_layout = QHBoxLayout()
        btn_copy = QPushButton("In Zwischenablage kopieren")
        btn_copy.setIcon(get_icon("📋"))
        btn_copy.setStyleSheet("""
            QPushButton {
                padding: 8px 16px; background: #17a2b8; color: white;
                border: none; border-radius: 4px; font-weight: bold;
            }
            QPushButton:hover { background: #138496; }
        """)
        btn_copy.clicked.connect(lambda: self._copy_to_clipboard(restore_key, btn_copy))
        btn_layout.addWidget(btn_copy)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addSpacing(10)

        btn_ok = QPushButton("Ich habe den Key notiert")
        btn_ok.setIcon(get_icon("✅"))
        btn_ok.setStyleSheet("""
            QPushButton {
                padding: 10px 24px; background: #27ae60; color: white;
                border: none; border-radius: 5px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background: #219a52; }
        """)
        btn_ok.clicked.connect(dlg.accept)
        layout.addWidget(btn_ok)

        dlg.exec()

    def _copy_to_clipboard(self, text: str, btn: QPushButton):
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        btn.setText("Kopiert!")
        btn.setIcon(get_icon("✅"))
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: (btn.setText("In Zwischenablage kopieren"), btn.setIcon(get_icon("📋"))))
