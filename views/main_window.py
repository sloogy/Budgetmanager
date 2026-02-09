from __future__ import annotations
import sqlite3
import sys
from datetime import date
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QMenuBar, QMenu, QMessageBox,
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QApplication
)
from PySide6.QtGui import QAction, QKeySequence, QIcon, QShortcut
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QScreen

from model.category_model import CategoryModel
from model.undo_redo_model import UndoRedoModel
from views.tabs.tracking_tab import TrackingTab
from views.tabs.categories_tab import CategoriesTab
from views.tabs.budget_tab import BudgetTab
from views.tabs.overview_tab import OverviewTab  # Original-Version (stabil)
from settings import Settings
from theme_manager import ThemeManager
from settings_dialog import SettingsDialog
from views.shortcuts_dialog import ShortcutsDialog
from views.quick_add_dialog import QuickAddDialog
from views.export_dialog import ExportDialog
from views.global_search_dialog import GlobalSearchDialog
from views.savings_goals_dialog import SavingsGoalsDialog
from views.backup_restore_dialog import BackupRestoreDialog
from views.appearance_profiles_dialog import AppearanceProfilesDialog
from views.category_manager_dialog import CategoryManagerDialog
from app_info import APP_NAME, APP_VERSION, app_window_title, app_about_title, app_version_label

class AboutDialog(QDialog):
    """Über-Dialog"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(app_about_title())

        layout = QVBoxLayout()

        html = f"""
<h2>{APP_NAME}</h2>
<p><b>Version:</b> {app_version_label()}</p>
<p><b>Entwickelt mit:</b> PySide6 (Qt für Python)</p>
<p><b>Datenbank:</b> SQLite</p>
<br>
<p>Ein einfacher Budgetmanager zur Verwaltung von:</p>
<ul>
  <li>Budget-Planung nach Kategorien</li>
  <li>Tracking von Einnahmen und Ausgaben</li>
  <li>Visualisierung und Auswertung</li>
  <li>Sparziele und Favoriten</li>
  <li>Tags und Budgetwarnungen</li>
</ul>
<br>
<p><b>Highlights {APP_VERSION}:</b></p>
<ul>
  <li>Integrierte Kategorie-Verwaltung im Budget-Dialog</li>
  <li>Management-Button mit allen Kategorie-Funktionen</li>
  <li>Kategorien-Tab als optionaler Experten-Modus</li>
  <li>Dashboard: Tabellarische Ansicht (Budget / Gebucht / Rest)</li>
