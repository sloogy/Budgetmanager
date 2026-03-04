from __future__ import annotations

import logging
import sqlite3
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence, QShortcut, QDesktopServices
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QMenuBar, QMenu, QMessageBox,
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QApplication, QPushButton
)

from app_info import APP_NAME, APP_VERSION, app_window_title, app_about_title, app_version_label
from model.app_paths import resolve_in_app, data_dir
from model.budget_warnings_model_extended import BudgetWarningsModelExtended
from model.category_model import CategoryModel
from model.shortcuts_config import load_shortcuts, save_shortcuts
from model.undo_redo_model import UndoRedoModel
from settings import Settings
from utils.icons import get_icon
from utils.i18n import tr
from settings_dialog import SettingsDialog
from theme_manager import ThemeManager
from views.account_management_dialog import AccountManagementDialog
from views.backup_restore_dialog import BackupRestoreDialog
from views.budget_adjustment_dialog import BudgetAdjustmentDialog
from views.category_manager_dialog import CategoryManagerDialog
from views.export_dialog import ExportDialog
from views.favorites_dashboard_dialog import FavoritesDashboardDialog
from views.global_search_dialog import GlobalSearchDialog
from views.quick_add_dialog import QuickAddDialog
from views.savings_goals_dialog import SavingsGoalsDialog
from views.shortcuts_dialog import ShortcutsDialog
from views.tabs.budget_tab import BudgetTab
from views.tabs.categories_tab import CategoriesTab
from views.tabs.overview_tab import OverviewTab
from views.tabs.tracking_tab import TrackingTab
from views.tags_manager_dialog import TagsManagerDialog
from views.update_dialog import UpdateDialog

logger = logging.getLogger(__name__)

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

        # Update-Button direkt im Info/Über-Dialog
        btn_updates = buttons.addButton("Updates...", QDialogButtonBox.ActionRole)
        btn_updates.clicked.connect(self._open_updates)

        layout.addWidget(info)
        layout.addWidget(buttons)
        self.setLayout(layout)
        self.setMinimumWidth(450)

    def _open_updates(self):
        """Öffnet den Update-Dialog (portable/EXE kompatibel)."""
        try:
            dlg = UpdateDialog(self.parent() or self)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Update", trf("lbl.updatedialog_konnte_nicht_geoeffnet"))

