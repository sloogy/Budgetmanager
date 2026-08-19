from __future__ import annotations

from utils.accessibility import configure_dialog_tab_order
from utils.notifications import show_info, show_warning
import logging

logger = logging.getLogger(__name__)

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QRadioButton,
    QButtonGroup,
    QGroupBox,
    QFrame,
    QFormLayout,
    QFileDialog,
    QMessageBox,
    QInputDialog,
    QStackedWidget,
    QTextEdit,
    QCheckBox,
)

from model.user_model import (
    UserModel,
    User,
    SECURITY_QUICK,
    SECURITY_PIN,
    SECURITY_PASSWORD,
)
from model.user_model import PIN_MIN_LENGTH, PIN_MAX_LENGTH, PASSWORD_MIN_LENGTH
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
        self._verified_import_bundle_path: Path | None = None
        self.imported_existing_database = False

        self.setWindowTitle(tr("dlg.setup_assistant"))
        self.setMinimumSize(560, 400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Title ──
        title = QLabel(tr("startup.welcome_title"))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 18px; font-weight: 700; padding: 16px 24px 8px 24px;"
        )
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

        self.btn_back = QPushButton(
            trf(
                "auto.views_startup_wizard.78_value_0_9628887f",
                value_0=(tr("btn.back_step")),
            )
        )
        self.btn_back.setVisible(False)
        self.btn_back.clicked.connect(self._go_back)
        nav.addWidget(self.btn_back)

        nav.addStretch(1)

        self.btn_cancel = QPushButton(tr("btn.cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        nav.addWidget(self.btn_cancel)

        self.btn_next = QPushButton(
            trf(
                "auto.views_startup_wizard.89_value_0_e2a7ae74",
                value_0=(tr("btn.continue")),
            )
        )
        self.btn_next.setDefault(True)
        self.btn_next.setMinimumWidth(110)
        self.btn_next.clicked.connect(self._go_next)
        nav.addWidget(self.btn_next)

        root.addLayout(nav)

        self._goto(self._PAGE_NAME)
        configure_dialog_tab_order(self)

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
        self.lbl_secret = QLabel(tr("create_user.pin_label"))
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
            self.btn_next.setText(
                trf(
                    "auto.views_startup_wizard.232_value_0_0df8e20d",
                    value_0=(tr("btn.continue")),
                )
            )
            self.btn_next.setVisible(True)

    def _go_next(self) -> None:
        page = self.stack.currentIndex()
        if page == self._PAGE_NAME:
            if not self.edt_name.text().strip():
                show_warning(
                    self, tr("msg.info"), tr("account.bitte_einen_namen_eingeben")
                )
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
            tr(
                "auto.views_startup_wizard.267_budgetmanager_backups_bmr_enc_db_d504b057"
            ),
        )
        if not src_path:
            return

        # Import wird erst nach Wahl der Sicherheitsstufe ausgeführt.
        # Vorher direkt einen Quick-User anzulegen war ein Dead-End: Bei falschem
        # Restore-Key blieb ein leerer Benutzer/DB-Rest zurück und der nächste
        # Start lief nicht mehr sauber als Erststart.
        self._import_src_path = src_path
        self._goto(self._PAGE_SECURITY)

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
            self.edt_secret2.setPlaceholderText(
                tr("create_user.pin_repeat_placeholder")
            )
            self.edt_secret2.setMaxLength(8)
            self.lbl_warn.setText(tr("account.pin_oder_restorekey_verlieren"))
            self.lbl_warn.setStyleSheet(
                f"color: {c.negative}; font-size: 11px; padding: 5px;"
            )
        elif not is_quick:
            self.lbl_secret.setText(tr("create_user.password_label"))
            self.edt_secret.setEchoMode(QLineEdit.Password)
            self.edt_secret.setPlaceholderText(tr("create_user.password_placeholder"))
            self.edt_secret.setMaxLength(128)
            self.lbl_secret2.setText(tr("create_user.repeat_label"))
            self.edt_secret2.setEchoMode(QLineEdit.Password)
            self.edt_secret2.setPlaceholderText(
                tr("create_user.password_repeat_placeholder")
            )
            self.edt_secret2.setMaxLength(128)
            self.lbl_warn.setText(tr("account.passwort_oder_restorekey_verlieren"))
            self.lbl_warn.setStyleSheet(
                f"color: {c.negative}; font-size: 11px; padding: 5px;"
            )
        else:
            self.lbl_warn.setText(tr("account.schuetzt_vor_versehenneugier_nicht"))
            self.lbl_warn.setStyleSheet(
                f"color: {c.text_dim}; font-size: 11px; padding: 5px;"
            )

    # ──────────────────────────────────────────────
    # Final step: create user (+ optional import)
    # ──────────────────────────────────────────────

    def _finish(self) -> None:
        name = self.edt_name.text().strip()
        if not name:
            show_warning(self, tr("msg.info"), tr("account.bitte_einen_namen_eingeben"))
            return

        if self.rb_quick.isChecked():
            security = SECURITY_QUICK
            secret = ""
        elif self.rb_pin.isChecked():
            security = SECURITY_PIN
            secret = self.edt_secret.text()
            if not secret.isdigit() or not (
                PIN_MIN_LENGTH <= len(secret) <= PIN_MAX_LENGTH
            ):
                show_warning(self, tr("msg.info"), tr("account.pin_length"))
                return
            if secret != self.edt_secret2.text():
                show_warning(
                    self, tr("msg.info"), tr("account.pins_stimmen_nicht_ueberein")
                )
                return
        else:
            security = SECURITY_PASSWORD
            secret = self.edt_secret.text()
            if len(secret) < PASSWORD_MIN_LENGTH:
                show_warning(self, tr("msg.info"), tr("account.password_min_length"))
                return
            if secret != self.edt_secret2.text():
                show_warning(
                    self,
                    tr("msg.info"),
                    tr("account.passwoerter_stimmen_nicht_ueberein"),
                )
                return

        try:
            user, restore_key = self.user_model.create_user(name, security, secret)
        except (ValueError, ImportError) as e:
            QMessageBox.critical(self, tr("msg.error"), str(e))
            return

        db_key = user.get_db_key(secret)

        def _rollback_created_user() -> None:
            try:
                self.user_model.delete_user(user.username, delete_db=True)
            except Exception as exc:
                logger.warning(
                    "Rollback des neu erstellten Benutzers fehlgeschlagen: %s", exc
                )

        # ── Import / Restore ZUERST versuchen (falls gewählt) ──────────────
        # Erst nach erfolgreicher Entschlüsselung wird fortgefahren. Schlägt sie
        # fehl (falscher Restore-Key, Abbruch oder defektes Backup), wird der
        # eben angelegte Benutzer sauber zurückgerollt und der Assistent kehrt
        # zum Anfang zurück ("wieder von vorne": neuen Benutzer anlegen ODER das
        # Backup erneut einspielen). So bleibt kein hängender Zwischenzustand und
        # es entsteht kein Brick-Loop auf der Sicherheitsseite.
        if self._import_src_path:
            try:
                self._restore_into_user(Path(self._import_src_path), user, db_key)
                self.imported_existing_database = True
                # Ein Import ist kein leerer Erststart. Einstellungen aus dem
                # Backup werden vorsichtig übernommen, aber Pfade/Benutzerkonto
                # bleiben zur neuen Installation passend. Danach wird der
                # geführte Setup-Assistent deaktiviert; sonst wirkt ein Restore
                # wie eine frische leere Datenbank und Vorschläge/Warnungen laufen
                # mit falschen Defaults.
                self._restore_safe_settings_from_bundle(Path(self._import_src_path))
                self._mark_import_as_existing_setup()
            except Exception as exc:
                _rollback_created_user()
                logger.info(
                    "Erststart-Restore fehlgeschlagen – zurück zum Anfang: %s", exc
                )
                QMessageBox.critical(
                    self,
                    tr("msg.error"),
                    trf("startup.import_failed", exc=str(exc))
                    + "\n\n"
                    + tr("startup.restore_retry_from_start"),
                )
                self._reset_to_start()
                return

        # Restore-Key beim Erststart IMMER anzeigen – auch für Quick-User. Bei
        # PIN/Passwort liefert create_user() den Key direkt; bei Quick wird er aus
        # dem db_key abgeleitet (gleiches lesbares Format). Bei einem Import erst
        # HIER, also NACH erfolgreicher Entschlüsselung – sonst würde der neue
        # Schlüssel für einen wieder verworfenen Benutzer angezeigt.
        if not restore_key:
            try:
                from model.crypto import db_key_to_restore_key

                restore_key = db_key_to_restore_key(db_key)
            except Exception as exc:
                logger.warning(
                    "Restore-Key für Quick-User konnte nicht abgeleitet werden: %s", exc
                )
                restore_key = ""

        if restore_key:
            if not self._show_restore_key(restore_key, user):
                _rollback_created_user()
                return  # user closed dialog without confirming

        if self._import_src_path:
            show_info(self, tr("startup.import_title"), tr("startup.import_success"))

        self.result = StartupResult(user=user, db_key=db_key)
        self.accept()

    def _reset_to_start(self) -> None:
        """Setzt den Assistenten nach einem fehlgeschlagenen Restore sauber zurück.

        Der gewählte Backup-Pfad wird verworfen und der Nutzer landet wieder auf
        der Auswahlseite (neuen Benutzer anlegen ODER Backup einspielen). So kann
        er es ohne hängenden Zwischenzustand erneut versuchen.
        """
        self._import_src_path = None
        # Eingegebene Geheimnisse leeren, damit kein Rest hängen bleibt.
        for fld in ("edt_secret", "edt_secret2"):
            w = getattr(self, fld, None)
            if w is not None:
                try:
                    w.clear()
                except Exception:
                    pass
        self._goto(self._PAGE_CHOICE)

    def _show_restore_key(self, key: str, user: User) -> bool:
        """Zeigt den Restore-Key und verlangt Bestätigung. Gibt True zurück wenn bestätigt."""
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("dlg.restore_key_note"))
        dlg.setMinimumSize(480, 380)
        layout = QVBoxLayout(dlg)

        c = ui_colors(dlg)
        intro_key = (
            "dlg.restore_key_intro_quick"
            if getattr(user, "is_quick", False)
            else "dlg.restore_key_intro"
        )
        layout.addWidget(QLabel(trf(intro_key, color=c.negative)))

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
        btn_ok.setStyleSheet(
            f"""
            QPushButton {{ padding: 10px; background: {c.ok}; color: white;
                           border: none; border-radius: 5px; font-weight: bold; }}
            QPushButton:disabled {{ background: {c.border}; color: {c.text_dim}; }}
        """
        )
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

    def _mark_import_as_existing_setup(self) -> None:
        """Nach erfolgreichem Erstimport Onboarding abschalten.

        Der Nutzer hat bereits eine echte Datenbank importiert. Wird hier der
        Standard ``setup_completed=False`` beibehalten, startet nach dem Login
        wieder die Einführung und überschreibt/irritiert Budget-Lern-Settings.
        """
        try:
            from settings import Settings

            settings = Settings()
            settings.set("show_onboarding", False)
            settings.set("setup_completed", True)
            settings.set(
                "tracking_budget_learning_enabled",
                bool(settings.get("tracking_budget_learning_enabled", True)),
            )
            settings.set(
                "tracking_budget_learning_show_in_report",
                bool(settings.get("tracking_budget_learning_show_in_report", True)),
            )
            settings.set(
                "auto_generate_budget_warnings",
                bool(settings.get("auto_generate_budget_warnings", True)),
            )
        except Exception as exc:
            logger.warning(
                "Import-Setup-Status konnte nicht gespeichert werden: %s", exc
            )

    def _restore_safe_settings_from_bundle(self, bundle_path: Path) -> None:
        """Übernimmt sichere App-Einstellungen aus einem .bmr-Backup.

        Nicht übernommen werden Speicherorte, Benutzerkonto-/Fensterzustand und
        Tab-Layout. Diese Werte können nach einem Restore auf einem anderen
        Rechner/Portable-Ordner ungültig sein. Fachliche Einstellungen für
        Lernmodus, Warnungen, Sprache, Währung und Forecast werden dagegen
        übernommen, weil sie Vorschläge/Warnungen direkt beeinflussen.
        """
        if Path(bundle_path).suffix.lower() != ".bmr":
            return
        import json
        import zipfile
        from model.restore_bundle import (
            MAX_SETTINGS_BYTES,
            read_member_limited,
            verify_open_bundle,
        )

        try:
            verified_path = self._verified_import_bundle_path
            if verified_path is None:
                verified_path, _db_file = self._prepare_verified_bundle(bundle_path)
                self._verified_import_bundle_path = verified_path
            with zipfile.ZipFile(verified_path, "r") as zf:
                verify_open_bundle(zf)
                if "settings.json" not in zf.namelist():
                    return
                raw = json.loads(
                    read_member_limited(zf, "settings.json", MAX_SETTINGS_BYTES).decode(
                        "utf-8"
                    )
                )
            if not isinstance(raw, dict):
                return
            from settings import Settings

            allowed_prefixes = (
                "budget_suggestion_",
                "tracking_budget_learning_",
            )
            allowed_keys = {
                "language",
                "currency",
                "number_format",
                "recurring_preferred_day",
                "budget_zero_balance_rule",
                "budget_surplus_strategy",
                "auto_generate_budget_warnings",
                "warn_budget_overrun",
                "carryover_start_month",
                "carryover_start_year",
                "active_design_profile",
                "last_design_profile_hell",
                "last_design_profile_dunkel",
            }
            settings = Settings()
            for key, value in raw.items():
                if key in allowed_keys or any(
                    str(key).startswith(prefix) for prefix in allowed_prefixes
                ):
                    settings.settings[key] = value
            # Import bleibt abgeschlossen, auch wenn das Backup selbst noch
            # show_onboarding=True enthielt.
            settings.settings["show_onboarding"] = False
            settings.settings["setup_completed"] = True
            settings.save()
            logger.info(
                "Sichere Settings aus Import-Backup übernommen: %s", bundle_path.name
            )
        except Exception as exc:
            logger.warning(
                "Sichere Settings aus Import-Backup konnten nicht übernommen werden: %s",
                exc,
            )

    def _restore_into_user(self, src: Path, user: User, db_key: bytes) -> None:
        """Schreibt ein Backup in die DB-Datei des neu angelegten Users.

        Unterstützt:
        - .db  → in den neuen Benutzer verschlüsseln
        - .enc → direkt übernehmen, wenn der Key passt, sonst per Restore-Key
        - .bmr → Bundle extrahieren; users.json wird aus Sicherheitsgründen
                 nie zum automatischen Entsperren verwendet.
        """
        src = Path(src)
        if not src.exists():
            raise FileNotFoundError(str(src))

        bundle_path: Path | None = src if src.suffix.lower() == ".bmr" else None
        extracted_tmp: Path | None = None

        try:
            if bundle_path is not None:
                extracted_tmp = self._extract_bmr_to_temp(bundle_path)
                src = extracted_tmp

            dest_enc = user.db_path
            dest_enc.parent.mkdir(parents=True, exist_ok=True)

            if src.suffix.lower() == ".db":
                self._import_db_to_enc(src, dest_enc, db_key, user.salt)
                return

            if src.suffix.lower() == ".enc":
                self._import_enc_to_user(
                    src_enc=src,
                    dest_enc=dest_enc,
                    new_db_key=db_key,
                    new_salt=user.salt,
                    bundle_path=bundle_path,
                )
                return

            raise ValueError(f"Unbekanntes Format: {src.name}")
        finally:
            if extracted_tmp is not None:
                try:
                    extracted_tmp.unlink(missing_ok=True)
                except Exception as e:
                    logger.debug(
                        "Temporäre Restore-Datei konnte nicht gelöscht werden: %s", e
                    )

    def _import_enc_to_user(
        self,
        *,
        src_enc: Path,
        dest_enc: Path,
        new_db_key: bytes,
        new_salt: bytes,
        bundle_path: Path | None = None,
    ) -> None:
        """Importiert eine verschlüsselte DB in den neu angelegten Benutzer."""
        from model.crypto import (
            decrypt_db_from_file,
            encrypt_db_to_file,
            restore_key_to_db_key,
        )

        # 1) Backup passt bereits zum neu erstellten Benutzer-Key.
        try:
            test = decrypt_db_from_file(src_enc, new_db_key)
            test.close()
            from model.restore_bundle import atomic_copy_verified

            atomic_copy_verified(src_enc, dest_enc)
            return
        except Exception as e:
            logger.info("Import-DB ist nicht mit neuem Benutzer-Key lesbar: %s", e)

        # 2) Restore-Key des alten Backups abfragen.
        #    Wichtig: users.json aus .bmr-Bundles wird hier bewusst NICHT als
        #    Ersatzschlüssel benutzt. Quick-Backups enthielten früher den DB-Key
        #    lokal in users.json; ein importiertes Backup durfte dadurch ohne
        #    Wiederherstellungscode geöffnet werden. Ab v2.2.7 gilt: Fremdes
        #    verschlüsseltes Backup = Restore-Key erforderlich.
        logger.info(
            "Restore-Key wird abgefragt; Bundle-users.json wird nicht als Schlüssel verwendet."
        )
        last_exc: Exception | None = None
        for attempt in range(3):
            restore_key = self._ask_restore_key()
            if not restore_key:
                raise ValueError(tr("startup.restore_aborted_no_key"))
            try:
                other_key = restore_key_to_db_key(restore_key)
                tmp_conn = decrypt_db_from_file(src_enc, other_key)
                try:
                    encrypt_db_to_file(tmp_conn, dest_enc, new_db_key, new_salt)
                finally:
                    tmp_conn.close()
                return
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    show_warning(
                        self,
                        tr("msg.info"),
                        trf(
                            "auto.views_startup_wizard.480_bitte_erneut_versuchen_value_0_2762b9bc",
                            value_0=(exc),
                        ),
                    )
        raise ValueError(
            trf(
                "dlg.entschluesselung_mit_restorekey_fehlgeschlagen",
                last_exc=str(last_exc),
            )
        )

    def _import_db_to_enc(
        self, src_db: Path, dest_enc: Path, db_key: bytes, salt: bytes
    ) -> None:
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
        mem_conn.execute("PRAGMA busy_timeout = 10000;")

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

    def _prepare_verified_bundle(self, bundle_path: Path) -> tuple[Path, str]:
        """Prüft ein Erststart-Backup und migriert bestätigte Legacy-Bundles."""
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
                raise ValueError(tr("backup.legacy_integrity_rejected"))
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            verified_copy = bundle_path.with_name(
                f"{bundle_path.stem}_verified_{stamp}.bmr"
            )
            upgrade_legacy_bundle(bundle_path, verified_copy)
            show_info(
                self,
                tr("backup.legacy_integrity_title"),
                trf("backup.legacy_integrity_upgraded", path=verified_copy),
            )
            return verified_copy, verify_bundle(verified_copy)

    def _extract_bmr_to_temp(self, bundle_path: Path) -> Path:
        import zipfile
        from model.file_permissions import secure_dir, secure_file
        from model.restore_bundle import (
            MAX_DB_BYTES,
            copy_member_limited,
            verify_open_bundle,
        )

        bundle_path, db_file = self._prepare_verified_bundle(Path(bundle_path))
        self._verified_import_bundle_path = bundle_path

        tmp_dir = bundle_path.parent / "_tmp_restore"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        secure_dir(tmp_dir)

        with zipfile.ZipFile(bundle_path, "r") as zf:
            opened_db_file = verify_open_bundle(zf)
            if opened_db_file != db_file:
                raise ValueError(tr("backup_restore.bundle_changed_during_restore"))
            suffix = ".enc" if db_file.endswith(".enc") else ".db"
            out = (
                tmp_dir
                / f"startup_restore_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{suffix}"
            )
            copy_member_limited(zf, db_file, out, MAX_DB_BYTES)
            secure_file(out)
        return out