</ul>
"""

        info = QLabel(html)
        info.setTextFormat(Qt.RichText)
        info.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)

        layout.addWidget(info)
        layout.addWidget(buttons)
        self.setLayout(layout)
        self.setMinimumWidth(450)

class MainWindow(QMainWindow):
    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn
        self.setWindowTitle(app_window_title())

        # Einstellungen laden
        self.settings = Settings()
        
        # Undo/Redo
        self.undo_redo = UndoRedoModel(conn)

        # Theme Manager initialisieren
        self.theme_manager = ThemeManager(self.settings)
        
        # Resize-Timer für Debouncing (verhindert zu häufiges Speichern)
        self.resize_timer = QTimer()
        self.resize_timer.timeout.connect(self._save_window_geometry)
        self.resize_timer.setSingleShot(True)
        
        # Defaults once
        CategoryModel(conn).ensure_defaults()

        # Tabs erstellen (verschiebbar)
        self.tabs = QTabWidget()
        self.tabs.setMovable(True)  # Tabs per Drag & Drop verschiebbar
        self.tabs.setDocumentMode(True)  # Moderneres Aussehen
        self.tabs.setTabPosition(QTabWidget.South)  # V2-Layout: Tabs unten
        
        # Tab-Widgets erstellen
        self.budget_tab = BudgetTab(conn)
        self.categories_tab = CategoriesTab(conn)
        self.tracking_tab = TrackingTab(conn, settings=self.settings)
        self.overview_tab = OverviewTab(conn)
        
        # Schnelleingabe-Signals von Tabs verbinden
        self.budget_tab.quick_add_requested.connect(self._show_quick_add)
        self.categories_tab.quick_add_requested.connect(self._show_quick_add)
        self.overview_tab.quick_add_requested.connect(self._show_quick_add)
        
        # Settings-Checkboxen mit Settings synchronisieren
        if hasattr(self.budget_tab, 'chk_autosave'):
            self.budget_tab.chk_autosave.toggled.connect(self._on_autosave_changed)
        if hasattr(self.budget_tab, 'chk_ask_due'):
            self.budget_tab.chk_ask_due.toggled.connect(self._on_ask_due_changed)
        
        # Tab-Definitionen (Index -> Widget, Name)
        self._tab_definitions = {
            0: (self.budget_tab, "💰 Budget"),
            1: (self.categories_tab, "📁 Kategorien"),
            2: (self.tracking_tab, "📊 Tracking"),
            3: (self.overview_tab, "📈 Übersicht"),
        }
        
        # Tabs in gespeicherter Reihenfolge hinzufügen
        self._load_tab_order()

        self.setCentralWidget(self.tabs)
        
        # Tab-Wechsel Signal verbinden (für dynamisches Bearbeiten-Menü)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        
        # Fenster-Geometrie und -Status wiederherstellen
        self._restore_window_state()
        
        # Menü erstellen
        self._create_menu()
        
        # Globale Shortcuts
        self._setup_shortcuts()
        
        # Einstellungen auf Tabs anwenden
        self._apply_settings_to_tabs()
        
        # Aktuelles Jahr setzen
        self._set_current_year()
        
        # Theme anwenden
        self._apply_theme()

        # Übersicht-Subtabs (Dashboard/Verlauf/…) gemäß Settings ein-/ausblenden
        self._apply_overview_subtabs_from_settings()
        
        # Bei Bedarf beim Start alle Tabs aktualisieren
        if self.settings.refresh_on_start:
            self._refresh_all_tabs()
    
    def _restore_window_state(self):
        """Stellt Fenster-Größe, -Position und -Status wieder her"""
        # Position und Größe laden
        width = self.settings.get("window_width", 1280)
        height = self.settings.get("window_height", 800)
        x = self.settings.get("window_x", 100)
        y = self.settings.get("window_y", 100)
        
        # Validiere Position (verhindert Off-Screen-Fenster)
        screen = QApplication.primaryScreen()
        if screen:
            screen_rect = screen.availableGeometry()
            # Falls Fenster komplett außerhalb des Screens wäre, reset auf Defaults
            if x + width < 0 or x > screen_rect.width() or \
               y + height < 0 or y > screen_rect.height():
                x, y = 100, 100
        
        # Position und Größe setzen
        self.setGeometry(x, y, width, height)
        
        # Maximiert/Fullscreen-Status
        is_maximized = self.settings.get("window_is_maximized", False)
        is_fullscreen = self.settings.get("window_is_fullscreen", False)
        
        if is_fullscreen:
            self.showFullScreen()
        elif is_maximized:
            self.showMaximized()
        else:
            self.show()
    
    def _save_window_geometry(self):
        """Speichert Fenster-Geometrie in Settings"""
        # Window-State nicht speichern wenn fullscreen/maximized
        # (das wird separat gespeichert)
        if self.isFullScreen() or self.isMaximized():
            return
        
        self.settings.set("window_x", self.x())
        self.settings.set("window_y", self.y())
        self.settings.set("window_width", self.width())
        self.settings.set("window_height", self.height())
    
    def resizeEvent(self, event):
        """Wird aufgerufen wenn Fenster resized wird"""
        super().resizeEvent(event)
        # Starte Timer um Geometrie nach Delay zu speichern (Debouncing)
        self.resize_timer.stop()
        self.resize_timer.start(500)  # 500ms Verzögerung
    
    def moveEvent(self, event):
        """Wird aufgerufen wenn Fenster verschoben wird"""
        super().moveEvent(event)
        # Auch hier Debouncing
        self.resize_timer.stop()
        self.resize_timer.start(500)
    
    def _setup_shortcuts(self):
        """Richtet globale Tastenkürzel ein"""
        # F1 = Hilfe
        self.shortcut_help = QShortcut(QKeySequence("F1"), self)
        self.shortcut_help.activated.connect(self._show_shortcuts)
        
        # Strg+F = Globale Suche
        self.shortcut_search = QShortcut(QKeySequence("Ctrl+F"), self)
        self.shortcut_search.activated.connect(self._show_global_search)
        
        # Strg+N = Quick-Add
        self.shortcut_quick_add = QShortcut(QKeySequence("Ctrl+N"), self)
        self.shortcut_quick_add.activated.connect(self._show_quick_add)
        
        # Strg+E = Export
        self.shortcut_export = QShortcut(QKeySequence("Ctrl+E"), self)
        self.shortcut_export.activated.connect(self._show_export)

    def _create_menu(self):
        """Erstellt das Hamburger-Menü (Menüleiste)"""
        menubar = self.menuBar()
        
        # === DATEI-MENÜ ===
        file_menu = menubar.addMenu("&Datei")
        
        # Speichern
        save_action = QAction("&Speichern", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.setStatusTip("Budget speichern (Strg+S)")
        save_action.triggered.connect(self._save_budget)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        # Einstellungen (NEU!)
        settings_action = QAction("&Einstellungen...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.setStatusTip("Programm-Einstellungen (Strg+,)")
        settings_action.triggered.connect(self._show_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        # Datenbank-Info
        db_info_action = QAction("Datenbank-&Info", self)
        db_info_action.triggered.connect(self._show_db_info)
        file_menu.addAction(db_info_action)
        
        file_menu.addSeparator()
        
        # Beenden
        exit_action = QAction("&Beenden", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.setStatusTip("Anwendung beenden (Strg+Q)")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # === BEARBEITEN-MENÜ (dynamisch je nach Tab) ===
        self.edit_menu = menubar.addMenu("&Bearbeiten")
        self._edit_menu_actions = {}  # Speichere Actions für spätere Aktualisierung
        self._setup_edit_menu()
        
        # === ANSICHT-MENÜ ===
        view_menu = menubar.addMenu("&Ansicht")
        
        # Anzeigen-Untermenü (Tabs/Module ein- & ausblenden)
        anzeigen_menu = view_menu.addMenu("&Anzeigen")

        # Übersicht → Subtabs ein/ausblenden
        overview_menu = anzeigen_menu.addMenu("📈 Ü&bersicht")
        self._overview_visibility_actions = {}

        # Sichtbarkeit aus Settings laden (Default: alles sichtbar)
        vis = self.settings.get('overview_visible_subtabs', {}) or {}
        specs = []
        try:
            specs = self.overview_tab.get_subtab_specs()
        except Exception:
            specs = []

        if specs:
            for key, title in specs:
                act = QAction(title, self)
                act.setCheckable(True)
                act.setChecked(bool(vis.get(key, True)))
                act.toggled.connect(lambda checked, k=key: self._toggle_overview_subtab(k, checked))
                overview_menu.addAction(act)
                self._overview_visibility_actions[key] = act
        else:
            # Fallback: falls Übersicht keine Specs liefert
            dummy = QAction('(Keine Optionen verfügbar)', self)
            dummy.setEnabled(False)
            overview_menu.addAction(dummy)

        view_menu.addSeparator()

        # Zu Tabs wechseln (navigiert zum Widget, nicht zur Position) (navigiert zum Widget, nicht zur Position)
        goto_budget = QAction("💰 &Budget", self)
        goto_budget.setShortcut("Ctrl+1")
        goto_budget.triggered.connect(lambda: self._goto_tab(self.budget_tab))
        view_menu.addAction(goto_budget)
        
        # Kategorien-Tab (nur anzeigen wenn aktiviert)
        self.goto_categories_action = QAction("📁 &Kategorien", self)
        self.goto_categories_action.setShortcut("Ctrl+2")
        self.goto_categories_action.triggered.connect(lambda: self._goto_tab(self.categories_tab))
        view_menu.addAction(self.goto_categories_action)
        # Sichtbarkeit basierend auf Einstellung
        self._update_categories_menu_visibility()
        
        goto_tracking = QAction("📊 &Tracking", self)
        goto_tracking.setShortcut("Ctrl+3")
        goto_tracking.triggered.connect(lambda: self._goto_tab(self.tracking_tab))
        view_menu.addAction(goto_tracking)
        
        goto_overview = QAction("📈 Ü&bersicht", self)
        goto_overview.setShortcut("Ctrl+4")
        goto_overview.triggered.connect(lambda: self._goto_tab(self.overview_tab))
        view_menu.addAction(goto_overview)
        
        view_menu.addSeparator()
        
        # Toggle für Kategorien-Tab
        self.toggle_categories_action = QAction("🛠️ Kategorien-Tab anzeigen (Experten)", self)
        self.toggle_categories_action.setCheckable(True)
        self.toggle_categories_action.setChecked(self.settings.show_categories_tab)
        self.toggle_categories_action.setToolTip(
            "Zeigt den separaten Kategorien-Tab für erweiterte Verwaltung.\n"
            "Kategorien können auch direkt im Budget-Tab verwaltet werden."
        )
        self.toggle_categories_action.toggled.connect(self._toggle_categories_tab)
        view_menu.addAction(self.toggle_categories_action)
        
        view_menu.addSeparator()
        
        # Aktualisieren
        refresh_action = QAction("&Aktualisieren", self)
        refresh_action.setShortcut(QKeySequence.Refresh)
        refresh_action.setStatusTip("Aktuelle Ansicht neu laden (F5)")
        refresh_action.triggered.connect(self._refresh_current_tab)
        view_menu.addAction(refresh_action)
        
        # === EXTRAS-MENÜ ===
        extras_menu = menubar.addMenu("E&xtras")
        
        # Quick-Add (NEU)
        quick_add_action = QAction("⚡ &Schnelleingabe...", self)
        quick_add_action.setShortcut("Ctrl+N")
        quick_add_action.setStatusTip("Schnell einen neuen Eintrag erfassen (Strg+N)")
        quick_add_action.triggered.connect(self._show_quick_add)
        extras_menu.addAction(quick_add_action)
        
        # Globale Suche (NEU)
        search_action = QAction("🔍 Globale &Suche...", self)
        search_action.setShortcut("Ctrl+F")
        search_action.setStatusTip("Durchsucht alle Daten (Strg+F)")
        search_action.triggered.connect(self._show_global_search)
        extras_menu.addAction(search_action)
        
        extras_menu.addSeparator()
        
        # === KATEGORIEN-MANAGER (NEU v2.2.0) ===
        category_manager_action = QAction("📁 &Kategorien-Manager...", self)
        category_manager_action.setShortcut("Ctrl+K")
        category_manager_action.setStatusTip("Alle Kategorien verwalten (Strg+K)")
        category_manager_action.triggered.connect(self._show_category_manager)
        extras_menu.addAction(category_manager_action)
        
        extras_menu.addSeparator()
        
        # Export (NEU)
        export_action = QAction("📤 &Exportieren...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.setStatusTip("Daten als CSV exportieren (Strg+E)")
        export_action.triggered.connect(self._show_export)
        extras_menu.addAction(export_action)
        
        extras_menu.addSeparator()
        
        # Sparziele (NEU v0.16)
        savings_action = QAction("💰 &Sparziele...", self)
        savings_action.setStatusTip("Sparziele verwalten und tracken")
        savings_action.triggered.connect(self._show_savings_goals)
        extras_menu.addAction(savings_action)
        
        # Backup & Wiederherstellung (NEU v0.16)
        backup_action = QAction("💾 &Backup && Wiederherstellung...", self)
        backup_action.setStatusTip("Datenbank sichern und wiederherstellen")
        backup_action.triggered.connect(self._show_backup_restore)
        extras_menu.addAction(backup_action)
        
        extras_menu.addSeparator()
        
        # Aktuelles Jahr setzen
        current_year_action = QAction("Aktuelles &Jahr laden", self)
        current_year_action.setShortcut("Ctrl+Y")
        current_year_action.triggered.connect(self._set_current_year)
        extras_menu.addAction(current_year_action)
        
        extras_menu.addSeparator()
        
        # Tab-Reihenfolge zurücksetzen
        reset_tabs_action = QAction("🔄 Tab-Reihenfolge zurücksetzen", self)
        reset_tabs_action.triggered.connect(self._reset_tab_order)
        extras_menu.addAction(reset_tabs_action)
        
        # === HILFE-MENÜ ===
        help_menu = menubar.addMenu("&Hilfe")
        
        # Tastenkürzel (NEU)
        shortcuts_action = QAction("⌨️ &Tastenkürzel...", self)
        shortcuts_action.setShortcut("F1")
        shortcuts_action.setStatusTip("Zeigt alle verfügbaren Tastenkürzel (F1)")
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)
        
        # Erste Schritte / Setup-Assistent
        setup_action = QAction("🧭 &Erste Schritte...", self)
        setup_action.setStatusTip("Startet den Setup-Assistenten (First-Start-Guide)")
        setup_action.triggered.connect(lambda: self._start_setup_assistant(force=True))
        help_menu.addAction(setup_action)
        
        help_menu.addSeparator()
        
        # Über
        about_action = QAction("Ü&ber...", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _apply_settings_to_tabs(self):
        """Wendet Einstellungen auf die Tabs an"""
        # Budget-Tab
        if hasattr(self.budget_tab, 'chk_autosave'):
            self.budget_tab.chk_autosave.setChecked(self.settings.auto_save)
        
        if hasattr(self.budget_tab, 'chk_ask_due'):
            self.budget_tab.chk_ask_due.setChecked(self.settings.ask_due)

        # Tracking-Tab
        if hasattr(self.tracking_tab, 'set_recent_days'):
            self.tracking_tab.set_recent_days(self.settings.recent_days)
    
    def _on_autosave_changed(self, checked: bool):
        """Speichert Auto-Save Einstellung wenn Checkbox geändert wird"""
        self.settings.auto_save = checked
        
    def _on_ask_due_changed(self, checked: bool):
        """Speichert Ask-Due Einstellung wenn Checkbox geändert wird"""
        self.settings.ask_due = checked
    
    def _load_tab_order(self):
        """Lädt Tabs in der gespeicherten Reihenfolge"""
        saved_order = self.settings.tab_order
        
        # Kategorien-Tab (ID 1) nur anzeigen wenn aktiviert
        show_categories = self.settings.show_categories_tab
        
        # Validierung: Stelle sicher, dass alle Indizes vorhanden sind
        all_ids = {0, 1, 2, 3}
        if not saved_order or not all_ids.issubset(set(saved_order) | {1}):  # 1 kann fehlen
            saved_order = [0, 1, 2, 3]
        
        # Tabs in gespeicherter Reihenfolge hinzufügen
        for tab_id in saved_order:
            # Kategorien-Tab überspringen wenn nicht aktiviert
            if tab_id == 1 and not show_categories:
                continue
            widget, name = self._tab_definitions[tab_id]
            # Kategorien-Tab umbenennen wenn sichtbar (Experten-Modus markieren)
            if tab_id == 1 and show_categories:
                name = "🛠️ Kategorien (Experten)"
            self.tabs.addTab(widget, name)
    
    def _save_tab_order(self):
        """Speichert die aktuelle Tab-Reihenfolge"""
        current_order = []
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            # Finde die ursprüngliche ID des Tabs
            for tab_id, (tab_widget, _) in self._tab_definitions.items():
                if widget is tab_widget:
                    current_order.append(tab_id)
                    break
        
        if current_order:
            self.settings.tab_order = current_order
    
    def _goto_tab(self, tab_widget):
        """Wechselt zum angegebenen Tab (unabhängig von Position)"""
        index = self.tabs.indexOf(tab_widget)
        if index >= 0:
            self.tabs.setCurrentIndex(index)
    
    def _update_categories_menu_visibility(self) -> None:
        """Aktualisiert die Sichtbarkeit des Kategorien-Menüpunkts."""
        show = self.settings.show_categories_tab
        if hasattr(self, 'goto_categories_action'):
            self.goto_categories_action.setVisible(show)
    
    def _toggle_categories_tab(self, checked: bool) -> None:
        """Schaltet den Kategorien-Tab ein/aus."""
        # Einstellung speichern
        self.settings.show_categories_tab = checked
        
        # Tab hinzufügen oder entfernen
        cat_index = self.tabs.indexOf(self.categories_tab)
        
        if checked:
            # Tab hinzufügen wenn nicht vorhanden
            if cat_index < 0:
                # Tab hinzufügen (nach Budget, vor Tracking)
                budget_index = self.tabs.indexOf(self.budget_tab)
                tracking_index = self.tabs.indexOf(self.tracking_tab)
                
                # Beste Position finden
                if budget_index >= 0:
                    insert_at = budget_index + 1
                elif tracking_index >= 0:
                    insert_at = tracking_index
                else:
                    insert_at = 1
                
                self.tabs.insertTab(insert_at, self.categories_tab, "🛠️ Kategorien (Experten)")
                self.statusBar().showMessage("Kategorien-Tab aktiviert", 2000)
        else:
            # Tab entfernen wenn vorhanden
            if cat_index >= 0:
                self.tabs.removeTab(cat_index)
                self.statusBar().showMessage("Kategorien-Tab ausgeblendet", 2000)
        
        # Menüpunkte aktualisieren
        self._update_categories_menu_visibility()
        
        # Toggle-Action synchronisieren (falls von extern aufgerufen)
        if hasattr(self, 'toggle_categories_action'):
            # Blockiere Signale um Rekursion zu vermeiden
            self.toggle_categories_action.blockSignals(True)
            self.toggle_categories_action.setChecked(checked)
            self.toggle_categories_action.blockSignals(False)
    
    def _reset_tab_order(self):
        """Setzt die Tab-Reihenfolge auf Standard zurück"""
        # Merke aktuellen Tab
        current_widget = self.tabs.currentWidget()
        
        # Alle Tabs entfernen (ohne zu löschen)
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)
        
        # Kategorien-Tab nur anzeigen wenn aktiviert
        show_categories = self.settings.show_categories_tab
        
        # Tabs in Standardreihenfolge hinzufügen
        default_order = [0, 1, 2, 3]
        for tab_id in default_order:
            # Kategorien-Tab überspringen wenn nicht aktiviert
            if tab_id == 1 and not show_categories:
                continue
            widget, name = self._tab_definitions[tab_id]
            # Kategorien-Tab umbenennen wenn sichtbar
            if tab_id == 1 and show_categories:
                name = "🛠️ Kategorien (Experten)"
            self.tabs.addTab(widget, name)
        
        # Vorherigen Tab wiederherstellen
        if current_widget:
            index = self.tabs.indexOf(current_widget)
            if index >= 0:
                self.tabs.setCurrentIndex(index)
        
        # Speichern
        self.settings.tab_order = default_order
        self.statusBar().showMessage("Tab-Reihenfolge zurückgesetzt", 2000)

    def _show_settings(self):
        """Zeigt Einstellungen-Dialog"""
        dialog = SettingsDialog(self.settings, self)
        
        if dialog.exec() == QDialog.Accepted:
            new_settings = dialog.get_settings()
            
            # Theme-Änderung?
            theme_changed = new_settings["theme"] != self.settings.theme
            
            # Einstellungen speichern
            self.settings.theme = new_settings["theme"]
            self.settings.auto_save = new_settings["auto_save"]
            self.settings.ask_due = new_settings["ask_due"]
            self.settings.refresh_on_start = new_settings["refresh_on_start"]
            # Tracking
            if "recent_days" in new_settings:
                self.settings.recent_days = int(new_settings["recent_days"] or 14)
            # Tracking: Standard-Tag im Monat für neue wiederkehrende Transaktionen
            if "recurring_preferred_day" in new_settings:
                try:
                    self.settings.set("recurring_preferred_day", int(new_settings.get("recurring_preferred_day") or 1))
                except Exception:
                    self.settings.set("recurring_preferred_day", 1)
            # Zusätzliche (neue) Einstellungen speichern
            # (Diese Keys sind rückwärtskompatibel – Tabs können sie später nutzen.)
            self.settings.set("show_onboarding", new_settings.get("show_onboarding", True))
            self.settings.set("remember_last_tab", new_settings.get("remember_last_tab", True))
            self.settings.set("remember_filters", new_settings.get("remember_filters", True))
            self.settings.set("language", new_settings.get("language", "Deutsch"))
            self.settings.set("warn_delete", new_settings.get("warn_delete", True))
            self.settings.set("warn_budget_overrun", new_settings.get("warn_budget_overrun", True))
            self.settings.set("table_density", new_settings.get("table_density", "Normal"))
            self.settings.set("highlight_fixcosts", new_settings.get("highlight_fixcosts", True))
            self.settings.set("auto_backup", new_settings.get("auto_backup", False))
            self.settings.set("backup_days", int(new_settings.get("backup_days", 30) or 30))
            # Datenbankpfad optional übernehmen
            if new_settings.get("database_path"):
                self.settings.database_path = new_settings["database_path"]
            
            # Kategorien-Tab Einstellung
            old_show_cat = self.settings.show_categories_tab
            new_show_cat = new_settings.get("show_categories_tab", False)
            self.settings.show_categories_tab = new_show_cat
            
            # Kategorien-Tab Toggle aktualisieren wenn geändert
            if old_show_cat != new_show_cat:
                if hasattr(self, 'toggle_categories_action'):
                    self.toggle_categories_action.setChecked(new_show_cat)
                # Tab direkt ein/ausblenden
                self._toggle_categories_tab(new_show_cat)
            
            # Auf Tabs anwenden
            self._apply_settings_to_tabs()
            
            # Theme anwenden (Profile werden automatisch geladen)
            self._apply_theme()
            
            if theme_changed:
                self.statusBar().showMessage(
                    f"Theme geändert zu: {new_settings['theme']}", 3000
                )
            else:
                self.statusBar().showMessage("Einstellungen gespeichert", 2000)

    def _change_theme(self, theme: str):
        """Ändert das Theme über Menü"""
        # Theme über Manager anwenden
        profile_name = "Standard Hell" if theme == "light" else "Standard Dunkel"
        self.theme_manager.apply_theme(profile_name=profile_name)
        
        # Settings aktualisieren für Kompatibilität
        self.settings.theme = theme
        
        # Radio-Buttons aktualisieren
        if hasattr(self, 'action_light'):
            self.action_light.setChecked(theme == "light")
        if hasattr(self, 'action_dark'):
            self.action_dark.setChecked(theme == "dark")
        
        self.statusBar().showMessage(f"Theme: {theme}", 2000)

    def _apply_theme(self):
        """Wendet das aktuelle Theme an"""
        # Theme Manager verwenden
        self.theme_manager.apply_theme()

        # Nach Theme-Wechsel: Typ-Farben/Badges neu anwenden
        try:
            if hasattr(self, "tracking_tab") and hasattr(self.tracking_tab, "refresh"):
                self.tracking_tab.refresh()
            if hasattr(self, "overview_tab"):
                if hasattr(self.overview_tab, "refresh_data"):
                    self.overview_tab.refresh_data()
                elif hasattr(self.overview_tab, "refresh"):
                    self.overview_tab.refresh()
        except Exception:
            pass

    # ------------------------------------------------------------
    # Bearbeiten-Menü (dynamisch je nach aktivem Tab)
    # ------------------------------------------------------------
    def _setup_edit_menu(self):
        """Erstellt das Bearbeiten-Menü mit allen möglichen Actions"""
        self.edit_menu.clear()

        # Undo/Redo (immer verfügbar)
        self.undo_action = QAction("↩️ &Undo", self)
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.setShortcutContext(Qt.ApplicationShortcut)
        self.undo_action.triggered.connect(self._undo_global)
        self.edit_menu.addAction(self.undo_action)

        self.redo_action = QAction("↪️ &Redo", self)
        self.redo_action.setShortcuts([QKeySequence.Redo, QKeySequence("Ctrl+Shift+Z")])
        self.redo_action.setShortcutContext(Qt.ApplicationShortcut)
        self.redo_action.triggered.connect(self._redo_global)
        self.edit_menu.addAction(self.redo_action)

        self.edit_menu.addSeparator()

        self._update_undo_redo_actions()
        
        # === ALLGEMEINE AKTIONEN (immer sichtbar) ===
        self._edit_actions_general = []
        
        # Neu hinzufügen
        add_action = QAction("➕ &Neu hinzufügen...", self)
        add_action.setShortcut("Ctrl+N")
        add_action.triggered.connect(self._edit_add)
        self.edit_menu.addAction(add_action)
        self._edit_actions_general.append(add_action)
        
        # Bearbeiten
        edit_action = QAction("✏️ &Bearbeiten...", self)
        edit_action.setShortcut("Ctrl+E")
        edit_action.triggered.connect(self._edit_edit)
        self.edit_menu.addAction(edit_action)
        self._edit_actions_general.append(edit_action)
        
        # Löschen
        delete_action = QAction("🗑️ &Löschen", self)
        delete_action.setShortcut("Delete")
        delete_action.triggered.connect(self._edit_delete)
        self.edit_menu.addAction(delete_action)
        self._edit_actions_general.append(delete_action)
        
        self.edit_menu.addSeparator()
        
        # === BUDGET-TAB AKTIONEN ===
        self._edit_actions_budget = []
        
        budget_entry_action = QAction("📝 Budget &erfassen...", self)
        budget_entry_action.triggered.connect(self._budget_entry)
        self.edit_menu.addAction(budget_entry_action)
        self._edit_actions_budget.append(budget_entry_action)
        
        budget_edit_action = QAction("✏️ Budget &bearbeiten...", self)
        budget_edit_action.triggered.connect(self._budget_edit)
        self.edit_menu.addAction(budget_edit_action)
        self._edit_actions_budget.append(budget_edit_action)
        
        self.edit_menu.addSeparator()
        
        budget_seed_action = QAction("🌱 Zeilen aus &Kategorien erzeugen", self)
        budget_seed_action.triggered.connect(self._budget_seed)
        self.edit_menu.addAction(budget_seed_action)
        self._edit_actions_budget.append(budget_seed_action)
        
        budget_copy_action = QAction("📋 Jahr &kopieren...", self)
        budget_copy_action.triggered.connect(self._budget_copy_year)
        self.edit_menu.addAction(budget_copy_action)
        self._edit_actions_budget.append(budget_copy_action)
        
        self.edit_menu.addSeparator()
        
        budget_remove_row_action = QAction("🗑️ Budget-&Zeile entfernen", self)
        budget_remove_row_action.triggered.connect(self._budget_remove_row)
        self.edit_menu.addAction(budget_remove_row_action)
        self._edit_actions_budget.append(budget_remove_row_action)
        
        budget_remove_cat_action = QAction("⚠️ Kategorie &löschen (global)", self)
        budget_remove_cat_action.triggered.connect(self._budget_remove_category)
        self.edit_menu.addAction(budget_remove_cat_action)
        self._edit_actions_budget.append(budget_remove_cat_action)
        
        # === KATEGORIEN-TAB AKTIONEN ===
        self._edit_actions_categories = []
        
        cat_new_main_action = QAction("📁 Neue &Hauptkategorie...", self)
        cat_new_main_action.triggered.connect(self._categories_new_main)
        self.edit_menu.addAction(cat_new_main_action)
        self._edit_actions_categories.append(cat_new_main_action)
        
        cat_new_sub_action = QAction("📂 Neue &Unterkategorie...", self)
        cat_new_sub_action.triggered.connect(self._categories_new_sub)
        self.edit_menu.addAction(cat_new_sub_action)
        self._edit_actions_categories.append(cat_new_sub_action)
        
        cat_delete_action = QAction("🗑️ Auswahl &löschen", self)
        cat_delete_action.triggered.connect(self._categories_delete)
        self.edit_menu.addAction(cat_delete_action)
        self._edit_actions_categories.append(cat_delete_action)
        
        self.edit_menu.addSeparator()
        
        cat_mass_edit_action = QAction("✏️ &Massenbearbeitung...", self)
        cat_mass_edit_action.setStatusTip("Flags für mehrere Kategorien gleichzeitig ändern")
        cat_mass_edit_action.triggered.connect(self._categories_mass_edit)
        self.edit_menu.addAction(cat_mass_edit_action)
        self._edit_actions_categories.append(cat_mass_edit_action)
        
        # === TRACKING-TAB AKTIONEN ===
        self._edit_actions_tracking = []
        
        self.edit_menu.addSeparator()
        
        fix_action = QAction("📅 &Fixkosten buchen...", self)
        fix_action.setShortcut("Ctrl+Shift+F")
        fix_action.triggered.connect(self._tracking_add_fixcosts)
        self.edit_menu.addAction(fix_action)
        self._edit_actions_tracking.append(fix_action)
        
        recurring_action = QAction("🔄 &Wiederkehrende verwalten...", self)
        recurring_action.triggered.connect(self._tracking_manage_recurring)
        self.edit_menu.addAction(recurring_action)
        self._edit_actions_tracking.append(recurring_action)
        
        # === ÜBERSICHT-TAB AKTIONEN ===
        self._edit_actions_overview = []
        
        refresh_overview_action = QAction("🔄 Daten &aktualisieren", self)
        refresh_overview_action.setShortcut("F5")
        refresh_overview_action.triggered.connect(self._overview_refresh)
        self.edit_menu.addAction(refresh_overview_action)
        self._edit_actions_overview.append(refresh_overview_action)
        
        # Initial aktualisieren
        self._update_edit_menu()
    
    def _on_tab_changed(self, index: int):
        """Wird aufgerufen wenn Tab gewechselt wird"""
        self._update_edit_menu()
        self._update_undo_redo_actions()


    
    def _update_edit_menu(self):
        """Aktualisiert die Sichtbarkeit der Bearbeiten-Menü-Einträge"""
        current_widget = self.tabs.currentWidget()
        
        # Alle Tab-spezifischen Actions verstecken
        for action in self._edit_actions_budget:
            action.setVisible(False)
        for action in self._edit_actions_categories:
            action.setVisible(False)
        for action in self._edit_actions_tracking:
            action.setVisible(False)
        for action in self._edit_actions_overview:
            action.setVisible(False)
        
        # Je nach Tab die entsprechenden Actions anzeigen
        if current_widget == self.budget_tab:
            for action in self._edit_actions_budget:
                action.setVisible(True)
        elif current_widget == self.categories_tab:
            for action in self._edit_actions_categories:
                action.setVisible(True)
        elif current_widget == self.tracking_tab:
            for action in self._edit_actions_tracking:
                action.setVisible(True)
        elif current_widget == self.overview_tab:
            for action in self._edit_actions_overview:
                action.setVisible(True)
            # Allgemeine Aktionen in Übersicht deaktivieren
            for action in self._edit_actions_general:
                action.setEnabled(False)
            return
        
        # Allgemeine Aktionen aktivieren für andere Tabs
        for action in self._edit_actions_general:
            action.setEnabled(True)

        self._update_undo_redo_actions()
    
    # --- Bearbeiten-Menü Handler ---
    def _edit_add(self):
        """Neu hinzufügen - delegiert an aktuellen Tab"""
        current = self.tabs.currentWidget()
        if hasattr(current, 'add'):
            current.add()
        elif hasattr(current, 'on_add'):
            current.on_add()
    
    def _edit_edit(self):
        """Bearbeiten - delegiert an aktuellen Tab"""
        current = self.tabs.currentWidget()
        if hasattr(current, 'edit'):
            current.edit()
        elif hasattr(current, 'on_edit'):
            current.on_edit()
    
    def _edit_delete(self):
        """Löschen - delegiert an aktuellen Tab"""
        current = self.tabs.currentWidget()
        if hasattr(current, 'delete'):
            current.delete()
        elif hasattr(current, 'on_delete'):
            current.on_delete()
    
    def _budget_copy_year(self):
        """Budget: Jahr kopieren"""
        if hasattr(self.budget_tab, 'copy_year_dialog'):
            self.budget_tab.copy_year_dialog()
    
    def _budget_entry(self):
        """Budget: Erfassen Dialog"""
        if hasattr(self.budget_tab, 'open_entry_dialog'):
            self.budget_tab.open_entry_dialog()
    
    def _budget_edit(self):
        """Budget: Bearbeiten Dialog"""
        if hasattr(self.budget_tab, 'open_edit_dialog'):
            self.budget_tab.open_edit_dialog()
    
    def _budget_seed(self):
        """Budget: Zeilen aus Kategorien erzeugen"""
        if hasattr(self.budget_tab, 'seed_from_categories'):
            self.budget_tab.seed_from_categories()
    
    def _budget_remove_row(self):
        """Budget: Zeile entfernen"""
        if hasattr(self.budget_tab, 'remove_budget_row'):
            self.budget_tab.remove_budget_row()
    
    def _budget_remove_category(self):
        """Budget: Kategorie global löschen"""
        if hasattr(self.budget_tab, 'delete_category_global'):
            self.budget_tab.delete_category_global()
    
    def _budget_adjust(self):
        """Budget: Anpassen Dialog"""
        if hasattr(self.budget_tab, 'adjust_budget'):
            self.budget_tab.adjust_budget()
    
    def _categories_new_main(self):
        """Kategorien: Neue Hauptkategorie"""
        if hasattr(self.categories_tab, 'add_root_category'):
            self.categories_tab.add_root_category()
    
    def _categories_new_sub(self):
        """Kategorien: Neue Unterkategorie"""
        if hasattr(self.categories_tab, 'add_subcategory'):
            self.categories_tab.add_subcategory()
    
    def _categories_delete(self):
        """Kategorien: Auswahl löschen"""
        if hasattr(self.categories_tab, 'delete_selected'):
            self.categories_tab.delete_selected()
    
    def _categories_mass_edit(self):
        """Kategorien: Massenbearbeitung"""
        if hasattr(self.categories_tab, 'mass_edit'):
            self.categories_tab.mass_edit()
    
    def _categories_sort(self):
        """Kategorien: Sortierung ändern"""
        if hasattr(self.categories_tab, 'change_sort'):
            self.categories_tab.change_sort()
    
    def _tracking_add_fixcosts(self):
        """Tracking: Fixkosten buchen"""
        if hasattr(self.tracking_tab, 'add_fixcosts'):
            self.tracking_tab.add_fixcosts()
    
    def _tracking_manage_recurring(self):
        """Tracking: Wiederkehrende verwalten"""
        from views.recurring_transactions_dialog_extended import RecurringTransactionsDialog
        from model.recurring_transactions_model import RecurringTransactionsModel
        from model.category_model import CategoryModel
        
        # Model und Kategorien vorbereiten
        rec_model = RecurringTransactionsModel(self.conn)
        cat_model = CategoryModel(self.conn)
        
        # Kategorien als Dict aufbereiten (Typ -> Liste von Namen)
        categories = {}
        for typ in ["Ausgaben", "Einkommen", "Ersparnisse"]:
            cats = cat_model.list(typ)
            categories[typ] = [c.name for c in cats]
        
        dialog = RecurringTransactionsDialog(self, rec_model, categories, preferred_day=int(self.settings.get("recurring_preferred_day", 1) or 1))
        dialog.exec()
        self.tracking_tab.refresh()
    
    def _overview_refresh(self):
        """Übersicht: Daten aktualisieren"""
        if hasattr(self.overview_tab, 'refresh_data'):
            self.overview_tab.refresh_data()
        elif hasattr(self.overview_tab, 'refresh'):
            self.overview_tab.refresh()

    # ------------------------------------------------------------
    # Ansicht → Anzeigen → Übersicht: Subtabs ein/ausblenden
    # ------------------------------------------------------------
    def _get_overview_subtab_visibility(self) -> dict:
        """Lädt/normalisiert die Sichtbarkeit der Übersicht-Subtabs aus den Settings."""
        specs = []
        try:
            specs = self.overview_tab.get_subtab_specs()
        except Exception:
            specs = []
        default = {k: True for k, _t in specs}
        saved = self.settings.get('overview_visible_subtabs', None)
        if isinstance(saved, dict):
            vis = default.copy()
            for k, v in saved.items():
                if k in vis:
                    vis[k] = bool(v)
            return vis
        return default

    def _apply_overview_subtabs_from_settings(self) -> None:
        """Wendet die gespeicherte Sichtbarkeit direkt auf die Übersicht an."""
        vis = self._get_overview_subtab_visibility()
        if hasattr(self.overview_tab, 'apply_subtab_visibility'):
            self.overview_tab.apply_subtab_visibility(vis)
        else:
            # Fallback: einzelne Tabs
            for k, on in vis.items():
                if hasattr(self.overview_tab, 'set_subtab_visible'):
                    self.overview_tab.set_subtab_visible(k, bool(on))

        # Menü-Checkboxen synchronisieren
        if hasattr(self, '_overview_visibility_actions'):
            for k, act in self._overview_visibility_actions.items():
                act.blockSignals(True)
                act.setChecked(bool(vis.get(k, True)))
                act.blockSignals(False)

        # Normalisierte Map speichern
        if vis:
            self.settings.set('overview_visible_subtabs', vis)

    def _toggle_overview_subtab(self, key: str, checked: bool) -> None:
        """Callback aus dem Menü: ein/ausblenden + persistieren."""
        vis = self._get_overview_subtab_visibility()
        if not vis or key not in vis:
            return

        # Mindestens 1 Tab sichtbar lassen
        vis[key] = bool(checked)
        if not any(vis.values()):
            vis[key] = True
            if hasattr(self, '_overview_visibility_actions') and key in self._overview_visibility_actions:
                act = self._overview_visibility_actions[key]
                act.blockSignals(True)
                act.setChecked(True)
                act.blockSignals(False)
            self.statusBar().showMessage('Mindestens ein Übersicht-Reiter muss sichtbar bleiben.', 3000)
            return

        self.settings.set('overview_visible_subtabs', vis)
        if hasattr(self.overview_tab, 'apply_subtab_visibility'):
            self.overview_tab.apply_subtab_visibility(vis)
        elif hasattr(self.overview_tab, 'set_subtab_visible'):
            self.overview_tab.set_subtab_visible(key, bool(checked))

    def _save_budget(self):
        """Speichert das Budget"""
        try:
            self.budget_tab.save()
            self.statusBar().showMessage("Budget gespeichert", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Fehler beim Speichern: {e}")

    def _refresh_current_tab(self):
        """Aktualisiert den aktuellen Tab"""
        current_widget = self.tabs.currentWidget()
        
        if hasattr(current_widget, 'refresh'):
            current_widget.refresh()
            self.statusBar().showMessage("Ansicht aktualisiert", 2000)
        elif hasattr(current_widget, 'load'):
            current_widget.load()
            self.statusBar().showMessage("Ansicht aktualisiert", 2000)
    
    def _refresh_all_tabs(self):
        """Aktualisiert alle Tabs"""
        for tab in [self.budget_tab, self.categories_tab, self.tracking_tab, self.overview_tab]:
            if hasattr(tab, 'refresh'):
                tab.refresh()
            elif hasattr(tab, 'load'):
                tab.load()
        self.statusBar().showMessage("Alle Tabs aktualisiert", 2000)


    def _update_undo_redo_actions(self) -> None:
        """Aktiviert/Deaktiviert Undo/Redo je nach Stack."""
        if hasattr(self, "undo_action"):
            self.undo_action.setEnabled(self.undo_redo.can_undo())
        if hasattr(self, "redo_action"):
            self.redo_action.setEnabled(self.undo_redo.can_redo())

    def _undo_global(self) -> None:
        if self.undo_redo.undo():
            self._refresh_all_tabs()
        self._update_undo_redo_actions()

    def _redo_global(self) -> None:
        if self.undo_redo.redo():
            self._refresh_all_tabs()
        self._update_undo_redo_actions()

    def _set_current_year(self):
        """Setzt in allen Tabs das aktuelle Jahr"""
        current_year = date.today().year
        
        # Budget-Tab
        if hasattr(self.budget_tab, 'year_spin'):
            self.budget_tab.year_spin.setValue(current_year)
        
        # Overview-Tab
        if hasattr(self.overview_tab, 'year'):
            for i in range(self.overview_tab.year.count()):
                if self.overview_tab.year.itemText(i) == str(current_year):
                    self.overview_tab.year.setCurrentIndex(i)
                    break
        
        self.statusBar().showMessage(f"Jahr {current_year} geladen", 2000)

    def _show_db_info(self):
        """Zeigt Datenbank-Informationen und Migrations-Status"""
        from model.migrations import get_migration_info, CURRENT_VERSION
        import os
        
        try:
            # Datenbank-Größe
            try:
                db_size = os.path.getsize("budgetmanager.db") / 1024  # KB
            except:
                db_size = 0
            
            # Migrations-Info
            migration_info = get_migration_info(self.conn)
            
            # Tabellen-Info
            cur = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in cur.fetchall()]
            
            # Daten-Statistik
            budget_count = self.conn.execute("SELECT COUNT(*) FROM budget").fetchone()[0]
            tracking_count = self.conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0]
            category_count = self.conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
            
            savings_count = 0
            if 'savings_goals' in tables:
                savings_count = self.conn.execute("SELECT COUNT(*) FROM savings_goals").fetchone()[0]
            
            years_budget = self.conn.execute("SELECT DISTINCT year FROM budget ORDER BY year").fetchall()
            years_tracking = self.conn.execute(
                "SELECT DISTINCT CAST(substr(date,1,4) AS INTEGER) AS y FROM tracking ORDER BY y"
            ).fetchall()
            
            years_b = [str(y[0]) for y in years_budget]
            years_t = [str(y[0]) for y in years_tracking]
            
            # Dialog aufbauen
            info = f"""<h3>Datenbank-Informationen</h3>
            
