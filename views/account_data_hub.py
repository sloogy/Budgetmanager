from __future__ import annotations

from utils.notifications import show_warning
import logging

logger = logging.getLogger(__name__)

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
)

from utils.i18n import tr, trf
from views.ui_colors import ui_colors

"""Zentraler Hub „Konto & Daten".

Eine wiederverwendbare Oberfläche, die bewusst NUR bündelt und an die bestehenden
(getesteten) Dialoge/Methoden des Hauptfensters delegiert:

- Konto verwalten            -> main_window._show_account_management()
- Backup & Wiederherstellung -> main_window._show_backup_restore()
- Datenbank zurücksetzen     -> main_window._show_database_management()

Inline (selbsttragend) enthalten ist nur der Speicherort-Bereich (Datenordner
wählen inkl. optionaler Datenübernahme), der über
main_window._handle_data_directory_change() angewandt wird.

Die gleiche Komponente wird im Reiter „Konto" und in der Einstellungen-Seite
„Konto & Daten" eingebettet.
"""


class AccountDataHub(QWidget):
    def __init__(
        self, settings, main_window, parent=None, *, encrypted_mode: bool = False
    ):
        super().__init__(parent)
        self.settings = settings
        self.main_window = main_window
        self.encrypted_mode = bool(encrypted_mode)
        self._initial_data_dir = str(self._get_setting("data_directory", "") or "")
        self._build_ui()
        self.refresh()

    # -- Hilfen -------------------------------------------------------
    def _get_setting(self, key, default=None):
        try:
            return self.settings.get(key, default)
        except Exception:
            return default

    def _mw(self):
        return self.main_window

    # -- Aufbau -------------------------------------------------------
    def _build_ui(self) -> None:
        c = ui_colors(self)
        root = QVBoxLayout(self)

        # v2.2.1 (Bericht-Punkt 6): Fehler landeten bisher nur im Log – der
        # Nutzer sah nichts, wenn z.B. der Speicherort nicht gespeichert oder
        # eine Hub-Aktion abgebrochen wurde. Sichtbare Fehlerzeile + Dialog.
        self.lbl_hub_error = QLabel("")
        self.lbl_hub_error.setWordWrap(True)
        self.lbl_hub_error.setVisible(False)
        self.lbl_hub_error.setStyleSheet(
            f"color: {ui_colors(self).negative}; font-weight: 600;"
        )
        root.addWidget(self.lbl_hub_error)
        root.setContentsMargins(4, 4, 4, 4)

        intro = QLabel(tr("account_hub.intro"))
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {c.text_dim}; padding-bottom: 4px;")
        root.addWidget(intro)

        # --- Konto (nur bei verschlüsseltem Login) ---
        if self.encrypted_mode:
            gb_acc = QGroupBox(tr("account_hub.group_account"))
            fa = QVBoxLayout(gb_acc)
            self.lbl_account_summary = QLabel("")
            self.lbl_account_summary.setWordWrap(True)
            fa.addWidget(self.lbl_account_summary)
            row_acc = QHBoxLayout()
            self.btn_account = QPushButton(tr("account_hub.btn_manage_account"))
            self.btn_account.clicked.connect(self._open_account)
            row_acc.addWidget(self.btn_account)
            row_acc.addStretch(1)
            fa.addLayout(row_acc)
            root.addWidget(gb_acc)

        # --- Speicherort (inline, mit Datenübernahme) ---
        gb_loc = QGroupBox(tr("settings.data_dir_group"))
        fl = QFormLayout(gb_loc)
        self.le_data_dir = QLineEdit()
        self.le_data_dir.setReadOnly(True)
        self.le_data_dir.setPlaceholderText(
            tr("settings.data_dir_portable_placeholder")
        )
        row_loc = QHBoxLayout()
        self.btn_loc_browse = QPushButton(tr("settings.choose_data_dir"))
        self.btn_loc_browse.clicked.connect(self._choose_data_dir)
        self.btn_loc_reset = QPushButton(tr("settings.reset_data_dir_portable"))
        self.btn_loc_reset.clicked.connect(self._reset_data_dir)
        self.btn_loc_save = QPushButton(tr("account_hub.btn_apply_location"))
        self.btn_loc_save.clicked.connect(self._apply_data_dir)
        row_loc.addWidget(self.btn_loc_browse)
        row_loc.addWidget(self.btn_loc_reset)
        row_loc.addWidget(self.btn_loc_save)
        row_loc.addStretch(1)
        row_loc_w = QWidget()
        row_loc_w.setLayout(row_loc)
        fl.addRow(tr("settings_ui.data_dir_current"), self.le_data_dir)
        fl.addRow("", row_loc_w)
        self.lbl_loc_effective = QLabel("")
        self.lbl_loc_effective.setWordWrap(True)
        self.lbl_loc_effective.setStyleSheet(f"color: {c.text_dim}; padding-top: 2px;")
        fl.addRow("", self.lbl_loc_effective)
        hint = QLabel(tr("settings.data_dir_restart_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {c.text_dim}; padding-top: 4px;")
        fl.addRow("", hint)
        root.addWidget(gb_loc)

        # --- Sicherung (Backup) ---
        gb_bak = QGroupBox(tr("account_hub.group_backup"))
        fb = QVBoxLayout(gb_bak)
        lbl_bak = QLabel(tr("account_hub.backup_desc"))
        lbl_bak.setWordWrap(True)
        lbl_bak.setStyleSheet(f"color: {c.text_dim};")
        fb.addWidget(lbl_bak)
        row_bak = QHBoxLayout()
        self.btn_backup = QPushButton(tr("account_hub.btn_backup"))
        self.btn_backup.clicked.connect(self._open_backup)
        row_bak.addWidget(self.btn_backup)
        row_bak.addStretch(1)
        fb.addLayout(row_bak)
        root.addWidget(gb_bak)

        # --- Zurücksetzen & Wartung ---
        gb_db = QGroupBox(tr("account_hub.group_reset"))
        fd = QVBoxLayout(gb_db)
        lbl_db = QLabel(tr("account_hub.reset_desc"))
        lbl_db.setWordWrap(True)
        lbl_db.setStyleSheet(f"color: {c.text_dim};")
        fd.addWidget(lbl_db)
        row_db = QHBoxLayout()
        self.btn_db = QPushButton(tr("account_hub.btn_reset_db"))
        self.btn_db.clicked.connect(self._open_database)
        row_db.addWidget(self.btn_db)
        row_db.addStretch(1)
        fd.addLayout(row_db)
        root.addWidget(gb_db)

        root.addStretch(1)

    # -- Aktualisierung ----------------------------------------------
    def refresh(self) -> None:
        """Lädt aktuelle Werte (Speicherort, Konto-Zusammenfassung)."""
        try:
            self.le_data_dir.setText(str(self._get_setting("data_directory", "") or ""))
            self._initial_data_dir = self.le_data_dir.text().strip()
            self._refresh_effective()
        except Exception as e:
            logger.debug("Hub-Refresh (Speicherort) fehlgeschlagen: %s", e)
            self._show_error(trf("hub.error_refresh", error=str(e)))
        if self.encrypted_mode and hasattr(self, "lbl_account_summary"):
            try:
                user = getattr(self._mw(), "_active_user", None)
                name = getattr(user, "display_name", None) or tr(
                    "account_hub.unknown_user"
                )
                self.lbl_account_summary.setText(
                    trf("account_hub.account_summary", name=name)
                )
            except Exception as e:
                logger.debug("Hub-Refresh (Konto) fehlgeschlagen: %s", e)
                self._show_error(trf("hub.error_refresh", error=str(e)))

    def _refresh_effective(self) -> None:
        try:
            from model.app_paths import resolve_data_dir

            raw = self.le_data_dir.text().strip()
            eff = resolve_data_dir(raw)
            self.lbl_loc_effective.setText(
                trf("settings.data_dir_effective", path=str(eff))
            )
        except Exception:
            self.lbl_loc_effective.setText("")

    # -- Speicherort -------------------------------------------------
    def _choose_data_dir(self) -> None:
        from model.app_paths import portable_data_dir

        start = self.le_data_dir.text().strip() or str(portable_data_dir())
        chosen = QFileDialog.getExistingDirectory(
            self, tr("settings.choose_data_dir"), start
        )
        if chosen:
            self.le_data_dir.setText(chosen.strip())
            self._refresh_effective()

    def _reset_data_dir(self) -> None:
        self.le_data_dir.setText("")
        self._refresh_effective()

    def _apply_data_dir(self) -> None:
        """Wendet den gewählten Speicherort an (inkl. optionaler Datenübernahme)."""
        new_raw = self.le_data_dir.text().strip()
        if new_raw == self._initial_data_dir:
            return  # keine Änderung -> keine Aktion / kein Neustart-Hinweis
        mw = self._mw()
        handler = getattr(mw, "_handle_data_directory_change", None)
        if callable(handler):
            applied = handler(new_raw)
            if applied is not False:
                self._initial_data_dir = str(
                    self._get_setting("data_directory", new_raw) or ""
                )
                self.le_data_dir.setText(self._initial_data_dir)
                self._refresh_effective()
        else:
            # Fallback: nur speichern
            try:
                self.settings.data_directory = new_raw
                self._initial_data_dir = new_raw
            except Exception as e:
                logger.warning("Speicherort konnte nicht gespeichert werden: %s", e)
                self._show_error(
                    trf("hub.error_save_location", error=str(e)), dialog=True
                )

    def _show_error(self, text: str, *, dialog: bool = False) -> None:
        """Zeigt Fehler sichtbar im Hub (und optional als Dialog)."""
        try:
            self.lbl_hub_error.setText(f"⚠️ {text}")
            self.lbl_hub_error.setVisible(True)
        except Exception as e:
            logger.debug("hub error label: %s", e)
        if dialog:
            try:
                show_warning(self, tr("msg.error"), text)
            except Exception as e:
                logger.debug("hub error dialog: %s", e)

    def _clear_error(self) -> None:
        try:
            self.lbl_hub_error.setVisible(False)
            self.lbl_hub_error.setText("")
        except Exception:
            pass

    # -- Delegationen an bestehende Dialoge --------------------------
    def _open_account(self) -> None:
        self._call_mw("_show_account_management")

    def _open_backup(self) -> None:
        self._call_mw("_show_backup_restore")

    def _open_database(self) -> None:
        self._call_mw("_show_database_management")

    def _call_mw(self, method_name: str) -> None:
        mw = self._mw()
        fn = getattr(mw, method_name, None)
        if callable(fn):
            try:
                self._clear_error()
                fn()
            except Exception as e:
                logger.exception("Hub-Aktion %s fehlgeschlagen: %s", method_name, e)
                self._show_error(trf("hub.error_action", error=str(e)), dialog=True)
        # Nach Rückkehr Werte aktualisieren (z.B. Speicherort nach Reset/Restore)
        self.refresh()
