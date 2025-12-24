from __future__ import annotations
import sqlite3
import sys
from datetime import date
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QMenuBar, QMenu, QMessageBox,
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QApplication
)
from PySide6.QtGui import QAction, QKeySequence, QIcon, QShortcut
from PySide6.QtCore import Qt

from model.category_model import CategoryModel
from views.tabs.tracking_tab import TrackingTab
from views.tabs.categories_tab import CategoriesTab
from views.tabs.budget_tab import BudgetTab
from views.tabs.overview_tab import OverviewTab
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

class AboutDialog(QDialog):
    """Über-Dialog"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Über Budgetmanager")
        
        layout = QVBoxLayout()
        
        info = QLabel(
            "<h2>Budgetmanager</h2>"
            "<p><b>Version:</b> 0.17.2 (Dezember 2024)</p>"
            "<p><b>Entwickelt mit:</b> PySide6 (Qt für Python)</p>"
            "<p><b>Datenbank:</b> SQLite</p>"
            "<br>"
            "<p>Ein einfacher Budgetmanager zur Verwaltung von:</p>"
            "<ul>"
            "<li>Budget-Planung nach Kategorien</li>"
            "<li>Tracking von Einnahmen und Ausgaben</li>"
            "<li>Visualisierung und Auswertung</li>"
            "<li>Sparziele und Favoriten</li>"
            "<li>Tags und Budgetwarnungen</li>"
            "</ul>"
            "<br>"
            "<p><b>Neue Features v0.17.2:</b></p>"
            "<ul>"
            "<li>Vollständig integrierter Theme Manager</li>"
            "<li>6 professionelle vordefinierte Profile</li>"
            "<li>Unbegrenzt eigene Themes erstellen</li>"
            "<li>Import/Export von Profilen</li>"
            "<li>Live-Vorschau in Einstellungen</li>"
            "<li>Fixkosten-Check und -Verwaltung</li>"
            "</ul>"
        )
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
        self.setWindowTitle("Budgetmanager v0.17.2")

        # Einstellungen laden
        self.settings = Settings()
        
        # Theme Manager initialisieren
        self.theme_manager = ThemeManager(self.settings)
        
        # Defaults once
        CategoryModel(conn).ensure_defaults()

        # Tabs erstellen (verschiebbar)
        self.tabs = QTabWidget()
        self.tabs.setMovable(True)  # Tabs per Drag & Drop verschiebbar
        self.tabs.setDocumentMode(True)  # Moderneres Aussehen
        
        # Tab-Widgets erstellen
        self.budget_tab = BudgetTab(conn)
        self.categories_tab = CategoriesTab(conn)
        self.tracking_tab = TrackingTab(conn, settings=self.settings)
        self.overview_tab = OverviewTab(conn)
        
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
        
        # Fenstergröße aus Einstellungen
        width = self.settings.get("window_width", 1280)
        height = self.settings.get("window_height", 800)
        self.resize(width, height)
        
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
        
        goto_categories = QAction("📁 &Kategorien", self)
        goto_categories.setShortcut("Ctrl+2")
        goto_categories.triggered.connect(lambda: self._goto_tab(self.categories_tab))
        view_menu.addAction(goto_categories)
        
        goto_tracking = QAction("📊 &Tracking", self)
        goto_tracking.setShortcut("Ctrl+3")
        goto_tracking.triggered.connect(lambda: self._goto_tab(self.tracking_tab))
        view_menu.addAction(goto_tracking)
        
        goto_overview = QAction("📈 Ü&bersicht", self)
        goto_overview.setShortcut("Ctrl+4")
        goto_overview.triggered.connect(lambda: self._goto_tab(self.overview_tab))
        view_menu.addAction(goto_overview)
        
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
    
    def _load_tab_order(self):
        """Lädt Tabs in der gespeicherten Reihenfolge"""
        saved_order = self.settings.tab_order
        
        # Validierung: Stelle sicher, dass alle Indizes vorhanden sind
        if not saved_order or set(saved_order) != {0, 1, 2, 3}:
            saved_order = [0, 1, 2, 3]
        
        # Tabs in gespeicherter Reihenfolge hinzufügen
        for tab_id in saved_order:
            widget, name = self._tab_definitions[tab_id]
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
    
    def _reset_tab_order(self):
        """Setzt die Tab-Reihenfolge auf Standard zurück"""
        # Merke aktuellen Tab
        current_widget = self.tabs.currentWidget()
        
        # Alle Tabs entfernen (ohne zu löschen)
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)
        
        # Tabs in Standardreihenfolge hinzufügen
        default_order = [0, 1, 2, 3]
        for tab_id in default_order:
            widget, name = self._tab_definitions[tab_id]
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
            if hasattr(self, "overview_tab") and hasattr(self.overview_tab, "refresh"):
                self.overview_tab.refresh()
        except Exception:
            pass

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
    
    def _show_theme_profiles(self):
        """Zeigt Erscheinungsprofile Dialog"""
        dialog = AppearanceProfilesDialog(self, self.settings)
        dialog.exec()
        # Nach Dialog: aktives Profil erneut anwenden
        self._apply_theme()


    def closeEvent(self, event):
        """Wird beim Schließen des Fensters aufgerufen"""
        # Fenstergröße speichern
        self.settings.set("window_width", self.width())
        self.settings.set("window_height", self.height())
        
        # Tab-Reihenfolge speichern
        self._save_tab_order()
        
        # Bestätigung vor dem Schließen
        reply = QMessageBox.question(
            self,
            "Beenden",
            "Möchten Sie den Budgetmanager wirklich beenden?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Speichern falls nötig
            if not self.settings.auto_save:
                reply2 = QMessageBox.question(
                    self,
                    "Speichern",
                    "Möchten Sie das Budget vor dem Beenden noch speichern?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                    QMessageBox.Yes
                )
                if reply2 == QMessageBox.Cancel:
                    event.ignore()
                    return
                elif reply2 == QMessageBox.Yes:
                    self.budget_tab.save()
            
            event.accept()
        else:
            event.ignore()