<p><b>Datei:</b> budgetmanager.db<br>
<b>Größe:</b> {db_size:.1f} KB<br>
<b>Schema-Version:</b> {migration_info['current_version']} / {CURRENT_VERSION}</p>

<h4>Migration-Status</h4>
<p>"""
            
            if migration_info['needs_migration']:
                info += f"<span style='color: orange;'>⚠️ Migration erforderlich</span><br>"
                if migration_info['missing_tables']:
                    info += f"<b>Fehlende Tabellen:</b> {', '.join(migration_info['missing_tables'])}"
            else:
                info += "<span style='color: green;'>✓ Datenbank ist aktuell</span>"
            
            info += f"""</p>

<h4>Daten-Statistik</h4>
<ul>
<li>Kategorien: {category_count}</li>
<li>Budget-Einträge: {budget_count}</li>
<li>Tracking-Buchungen: {tracking_count}</li>
<li>Sparziele: {savings_count}</li>
</ul>

<p><b>Jahre mit Budget:</b> {', '.join(years_b) if years_b else 'Keine'}<br>
<b>Jahre mit Tracking:</b> {', '.join(years_t) if years_t else 'Keine'}</p>

<h4>Verfügbare Tabellen ({len(tables)})</h4>
<p><small>{', '.join(tables)}</small></p>
"""
            
            msg = QMessageBox(self)
            msg.setWindowTitle("Datenbank-Info")
            msg.setTextFormat(Qt.RichText)
            msg.setText(info)
            msg.exec()
            
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Fehler beim Laden der DB-Info: {e}")

    def _show_about(self):
        """Zeigt Über-Dialog"""
        dialog = AboutDialog(self)
        dialog.exec()
    
    def _show_shortcuts(self):
        """Zeigt Tastenkürzel-Übersicht (F1)"""
        dialog = ShortcutsDialog(self)
        dialog.exec()
    
    def _show_quick_add(self):
        """Zeigt Schnelleingabe-Dialog (Strg+N)"""
        dialog = QuickAddDialog(self.conn, self)
        if dialog.exec() == QDialog.Accepted:
            # Tracking-Tab aktualisieren
            if hasattr(self.tracking_tab, 'refresh'):
                self.tracking_tab.refresh()
            self.statusBar().showMessage("Eintrag hinzugefügt", 2000)
    
    def _show_global_search(self):
        """Zeigt Globale Suche (Strg+F)"""
        dialog = GlobalSearchDialog(self.conn, self)
        dialog.exec()
    
    def _show_export(self):
        """Zeigt Export-Dialog (Strg+E)"""
        dialog = ExportDialog(self.conn, self)
        dialog.exec()
    
    def _show_savings_goals(self):
        """Zeigt Sparziele-Dialog (NEU v0.16)"""
        dialog = SavingsGoalsDialog(self, self.conn)
        dialog.exec()
        # Nach Schließen: ggf. Tabs aktualisieren
        self._refresh_current_tab()
    
    def _show_backup_restore(self):
        """Zeigt Backup & Restore Dialog (NEU v0.16)"""
        db_path = self.settings.database_path
        dialog = BackupRestoreDialog(self, self.conn, db_path, self.settings)
        result = dialog.exec()
        # Falls Datenbank restored wurde, sollte App neu gestartet werden
        if result == QDialog.Accepted:
            QMessageBox.information(
                self,
                "Neustart erforderlich",
                "Bitte starten Sie die Anwendung neu, um die Änderungen zu übernehmen."
            )
    
    def _show_category_manager(self):
        """Zeigt den Kategorien-Manager-Dialog (NEU v2.2.0)"""
        dialog = CategoryManagerDialog(self, conn=self.conn)
        dialog.categories_changed.connect(self._refresh_current_tab)
        dialog.exec()
        # Nach Schließen: Alle Tabs aktualisieren
        self._refresh_all_tabs()
    
    def _refresh_all_tabs(self):
        """Aktualisiert alle Tabs nach Kategorien-Änderungen."""
        try:
            if hasattr(self.budget_tab, 'load'):
                self.budget_tab.load()
            if hasattr(self.tracking_tab, 'load'):
                self.tracking_tab.load()
            if hasattr(self.categories_tab, 'load'):
                self.categories_tab.load()
            if hasattr(self.overview_tab, 'load'):
                self.overview_tab.load()
        except Exception:
            pass  # Fehler ignorieren
    
    def _show_theme_profiles(self):
        """Zeigt Erscheinungsprofile Dialog"""
        dialog = AppearanceProfilesDialog(self, self.settings)
        dialog.exec()
        # Nach Dialog: aktives Profil erneut anwenden
        self._apply_theme()

    def _toggle_fullscreen(self, checked):
        """Toggle Vollbildmodus (F11)"""
        if checked:
            self.showFullScreen()
            self.statusBar().showMessage("Vollbildmodus aktiviert", 2000)
        else:
            # Zurück zu Normal oder Maximiert
            if self.isMaximized():
                self.showMaximized()
            else:
                self.showNormal()
            self.statusBar().showMessage("Vollbildmodus deaktiviert", 2000)
        
        self.settings.set("window_is_fullscreen", checked)
    
    def _toggle_maximize(self, checked):
        """Toggle Maximiert-Modus (F10)"""
        if self.isFullScreen():
            # Wenn fullscreen, erst aus fullscreen
            self.showNormal()
            self.settings.set("window_is_fullscreen", False)
        
        if checked:
            self.showMaximized()
            self.statusBar().showMessage("Fenster maximiert", 2000)
        else:
            self.showNormal()
            self.statusBar().showMessage("Fenster normalisiert", 2000)
        
        self.settings.set("window_is_maximized", checked)

    def changeEvent(self, event):
        """Wird aufgerufen wenn Fenster-State sich ändert (minimize, maximize, etc)"""
        from PySide6.QtGui import QWindowStateChangeEvent
        if isinstance(event, QWindowStateChangeEvent):
            # Update maximize status (nur wenn settings schon initialisiert)
            if hasattr(self, 'settings'):
                is_max = self.isMaximized()
                self.settings.set("window_is_maximized", is_max)
        super().changeEvent(event)

    def closeEvent(self, event):
        """Wird beim Schließen des Fensters aufgerufen"""
        # Speichere Fenster-State BEVOR wir fragen (nur wenn settings existiert)
        if hasattr(self, 'settings'):
            self.settings.set("window_is_fullscreen", self.isFullScreen())
            self.settings.set("window_is_maximized", self.isMaximized())
            
            # Fenstergröße speichern (nur wenn nicht fullscreen/maximized)
            if not self.isFullScreen() and not self.isMaximized():
                self.settings.set("window_width", self.width())
                self.settings.set("window_height", self.height())
                self.settings.set("window_x", self.x())
                self.settings.set("window_y", self.y())
        
        # Tab-Reihenfolge speichern
        self._save_tab_order()
        
        # Wenn Auto-Save aktiv: Einfach speichern und schließen
        if hasattr(self, 'settings') and self.settings.auto_save:
            try:
                self.budget_tab.save()
            except Exception:
                pass  # Fehler ignorieren beim Schließen
            event.accept()
            return
        
        # Wenn Auto-Save nicht aktiv: Einmal fragen ob gespeichert werden soll
        reply = QMessageBox.question(
            self,
            "Beenden",
            "Möchten Sie das Budget vor dem Beenden speichern?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save
        )
        
        if reply == QMessageBox.Save:
            try:
                self.budget_tab.save()
            except Exception:
                pass
            event.accept()
        elif reply == QMessageBox.Discard:
            event.accept()
        else:  # Cancel
            event.ignore()

    # =========================================================================
    # Setup-Assistent / Onboarding
    # =========================================================================
    def _start_setup_assistant(self, *, force: bool = False, db_existed_before: bool | None = None) -> None:
        """Startet den First-Start-Guide (Setup-Assistent).
        
        Args:
            force: True = immer starten (z.B. aus Menü), False = nur wenn Bedingungen erfüllt
            db_existed_before: Optional, ob die DB vor dem Start schon existierte
        """
        try:
            from views.setup_assistant_dialog import SetupAssistantDialog

            # Autostart: nur wenn aktiviert und noch nicht abgeschlossen
            if not force:
                if not bool(self.settings.get("show_onboarding", True)):
                    return
                if bool(self.settings.get("setup_completed", False)):
                    return

            # db_existed_before: idealerweise aus main.py (vor open_db) übergeben
            db_existed = True
            if db_existed_before is not None:
                db_existed = bool(db_existed_before)
            else:
                try:
                    db_path = Path(self.settings.get("database_path", "budgetmanager.db")).expanduser()
                    db_existed = db_path.exists()
                except Exception:
                    db_existed = True

            dlg = SetupAssistantDialog(self, self.conn, self.settings, db_existed_before=db_existed)
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Setup-Assistent konnte nicht gestartet werden:\n{e}")