class MainWindow(QMainWindow):
    def __init__(self, conn: sqlite3.Connection, *,
                 active_user=None, user_model=None):
        super().__init__()
        self.conn = conn
        self._active_user = active_user    # User-Objekt (oder None bei unverschlüsselter DB)
        self._user_model = user_model      # UserModel (oder None)
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
        self._apply_tab_position()
        self._apply_tab_bar_visibility()
        
        # Tab-Widgets erstellen
        self.budget_tab = BudgetTab(conn)
        self.categories_tab = CategoriesTab(conn)
        self.tracking_tab = TrackingTab(conn, settings=self.settings)
        self.overview_tab = OverviewTab(conn, settings=self.settings)
        
        # Schnelleingabe-Signals von Tabs verbinden
        self.budget_tab.quick_add_requested.connect(self._show_quick_add)
        self.categories_tab.quick_add_requested.connect(self._show_quick_add)
        self.overview_tab.quick_add_requested.connect(self._show_quick_add)

        # "Vorschläge"-Button in der Übersicht soll den Budgetwarner öffnen
        try:
            self.overview_tab.budget_warnings_requested.connect(self._check_budget_warnings_from_overview)
        except Exception as e:
            logger.debug("%s", e)
        try:
            self.overview_tab.budget_edit_requested.connect(self._open_budget_editor_from_overview)
        except Exception as e:
            logger.debug("%s", e)
        
        # Settings-Checkboxen mit Settings synchronisieren
        if hasattr(self.budget_tab, 'chk_autosave'):
            self.budget_tab.chk_autosave.toggled.connect(self._on_autosave_changed)
        if hasattr(self.budget_tab, 'chk_ask_due'):
            self.budget_tab.chk_ask_due.toggled.connect(self._on_ask_due_changed)
        if hasattr(self.budget_tab, 'budget_data_changed'):
            self.budget_tab.budget_data_changed.connect(self._update_undo_redo_actions)
        
        # Tab-Definitionen (Index -> Widget, Name)
        # Tab-Labels: keys statt eingefrorenem tr()-String (fuer retranslate_ui)
        self._tab_label_keys = {
            0: ("tr", "tab.budget"),
            1: ("fixed", tr("tab.categories")),
            2: ("fixed", tr("tab.tracking")),
            3: ("tr", "tab.overview"),
        }
        self._tab_definitions = {
            0: (self.budget_tab, tr("tab.budget")),
            1: (self.categories_tab, tr("tab.categories")),
            2: (self.tracking_tab, tr("tab.tracking")),
            3: (self.overview_tab, tr("tab.overview")),
        }
        
        # Tabs in gespeicherter Reihenfolge hinzufügen
        self._load_tab_order()
        self._apply_tab_icons()

        self.setCentralWidget(self.tabs)
        
        # Tab-Wechsel Signal verbinden (für dynamisches Bearbeiten-Menü)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        
        # Fenster-Geometrie und -Status wiederherstellen
        self._restore_window_state()
        
        # Menü erstellen
        self._create_menu()

        # Footer/Statusbar-Info (User + DB-Pfad)
        self._setup_statusbar_info()
        
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

        # Auto-Backup prüfen (wenn aktiviert)
        self._check_auto_backup()
    
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
        """Richtet globale Tastenkürzel ein (konfigurierbar über Einstellungen)."""
        sc = load_shortcuts(self.settings)

        # Alte Shortcuts entfernen (bei Re-Apply nach Settings-Änderung)
        for attr in list(vars(self)):
            if attr.startswith("_sc_"):
                old = getattr(self, attr, None)
                if old:
                    try:
                        old.setEnabled(False)
                        old.deleteLater()
                    except Exception as e:
                        logger.debug("%s", e)

        def _bind(action_id: str, slot):
            key = sc.get(action_id, "")
            if key:
                shortcut = QShortcut(QKeySequence(key), self)
                shortcut.activated.connect(slot)
                setattr(self, f"_sc_{action_id}", shortcut)

        _bind("help", self._show_shortcuts)
        _bind("search", self._show_global_search)
        _bind("quick_add", self._show_quick_add)
        _bind("export", self._show_export)

    def _create_menu(self):
        """Erstellt das Hamburger-Menü (Menüleiste)"""
        menubar = self.menuBar()

        self._create_file_menu(menubar)

        # Bearbeiten-Menü (dynamisch je nach Tab)
        self.edit_menu = menubar.addMenu(tr("menu.edit"))
        self._edit_menu_actions = {}
        self._setup_edit_menu()

        self._create_view_menu(menubar)
        self._create_extras_menu(menubar)
        self._create_account_menu(menubar)
        self._create_help_menu(menubar)

    # ── Menü-Sektionen ──────────────────────────────────────────

    def _create_file_menu(self, menubar: QMenuBar) -> None:
        """Datei-Menü: Speichern, Einstellungen, DB-Info, Beenden."""
        file_menu = menubar.addMenu(tr("menu.file"))

        save_action = QAction(tr("menu.save"), self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.setStatusTip(tr("menu.save_tip"))
        save_action.triggered.connect(self._save_budget)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        settings_action = QAction(tr("menu.settings"), self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.setStatusTip(tr("menu.settings_tip"))
        settings_action.triggered.connect(self._show_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        db_info_action = QAction(tr("menu.db_info"), self)
        db_info_action.triggered.connect(self._show_db_info)
        file_menu.addAction(db_info_action)

        open_data_action = QAction(tr("menu.open_data_folder"), self)
        open_data_action.setStatusTip(tr("menu.open_data_folder_tip"))
        open_data_action.triggered.connect(self._open_data_folder)
        file_menu.addAction(open_data_action)

        file_menu.addSeparator()

        exit_action = QAction(tr("menu.exit"), self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.setStatusTip(tr("menu.exit_tip"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _create_view_menu(self, menubar: QMenuBar) -> None:
        """Ansicht-Menü: Tab-Navigation, Subtab-Sichtbarkeit, Vollbild."""
        view_menu = menubar.addMenu(tr("menu.view"))

        # Anzeigen-Untermenü (Tabs/Module ein- & ausblenden)
        anzeigen_menu = view_menu.addMenu(tr("menu.show"))

        # Übersicht → Subtabs ein/ausblenden
        overview_menu = anzeigen_menu.addMenu(tr("menu.overview_subtabs"))
        overview_menu.setIcon(get_icon("📈"))
        self._overview_visibility_actions = {}

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
            dummy = QAction(tr("lbl.keine_optionen_verfuegbar"), self)
            dummy.setEnabled(False)
            overview_menu.addAction(dummy)

        view_menu.addSeparator()

        # Zu Tabs wechseln
        goto_budget = QAction(tr("menu.goto_budget"), self)
        goto_budget.setIcon(get_icon("💰"))
        goto_budget.setShortcut("Ctrl+1")
        goto_budget.triggered.connect(lambda: self._goto_tab(self.budget_tab))
        view_menu.addAction(goto_budget)

        self.goto_categories_action = QAction(tr("menu.goto_categories"), self)
        self.goto_categories_action.setIcon(get_icon("📁"))
        self.goto_categories_action.setShortcut("Ctrl+2")
        self.goto_categories_action.triggered.connect(lambda: self._goto_tab(self.categories_tab))
        view_menu.addAction(self.goto_categories_action)
        self._update_categories_menu_visibility()

        goto_tracking = QAction(tr("menu.goto_tracking"), self)
        goto_tracking.setIcon(get_icon("📊"))
        goto_tracking.setShortcut("Ctrl+3")
        goto_tracking.triggered.connect(lambda: self._goto_tab(self.tracking_tab))
        view_menu.addAction(goto_tracking)

        goto_overview = QAction(tr("menu.goto_overview"), self)
        goto_overview.setIcon(get_icon("📈"))
        goto_overview.setShortcut("Ctrl+4")
        goto_overview.triggered.connect(lambda: self._goto_tab(self.overview_tab))
        view_menu.addAction(goto_overview)

        view_menu.addSeparator()

        # Toggle für Kategorien-Tab
        self.toggle_categories_action = QAction(tr("menu.toggle_categories"), self)
        self.toggle_categories_action.setIcon(get_icon("🛠️"))
        self.toggle_categories_action.setCheckable(True)
        self.toggle_categories_action.setChecked(self.settings.show_categories_tab)
        self.toggle_categories_action.setToolTip(tr("tip.categories_tab_expert"))
        self.toggle_categories_action.toggled.connect(self._toggle_categories_tab)
        view_menu.addAction(self.toggle_categories_action)

        view_menu.addSeparator()

        refresh_action = QAction(tr("menu.refresh"), self)
        refresh_action.setShortcut(QKeySequence.Refresh)
        refresh_action.setStatusTip(tr("menu.refresh_tip"))
        refresh_action.triggered.connect(self._refresh_current_tab)
        view_menu.addAction(refresh_action)

        view_menu.addSeparator()

        fullscreen_action = QAction(tr("menu.fullscreen"), self)
        fullscreen_action.setIcon(get_icon("🖥️"))
        fullscreen_action.setShortcut("F11")
        fullscreen_action.setCheckable(True)
        fullscreen_action.setChecked(self.settings.get("window_is_fullscreen", False))
        fullscreen_action.toggled.connect(self._toggle_fullscreen)
        view_menu.addAction(fullscreen_action)

        maximize_action = QAction(tr("menu.maximize"), self)
        maximize_action.setIcon(get_icon("🔲"))
        maximize_action.setShortcut("F10")
        maximize_action.setCheckable(True)
        maximize_action.toggled.connect(self._toggle_maximize)
        view_menu.addAction(maximize_action)

        view_menu.addSeparator()

        # ── Tab-Leiste: Sichtbarkeit + Position ──────────────────────
        tab_bar_menu = view_menu.addMenu(tr("menu.tab_bar"))
        tab_bar_menu.setIcon(get_icon("📌"))

        self._act_tab_bar_show = QAction(tr("menu.tab_bar_show"), self)
        self._act_tab_bar_show.setCheckable(True)
        self._act_tab_bar_show.setChecked(self.settings.get("tab_bar_visible", True))
        self._act_tab_bar_show.toggled.connect(self._on_tab_bar_show_toggled)
        tab_bar_menu.addAction(self._act_tab_bar_show)

        tab_bar_menu.addSeparator()

        pos_group = QActionGroup(self)
        pos_group.setExclusive(True)

        _cur_pos = self.settings.get("tab_position", "west")
        _pos_defs = [
            ("west",  tr("menu.tab_bar_pos_left")),
            ("east",  tr("menu.tab_bar_pos_right")),
            ("north", tr("menu.tab_bar_pos_top")),
            ("south", tr("menu.tab_bar_pos_bottom")),
        ]
        for pos_key, pos_label in _pos_defs:
            act = QAction(pos_label, self)
            if pos_key == "west":
                act.setIcon(get_icon("⬅️"))
            elif pos_key == "east":
                act.setIcon(get_icon("➡️"))
            elif pos_key == "north":
                act.setIcon(get_icon("⬆️"))
            elif pos_key == "south":
                act.setIcon(get_icon("⬇️"))
            act.setCheckable(True)
            act.setChecked(pos_key == _cur_pos)
            act.setData(pos_key)
            act.triggered.connect(lambda checked, k=pos_key: self._on_tab_position_changed(k))
            pos_group.addAction(act)
            tab_bar_menu.addAction(act)

    def _create_extras_menu(self, menubar: QMenuBar) -> None:
        """Extras-Menü: Schnelleingabe, Suche, Manager, Export, Backup usw."""
        extras_menu = menubar.addMenu(tr("menu.extras"))

        quick_add_action = QAction(tr("menu.quick_add"), self)
        quick_add_action.setIcon(get_icon("⚡"))
        quick_add_action.setShortcut("Ctrl+N")
        quick_add_action.setStatusTip(tr("menu.quick_add_tip"))
        quick_add_action.triggered.connect(self._show_quick_add)
        extras_menu.addAction(quick_add_action)

        search_action = QAction(tr("menu.search"), self)
        search_action.setIcon(get_icon("🔍"))
        search_action.setShortcut("Ctrl+F")
        search_action.setStatusTip(tr("menu.search_tip"))
        search_action.triggered.connect(self._show_global_search)
        extras_menu.addAction(search_action)

        extras_menu.addSeparator()

        category_manager_action = QAction(tr("menu.category_manager"), self)
        category_manager_action.setIcon(get_icon("📁"))
        category_manager_action.setShortcut("Ctrl+K")
        category_manager_action.setStatusTip(tr("menu.category_manager_tip"))
        category_manager_action.triggered.connect(self._show_category_manager)
        extras_menu.addAction(category_manager_action)

        tags_manager_action = QAction(tr("menu.tags_manager"), self)
        tags_manager_action.setIcon(get_icon("🏷️"))
        tags_manager_action.setShortcut("Ctrl+T")
        tags_manager_action.setStatusTip(tr("menu.tags_manager_tip"))
        tags_manager_action.triggered.connect(self._show_tags_manager)
        extras_menu.addAction(tags_manager_action)

        favorites_action = QAction(tr("menu.favorites"), self)
        favorites_action.setIcon(get_icon("⭐"))
        favorites_action.setShortcut("F12")
        favorites_action.setStatusTip(tr("menu.favorites_tip"))
        favorites_action.triggered.connect(self._show_favorites_dashboard)
        extras_menu.addAction(favorites_action)

        budget_warnings_action = QAction(tr("menu.budget_warnings"), self)
        budget_warnings_action.setIcon(get_icon("🚨"))
        budget_warnings_action.setShortcut("Ctrl+W")
        budget_warnings_action.setStatusTip(tr("menu.budget_warnings_tip"))
        budget_warnings_action.triggered.connect(lambda: self._check_budget_warnings())
        extras_menu.addAction(budget_warnings_action)

        extras_menu.addSeparator()

        updates_action = QAction(tr("menu.updates"), self)
        updates_action.setIcon(get_icon("⬆️"))
        updates_action.setShortcut("Ctrl+U")
        updates_action.setStatusTip(tr("menu.updates_tip"))
        updates_action.triggered.connect(self._show_update_dialog)
        extras_menu.addAction(updates_action)

        extras_menu.addSeparator()

        export_action = QAction(tr("menu.export"), self)
        export_action.setIcon(get_icon("📤"))
        export_action.setShortcut("Ctrl+E")
        export_action.setStatusTip(tr("menu.export_tip"))
        export_action.triggered.connect(self._show_export)
        extras_menu.addAction(export_action)

        extras_menu.addSeparator()

        savings_action = QAction(tr("menu.savings_goals"), self)
        savings_action.setIcon(get_icon("💰"))
        savings_action.triggered.connect(self._show_savings_goals)
        extras_menu.addAction(savings_action)

        backup_action = QAction(tr("menu.backup"), self)
        backup_action.setIcon(get_icon("💾"))
        backup_action.setStatusTip(tr("menu.backup_tip"))
        backup_action.triggered.connect(self._show_backup_restore)
        extras_menu.addAction(backup_action)

        db_manage_action = QAction(tr("menu.db_management"), self)
        db_manage_action.setIcon(get_icon("🗄️"))
        db_manage_action.triggered.connect(self._show_database_management)
        extras_menu.addAction(db_manage_action)

        extras_menu.addSeparator()

        current_year_action = QAction(tr("menu.current_year"), self)
        current_year_action.setShortcut("Ctrl+Y")
        current_year_action.triggered.connect(self._set_current_year)
        extras_menu.addAction(current_year_action)

        extras_menu.addSeparator()

        reset_tabs_action = QAction(tr("menu.reset_tab_order"), self)
        reset_tabs_action.setIcon(get_icon("🔄"))
        reset_tabs_action.triggered.connect(self._reset_tab_order)
        extras_menu.addAction(reset_tabs_action)

    def _create_account_menu(self, menubar: QMenuBar) -> None:
        """Konto-Menü (nur bei verschlüsseltem Login sichtbar)."""
        if not (self._active_user and self._user_model):
            return

        account_menu = menubar.addMenu(tr("menu.account"))

        account_manage_action = QAction(tr("menu.account_manage"), self)
        account_manage_action.setIcon(get_icon("👤"))
        account_manage_action.setStatusTip(tr("menu.account_manage_tip"))
        account_manage_action.triggered.connect(self._show_account_management)
        account_menu.addAction(account_manage_action)

        account_menu.addSeparator()

        sec_info = (f"{self._active_user.security_icon} "
                    f"{self._active_user.display_name} — "
                    f"{self._active_user.security_label}")
        info_action = QAction(sec_info, self)
        info_action.setEnabled(False)
        account_menu.addAction(info_action)
        self._account_info_action = info_action

    def _create_help_menu(self, menubar: QMenuBar) -> None:
        """Hilfe-Menü: Tastenkürzel, Setup-Assistent, Über."""
        help_menu = menubar.addMenu(tr("menu.help"))

        shortcuts_action = QAction(tr("menu.shortcuts"), self)
        shortcuts_action.setIcon(get_icon("⌨️"))
        shortcuts_action.setShortcut("F1")
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)

        setup_action = QAction(tr("menu.setup_assistant"), self)
        setup_action.setIcon(get_icon("🚀"))
        setup_action.triggered.connect(lambda: self._start_setup_assistant(force=True))
        help_menu.addAction(setup_action)

        help_menu.addSeparator()

        about_action = QAction(tr("menu.about"), self)
        about_action.setIcon(get_icon("ℹ️"))
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    
    def _setup_statusbar_info(self):
        """Zeigt dauerhaft an, welcher User/DB gerade aktiv ist.

        Das löst typische 'portable' Verwirrung: mehrere Ordner = mehrere data/.
        """
        try:
            sb = self.statusBar()

            self._status_user_label = QLabel()
            self._status_db_label = QLabel()
            self._status_user_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._status_db_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

            user_name = "(unverschlüsselt)"
            if self._active_user is not None:
                user_name = self._active_user.display_name or self._active_user.username

            if self._active_user is not None and getattr(self._active_user, "db_path", None):
                dbp = Path(self._active_user.db_path)
            else:
                try:
                    dbp = resolve_in_app(self.settings.database_path)
                except Exception:
                    dbp = Path("(unbekannt)")

            self._status_user_label.setText(f"User: {user_name}")
            self._status_db_label.setText(f"DB: {dbp}")

            sb.addPermanentWidget(self._status_user_label)
            sb.addPermanentWidget(self._status_db_label, 1)
        except Exception as e:
            logger.warning(tr("lbl.statusbarinfo_konnte_nicht_gesetzt"), e)

    def _open_data_folder(self):
        """Öffnet den aktuellen Datenordner im Dateimanager."""
        try:
            folder = data_dir()
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
            self.statusBar().showMessage(trf("lbl.datenordner_geoeffnet_folder"), 3000)
        except Exception as e:
            QMessageBox.warning(self, "Datenordner", trf("msg.datenordner_fehler"))
        

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
                name = "Kategorien (Experten)"
            self.tabs.addTab(widget, name)

    def _apply_tab_icons(self) -> None:
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if widget is self.categories_tab:
                self.tabs.setTabIcon(i, get_icon("📁"))
            elif widget is self.tracking_tab:
                self.tabs.setTabIcon(i, get_icon("📊"))
            else:
                self.tabs.setTabIcon(i, QIcon())
    
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
                
                self.tabs.insertTab(insert_at, self.categories_tab, "Kategorien (Experten)")
                self.tabs.setTabIcon(insert_at, get_icon("🛠️"))
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
                name = "Kategorien (Experten)"
            self.tabs.addTab(widget, name)
        self._apply_tab_icons()
        
        # Vorherigen Tab wiederherstellen
        if current_widget:
            index = self.tabs.indexOf(current_widget)
            if index >= 0:
                self.tabs.setCurrentIndex(index)
        
        # Speichern
        self.settings.tab_order = default_order
        self.statusBar().showMessage(tr("lbl.tabreihenfolge_zurueckgesetzt"), 2000)

    # ── Tab-Leiste Position & Sichtbarkeit ───────────────────────────

    _TAB_POS_MAP = {
        "north": QTabWidget.North,
        "south": QTabWidget.South,
        "east":  QTabWidget.East,
        "west":  QTabWidget.West,
    }

    def _apply_tab_position(self) -> None:
        """Setzt Tab-Position aus Settings."""
        pos_key = self.settings.get("tab_position", "west")
        qt_pos = self._TAB_POS_MAP.get(pos_key, QTabWidget.West)
        self.tabs.setTabPosition(qt_pos)

    def _apply_tab_bar_visibility(self) -> None:
        """Zeigt/versteckt die Tab-Leiste gemäß Settings."""
        visible = self.settings.get("tab_bar_visible", True)
        self.tabs.tabBar().setVisible(visible)

    def _on_tab_position_changed(self, pos_key: str) -> None:
        """Wird aufgerufen wenn Nutzer eine neue Tab-Position wählt."""
        self.settings.set("tab_position", pos_key)
        self.settings.save()
        self._apply_tab_position()

    def _on_tab_bar_show_toggled(self, visible: bool) -> None:
        """Zeigt/versteckt die Tab-Leiste."""
        self.settings.set("tab_bar_visible", visible)
        self.settings.save()
        self._apply_tab_bar_visibility()

    def _show_settings(self):
        """Zeigt Einstellungen-Dialog"""
        is_encrypted = hasattr(self, '_encrypted_session') and self._encrypted_session is not None
        dialog = SettingsDialog(
            self.settings,
            self,
            encrypted_mode=is_encrypted,
            encrypted_session=getattr(self, '_encrypted_session', None),
        )
        
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
            # Budgetübersicht: Monate für Vorschläge
            if "budget_suggestion_months" in new_settings:
                try:
                    self.settings.set("budget_suggestion_months", int(new_settings.get("budget_suggestion_months") or 3))
                except Exception:
                    self.settings.set("budget_suggestion_months", 3)

            # Budgetübersicht: Übertrag-Kumulation Start (Monat/Jahr)
            # BUGFIX: Diese Werte kamen zwar aus dem SettingsDialog, wurden aber nie persistiert.
            if "carryover_start_month" in new_settings:
                try:
                    m = int(new_settings.get("carryover_start_month") or 1)
                except Exception:
                    m = 1
                if m < 1:
                    m = 1
                if m > 12:
                    m = 12
                self.settings.set("carryover_start_month", m)

            if "carryover_start_year" in new_settings:
                try:
                    y = int(new_settings.get("carryover_start_year") or 0)
                except Exception:
                    y = 0
                # 0 ist bewusst erlaubt (= aktuelles Jahr). Wenn gesetzt, nicht clampen.
                self.settings.set("carryover_start_year", y)
            # Zusätzliche (neue) Einstellungen speichern
            # (Diese Keys sind rückwärtskompatibel – Tabs können sie später nutzen.)
            self.settings.set("show_onboarding", new_settings.get("show_onboarding", True))
            self.settings.set("remember_last_tab", new_settings.get("remember_last_tab", True))
            self.settings.set("remember_filters", new_settings.get("remember_filters", True))
            self.settings.set("language", new_settings.get("language", "Deutsch"))
            self.settings.set("currency", new_settings.get("currency", "CHF"))

            # Sprache & Währung sofort in den Modulen aktualisieren
            try:
                from utils.i18n import set_language
                from utils.money import set_currency
                set_language(new_settings.get("language", "Deutsch"))
                set_currency(new_settings.get("currency", "CHF"))
                # UI-Labels nach Sprachänderung aktualisieren
                self._retranslate_ui()
            except ImportError as e:
                logger.debug("from utils.i18n import set_language: %s", e)

            self.settings.set("warn_delete", new_settings.get("warn_delete", True))
            self.settings.set("warn_budget_overrun", new_settings.get("warn_budget_overrun", True))
            self.settings.set("table_density", new_settings.get("table_density", "Normal"))
            self.settings.set("highlight_fixcosts", new_settings.get("highlight_fixcosts", True))
            self.settings.set("auto_backup", new_settings.get("auto_backup", False))
            self.settings.set("backup_days", int(new_settings.get("backup_days", 30) or 30))
            self.settings.set("auto_backup_keep", int(new_settings.get("auto_backup_keep", 10) or 10))
            self.settings.set("backup_auto_delete", bool(new_settings.get("backup_auto_delete", False)))

            # Tastenkürzel speichern und neu laden
            shortcut_map = new_settings.get("shortcuts")
            if shortcut_map and isinstance(shortcut_map, dict):
                save_shortcuts(self.settings, shortcut_map)
                self._setup_shortcuts()  # Shortcuts sofort neu binden
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

            # Nach dem Speichern: Views neu laden, damit Änderungen (z.B.
            # Warnhinweise, Tab-Sichtbarkeit, Dichte, etc.) sofort wirken.
            self._refresh_all_tabs()
            
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
        except Exception as e:
            logger.debug("if hasattr(self, 'tracking_tab') and hasattr(self.: %s", e)

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
        add_action = QAction(tr("btn.neu_hinzufuegen"), self)
        add_action.setShortcut("Insert")
        add_action.triggered.connect(self._edit_add)
        self.edit_menu.addAction(add_action)
        self._edit_actions_general.append(add_action)
        
        # Bearbeiten
        edit_action = QAction("&Bearbeiten...", self)
        edit_action.setIcon(get_icon("✏️"))
        edit_action.setShortcut("F2")
        edit_action.triggered.connect(self._edit_edit)
        self.edit_menu.addAction(edit_action)
        self._edit_actions_general.append(edit_action)
        
        # Löschen
        delete_action = QAction(tr("btn.loeschen"), self)
        delete_action.setShortcut("Delete")
        delete_action.triggered.connect(self._edit_delete)
        self.edit_menu.addAction(delete_action)
        self._edit_actions_general.append(delete_action)
        
        self.edit_menu.addSeparator()
        
        # === BUDGET-TAB AKTIONEN ===
        self._edit_actions_budget = []
        
        budget_entry_action = QAction("Budget &erfassen...", self)
        budget_entry_action.setIcon(get_icon("📝"))
        budget_entry_action.triggered.connect(self._budget_entry)
        self.edit_menu.addAction(budget_entry_action)
        self._edit_actions_budget.append(budget_entry_action)
        
        budget_edit_action = QAction("Budget &bearbeiten...", self)
        budget_edit_action.setIcon(get_icon("✏️"))
        budget_edit_action.triggered.connect(self._budget_edit)
        self.edit_menu.addAction(budget_edit_action)
        self._edit_actions_budget.append(budget_edit_action)
        
        self.edit_menu.addSeparator()
        
        budget_seed_action = QAction("Zeilen aus &Kategorien erzeugen", self)
        budget_seed_action.setIcon(get_icon("🌱"))
        budget_seed_action.triggered.connect(self._budget_seed)
        self.edit_menu.addAction(budget_seed_action)
        self._edit_actions_budget.append(budget_seed_action)
        
        budget_copy_action = QAction("Jahr &kopieren...", self)
        budget_copy_action.setIcon(get_icon("📋"))
        budget_copy_action.triggered.connect(self._budget_copy_year)
        self.edit_menu.addAction(budget_copy_action)
        self._edit_actions_budget.append(budget_copy_action)
        
        self.edit_menu.addSeparator()
        
        budget_remove_row_action = QAction("Budget-&Zeile entfernen", self)
        budget_remove_row_action.setIcon(get_icon("🗑️"))
        budget_remove_row_action.triggered.connect(self._budget_remove_row)
        self.edit_menu.addAction(budget_remove_row_action)
        self._edit_actions_budget.append(budget_remove_row_action)
        
        budget_remove_cat_action = QAction(tr("btn.kategorie_loeschen_global"), self)
        budget_remove_cat_action.triggered.connect(self._budget_remove_category)
        self.edit_menu.addAction(budget_remove_cat_action)
        self._edit_actions_budget.append(budget_remove_cat_action)
        
        # === KATEGORIEN-TAB AKTIONEN ===
        self._edit_actions_categories = []
        
        cat_new_main_action = QAction("Neue &Hauptkategorie...", self)
        cat_new_main_action.setIcon(get_icon("📁"))
        cat_new_main_action.triggered.connect(self._categories_new_main)
        self.edit_menu.addAction(cat_new_main_action)
        self._edit_actions_categories.append(cat_new_main_action)
        
        cat_new_sub_action = QAction("Neue &Unterkategorie...", self)
        cat_new_sub_action.setIcon(get_icon("📂"))
        cat_new_sub_action.triggered.connect(self._categories_new_sub)
        self.edit_menu.addAction(cat_new_sub_action)
        self._edit_actions_categories.append(cat_new_sub_action)
        
        cat_delete_action = QAction(tr("btn.auswahl_loeschen"), self)
        cat_delete_action.triggered.connect(self._categories_delete)
        self.edit_menu.addAction(cat_delete_action)
        self._edit_actions_categories.append(cat_delete_action)
        
        self.edit_menu.addSeparator()
        
        cat_mass_edit_action = QAction("&Massenbearbeitung...", self)
        cat_mass_edit_action.setIcon(get_icon("✏️"))
        cat_mass_edit_action.setStatusTip(tr("lbl.flags_fuer_mehrere_kategorien"))
        cat_mass_edit_action.triggered.connect(self._categories_mass_edit)
        self.edit_menu.addAction(cat_mass_edit_action)
        self._edit_actions_categories.append(cat_mass_edit_action)
        
        # === TRACKING-TAB AKTIONEN ===
        self._edit_actions_tracking = []
        
        self.edit_menu.addSeparator()
        
        fix_action = QAction("&Fixkosten buchen...", self)
        fix_action.setIcon(get_icon("📅"))
        fix_action.setShortcut("Ctrl+Shift+F")
        fix_action.triggered.connect(self._tracking_add_fixcosts)
        self.edit_menu.addAction(fix_action)
        self._edit_actions_tracking.append(fix_action)
        
        # === ÜBERSICHT-TAB AKTIONEN ===
        self._edit_actions_overview = []
        
        refresh_overview_action = QAction("Daten &aktualisieren", self)
        refresh_overview_action.setIcon(get_icon("🔄"))
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

        # WICHTIG: Daten/Ansicht immer frisch halten.
        # Hintergrund: z.B. Budgetwarnungen/Übersicht wurden sonst erst nach
        # Neustart oder manuellem Refresh aktualisiert.
        self._refresh_current_tab_safe()

    def _refresh_current_tab_safe(self) -> None:
        """Aktualisiert den aktuell sichtbaren Tab (robust, ohne UI-Crash)."""
        try:
            tab = self.tabs.currentWidget()
            self._refresh_tab_widget(tab)
        except Exception:
            import traceback
            traceback.print_exc()

    def _refresh_tab_widget(self, tab) -> None:
        """Versucht verschiedene Refresh-Methoden (Abwärtskompatibel)."""
        if tab is None:
            return

        # Reihenfolge: refresh() -> refresh_data() -> load()
        if hasattr(tab, 'refresh') and callable(getattr(tab, 'refresh')):
            tab.refresh()
            return
        if hasattr(tab, 'refresh_data') and callable(getattr(tab, 'refresh_data')):
            tab.refresh_data()
            return
        if hasattr(tab, 'load') and callable(getattr(tab, 'load')):
            tab.load()
            return



    
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
    
    def _overview_refresh(self):
        """Übersicht: Daten aktualisieren"""
        if hasattr(self.overview_tab, 'refresh_data'):
            self.overview_tab.refresh_data()
        elif hasattr(self.overview_tab, 'refresh'):
            self.overview_tab.refresh()

    def _open_budget_editor_from_overview(self, typ: str, category: str, year: int, month: int) -> None:
        """Springt von der Übersicht direkt in den Budget-Editor der gewählten Kategorie."""
        try:
            self._goto_tab(self.budget_tab)
            if hasattr(self.budget_tab, "focus_budget_entry"):
                found = self.budget_tab.focus_budget_entry(
                    typ=typ,
                    category=category,
                    year=int(year),
                    month=int(month),
                    open_dialog=True,
                )
                if not found and self.statusBar():
                    self.statusBar().showMessage(
                        f"Kategorie nicht gefunden: {category} ({typ})",
                        3000,
                    )
        except Exception as e:
            logger.debug("_open_budget_editor_from_overview: %s", e)

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
            self.statusBar().showMessage(tr("lbl.mindestens_ein_uebersichtreiter_muss"), 3000)
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
            self._update_undo_redo_actions()
        except Exception as e:
            logger.error("Budget speichern fehlgeschlagen: %s", e, exc_info=True)
            QMessageBox.warning(self, "Hinweis", trf("msg.fehler_beim_speichern_e", e=str(e)))

    def _refresh_current_tab(self):
        """Aktualisiert den aktuellen Tab"""
        current_widget = self.tabs.currentWidget()
        
        if hasattr(current_widget, 'refresh'):
            current_widget.refresh()
            self.statusBar().showMessage("Ansicht aktualisiert", 2000)
        elif hasattr(current_widget, 'load'):
            current_widget.load()
            self.statusBar().showMessage("Ansicht aktualisiert", 2000)
    

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
        if hasattr(self.overview_tab, 'year_combo'):
            for i in range(self.overview_tab.year_combo.count()):
                if self.overview_tab.year_combo.itemText(i) == str(current_year):
                    self.overview_tab.year_combo.setCurrentIndex(i)
                    break
        
        self.statusBar().showMessage(f"Jahr {current_year} geladen", 2000)

    def _show_db_info(self):
        """Zeigt Datenbank-Informationen und Migrations-Status"""
        from model.migrations import get_migration_info, CURRENT_VERSION
        import os
        from pathlib import Path
        from model.app_paths import resolve_in_app
        
        try:
            # Aktive DB-Datei (für Anzeige & Größe)
            encrypted_session = getattr(self, "_encrypted_session", None)
            if encrypted_session is not None:
                active_file = Path(encrypted_session.enc_path)
            else:
                active_file = resolve_in_app(self.settings.database_path)

            # Migrations-Info
            migration_info = get_migration_info(self.conn)

            # Statistiken via Model (kein raw SQL in View)
            from model.database_management_model import DatabaseManagementModel
            db_stats = DatabaseManagementModel(
                str(active_file), conn=self.conn
            ).get_database_statistics()

            db_size = db_stats.get('db_size_kb', 0)
            tables = db_stats.get('tables', [])
            budget_count = db_stats.get(tr("lbl.budgeteintraege"), 0)
            tracking_count = db_stats.get('Buchungen', 0)
            category_count = db_stats.get(tr("tab.categories"), 0)
            savings_count = db_stats.get(tr("dlg.savings_goals"), 0)
            years_b = [str(y) for y in db_stats.get('years_budget', [])]
            years_t = [str(y) for y in db_stats.get('years_tracking', [])]
            
            # Dialog aufbauen
            info = f"""<h3>Datenbank-Informationen</h3>
            
<p><b>Datei:</b> {active_file.name}<br>
<b>Pfad:</b> {active_file}<br>
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
            msg.setWindowTitle(tr("dlg.db_info"))
            msg.setTextFormat(Qt.RichText)
            msg.setText(info)
            msg.exec()
            
        except Exception as e:
            QMessageBox.warning(self, "Hinweis", trf("msg.fehler_beim_laden_der"))

    def _show_about(self):
        """Zeigt Über-Dialog"""
        dialog = AboutDialog(self)
        dialog.exec()

    def _show_account_management(self):
        """Zeigt den Kontoverwaltungs-Dialog."""
        if not self._active_user or not self._user_model:
            QMessageBox.information(
                self, "Info",
                "Kontoverwaltung ist nur bei verschlüsselten Konten verfügbar."
            )
            return

        # Restore-Key / DB-Key für den aktiven User (wichtig auch im Quick-Modus).
        # Der Key steckt in der EncryptedSession, nicht zwingend im User-Objekt.
        db_key = None
        encrypted_session = getattr(self, "_encrypted_session", None)
        if encrypted_session is not None:
            try:
                db_key = encrypted_session.db_key
            except Exception:
                db_key = None

        dlg = AccountManagementDialog(
            self,
            user=self._active_user,
            user_model=self._user_model,
            db_key=db_key,
        )

        # Bei Namensänderung: Fenstertitel aktualisieren
        dlg.display_name_changed.connect(self._on_display_name_changed)
        # Bei Sicherheitsstufen-Wechsel: Titel + Menü aktualisieren
        dlg.security_changed.connect(self._on_security_changed)

        dlg.exec()

    def _on_display_name_changed(self, new_name: str):
        """Aktualisiert den Fenstertitel nach Namensänderung."""
        if self._active_user:
            icon = self._active_user.security_icon
            base = app_window_title()
            self.setWindowTitle(f"{base} — {icon} {new_name}")
            # Konto-Menü Info aktualisieren
            if hasattr(self, '_account_info_action'):
                self._account_info_action.setText(
                    f"{icon} {new_name} — {self._active_user.security_label}"
                )
            self.statusBar().showMessage(trf("lbl.anzeigename_geaendert_new_name"), 3000)

    def _on_security_changed(self, new_security: str):
        """Aktualisiert den Fenstertitel nach Sicherheitsstufen-Wechsel."""
        if self._active_user:
            icon = self._active_user.security_icon
            name = self._active_user.display_name
            base = app_window_title()
            self.setWindowTitle(f"{base} — {icon} {name}")
            # Konto-Menü Info aktualisieren
            if hasattr(self, '_account_info_action'):
                self._account_info_action.setText(
                    f"{icon} {name} — {self._active_user.security_label}"
                )
            self.statusBar().showMessage(
                trf("lbl.sicherheitsstufe_geaendert_self_active_usersecurity_label"), 3000
            )
    
    def _show_shortcuts(self):
        """Zeigt Tastenkürzel-Übersicht (F1)"""
        dialog = ShortcutsDialog(self, settings=self.settings)
        dialog.exec()
    
    def _show_quick_add(self):
        """Zeigt Schnelleingabe-Dialog (Strg+N)"""
        dialog = QuickAddDialog(self.conn, self)
        if dialog.exec() == QDialog.Accepted:
            # Tracking-Tab aktualisieren
            if hasattr(self.tracking_tab, 'refresh'):
                self.tracking_tab.refresh()
            self.statusBar().showMessage(tr("lbl.eintrag_hinzugefuegt"), 2000)
    
    def _show_global_search(self):
        """Zeigt Globale Suche (Strg+F)"""
        dialog = GlobalSearchDialog(self.conn, self)
        if dialog.exec() and dialog.selected_result:
            tab_key = dialog.selected_result.get("tab")
            tab_map = {
                "budget": self.budget_tab,
                "tracking": self.tracking_tab,
                "categories": self.categories_tab,
            }
            widget = tab_map.get(tab_key)
            if widget:
                self._goto_tab(widget)
    
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
    
    def _check_auto_backup(self):
        """Prüft ob ein automatisches Backup fällig ist und erstellt es ggf."""
        try:
            if not self.settings.get("auto_backup", False):
                return

            from datetime import datetime, timedelta
            from model.app_paths import resolve_in_app
            from model.restore_bundle import create_bundle
            from app_info import APP_NAME, APP_VERSION

            backup_dir = resolve_in_app(
                self.settings.get("backup_directory", "data/backups")
            )

            backup_days = int(self.settings.get("backup_days", 30) or 30)
            last_backup_str = self.settings.get("last_auto_backup", "")

            # Prüfe ob Intervall abgelaufen
            needs_backup = True
            if last_backup_str:
                try:
                    last_backup_dt = datetime.fromisoformat(last_backup_str)
                    if datetime.now() - last_backup_dt < timedelta(days=backup_days):
                        needs_backup = False
                except (ValueError, TypeError):
                    needs_backup = True  # Ungültiges Datum → Backup erstellen

            if needs_backup:
                encrypted_session = getattr(self, "_encrypted_session", None)

                # Backup erstellen (als Restore-Bundle .bmr)
                if encrypted_session is not None:
                    try:
                        encrypted_session.save()
                    except Exception as e:
                        logger.debug("%s", e)
                    src_db = Path(encrypted_session.enc_path)
                else:
                    src_db = resolve_in_app(self.settings.database_path)

                if src_db.exists():
                    backup_dir.mkdir(parents=True, exist_ok=True)

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_name = f"budgetmanager_backup_auto_{timestamp}.bmr"
                    backup_path = backup_dir / backup_name

                    from model.app_paths import settings_path as _get_settings_path
                    from model.user_model import _users_file_path as _get_users_path
                    _s_path = _get_settings_path()
                    _u_path = _get_users_path()
                    create_bundle(
                        source_db=src_db,
                        out_path=backup_path,
                        app=APP_NAME,
                        app_version=APP_VERSION,
                        note="AutoBackup",
                        settings_path=_s_path if _s_path.exists() else None,
                        users_json_path=_u_path if _u_path.exists() else None,
                    )

                    self.settings.set("last_auto_backup", datetime.now().isoformat())
                    logger.info("Auto-Backup erstellt: %s", backup_name)
                    self.statusBar().showMessage(f"Auto-Backup erstellt: {backup_name}", 5000)

            # Alte Backups immer bereinigen (auch wenn kein neues Backup nötig)
            if backup_dir.exists():
                keep_n = int(self.settings.get("auto_backup_keep", 10) or 10)
                keep_n = max(3, min(200, keep_n))
                all_backups = sorted(
                    backup_dir.glob("budgetmanager_backup_*.bmr"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                for old in all_backups[keep_n:]:
                    try:
                        old.unlink()
                        logger.debug("Altes Backup gelöscht: %s", old.name)
                    except Exception as e:
                        logger.debug("%s", e)

        except Exception as exc:
            logger.warning("Auto-Backup fehlgeschlagen: %s", exc)

    def _show_backup_restore(self):
        """Zeigt Backup & Restore Dialog (NEU v0.16)"""
        encrypted_session = getattr(self, "_encrypted_session", None)
        db_path = None
        if encrypted_session is None:
            db_path = str(resolve_in_app(self.settings.database_path))
        dialog = BackupRestoreDialog(
            self, self.conn, db_path, self.settings,
            encrypted_session=encrypted_session,
            active_user=self._active_user,
        )
        result = dialog.exec()
        # Nur dann Neustart verlangen, wenn die aktive DB wirklich ersetzt wurde
        if result == QDialog.Accepted and getattr(dialog, "db_changed", False) and not getattr(dialog, "exit_requested", False):
            QMessageBox.information(
                self,
                "Neustart erforderlich",
                "Bitte starten Sie die Anwendung neu, um die Änderungen zu übernehmen."
            )
    
    def _show_database_management(self):
        """Zeigt den Datenbank-Verwaltungsdialog (Statistiken, Reset, Bereinigung)"""
        from views.database_management_dialog import DatabaseManagementDialog

        # In verschlüsseltem Modus existiert keine "budgetmanager.db" auf Disk.
        # Daher immer den aktiven Dateipfad anzeigen (enc) – oder bei unverschlüsselt den db-Pfad.
        encrypted_session = getattr(self, "_encrypted_session", None)
        if encrypted_session is not None:
            db_path = str(Path(encrypted_session.enc_path))
        else:
            db_path = str(resolve_in_app(self.settings.database_path))

        dialog = DatabaseManagementDialog(db_path, parent=self, conn=self.conn)
        result = dialog.exec()

        # Nach Änderungen (Reset/Bereinigung): Encrypted Session auf Disk schreiben + Tabs refreshen
        if result == QDialog.Accepted or getattr(dialog, "data_changed", False):
            if encrypted_session is not None:
                try:
                    encrypted_session.save()
                except Exception as _e:
                    logger.warning("encrypted_session.save nach DB-Reset fehlgeschlagen: %s", _e)
            self._refresh_all_tabs()
            self.statusBar().showMessage(tr("lbl.datenbankaenderungen_uebernommen"), 3000)
    
    def _show_category_manager(self):
        """Zeigt den Kategorien-Manager-Dialog (NEU v2.2.0)"""
        dialog = CategoryManagerDialog(self, conn=self.conn)
        dialog.categories_changed.connect(self._refresh_current_tab)
        dialog.exec()
        # Nach Schließen: Alle Tabs aktualisieren
        self._refresh_all_tabs()

    def _show_tags_manager(self):
        """Öffnet den Tags-Manager (v2.4.0)"""
        dialog = TagsManagerDialog(self.conn, self)
        dialog.exec()

    def _show_favorites_dashboard(self):
        """Öffnet das Favoriten-Dashboard (v2.4.0)"""
        # Jahr/Monat aus Budget-Tab wenn vorhanden, sonst heute
        try:
            year = int(self.budget_tab.year_spin.value()) if hasattr(self.budget_tab, "year_spin") else None
        except Exception:
            year = None
        from datetime import date as _date
        if year is None:
            year = _date.today().year
        month = _date.today().month
        dialog = FavoritesDashboardDialog(self.conn, current_year=year, current_month=month, parent=self)
        dialog.exec()


    def _retranslate_ui(self) -> None:
        """Aktualisiert alle UI-Labels nach einer Sprachänderung."""
        from utils.i18n import tr
        # Tab-Labels aktualisieren
        self._tab_definitions = {
            0: (self.budget_tab, tr("tab.budget")),
            1: (self.categories_tab, tr("tab.categories")),
            2: (self.tracking_tab, tr("tab.tracking")),
            3: (self.overview_tab, tr("tab.overview")),
        }
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            for tab_id, (tab_widget, label) in self._tab_definitions.items():
                if widget is tab_widget:
                    self.tabs.setTabText(i, label)
                    break
        self._apply_tab_icons()
        # Menü-Einträge aktualisieren
        try:
            self._setup_menus()
        except Exception as e:
            logger.debug("_retranslate_ui menu rebuild: %s", e)
        # Status-Bar
        self.statusBar().showMessage(tr("msg.language_changed"), 2000)

    def _check_budget_warnings(self, year: int | None = None, month: int | None = None):
        """Prüft Budgetwarnungen und zeigt Anpassungsdialog (v2.4.0)"""
        from datetime import date
        from PySide6.QtWidgets import QMessageBox
        # Jahr/Monat möglichst aus der UI ableiten, damit "Extras → Budgetwarnungen"
        # dasselbe zeigt wie die Übersicht (kein "nur über Klick in Übersicht").
        try:
            if year is None and hasattr(self.overview_tab, 'year_combo'):
                year = int(self.overview_tab.year_combo.currentText())
        except Exception:
            year = None
        try:
            if month is None and hasattr(self.overview_tab, 'month_combo'):
                idx = int(self.overview_tab.month_combo.currentIndex())
                # idx==0 ist "Gesamt" → dann nehmen wir den aktuellen Monat
                month = date.today().month if idx == 0 else idx
        except Exception:
            month = None

        # Fallback: Budget-Tab Jahr, sonst heute
        try:
            if year is None:
                year = int(self.budget_tab.year_spin.value()) if hasattr(self.budget_tab, "year_spin") else date.today().year
        except Exception:
            year = date.today().year
        if month is None:
            month = date.today().month

        # Lookback identisch zur Einstellung, damit "keine Auffälligkeiten" nicht
        # fälschlich erscheint, obwohl der Dialog später Vorschläge hätte.
        try:
            lookback = int(self.settings.get('budget_suggestion_months', 3) or 3)
        except Exception:
            lookback = 3

        warnings_model = BudgetWarningsModelExtended(self.conn)
        # Kein vorzeitiger Abbruch: BudgetAdjustmentDialog nutzt BudgetOverviewModel
        # als Primärquelle und findet ggf. Vorschläge auch ohne gespeicherte Warnregeln.
        # Der Dialog zeigt selbst eine Meldung wenn nichts gefunden wird.

        # BudgetModel für Vorschläge (Fallback, falls Tab kein Modell exposed)
        budget_model = getattr(self.budget_tab, "model", None)
        if budget_model is None:
            try:
                from model.budget_model import BudgetModel
                budget_model = BudgetModel(self.conn)
            except Exception:
                budget_model = None

        dlg = BudgetAdjustmentDialog(self, warnings_model, budget_model, year, month)
        dlg.exec()

    def _check_budget_warnings_from_overview(self):
        """Öffnet Budgetwarner mit Jahr/Monat aus der Übersicht."""
        from datetime import date
        year = None
        month = None
        try:
            if hasattr(self.overview_tab, 'year_combo'):
                year = int(self.overview_tab.year_combo.currentText())
        except Exception:
            year = None
        try:
            if hasattr(self.overview_tab, 'month_combo'):
                idx = int(self.overview_tab.month_combo.currentIndex())
                month = date.today().month if idx == 0 else idx
        except Exception:
            month = None
        self._check_budget_warnings(year=year, month=month)

    def _show_update_dialog(self):
        """Öffnet den Portable-Updater Dialog (still)"""
        dialog = UpdateDialog(self)
        dialog.exec()

    def _refresh_all_tabs(self):
        """Aktualisiert alle Tabs nach Änderungen.

        Wichtig: Tabs implementieren nicht einheitlich `load()`.
        Für Stabilität bevorzugen wir `refresh()` und fallen auf `load()` zurück.
        """
        try:
            for tab in [self.budget_tab, self.categories_tab, self.tracking_tab, self.overview_tab]:
                self._refresh_tab_widget(tab)
        except Exception:
            # Refresh darf nie die UI killen, aber wir wollen wenigstens eine Spur im Terminal.
            import traceback
            traceback.print_exc()
    
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
            except Exception as e:
                logger.warning(tr("btn.budget_tabsave_beim_schliessen_fehlgeschlagen"), e)
            self._save_encrypted_session()
            event.accept()
            return
        
        # Wenn Auto-Save nicht aktiv: Einmal fragen ob gespeichert werden soll
        reply = QMessageBox.question(
            self,
            "Beenden",
            tr("btn.moechten_sie_das_budget"),
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save
        )
        
        if reply == QMessageBox.Save:
            try:
                self.budget_tab.save()
            except Exception as e:
                logger.debug("self.budget_tab.save(): %s", e)
            self._save_encrypted_session()
            event.accept()
        elif reply == QMessageBox.Discard:
            event.accept()
        else:  # Cancel
            event.ignore()

    def _save_encrypted_session(self):
        """Speichert verschlüsselte DB-Session falls vorhanden."""
        session = getattr(self, '_encrypted_session', None)
        if session:
            try:
                session.save()
            except Exception as e:
                logger.error(tr("msg.fehler_beim_speichern_der"), e)

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
            QMessageBox.critical(self, "Fehler", trf("msg.setup_assistent_fehler"))
