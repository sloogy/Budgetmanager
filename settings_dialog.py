from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QListWidget, QStackedWidget, QDialogButtonBox,
    QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QLabel,
    QCheckBox, QComboBox, QSpinBox, QPushButton, QLineEdit,
    QFileDialog, QMessageBox, QWidget, QApplication
)
from PySide6.QtCore import Qt
from theme_manager import ThemeManager
from views.appearance_profiles_dialog import AppearanceProfilesDialog


class SettingsDialog(QDialog):
    """
    Neuer Einstellungsdialog (Deutsch, UX-optimiert), kompatibel zur bestehenden App.

    Erwartet: `settings` Instanz aus settings.py (JSON Settings).
    Liefert: get_settings() dict mit bestehenden Keys:
      - theme, auto_save, ask_due, refresh_on_start, recent_days
    plus zusätzliche neue Keys (werden in settings.json gespeichert, wenn MainWindow es übernimmt).
    """

    def __init__(self, settings, parent=None, app_version: str | None = None):
        super().__init__(parent)
        self.settings = settings
        self.app_version = app_version or ""
        
        # Theme Manager initialisieren
        self.theme_manager = ThemeManager(settings)

        self.setWindowTitle("Einstellungen")
        self.setMinimumSize(860, 560)

        # --- Root Layout
        root = QVBoxLayout(self)

        content = QHBoxLayout()
        root.addLayout(content)

        # --- Navigation links
        self.lw_nav = QListWidget()
        self.lw_nav.setMaximumWidth(220)
        self.lw_nav.addItems([
            "Allgemein",
            "Verhalten",
            "Darstellung",
            "Datenbank",
            "Über",
        ])
        content.addWidget(self.lw_nav)

        # --- Seiten rechts
        self.sw_pages = QStackedWidget()
        content.addWidget(self.sw_pages, 1)

        # Seiten erstellen
        self.page_general = self._build_page_general()
        self.page_behavior = self._build_page_behavior()
        self.page_appearance = self._build_page_appearance()
        self.page_database = self._build_page_database()
        self.page_about = self._build_page_about()

        for p in [self.page_general, self.page_behavior, self.page_appearance, self.page_database, self.page_about]:
            self.sw_pages.addWidget(p)

        self.lw_nav.currentRowChanged.connect(self.sw_pages.setCurrentIndex)
        self.lw_nav.setCurrentRow(0)

        # --- Buttons unten
        self.bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel
        )
        self.bb.accepted.connect(self._on_ok)
        self.bb.rejected.connect(self.reject)
        self.bb.clicked.connect(self._on_button_clicked)
        root.addWidget(self.bb)

        # --- UI mit aktuellen Werten füllen
        self._load_from_settings()

        # Enable/disable
        self.cb_auto_backup.toggled.connect(self.sb_backup_days.setEnabled)
        self.sb_backup_days.setEnabled(self.cb_auto_backup.isChecked())

        # Sofort-Vorschau Theme (optional, aber nice)
        self.cmb_design_profile.currentTextChanged.connect(self._preview_profile)
        self.btn_open_profiles.clicked.connect(self._open_profile_manager)

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
        lay.addWidget(self._title("Allgemein"))

        gb_start = QGroupBox("Start & Bedienung")
        vb = QVBoxLayout(gb_start)
        self.cb_show_onboarding = QCheckBox("Einführung beim Start anzeigen")
        self.cb_remember_last_tab = QCheckBox("Letzten geöffneten Reiter merken")
        self.cb_remember_filters = QCheckBox("Letzte Filtereinstellungen merken")
        self.cb_refresh_on_start = QCheckBox("Beim Start automatisch aktualisieren")
        vb.addWidget(self.cb_show_onboarding)
        vb.addWidget(self.cb_remember_last_tab)
        vb.addWidget(self.cb_remember_filters)
        vb.addWidget(self.cb_refresh_on_start)
        lay.addWidget(gb_start)

        gb_locale = QGroupBox("Sprache & Region")
        fl = QFormLayout(gb_locale)
        self.cmb_language = QComboBox()
        self.cmb_language.addItems(["Deutsch", "Englisch"])
        fl.addRow("Sprache", self.cmb_language)
        lay.addWidget(gb_locale)

        lay.addStretch(1)
        return w

    def _build_page_behavior(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self._title("Verhalten"))

        gb_workflow = QGroupBox("Eingabe & Workflow")
        vb = QVBoxLayout(gb_workflow)

        # Bestehende App-Settings
        self.cb_auto_save = QCheckBox("Im Budget automatisch speichern (Auto-Speichern)")
        self.cb_ask_due = QCheckBox("Bei Fälligkeit nachfragen (z. B. wiederkehrende Kosten)")

        # Zusätzliche UX-Settings (werden in JSON gespeichert, wenn MainWindow sie übernimmt)
        self.cb_warn_delete = QCheckBox("Löschvorgänge bestätigen lassen")
        self.cb_warn_budget_overrun = QCheckBox("Warnen, wenn das Budget überschritten wird")

        vb.addWidget(self.cb_auto_save)
        vb.addWidget(self.cb_ask_due)
        vb.addSpacing(8)
        vb.addWidget(self.cb_warn_delete)
        vb.addWidget(self.cb_warn_budget_overrun)
        lay.addWidget(gb_workflow)

        gb_tracking = QGroupBox("Tracking")
        fl = QFormLayout(gb_tracking)
        self.cmb_recent_days = QComboBox()
        self.cmb_recent_days.addItems(["14", "30"])
        fl.addRow("Schnellfilter „nur letzte … Tage“", self.cmb_recent_days)
        lay.addWidget(gb_tracking)

        lay.addStretch(1)
        return w

    def _build_page_appearance(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self._title("Darstellung"))

        gb_theme = QGroupBox("Erscheinungsbild")
        fl = QFormLayout(gb_theme)
        self.cmb_theme = QComboBox()
        # System-Option würde aktuell wie "Hell" wirken (ThemeManager kennt nur light/dark)
        self.cmb_theme.addItems(["Hell", "Dunkel"])
        fl.addRow("Design", self.cmb_theme)
        
        # Design-Profil Dropdown und Manager-Button
        self.cmb_design_profile = QComboBox()
        self.btn_open_profiles = QPushButton("Profile verwalten...")
        profile_layout = QHBoxLayout()
        profile_layout.addWidget(self.cmb_design_profile, 1)
        profile_layout.addWidget(self.btn_open_profiles)
        fl.addRow("Design-Profil", profile_layout)
        
        lay.addWidget(gb_theme)

        gb_tables = QGroupBox("Tabellen & Listen")
        fl2 = QFormLayout(gb_tables)
        self.cmb_density = QComboBox()
        self.cmb_density.addItems(["Kompakt", "Normal", "Groß"])
        self.cb_highlight_fixcosts = QCheckBox("Fixkosten optisch hervorheben")
        fl2.addRow("Tabellendichte", self.cmb_density)
        fl2.addRow(self.cb_highlight_fixcosts)
        lay.addWidget(gb_tables)

        lay.addStretch(1)
        return w

    def _build_page_database(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self._title("Datenbank"))

        gb_db = QGroupBox("Datenbankpfad")
        fl = QFormLayout(gb_db)
        self.le_db_path = QLineEdit()
        self.le_db_path.setReadOnly(True)
        self.btn_db_change = QPushButton("Datenbank wechseln…")
        self.btn_db_change.clicked.connect(self._choose_db)

        fl.addRow("Pfad", self.le_db_path)
        fl.addRow("", self.btn_db_change)
        lay.addWidget(gb_db)

        gb_backup = QGroupBox("Sicherung")
        flb = QFormLayout(gb_backup)
        self.cb_auto_backup = QCheckBox("Automatische Sicherung aktivieren")
        self.sb_backup_days = QSpinBox()
        self.sb_backup_days.setRange(1, 90)
        self.sb_backup_days.setValue(30)
        self.sb_backup_days.setSuffix(" Tage")
        self.btn_backup_now = QPushButton("Sicherung jetzt erstellen (Platzhalter)")
        self.btn_backup_now.clicked.connect(self._backup_placeholder)

        flb.addRow(self.cb_auto_backup)
        flb.addRow("Intervall", self.sb_backup_days)
        flb.addRow("", self.btn_backup_now)
        lay.addWidget(gb_backup)

        lay.addStretch(1)
        return w

    def _build_page_about(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self._title("Über"))

        gb = QGroupBox("Anwendung")
        fl = QFormLayout(gb)
        self.lbl_app_name = QLabel("Budgetmanager")
        self.lbl_version = QLabel(self.app_version or "(Version unbekannt)")
        fl.addRow("Name", self.lbl_app_name)
        fl.addRow("Version", self.lbl_version)
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

        self.cmb_language.setCurrentText(str(self.settings.get("language", "Deutsch")))

        # Verhalten (bestehend)
        self.cb_auto_save.setChecked(bool(self.settings.auto_save))
        self.cb_ask_due.setChecked(bool(self.settings.ask_due))
        self.cmb_recent_days.setCurrentText(str(self.settings.recent_days))

        # Zusätzliche Warnungen (neue Keys)
        self.cb_warn_delete.setChecked(bool(self.settings.get("warn_delete", True)))
        self.cb_warn_budget_overrun.setChecked(bool(self.settings.get("warn_budget_overrun", True)))

        # Darstellung
        theme = (self.settings.theme or "light").lower()
        self._load_design_profiles()
        self.cmb_density.setCurrentText(str(self.settings.get("table_density", "Normal")))
        self.cb_highlight_fixcosts.setChecked(bool(self.settings.get("highlight_fixcosts", True)))

        # Datenbank
        self.le_db_path.setText(str(self.settings.database_path))

        # Backup (neue Keys)
        self.cb_auto_backup.setChecked(bool(self.settings.get("auto_backup", False)))
        self.sb_backup_days.setValue(int(self.settings.get("backup_days", 30)))

    def get_settings(self) -> dict:
        """Kompatibel zum bisherigen MainWindow._show_settings()"""
        theme_value = "dark" if self.cmb_theme.currentText() == "Dunkel" else "light"

        return {
            # Keys, die MainWindow bereits verwendet:
            "theme": theme_value,
            "auto_save": self.cb_auto_save.isChecked(),
            "ask_due": self.cb_ask_due.isChecked(),
            "refresh_on_start": self.cb_refresh_on_start.isChecked(),
            "recent_days": int(self.cmb_recent_days.currentText()),

            # Zusätzliche neue Keys (optional später im MainWindow übernehmen):
            "show_onboarding": self.cb_show_onboarding.isChecked(),
            "remember_last_tab": self.cb_remember_last_tab.isChecked(),
            "remember_filters": self.cb_remember_filters.isChecked(),
            "language": self.cmb_language.currentText(),
            "warn_delete": self.cb_warn_delete.isChecked(),
            "warn_budget_overrun": self.cb_warn_budget_overrun.isChecked(),
            "table_density": self.cmb_density.currentText(),
            "highlight_fixcosts": self.cb_highlight_fixcosts.isChecked(),
            "database_path": self.le_db_path.text().strip(),
            "auto_backup": self.cb_auto_backup.isChecked(),
            "backup_days": int(self.sb_backup_days.value()),
        }

    # ---------------------------------------------------------------------
    # Actions
    # ---------------------------------------------------------------------
    def _on_button_clicked(self, btn) -> None:
        role = self.bb.buttonRole(btn)
        if role.name == "ApplyRole":
            self._apply()

    def _on_ok(self) -> None:
        self._apply()
        self.accept()

    def _apply(self) -> None:
        # Theme anwenden
        profile_name = self.cmb_design_profile.currentText()
        if profile_name and not profile_name.startswith('---') and profile_name != '(Keine Profile vorhanden)':
            self.theme_manager.apply_theme(profile_name=profile_name)

    def _preview_profile(self, profile_name: str) -> None:
        """Vorschau des ausgewählten Design-Profils."""
        # Überschriften-Items ignorieren
        if profile_name.startswith('---') or profile_name == '(Keine Profile vorhanden)':
            return
        
        # Profil anwenden
        self.theme_manager.apply_theme(profile_name=profile_name)
    
    def _open_profile_manager(self) -> None:
        """Öffnet den Profil-Manager Dialog."""
        dlg = AppearanceProfilesDialog(parent=self, settings=self.settings)
        if dlg.exec():
            # Profile wurden evtl. geändert, Dropdown aktualisieren
            # (Theme Manager lädt Profile automatisch beim Abruf)
            self._load_design_profiles()
    
    def _preview_theme(self, text: str) -> None:
        # Vorschau: Theme anwenden
        profile_name = "Standard Dunkel" if text == "Dunkel" else "Standard Hell"
        self.theme_manager.apply_theme(profile_name=profile_name)

    def _choose_db(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Datenbank auswählen",
            str(Path.home()),
            "SQLite Datenbank (*.db *.sqlite *.sqlite3);;Alle Dateien (*)",
        )
        if file_path:
            self.le_db_path.setText(file_path)

    def _backup_placeholder(self) -> None:
        QMessageBox.information(
            self,
            "Sicherung",
            "Platzhalter: Hier kannst du später die Datenbank sichern (z. B. DB kopieren/zippen).",
        )
    def _load_design_profiles(self) -> None:
        """Lädt alle Designprofile aus den Settings in das Dropdown."""
        if not hasattr(self, 'cmb_design_profile'):
            return
        
        # Profile vom Theme Manager holen
        all_profiles = self.theme_manager.get_all_profiles()
        
        self.cmb_design_profile.blockSignals(True)
        self.cmb_design_profile.clear()
        
        if all_profiles:
            # Sortiere Profile: Vordefiniert zuerst, dann benutzerdefiniert
            predefined = ThemeManager.get_predefined_profiles()
            all_profile_names = self.theme_manager.get_all_profiles()
            
            # Benutzerdefinierte Profile = alle Profile minus vordefinierte
            custom = [p for p in all_profile_names if p not in predefined]
            
            # Vordefinierte hinzufügen
            if predefined:
                self.cmb_design_profile.addItem("--- Vordefinierte Profile ---")
                for name in predefined:
                    self.cmb_design_profile.addItem(name)
            
            # Benutzerdefinierte hinzufügen
            if custom:
                if predefined:
                    self.cmb_design_profile.addItem("--- Eigene Profile ---")
                for name in custom:
                    self.cmb_design_profile.addItem(name)
        else:
            self.cmb_design_profile.addItem('(Keine Profile vorhanden)')
            self.cmb_design_profile.setEnabled(False)
            self.cmb_design_profile.blockSignals(False)
            return
        
        self.cmb_design_profile.setEnabled(True)
        
        # Aktives Profil auswählen
        current_profile = self.theme_manager.get_current_profile()
        if current_profile:
            current_name = current_profile.name
            index = self.cmb_design_profile.findText(current_name)
            if index >= 0:
                self.cmb_design_profile.setCurrentIndex(index)
        
        self.cmb_design_profile.blockSignals(False)
