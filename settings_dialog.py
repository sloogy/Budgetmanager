from __future__ import annotations

import logging
logger = logging.getLogger(__name__)
from pathlib import Path
from views.ui_colors import ui_colors
from PySide6.QtWidgets import (
    QDialog, QListWidget, QListWidgetItem, QStackedWidget, QDialogButtonBox,
    QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QLabel,
    QCheckBox, QComboBox, QSpinBox, QPushButton, QLineEdit,
    QFileDialog, QMessageBox, QWidget, QApplication,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QKeySequenceEdit
)
from PySide6.QtCore import QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QFont
from theme_manager import ThemeManager
from views.theme_editor_dialog import ThemeEditorDialog
from model.shortcuts_config import (
    SHORTCUT_DEFS, load_shortcuts, save_shortcuts, default_key,
    shortcut_display_name, all_action_ids
)

# i18n
from utils.i18n import tr, trf, available_languages


class SettingsDialog(QDialog):
    """
    Neuer Einstellungsdialog (Deutsch, UX-optimiert), kompatibel zur bestehenden App.

    Erwartet: `settings` Instanz aus settings.py (JSON Settings).
    Liefert: get_settings() dict mit bestehenden Keys:
      - theme, auto_save, ask_due, refresh_on_start, recent_days
    plus zusätzliche neue Keys (werden in settings.json gespeichert, wenn MainWindow es übernimmt).
    """

    def __init__(self, settings, parent=None, app_version: str | None = None,
                 encrypted_mode: bool = False, encrypted_session=None):
        super().__init__(parent)
        self.settings = settings
        self.app_version = app_version or ""
        self.encrypted_mode = encrypted_mode
        # Optional: EncryptedSession (damit manuelles Backup auch im verschlüsselten Modus funktioniert)
        self.encrypted_session = encrypted_session
        
        # Theme Manager initialisieren
        self.theme_manager = ThemeManager(settings)

        # Merker: wurde bereits "Anwenden" gedrückt?
        # Wenn ja, soll "OK" nur noch schliessen (User-Wunsch).
        self._applied_once = False
        self._last_mode = None  # "hell" oder "dunkel" (für Filter-Logik)
        self._last_selected_by_mode: dict[str, str] = {}
        self._last_mode = None  # "hell" | "dunkel"

        self.setWindowTitle(tr("dlg.settings"))
        self.setMinimumSize(860, 560)

        # --- Root Layout
        root = QVBoxLayout(self)

        content = QHBoxLayout()
        root.addLayout(content)

        # --- Navigation links
        self.lw_nav = QListWidget()
        self.lw_nav.setMaximumWidth(220)
        self.lw_nav.addItems([
            tr("settings.general"),
            tr("settings.behavior"),
            tr("settings.appearance"),
            tr("dlg.shortcuts"),
            tr("settings.database"),
            tr("settings.about"),
        ])
        content.addWidget(self.lw_nav)

        # --- Seiten rechts
        self.sw_pages = QStackedWidget()
        content.addWidget(self.sw_pages, 1)

        # Seiten erstellen
        self.page_general = self._build_page_general()
        self.page_behavior = self._build_page_behavior()
        self.page_appearance = self._build_page_appearance()
        self.page_shortcuts = self._build_page_shortcuts()
        self.page_database = self._build_page_database()
        self.page_about = self._build_page_about()

        for p in [self.page_general, self.page_behavior, self.page_appearance,
                  self.page_shortcuts, self.page_database, self.page_about]:
            self.sw_pages.addWidget(p)

        self.lw_nav.currentRowChanged.connect(self.sw_pages.setCurrentIndex)
        self.lw_nav.setCurrentRow(0)

        # --- Buttons unten
        self.bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel
        )

        # Deutsche Button-Texte (Qt übersetzt nicht immer zuverlässig)
        try:
            self.bb.button(QDialogButtonBox.Ok).setText("OK")
            self.bb.button(QDialogButtonBox.Apply).setText(tr("btn.apply"))
            self.bb.button(QDialogButtonBox.Cancel).setText(tr("btn.cancel"))
        except Exception as e:
            logger.debug("self.bb.button(QDialogButtonBox.Ok).setText('OK'): %s", e)
        self.bb.accepted.connect(self._on_ok)
        self.bb.rejected.connect(self.reject)
        self.bb.clicked.connect(self._on_button_clicked)
        root.addWidget(self.bb)

        # --- UI mit aktuellen Werten füllen
        self._load_from_settings()

        # Enable/disable
        self.cb_auto_backup.toggled.connect(self.sb_backup_days.setEnabled)
        self.sb_backup_days.setEnabled(self.cb_auto_backup.isChecked())

        # Sofort-Vorschau Designprofil
        self.cmb_design_profile.currentTextChanged.connect(self._preview_profile)
        self.sb_fontsize.valueChanged.connect(self._on_fontsize_changed)
        self.btn_open_profiles.clicked.connect(self._open_profile_manager)

        # Hell/Dunkel = Filter für Profil-Dropdown
        self.cmb_theme.currentTextChanged.connect(self._on_mode_changed)

    # ---------------------------------------------------------------------
    # Seitenbau
    # ---------------------------------------------------------------------
    def _title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        f = lbl.font()
        f.setPointSize(14)
        f.setBold(True)
        lbl.setFont(f)
        return lbl

    def _build_page_general(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self._title(tr("settings.general")))

        gb_start = QGroupBox("Start & Bedienung")
        vb = QVBoxLayout(gb_start)
        self.cb_show_onboarding = QCheckBox(tr("chk.show_onboarding"))
        self.cb_remember_last_tab = QCheckBox(tr("dlg.letzten_geoeffneten_reiter_merken"))
        self.cb_remember_filters = QCheckBox(tr("settings.remember_filters"))
        self.cb_refresh_on_start = QCheckBox(tr("chk.auto_update"))
        vb.addWidget(self.cb_show_onboarding)
        vb.addWidget(self.cb_remember_last_tab)
        vb.addWidget(self.cb_remember_filters)
        vb.addWidget(self.cb_refresh_on_start)
        lay.addWidget(gb_start)

        gb_locale = QGroupBox(tr("grp.locale"))
        fl = QFormLayout(gb_locale)
        self.cmb_language = QComboBox()
        # Sprachen dynamisch aus locales/*.json entdecken
        for lang in available_languages():
            self.cmb_language.addItem(lang.get("name", lang.get("code", "")), lang.get("code", ""))
        fl.addRow(tr("settings.language"), self.cmb_language)

        self.cmb_currency = QComboBox()
        from utils.money import CURRENCIES, CURRENCY_CODES
        for code in CURRENCY_CODES:
            self.cmb_currency.addItem(CURRENCIES[code]["label"], code)
        self.cmb_currency.setToolTip(tr("settings.currency_tip"))
        fl.addRow(tr("settings.currency"), self.cmb_currency)
        lay.addWidget(gb_locale)

        lay.addStretch(1)
        return w

    def _build_page_behavior(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self._title(tr("settings.behavior")))

        gb_workflow = QGroupBox("Eingabe & Workflow")
        vb = QVBoxLayout(gb_workflow)

        # Bestehende App-Settings
        self.cb_auto_save = QCheckBox(tr("settings.auto_save"))
        self.cb_ask_due = QCheckBox(tr("dlg.bei_faelligkeit_nachfragen_z"))

        # Zusätzliche UX-Settings (werden in JSON gespeichert, wenn MainWindow sie übernimmt)
        self.cb_warn_delete = QCheckBox(tr("dlg.loeschvorgaenge_bestaetigen_lassen"))
        self.cb_warn_budget_overrun = QCheckBox(tr("dlg.warnen_wenn_das_budget"))

        vb.addWidget(self.cb_auto_save)
        vb.addWidget(self.cb_ask_due)
        vb.addSpacing(8)
        vb.addWidget(self.cb_warn_delete)
        vb.addWidget(self.cb_warn_budget_overrun)
        lay.addWidget(gb_workflow)

        gb_tracking = QGroupBox(tr("tab.tracking"))
        fl = QFormLayout(gb_tracking)
        self.cmb_recent_days = QComboBox()
        self.cmb_recent_days.addItems(["14", "30"])
        fl.addRow("Schnellfilter „nur letzte … Tage“", self.cmb_recent_days)

        # Wiederkehrend: Default-Tag
        self.cmb_recurring_day = QComboBox()
        for d in range(1, 29):
            self.cmb_recurring_day.addItem(str(d), d)
        self.cmb_recurring_day.addItem(tr("settings.month_end"), 31)
        self.cmb_recurring_day.setToolTip(
            "Bevorzugter Tag für neue wiederkehrende Kategorien/Buchungen.\n"
            "Wird automatisch gesetzt, wenn du eine Kategorie als wiederkehrend markierst.\n"
            "Monatsende = letzter Tag des Monats."
        )
        fl.addRow("Bevorzugter Tag (wiederkehrend)", self.cmb_recurring_day)
        lay.addWidget(gb_tracking)

        # Budget-Übersicht
        gb_budget_ov = QGroupBox(tr("grp.budget_overview"))
        fl_bo = QFormLayout(gb_budget_ov)
        self.sb_budget_suggestion_months = QSpinBox()
        self.sb_budget_suggestion_months.setRange(2, 12)
        self.sb_budget_suggestion_months.setSuffix(" Monate")
        self.sb_budget_suggestion_months.setToolTip(
            "Mindestanzahl aufeinanderfolgender Monate mit gleichem Trend,\n"
            "bevor ein Anpassungsvorschlag angezeigt wird."
        )
        fl_bo.addRow(tr("dlg.ueberschussdefizitvorschlag_ab"), self.sb_budget_suggestion_months)

        self.cb_carryover_start = QComboBox()
        self.cb_carryover_start.addItems([
            "Januar", "Februar", "März", "April", "Mai", "Juni",
            "Juli", "August", tr("month.9"), "Oktober", tr("month.11"), tr("month.12")
        ])
        self.cb_carryover_start.setToolTip(
            "Ab welchem Monat soll der Übertrag kumuliert werden?\n"
            "Beispiel: Ab März → Jan/Feb haben keinen Übertrag,\n"
            "Kumulation beginnt erst ab März."
        )
        fl_bo.addRow("Kumulation Startmonat", self.cb_carryover_start)

        self.sb_carryover_start_year = QSpinBox()
        self.sb_carryover_start_year.setRange(2020, 2099)
        self.sb_carryover_start_year.setToolTip(
            "Ab welchem Jahr soll der Übertrag kumuliert werden?\n"
            "Der Übertrag wird jahresübergreifend mitgenommen.\n"
            "Beispiel: Startjahr 2025, Startmonat März →\n"
            "Kumulation beginnt ab März 2025 und zieht sich\n"
            "über alle Folgejahre."
        )
        fl_bo.addRow("Kumulation Startjahr", self.sb_carryover_start_year)

        lay.addWidget(gb_budget_ov)

        # Experten-Einstellungen
        gb_expert = QGroupBox(tr("settings.expert_mode"))
        vb_expert = QVBoxLayout(gb_expert)
        
        self.cb_show_categories_tab = QCheckBox("Separaten Kategorien-Tab anzeigen")
        self.cb_show_categories_tab.setToolTip(
            "Aktiviert den separaten Kategorien-Tab für erweiterte Kategorie-Verwaltung.\n\n"
            "Standard: Deaktiviert – Kategorien werden direkt im Budget-Dialog erstellt und verwaltet.\n"
            "Der separate Tab ist nützlich für Massenbearbeitung, Filter und erweiterte Optionen.\n\n"
            "Änderung erfordert Neustart der Anwendung."
        )
        vb_expert.addWidget(self.cb_show_categories_tab)
        
        hint = QLabel(
            "<small><i>Hinweis: Kategorien können auch direkt im Budget-Dialog über das ⚙-Menü "
            "erstellt und bearbeitet werden.</i></small>"
        )
        hint.setWordWrap(True)
        vb_expert.addWidget(hint)
        
        lay.addWidget(gb_expert)

        lay.addStretch(1)
        return w

    def _build_page_appearance(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self._title(tr("settings.appearance")))

        gb_theme = QGroupBox(tr("dlg.appearance"))
        fl = QFormLayout(gb_theme)
        self.cmb_theme = QComboBox()
        # System-Option würde aktuell wie "Hell" wirken (ThemeManager kennt nur light/dark)
        self.cmb_theme.addItems([tr("settings.theme_light"), tr("settings.theme_dark")])
        fl.addRow("Design", self.cmb_theme)
        
        # Design-Profil Dropdown und Manager-Button
        self.cmb_design_profile = QComboBox()
        self.btn_open_profiles = QPushButton(tr("btn.manage_profiles"))
        profile_layout = QHBoxLayout()
        profile_layout.addWidget(self.cmb_design_profile, 1)
        profile_layout.addWidget(self.btn_open_profiles)
        fl.addRow(tr("settings.design_profile"), profile_layout)

        # Schriftgröße (pro Profil)
        self.sb_fontsize = QSpinBox()
        self.sb_fontsize.setRange(8, 16)
        self.sb_fontsize.setSingleStep(1)
        self.sb_fontsize.setValue(10)
        fl.addRow(tr("dlg.schriftgroesse"), self.sb_fontsize)
        
        lay.addWidget(gb_theme)

        gb_tables = QGroupBox("Tabellen & Listen")
        fl2 = QFormLayout(gb_tables)
        self.cmb_density = QComboBox()
        self.cmb_density.addItems([tr("settings.density_compact"), tr("settings.density_normal"), tr("settings.density_large")])
        self.cb_highlight_fixcosts = QCheckBox(tr("settings.fix_highlight"))
        fl2.addRow(tr("settings.table_density"), self.cmb_density)
        fl2.addRow(self.cb_highlight_fixcosts)
        lay.addWidget(gb_tables)

        lay.addStretch(1)
        return w

    def _build_page_shortcuts(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self._title(tr("dlg.shortcuts")))

        hint = QLabel(
            "<i>Klicke auf ein Kürzel und drücke die gewünschte Tastenkombination. "
            "Leere Felder deaktivieren das Kürzel.</i>"
        )
        hint.setWordWrap(True)
        lay.addWidget(hint)

        # Shortcuts-Tabelle
        self.tbl_shortcuts = QTableWidget()
        self.tbl_shortcuts.setColumnCount(4)
        self.tbl_shortcuts.setHorizontalHeaderLabels([
            "Aktion", tr("header.shortcut_current"), tr("settings.standard"), "Gruppe"
        ])
        self.tbl_shortcuts.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_shortcuts.setAlternatingRowColors(True)
        self.tbl_shortcuts.verticalHeader().setVisible(False)

        # Daten laden
        current_map = load_shortcuts(self.settings)
        self._shortcut_editors: dict[str, QKeySequenceEdit] = {}

        self.tbl_shortcuts.setRowCount(len(SHORTCUT_DEFS))
        for i, (aid, dkey, label, group) in enumerate(SHORTCUT_DEFS):
            # Aktion (read-only)
            act_item = QTableWidgetItem(label)
            act_item.setFlags(act_item.flags() & ~Qt.ItemIsEditable)
            self.tbl_shortcuts.setItem(i, 0, act_item)

            # KeySequenceEdit für aktives Kürzel
            editor = QKeySequenceEdit()
            cur_key = current_map.get(aid, dkey)
            if cur_key:
                from PySide6.QtGui import QKeySequence
                editor.setKeySequence(QKeySequence(cur_key))
            self._shortcut_editors[aid] = editor
            self.tbl_shortcuts.setCellWidget(i, 1, editor)

            # Standard (read-only)
            std_item = QTableWidgetItem(shortcut_display_name(dkey))
            std_item.setFlags(std_item.flags() & ~Qt.ItemIsEditable)
            std_item.setForeground(Qt.gray)
            self.tbl_shortcuts.setItem(i, 2, std_item)

            # Gruppe (read-only)
            grp_item = QTableWidgetItem(group)
            grp_item.setFlags(grp_item.flags() & ~Qt.ItemIsEditable)
            grp_item.setForeground(Qt.gray)
            self.tbl_shortcuts.setItem(i, 3, grp_item)

        # Spaltenbreiten
        header = self.tbl_shortcuts.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self.tbl_shortcuts.setColumnWidth(1, 180)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.tbl_shortcuts.setColumnWidth(2, 130)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.tbl_shortcuts.setColumnWidth(3, 100)

        lay.addWidget(self.tbl_shortcuts, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_reset_all = QPushButton(tr("dlg.alle_auf_standard_zuruecksetzen"))
        btn_reset_all.clicked.connect(self._reset_all_shortcuts)
        btn_layout.addWidget(btn_reset_all)
        btn_layout.addStretch()
        lay.addLayout(btn_layout)

        return w

    def _reset_all_shortcuts(self) -> None:
        """Setzt alle Shortcut-Editoren auf die Standardwerte zurück."""
        from PySide6.QtGui import QKeySequence
        for aid, dkey, _label, _grp in SHORTCUT_DEFS:
            editor = self._shortcut_editors.get(aid)
            if editor:
                if dkey:
                    editor.setKeySequence(QKeySequence(dkey))
                else:
                    editor.clear()

    def _get_shortcut_mapping(self) -> dict[str, str]:
        """Liest die aktuellen Kürzel aus den Editoren."""
        result: dict[str, str] = {}
        for aid in all_action_ids():
            editor = self._shortcut_editors.get(aid)
            if editor:
                seq = editor.keySequence()
                result[aid] = seq.toString() if not seq.isEmpty() else ""
            else:
                result[aid] = default_key(aid)
        return result

    def _build_page_database(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self._title(tr("settings.database")))

        if self.encrypted_mode:
            # Bei verschlüsselter DB: Info statt Pfad-Wechsel
            gb_info = QGroupBox(tr("dlg.verschluesselte_datenbank"))
            fl_info = QFormLayout(gb_info)
            lbl_enc = QLabel(tr("settings_ui.enc_info"))
            lbl_enc.setWordWrap(True)
            lbl_enc.setStyleSheet(f"padding: 8px; color: {ui_colors(self).text_dim};")
            fl_info.addRow(lbl_enc)
            lay.addWidget(gb_info)
        else:
            gb_db = QGroupBox(tr("grp.db_path"))
            fl = QFormLayout(gb_db)
            self.le_db_path = QLineEdit()
            self.le_db_path.setReadOnly(True)
            self.btn_db_change = QPushButton(tr("settings.change_db"))
            self.btn_db_change.clicked.connect(self._choose_db)

            fl.addRow(tr("settings_ui.lbl_path"), self.le_db_path)
            fl.addRow("", self.btn_db_change)
            lay.addWidget(gb_db)

        gb_backup = QGroupBox(tr("settings.backup_group"))
        flb = QFormLayout(gb_backup)
        self.cb_auto_backup = QCheckBox(tr("chk.auto_backup"))
        self.sb_backup_days = QSpinBox()
        self.sb_backup_days.setRange(1, 90)
        self.sb_backup_days.setValue(30)
        self.sb_backup_days.setSuffix(tr("settings_ui.suffix_days"))

        self.sb_backup_keep = QSpinBox()
        self.sb_backup_keep.setRange(3, 200)
        self.sb_backup_keep.setValue(10)
        self.sb_backup_keep.setSuffix(tr("settings_ui.suffix_backups"))
        self.sb_backup_keep.setToolTip(tr("settings_ui.backup_keep_tooltip"))
        self.btn_backup_now = QPushButton(tr("settings.create_backup_now"))
        self.btn_backup_now.clicked.connect(self._create_backup_now)
        self.lbl_last_backup = QLabel(tr("settings_ui.last_backup_never"))
        self.lbl_backup_count = QLabel("0")

        flb.addRow(self.cb_auto_backup)
        flb.addRow(tr("settings_ui.lbl_interval"), self.sb_backup_days)
        flb.addRow(tr("settings_ui.lbl_keep"), self.sb_backup_keep)
        flb.addRow(tr("settings_ui.lbl_last_backup"), self.lbl_last_backup)
        flb.addRow(tr("settings_ui.lbl_backup_count"), self.lbl_backup_count)
        flb.addRow("", self.btn_backup_now)
        lay.addWidget(gb_backup)

        lay.addStretch(1)
        return w

    def _build_page_about(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self._title(tr("settings.about")))

        gb = QGroupBox(tr("grp.application"))
        fl = QFormLayout(gb)
        self.lbl_app_name = QLabel("Budgetmanager")
        self.lbl_version = QLabel(self.app_version or "(Version unbekannt)")
        fl.addRow(tr("settings_ui.about_name"), self.lbl_app_name)
        fl.addRow(tr("settings_ui.about_version"), self.lbl_version)
        lay.addWidget(gb)

        lay.addStretch(1)
        return w

    # ---------------------------------------------------------------------
    # Laden / Speichern
    # ---------------------------------------------------------------------
    def _load_from_settings(self) -> None:
        # Allgemein (neue Keys, werden via get_settings zurückgegeben)
        self.cb_show_onboarding.setChecked(bool(self.settings.get("show_onboarding", True)))
        self.cb_remember_last_tab.setChecked(bool(self.settings.get("remember_last_tab", True)))
        self.cb_remember_filters.setChecked(bool(self.settings.get("remember_filters", True)))
        self.cb_refresh_on_start.setChecked(bool(self.settings.get("refresh_on_start", False)))

        # Sprache kann als Name ("Deutsch") oder Code ("de") gespeichert sein.
        saved_lang = str(self.settings.get("language", "de"))
        # 1) Match per code (userData)
        idx = -1
        for i in range(self.cmb_language.count()):
            if str(self.cmb_language.itemData(i)) == saved_lang:
                idx = i
                break
        if idx >= 0:
            self.cmb_language.setCurrentIndex(idx)
        else:
            # 2) Fallback: Match per sichtbarem Namen
            self.cmb_language.setCurrentText(saved_lang)

        # Währung: nach Data-Feld (CHF, EUR, …) suchen
        saved_currency = str(self.settings.get("currency", "CHF"))
        for i in range(self.cmb_currency.count()):
            if self.cmb_currency.itemData(i) == saved_currency:
                self.cmb_currency.setCurrentIndex(i)
                break

        # Verhalten (bestehend)
        self.cb_auto_save.setChecked(bool(self.settings.auto_save))
        self.cb_ask_due.setChecked(bool(self.settings.ask_due))
        self.cmb_recent_days.setCurrentText(str(self.settings.recent_days))

        # Wiederkehrend: Default-Tag
        pref_day = int(self.settings.get("recurring_preferred_day", 25) or 25)
        idx = self.cmb_recurring_day.findData(pref_day)
        if idx < 0:
            idx = self.cmb_recurring_day.findData(25)
        self.cmb_recurring_day.setCurrentIndex(max(0, idx))

        # Budget-Übersicht
        self.sb_budget_suggestion_months.setValue(int(self.settings.get("budget_suggestion_months", 3) or 3))
        self.cb_carryover_start.setCurrentIndex(int(self.settings.get("carryover_start_month", 1) or 1) - 1)
        saved_year = int(self.settings.get("carryover_start_year", 0) or 0)
        if saved_year < 2020:
            from datetime import date as _date
            saved_year = _date.today().year
        self.sb_carryover_start_year.setValue(saved_year)

        # Zusätzliche Warnungen (neue Keys)
        self.cb_warn_delete.setChecked(bool(self.settings.get("warn_delete", True)))
        self.cb_warn_budget_overrun.setChecked(bool(self.settings.get("warn_budget_overrun", True)))

        # Experten-Modus
        self.cb_show_categories_tab.setChecked(bool(self.settings.get("show_categories_tab", False)))

        # Darstellung
        theme = (self.settings.theme or "light").lower()
        # Hell/Dunkel Dropdown auf Settings spiegeln
        blocker = QSignalBlocker(self.cmb_theme)
        self.cmb_theme.setCurrentText(tr("settings.theme_dark") if theme == "dark" else tr("settings.theme_light"))
        del blocker

        # Profil-Dropdown anhand Hell/Dunkel filtern
        self._last_mode = self._current_mode()
        self._load_design_profiles()
        _density_map = {"Kompakt": tr("settings.density_compact"), "Normal": tr("settings.density_normal"), "Groß": tr("settings.density_large")}
        _raw_density = str(self.settings.get("table_density", "Normal"))
        self.cmb_density.setCurrentText(_density_map.get(_raw_density, tr("settings.density_normal")))
        self.cb_highlight_fixcosts.setChecked(bool(self.settings.get("highlight_fixcosts", True)))

        # Datenbank
        if hasattr(self, 'le_db_path'):
            self.le_db_path.setText(str(self.settings.database_path))

        # Backup (neue Keys)
        self.cb_auto_backup.setChecked(bool(self.settings.get("auto_backup", False)))
        self.sb_backup_days.setValue(int(self.settings.get("backup_days", 30)))
        self.sb_backup_keep.setValue(int(self.settings.get("auto_backup_keep", 10) or 10))
        self._refresh_backup_status()

        # Nach vollständigem Rendern prüfen ob Backup-Limit überschritten
        from model.app_paths import resolve_in_app
        _bdir = resolve_in_app(self.settings.get("backup_directory", "data/backups"))
        QTimer.singleShot(300, lambda: self._check_and_cleanup_backups(_bdir))

    def get_settings(self) -> dict:
        """Kompatibel zum bisherigen MainWindow._show_settings()"""
        theme_value = "dark" if self.cmb_theme.currentText() == tr("settings.theme_dark") else "light"

        return {
            # Keys, die MainWindow bereits verwendet:
            "theme": theme_value,
            "auto_save": self.cb_auto_save.isChecked(),
            "ask_due": self.cb_ask_due.isChecked(),
            "refresh_on_start": self.cb_refresh_on_start.isChecked(),
            "recent_days": int(self.cmb_recent_days.currentText()),
            "recurring_preferred_day": int(self.cmb_recurring_day.currentData() or 25),
            "budget_suggestion_months": int(self.sb_budget_suggestion_months.value()),
            "carryover_start_month": self.cb_carryover_start.currentIndex() + 1,
            "carryover_start_year": self.sb_carryover_start_year.value(),

            # Zusätzliche neue Keys (optional später im MainWindow übernehmen):
            "show_onboarding": self.cb_show_onboarding.isChecked(),
            "remember_last_tab": self.cb_remember_last_tab.isChecked(),
            "remember_filters": self.cb_remember_filters.isChecked(),
            # Persistiere Code, nicht den Anzeigenamen (stabil bei Übersetzungen)
            "language": self.cmb_language.currentData() or self.cmb_language.currentText(),
            "currency": self.cmb_currency.currentData() or "CHF",
            "warn_delete": self.cb_warn_delete.isChecked(),
            "warn_budget_overrun": self.cb_warn_budget_overrun.isChecked(),
            "table_density": {"Kompakt": "Kompakt", "Normal": "Normal", "Groß": "Groß", tr("settings.density_compact"): "Kompakt", tr("settings.density_normal"): "Normal", tr("settings.density_large"): "Groß"}.get(self.cmb_density.currentText(), "Normal"),
            "highlight_fixcosts": self.cb_highlight_fixcosts.isChecked(),
            "database_path": self.le_db_path.text().strip() if hasattr(self, 'le_db_path') else "",
            "auto_backup": self.cb_auto_backup.isChecked(),
            "backup_days": int(self.sb_backup_days.value()),
            "auto_backup_keep": int(self.sb_backup_keep.value()),
            # Experten-Modus
            "show_categories_tab": self.cb_show_categories_tab.isChecked(),
            # Tastenkürzel
            "shortcuts": self._get_shortcut_mapping(),
        }

    # ---------------------------------------------------------------------
    # Actions
    # ---------------------------------------------------------------------
    def _on_button_clicked(self, btn) -> None:
        role = self.bb.buttonRole(btn)
        if role == QDialogButtonBox.ApplyRole:
            self._apply()

    def _on_ok(self) -> None:
        # OK soll (wenn vorher schon "Anwenden" gedrückt wurde) nur noch schliessen.
        # Trotzdem persistieren wir die Auswahl, damit MainWindow nach Dialogschluss korrekt lädt.
        self._persist_design_selection()
        try:
            self._apply_fontsize_to_profile(self.cmb_design_profile.currentText(), int(self.sb_fontsize.value()))
        except Exception as e:
            logger.debug("self._apply_fontsize_to_profile(self.cmb_design_pr: %s", e)
        if not self._applied_once:
            self._apply()
        self.accept()

    def _apply(self) -> None:
        # Theme anwenden + persistieren
        self._persist_design_selection()
        # Schriftgröße ins Profil schreiben
        try:
            self._apply_fontsize_to_profile(self.cmb_design_profile.currentText(), int(self.sb_fontsize.value()))
        except Exception as e:
            logger.debug("self._apply_fontsize_to_profile(self.cmb_design_pr: %s", e)
        profile_name = self.cmb_design_profile.currentText().strip()
        if profile_name and profile_name not in (tr("dlg.keine_profile_vorhanden"), tr("dlg.keine_passenden_profile")):
            self.theme_manager.apply_theme(profile_name=profile_name)
            self._applied_once = True

    def _preview_profile(self, profile_name: str) -> None:
        """Vorschau des ausgewählten Design-Profils."""
        profile_name = (profile_name or "").strip()
        if not profile_name or profile_name in (tr("dlg.keine_profile_vorhanden"), tr("dlg.keine_passenden_profile")):
            return

        # Vorschau: Stylesheet direkt setzen, OHNE Settings zu überschreiben
        # Merke Auswahl pro Modus (damit Hell/Dunkel-Wechsel sofort "letztes" Profil nimmt)
        try:
            self._last_selected_by_mode[self._current_mode()] = profile_name
        except Exception as e:
            logger.debug("self._last_selected_by_mode[self._current_mode()] : %s", e)

        app = QApplication.instance()
        prof = self.theme_manager.get_profile(profile_name)
        if app and prof:
            try:
                b = QSignalBlocker(self.sb_fontsize)
                self.sb_fontsize.setValue(int(prof.get('schriftgroesse', 10) or 10))
                del b
            except Exception as e:
                logger.debug("b = QSignalBlocker(self.sb_fontsize): %s", e)
            app.setStyleSheet(self.theme_manager.build_stylesheet(prof))
    
    def _open_profile_manager(self) -> None:
        """Öffnet den Theme-Editor Dialog."""
        dlg = ThemeEditorDialog(self.settings, self.theme_manager, self)
        if dlg.exec():
            # Profile wurden evtl. geändert, Dropdown aktualisieren
            self._load_design_profiles()
    
    def _preview_theme(self, text: str) -> None:
        # Vorschau: Theme anwenden
        profile_name = "Standard Dunkel" if text == tr("settings.theme_dark") else "Standard Hell"
        self.theme_manager.apply_theme(profile_name=profile_name)

    def _choose_db(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("dlg.datenbank_auswaehlen"),
            str(Path.home()),
            "SQLite Datenbank (*.db *.sqlite *.sqlite3);;Alle Dateien (*)",
        )
        if file_path:
            self.le_db_path.setText(file_path)

    def _refresh_backup_status(self) -> None:
        """Aktualisiert 'Letzte Sicherung' und Backup-Anzahl in der UI."""
        from datetime import datetime as _dt
        from model.app_paths import resolve_in_app

        # Letzte Sicherung
        last_backup_str = self.settings.get("last_auto_backup", "")
        if last_backup_str:
            try:
                last_dt = _dt.fromisoformat(last_backup_str)
                self.lbl_last_backup.setText(last_dt.strftime("%d.%m.%Y %H:%M"))
            except (ValueError, TypeError):
                self.lbl_last_backup.setText(tr("settings_ui.last_backup_never"))
        else:
            self.lbl_last_backup.setText(tr("settings_ui.last_backup_never"))

        # Anzahl Backups im Backup-Ordner
        try:
            backup_dir = resolve_in_app(self.settings.get("backup_directory", "data/backups"))
            count = sum(1 for _ in backup_dir.glob("*.bmr")) if backup_dir.exists() else 0
            self.lbl_backup_count.setText(str(count))
        except Exception:
            self.lbl_backup_count.setText("?")

    def _create_backup_now(self) -> None:
        """Erstellt sofort ein manuelles Backup der Datenbank."""
        from datetime import datetime
        from model.app_paths import resolve_in_app
        from model.restore_bundle import create_bundle
        from app_info import APP_NAME, APP_VERSION

        try:
            # Quelle bestimmen: verschlüsselt -> .enc, sonst -> .db
            if self.encrypted_mode and self.encrypted_session is not None:
                try:
                    self.encrypted_session.save()
                except Exception as e:
                    logger.warning("encrypted_session.save() fehlgeschlagen: %s", e)
                src_db = Path(self.encrypted_session.enc_path)
            else:
                src_db = resolve_in_app(self.settings.database_path)

            if not src_db.exists():
                QMessageBox.warning(self, "Sicherung", trf("msg.db_nicht_gefunden"))
                return

            backup_dir = resolve_in_app(
                self.settings.get("backup_directory", "data/backups")
            )
            backup_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"budgetmanager_backup_{timestamp}.bmr"
            backup_path = backup_dir / backup_name

            # Immer als Restore-Bundle speichern (.bmr)
            from model.app_paths import settings_path as _get_settings_path
            from model.user_model import _users_file_path as _get_users_path
            _s_path = _get_settings_path()
            _u_path = _get_users_path()
            create_bundle(
                source_db=src_db,
                out_path=backup_path,
                app=APP_NAME,
                app_version=APP_VERSION,
                note="Manuelles Backup (Einstellungen)",
                settings_path=_s_path if _s_path.exists() else None,
                users_json_path=_u_path if _u_path.exists() else None,
            )

            self.settings.set("last_auto_backup", datetime.now().isoformat())
            self._refresh_backup_status()

            QMessageBox.information(
                self,
                "Sicherung",
                f"Backup erfolgreich erstellt:\n{backup_name}\n\nOrt: {backup_dir}",
            )

            # Bereinigung prüfen
            self._check_and_cleanup_backups(backup_dir)

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Sicherung fehlgeschlagen",
                trf("msg.backup_erstellen_fehler"),
            )

    def _check_and_cleanup_backups(self, backup_dir: Path) -> None:
        """Prüft ob mehr Backups als erlaubt vorhanden sind.
        Zeigt Dialog zur Auswahl, welche gelöscht werden sollen (älteste vorausgewählt).
        """
        keep_n = int(self.settings.get("auto_backup_keep", 10) or 10)
        keep_n = max(3, min(200, keep_n))

        all_backups = sorted(
            backup_dir.glob("budgetmanager_backup_*.bmr"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,  # Neueste zuerst
        )

        if len(all_backups) <= keep_n:
            return

        to_delete_count = len(all_backups) - keep_n

        # Dialog aufbauen
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("backup.cleanup_title"))
        dlg.setModal(True)
        dlg.resize(550, 400)

        layout = QVBoxLayout(dlg)
        intro = QLabel(trf("backup.cleanup_intro", count=len(all_backups), keep=keep_n, excess=to_delete_count))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        list_widget = QListWidget()
        list_widget.setSelectionMode(QAbstractItemView.MultiSelection)

        from datetime import datetime as _dt
        for i, p in enumerate(all_backups):
            size_kb = p.stat().st_size / 1024
            mtime = _dt.fromtimestamp(p.stat().st_mtime).strftime("%d.%m.%Y %H:%M")
            item_text = f"{p.name}  ({size_kb:.1f} KB, {mtime})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, str(p))
            list_widget.addItem(item)
            # Älteste (überschüssige) vorauswählen
            if i >= keep_n:
                item.setSelected(True)

        layout.addWidget(list_widget)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Ok).setText(tr("backup.cleanup_delete_btn"))
        btn_box.button(QDialogButtonBox.Cancel).setText(tr("cancel"))
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        if dlg.exec() != QDialog.Accepted:
            return

        selected = list_widget.selectedItems()
        if not selected:
            return

        errors = []
        for item in selected:
            p = Path(item.data(Qt.UserRole))
            try:
                p.unlink()
            except Exception as e:
                errors.append(f"{p.name}: {e}")

        self._refresh_backup_status()

        if errors:
            QMessageBox.warning(self, tr("msg.error"), "\n".join(errors))

    # -----------------------------------------------------------------
    # Design/Theme-Logik
    # -----------------------------------------------------------------
    def _current_mode(self) -> str:
        """"hell" oder "dunkel" basierend auf dem UI-Dropdown."""
        return "dunkel" if self.cmb_theme.currentText() == tr("settings.theme_dark") else "hell"

    def _on_fontsize_changed(self, _val: int) -> None:
        """Schnelleinstellung: Schriftgröße direkt im aktiven Profil speichern.

        Erwartung: Wenn man in Einstellungen → Darstellung die Schriftgröße ändert,
        soll das *sofort* ins Design-Profil geschrieben werden, damit:
        - der Designmanager (Theme-Editor) denselben Wert sieht
        - beim nächsten Öffnen/Start die Größe identisch ist
        - die UI live reagiert (inkl. Tabellen-Row-Height)
        """

        profile_name = (self.cmb_design_profile.currentText() or "").strip()
        if not profile_name or profile_name in (tr("dlg.keine_profile_vorhanden"), tr("dlg.keine_passenden_profile")):
            return

        try:
            self._apply_fontsize_to_profile(profile_name, int(self.sb_fontsize.value()))
        except Exception as e:
            logger.debug("self._apply_fontsize_to_profile(profile_name, int(: %s", e)

        # Live anwenden (inkl. Table-Autosize via ThemeManager)
        try:
            self.theme_manager.apply_theme(profile_name=profile_name)
        except Exception:
            # Fallback: nur Vorschau setzen
            self._preview_profile(profile_name)

    def _apply_fontsize_to_profile(self, profile_name: str, font_size: int) -> None:
        """Speichert Schriftgröße direkt im Profil-JSON (damit alle Widgets davon profitieren)."""
        profile_name = (profile_name or "").strip()
        if not profile_name or profile_name in (tr("dlg.keine_profile_vorhanden"), tr("dlg.keine_passenden_profile")):
            return
        prof = self.theme_manager.get_profile(profile_name)
        if not prof:
            return
        data = prof.to_dict()
        data["schriftgroesse"] = int(font_size)
        self.theme_manager.update_profile(profile_name, data)

    def _persist_design_selection(self) -> None:
        """Persistiert Hell/Dunkel + aktives Profil + letztes Profil pro Modus."""
        mode = self._current_mode()
        theme_value = "dark" if mode == "dunkel" else "light"

        # 1) Theme-Key für Rückwärtskompatibilität
        try:
            self.settings.theme = theme_value
        except Exception:
            self.settings.set("theme", theme_value)

        # 2) Profil
        profile_name = (self.cmb_design_profile.currentText() or "").strip()
        if not profile_name or profile_name in (tr("dlg.keine_profile_vorhanden"), tr("dlg.keine_passenden_profile")):
            return

        self.settings.set("active_design_profile", profile_name)
        self.settings.set(f"last_design_profile_{mode}", profile_name)

    def _on_mode_changed(self, _text: str) -> None:
        """Hell/Dunkel wurde umgestellt → Dropdown neu füllen + zuletzt genutztes Profil wählen."""
        # Merke neuen Modus
        self._last_mode = self._current_mode()
        self._load_design_profiles()
        # Live-Vorschau mit neuem Profil
        self._preview_profile(self.cmb_design_profile.currentText())

    def _load_design_profiles(self) -> None:
        """Lädt Design-Profile in ein *einzelnes* Dropdown und filtert per Hell/Dunkel."""
        if not hasattr(self, "cmb_design_profile"):
            return

        mode = self._current_mode()  # "hell" oder "dunkel"
        all_names = self.theme_manager.get_all_profiles() or []

        # Filtern nach Modus
        filtered: list[str] = []
        for name in all_names:
            prof = self.theme_manager.get_profile(name)
            if not prof:
                continue
            if str(prof.get("modus", "hell")).strip().lower() == mode:
                filtered.append(name)

        filtered.sort(key=lambda s: s.casefold())

        blocker = QSignalBlocker(self.cmb_design_profile)
        self.cmb_design_profile.clear()

        if not filtered:
            self.cmb_design_profile.addItem(tr("dlg.keine_passenden_profile"))
            self.cmb_design_profile.setEnabled(False)
            del blocker
            return

        self.cmb_design_profile.addItems(filtered)
        self.cmb_design_profile.setEnabled(True)

        # Auswahl: 1) aktives Profil, 2) letztes Profil pro Modus, 3) Standard
        active = (self.settings.get("active_design_profile") or "").strip()
        last = (self._last_selected_by_mode.get(mode) or self.settings.get(f"last_design_profile_{mode}") or "").strip()
        fallback = "Standard Dunkel" if mode == "dunkel" else "Standard Hell"

        if active in filtered:
            pick = active
        elif last in filtered:
            pick = last
        elif fallback in filtered:
            pick = fallback
        else:
            pick = filtered[0]

        idx = self.cmb_design_profile.findText(pick)
        if idx >= 0:
            self.cmb_design_profile.setCurrentIndex(idx)

        del blocker
