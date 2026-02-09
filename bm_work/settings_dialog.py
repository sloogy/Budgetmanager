from __future__ import annotations

from pathlib import Path
from model.app_paths import resolve_in_app
from PySide6.QtWidgets import (
    QDialog, QListWidget, QStackedWidget, QDialogButtonBox,
    QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QLabel,
    QCheckBox, QComboBox, QSpinBox, QPushButton, QLineEdit,
    QFileDialog, QMessageBox, QWidget, QApplication
)
from PySide6.QtCore import Qt, QSignalBlocker
from theme_manager import ThemeManager
from views.theme_editor_dialog import ThemeEditorDialog


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

        # Merker: wurde bereits "Anwenden" gedrückt?
        # Wenn ja, soll "OK" nur noch schliessen (User-Wunsch).
        self._applied_once = False
        self._last_mode = None  # "hell" oder "dunkel" (für Filter-Logik)
        self._last_selected_by_mode: dict[str, str] = {}
        self._last_mode = None  # "hell" | "dunkel"

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

        # Deutsche Button-Texte (Qt übersetzt nicht immer zuverlässig)
        try:
            self.bb.button(QDialogButtonBox.Ok).setText("OK")
            self.bb.button(QDialogButtonBox.Apply).setText("Anwenden")
            self.bb.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        except Exception:
            pass
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
        self.sb_recurring_preferred_day = QSpinBox()
        self.sb_recurring_preferred_day.setRange(1, 31)
        self.sb_recurring_preferred_day.setSuffix(". Tag")
        self.sb_recurring_preferred_day.setToolTip("Wird als Standard beim Anlegen neuer wiederkehrender Transaktionen verwendet.")
        fl.addRow("Bevorzugter Monatstag für wiederkehrende Buchungen", self.sb_recurring_preferred_day)
        lay.addWidget(gb_tracking)

        # Experten-Einstellungen
        gb_expert = QGroupBox("Experten-Modus")
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

        # Schriftgröße (pro Profil)
        self.sb_fontsize = QSpinBox()
        self.sb_fontsize.setRange(8, 16)
        self.sb_fontsize.setSingleStep(1)
        self.sb_fontsize.setValue(10)
        fl.addRow("Schriftgröße", self.sb_fontsize)
        
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
        self.sb_recurring_preferred_day.setValue(int(self.settings.get("recurring_preferred_day", getattr(self.settings, "recurring_preferred_day", 1)) or 1))

        # Zusätzliche Warnungen (neue Keys)
        self.cb_warn_delete.setChecked(bool(self.settings.get("warn_delete", True)))
        self.cb_warn_budget_overrun.setChecked(bool(self.settings.get("warn_budget_overrun", True)))

        # Experten-Modus
        self.cb_show_categories_tab.setChecked(bool(self.settings.get("show_categories_tab", False)))

        # Darstellung
        theme = (self.settings.theme or "light").lower()
        # Hell/Dunkel Dropdown auf Settings spiegeln
        blocker = QSignalBlocker(self.cmb_theme)
        self.cmb_theme.setCurrentText("Dunkel" if theme == "dark" else "Hell")
        del blocker

        # Profil-Dropdown anhand Hell/Dunkel filtern
        self._last_mode = self._current_mode()
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
            "recurring_preferred_day": int(self.sb_recurring_preferred_day.value()),

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
            # Experten-Modus
            "show_categories_tab": self.cb_show_categories_tab.isChecked(),
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
        except Exception:
            pass
        if not self._applied_once:
            self._apply()
        self.accept()

    def _apply(self) -> None:
        # Theme anwenden + persistieren
        self._persist_design_selection()
        # Schriftgröße ins Profil schreiben
        try:
            self._apply_fontsize_to_profile(self.cmb_design_profile.currentText(), int(self.sb_fontsize.value()))
        except Exception:
            pass
        profile_name = self.cmb_design_profile.currentText().strip()
        if profile_name and profile_name not in ('(Keine Profile vorhanden)', '(Keine passenden Profile)'):
            self.theme_manager.apply_theme(profile_name=profile_name)
            self._applied_once = True

    def _preview_profile(self, profile_name: str) -> None:
        """Vorschau des ausgewählten Design-Profils."""
        profile_name = (profile_name or "").strip()
        if not profile_name or profile_name in ('(Keine Profile vorhanden)', '(Keine passenden Profile)'):
            return

        # Vorschau: Stylesheet direkt setzen, OHNE Settings zu überschreiben
        # Merke Auswahl pro Modus (damit Hell/Dunkel-Wechsel sofort "letztes" Profil nimmt)
        try:
            self._last_selected_by_mode[self._current_mode()] = profile_name
        except Exception:
            pass

        app = QApplication.instance()
        prof = self.theme_manager.get_profile(profile_name)
        if app and prof:
            try:
                b = QSignalBlocker(self.sb_fontsize)
                self.sb_fontsize.setValue(int(prof.get('schriftgroesse', 10) or 10))
                del b
            except Exception:
                pass
            app.setStyleSheet(self.theme_manager.build_stylesheet(prof))
    
    def _open_profile_manager(self) -> None:
        """Öffnet den Theme-Editor Dialog."""
        dlg = ThemeEditorDialog(self.settings, self.theme_manager, self)
        if dlg.exec():
            # Profile wurden evtl. geändert, Dropdown aktualisieren
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

    # -----------------------------------------------------------------
    # Design/Theme-Logik
    # -----------------------------------------------------------------
    def _current_mode(self) -> str:
        """"hell" oder "dunkel" basierend auf dem UI-Dropdown."""
        return "dunkel" if self.cmb_theme.currentText() == "Dunkel" else "hell"

    def _on_fontsize_changed(self, _val: int) -> None:
        # Live-Vorschau: aktuelle Auswahl + Fontsize
        self._preview_profile(self.cmb_design_profile.currentText())

    def _apply_fontsize_to_profile(self, profile_name: str, font_size: int) -> None:
        """Speichert Schriftgröße direkt im Profil-JSON (damit alle Widgets davon profitieren)."""
        profile_name = (profile_name or "").strip()
        if not profile_name or profile_name in ("(Keine Profile vorhanden)", "(Keine passenden Profile)"):
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
        if not profile_name or profile_name in ("(Keine Profile vorhanden)", "(Keine passenden Profile)"):
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
            self.cmb_design_profile.addItem("(Keine passenden Profile)")
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
