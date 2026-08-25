from __future__ import annotations

import logging
import os
import sqlite3
from datetime import date
from pathlib import Path

from PySide6.QtCore import QPoint, QProcess, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QDesktopServices,
    QGuiApplication,
    QIcon,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app_info import APP_NAME, app_version_label, app_window_title
from model.app_paths import (
    configured_backups_dir,
    configured_db_path,
    data_dir,
)
from model.budget_warnings_model_extended import BudgetWarningsModelExtended
from model.category_model import CategoryModel
from model.shortcuts_config import default_key, load_shortcuts
from model.undo_redo_model import UndoRedoModel
from settings import Settings
from theme_manager import ThemeManager
from utils.defensive_log import uebersprungen as _uebersprungen
from utils.i18n import display_security_label, tr, trf
from utils.icons import get_icon
from utils.notifications import show_info, show_warning
from views.account_management_dialog import AccountManagementDialog
from views.backup_restore_dialog import BackupRestoreDialog
from views.budget_adjustment_dialog import BudgetAdjustmentDialog
from views.category_manager_dialog import CategoryManagerDialog
from views.export_dialog import ExportDialog
from views.favorites_dashboard_dialog import FavoritesDashboardDialog
from views.global_search_dialog import GlobalSearchDialog
from views.help_launcher import (
    help_file_candidates,
    install_help_corner_button,
    open_help_file,
)
from views.help_menu import build_help_menu
from views.lifeplanner_import_dialog import LifePlannerImportDialog
from views.main_window_diagnostics import (
    create_diagnostic_report,
    open_diagnostics_folder,
    show_app_log,
    show_crash_log,
    show_log_file,
)
from views.main_window_dialogs import AboutDialog
from views.main_window_update import MainWindowUpdateMixin
from views.quick_add_dialog import QuickAddDialog
from views.savings_goals_dialog import SavingsGoalsDialog
from views.shortcuts_dialog import ShortcutsDialog
from views.tabs.budget_tab import BudgetTab
from views.tabs.categories_tab import CategoriesTab
from views.tabs.cockpit_tab import CockpitTab
from views.tabs.overview_savings_panel import OverviewSavingsPanel
from views.tabs.overview_tab import OverviewTab
from views.tabs.tracking_tab import TrackingTab
from views.tags_manager_dialog import TagsManagerDialog

logger = logging.getLogger(__name__)


class MainWindow(MainWindowUpdateMixin, QMainWindow):
    def __init__(self, conn: sqlite3.Connection, *, active_user=None, user_model=None):
        super().__init__()
        self.conn = conn
        self._active_user = (
            active_user  # User-Objekt (oder None bei unverschlüsselter DB)
        )
        self._user_model = user_model  # UserModel (oder None)
        self.setWindowTitle(app_window_title())

        # Einstellungen laden
        self.settings = Settings()
        self._startup_update_proc: QProcess | None = None
        self._startup_update_prompt_shown = False
        # Start-Auto-Backup und Setup-Abschluss laufen bewusst ueber
        # parent-gebundene QTimer. Native Qt-Dialoge duerfen waehrend ihres
        # finished-/closeEvent-Stacks weder schwere I/O-Arbeit starten noch ihre
        # letzte Python-Referenz verlieren (PySide/Shiboken-Segfaultschutz).
        self._startup_auto_backup_timer: QTimer | None = None
        self._setup_assistant_finalize_timer: QTimer | None = None
        self._setup_assistant_finish_pending = False
        # Qt/PySide Crashschutz: Voll-Refreshes werden nach Dialog-/Menüaktionen
        # verzögert ausgeführt. Direktes Rebuild von QTableWidget-Inhalten im
        # QAction-/Dialog-Stack kann unter PySide6/Qt6 native Shiboken-Abbrüche
        # auslösen, obwohl Python selbst keine Exception wirft.
        self._refresh_all_tabs_pending = False
        self._refresh_all_tabs_running = False

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
        self.cockpit_tab = CockpitTab(conn, settings=self.settings)
        self.budget_tab = BudgetTab(conn)
        self.categories_tab = CategoriesTab(conn)
        self.tracking_tab = TrackingTab(conn, settings=self.settings)
        self.overview_tab = OverviewTab(conn, settings=self.settings)
        self.savings_tab = OverviewSavingsPanel(conn)

        # Reiter „Konto" – zentraler Hub (Konto, Speicherort, Backup, Zurücksetzen).
        # encrypted_mode anhand des aktiven Users (verschlüsselter Login).
        from views.account_data_hub import AccountDataHub

        self.account_tab = AccountDataHub(
            self.settings,
            self,
            encrypted_mode=(self._active_user is not None),
        )

        # Schnelleingabe-Signals von Tabs verbinden
        self.cockpit_tab.quick_add_requested.connect(self._show_quick_add)
        self.cockpit_tab.fixcost_requested.connect(self._tracking_add_fixcosts)
        self.cockpit_tab.favorites_requested.connect(self._show_favorites_dashboard)
        self.cockpit_tab.savings_requested.connect(self._show_savings_goals)
        self.cockpit_tab.goto_budget_requested.connect(
            lambda: self._goto_tab(self.budget_tab)
        )
        self.cockpit_tab.goto_tracking_requested.connect(
            lambda: self._goto_tab(self.tracking_tab)
        )
        self.cockpit_tab.goto_overview_requested.connect(
            lambda: self._goto_tab(self.overview_tab)
        )
        self.cockpit_tab.goto_savings_requested.connect(
            lambda: self._goto_tab(self.savings_tab)
        )
        self.cockpit_tab.budget_warnings_requested.connect(
            lambda: self._check_budget_warnings()
        )
        self.budget_tab.quick_add_requested.connect(self._show_quick_add)
        self.budget_tab.savings_goals_requested.connect(self._show_savings_goals)
        self.categories_tab.quick_add_requested.connect(self._show_quick_add)
        self.overview_tab.quick_add_requested.connect(self._show_quick_add)

        # "Vorschläge"-Button in der Übersicht soll den Budgetwarner öffnen
        try:
            self.overview_tab.budget_warnings_requested.connect(
                self._check_budget_warnings_from_overview
            )
        except Exception as e:
            logger.debug("%s", e)
        try:
            self.overview_tab.budget_edit_requested.connect(
                self._open_budget_editor_from_overview
            )
        except Exception as e:
            logger.debug("%s", e)

        # Settings-Checkboxen mit Settings synchronisieren
        if hasattr(self.budget_tab, "chk_autosave"):
            self.budget_tab.chk_autosave.toggled.connect(self._on_autosave_changed)
        if hasattr(self.budget_tab, "chk_ask_due"):
            self.budget_tab.chk_ask_due.toggled.connect(self._on_ask_due_changed)
        if hasattr(self.budget_tab, "budget_data_changed"):
            self.budget_tab.budget_data_changed.connect(self._update_undo_redo_actions)

        # Tab-Definitionen (Index -> Widget, Name)
        # Tab-Labels: keys statt eingefrorenem tr()-String (fuer retranslate_ui)
        self._tab_label_keys = {
            5: ("tr", "tab.cockpit"),
            0: ("tr", "tab.budget"),
            1: ("tr", "tab.categories"),
            2: ("tr", "tab.tracking"),
            3: ("tr", "tab.overview"),
            4: ("tr", "tab.savings"),
            6: ("tr", "tab.account"),
        }
        self._tab_definitions = {
            5: (self.cockpit_tab, tr("tab.cockpit")),
            0: (self.budget_tab, tr("tab.budget")),
            1: (self.categories_tab, tr("tab.categories")),
            2: (self.tracking_tab, tr("tab.tracking")),
            3: (self.overview_tab, tr("tab.overview")),
            4: (self.savings_tab, tr("tab.savings")),
            6: (self.account_tab, tr("tab.account")),
        }
        self._tab_visibility_keys = {
            5: "cockpit",
            0: "budget",
            1: "categories",
            2: "tracking",
            3: "overview",
            4: "savings",
            6: "account",
        }

        # Tabs in gespeicherter Reihenfolge hinzufügen
        self._load_tab_order()
        self._apply_tab_icons()

        self._build_modern_shell()

        # Tab-Wechsel Signal verbinden (für dynamisches Bearbeiten-Menü).
        # _last_tab_widget erlaubt Speichern BEVOR der alte Tab verlassen wird.
        self._last_tab_widget = self.tabs.currentWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Fenster-Geometrie und -Status wiederherstellen
        self._restore_window_state()

        # v2.2.0: Cockpit als Startseite – unabhängig vom zuletzt offenen Tab
        # startet das Programm auf dem Cockpit (abschaltbar via Einstellung).
        try:
            if bool(self.settings.get("start_on_cockpit", True)):
                idx = self.tabs.indexOf(self.cockpit_tab)
                if idx >= 0:
                    self.tabs.setCurrentIndex(idx)
        except Exception as e:
            logger.debug("start_on_cockpit: %s", e)

        # Menü erstellen
        self._create_menu()
        self._create_unified_action_toolbar()
        self._watch_system_color_scheme()
        self._reduce_duplicate_quick_actions()
        self._install_edit_context_menus()

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

        # LifePlanner-Bridge erst nach vollständigem UI-Aufbau prüfen.
        # Es wird ausschließlich ein Zähler angezeigt; nie automatisch gebucht.
        QTimer.singleShot(500, self._update_lifeplanner_import_badge)

        # Einmal beim Start herausschreiben. Damit ist die Brücke aktuell,
        # sobald BudgetManager läuft - auch wenn zuletzt außerhalb der
        # Oberfläche etwas geändert wurde oder ein Lauf ohne sauberes Beenden
        # endete.
        QTimer.singleShot(1500, self._sync_bridge_outboxes_safely)

        # Auto-Backup wird via QTimer.singleShot aus main.py gestartet,
        # damit _encrypted_session korrekt gesetzt ist.

    def _build_modern_shell(self) -> None:
        """Baut die moderne Seitenleisten-Navigation um die bestehenden Tabs.

        Die fachlichen Reiter bleiben unverändert. Nur ihre Navigation wird in
        eine feste, beschriftete Seitenleiste verlegt. Dadurch bleiben Modelle,
        Signale und Controller kompatibel, während die Oberfläche wesentlich
        ruhiger und eindeutiger wird.
        """
        shell = QWidget(self)
        shell.setObjectName("modernShell")
        layout = QHBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame(shell)
        sidebar.setObjectName("mainSidebar")
        sidebar.setMinimumWidth(188)
        sidebar.setMaximumWidth(228)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(12, 14, 12, 12)
        side.setSpacing(6)

        brand = QLabel(APP_NAME, sidebar)
        brand.setObjectName("sidebarBrand")
        brand.setMinimumHeight(38)
        side.addWidget(brand)

        self._sidebar_group = QButtonGroup(self)
        self._sidebar_group.setExclusive(True)
        self._sidebar_buttons = {}

        navigation = [
            (self.cockpit_tab, "🏠", tr("tab.cockpit")),
            (self.tracking_tab, "💳", tr("tab.tracking")),
            (self.budget_tab, "📒", tr("tab.budget")),
            (self.savings_tab, "🎯", tr("tab.savings")),
            (self.overview_tab, "📊", tr("tab.overview")),
            (self.categories_tab, "🗂", tr("tab.categories")),
            (self.account_tab, "🛡", tr("tab.account")),
        ]
        for widget, icon, label in navigation:
            if self.tabs.indexOf(widget) < 0:
                continue
            button = QPushButton(f"{icon}  {label}", sidebar)
            button.setObjectName("sidebarNavButton")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumHeight(40)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.clicked.connect(
                lambda _checked=False, target=widget: self._goto_tab(target)
            )
            self._sidebar_group.addButton(button)
            self._sidebar_buttons[widget] = button
            side.addWidget(button)
        side.addStretch(1)

        def add_utility(text, callback, tip=""):
            button = QPushButton(text, sidebar)
            button.setObjectName("sidebarUtilityButton")
            button.setMinimumHeight(38)
            if tip:
                button.setToolTip(tip)
            button.clicked.connect(callback)
            side.addWidget(button)
            return button

        self.sidebar_import_button = add_utility(
            f"📥  {tr('lifeplanner_import.sidebar')}",
            self._show_lifeplanner_imports,
            tr("lifeplanner_import.intro"),
        )
        self.sidebar_help_button = add_utility(
            f"?  {tr('menu.help')}", self._show_handbook, tr("menu.handbook_tip")
        )
        self.sidebar_settings_button = add_utility(
            f"⚙  {tr('menu.settings')}", self._show_settings
        )
        version = QLabel(app_version_label(), sidebar)
        version.setObjectName("sidebarVersion")
        version.setAlignment(Qt.AlignCenter)
        side.addWidget(version)
        # Der Tab-Bar wird nur noch als interner Seiten-Container verwendet.
        self.tabs.tabBar().hide()
        self.tabs.setObjectName("modernContentTabs")
        layout.addWidget(sidebar)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(shell)
        self.modern_shell = shell
        self.main_sidebar = sidebar

        self.tabs.currentChanged.connect(self._sync_sidebar_selection)
        self._sync_sidebar_selection(self.tabs.currentIndex())

    def _sync_sidebar_selection(self, _index: int = -1) -> None:
        current = self.tabs.currentWidget()
        for widget, button in getattr(self, "_sidebar_buttons", {}).items():
            button.setChecked(widget is current)

    def _apply_modern_shell_style(self) -> None:
        """Ergänzt **rein strukturelle** Regeln für Sidebar und Aktionsleiste.

        v2.2.33 – zwei Fehler behoben:

        1. **Farben gehörten nie hierher.** Diese Methode setzte Hintergründe
           über ``palette(base)``/``palette(highlight)`` usw. Der ThemeManager
           setzt aber ausschliesslich ein Stylesheet und **nie** eine
           ``QPalette`` – ``palette(...)`` löst deshalb gegen die *System*-
           Palette auf. Auf einem dunklen Desktop blieb die Seitenleiste damit
           dunkel, obwohl ein helles Profil aktiv war; der Selektor
           ``QFrame#mainSidebar`` ist spezifischer als das generische
           ``QWidget`` des App-Themes und gewann. Alle Farben liegen jetzt im
           ThemeManager (``build_stylesheet``), hier bleibt nur Geometrie.
        2. **Stylesheet-Akkumulation.** Der Block wurde per
           ``setStyleSheet(self.styleSheet() + ...)`` angehängt und diese
           Methode läuft bei *jedem* Theme-Wechsel erneut – das Stylesheet
           wuchs unbegrenzt. Der Block wird jetzt idempotent gesetzt.
        """
        self.setStyleSheet(
            """
            QLabel#sidebarBrand {
                font-size: 17px;
                font-weight: 700;
                padding: 4px 8px 10px 8px;
            }
            QPushButton#sidebarNavButton, QPushButton#sidebarUtilityButton {
                border: 0;
                border-radius: 8px;
                padding: 9px 11px;
                text-align: left;
            }
            QPushButton#sidebarNavButton:checked {
                font-weight: 600;
            }
            QLabel#sidebarVersion {
                font-size: 11px;
                font-weight: 500;
                padding-top: 8px;
            }
            QToolBar#unifiedActionToolbar {
                spacing: 7px;
                padding: 7px 10px;
            }
            QToolBar#unifiedActionToolbar QToolButton {
                border-radius: 7px;
                padding: 7px 11px;
                font-weight: 600;
            }
            QTabWidget#modernContentTabs::pane { border: 0; }
        """
        )

    def _restore_window_state(self):
        """Stellt Fenster-Größe, -Position und -Status wieder her"""
        # Position und Größe laden
        width = self.settings.get("window_width", 1280)
        height = self.settings.get("window_height", 800)
        x = self.settings.get("window_x", 100)
        y = self.settings.get("window_y", 100)

        # Validiere Position/Groesse (verhindert Off-Screen- und DPI-Wechsel-Probleme)
        try:
            from utils.ui_scaling import clamp_geometry_to_available_screen

            x, y, width, height = clamp_geometry_to_available_screen(
                x, y, width, height
            )
        except Exception as e:
            logger.debug(
                "Fenstergeometrie konnte nicht DPI-sicher geklemmt werden: %s", e
            )
            screen = QApplication.primaryScreen()
            if screen:
                screen_rect = screen.availableGeometry()
                if (
                    x + width < 0
                    or x > screen_rect.width()
                    or y + height < 0
                    or y > screen_rect.height()
                ):
                    x, y = 100, 100

        # Position und Groesse setzen
        self.setGeometry(x, y, width, height)

        # Maximiert/Fullscreen-Status nur merken, aber hier NICHT anzeigen.
        #
        # Wichtig: Dieses Objekt wird noch im Konstruktor aufgebaut. Ein show()/
        # showMaximized() innerhalb von __init__ ist fehleranfällig: Das Fenster
        # wird sichtbar, bevor Menü, Cockpit-Signale, Setup-Assistent und Auto-
        # Backup vollständig verdrahtet sind. In der Cockpit-Integration konnte
        # das wie zusätzliche Fenster/Instanzen wirken. Angezeigt wird jetzt
        # genau einmal über show_restored() aus main.py.
        is_maximized = self.settings.get("window_is_maximized", False)
        is_fullscreen = self.settings.get("window_is_fullscreen", False)
        if is_fullscreen:
            self._initial_show_mode = "fullscreen"
        elif is_maximized:
            self._initial_show_mode = "maximized"
        else:
            self._initial_show_mode = "normal"

    def show_restored(self) -> None:
        """Zeigt das Hauptfenster genau einmal im gespeicherten Zustand.

        Diese Methode ersetzt das frühere frühe show() in _restore_window_state().
        Dadurch gibt es einen klaren Startpunkt für das Hauptfenster und Cockpit/
        Setup-Assistent erzeugen keine scheinbaren Doppel-Fenster mehr.
        """
        mode = getattr(self, "_initial_show_mode", "normal")
        if mode == "fullscreen":
            self.showFullScreen()
        elif mode == "maximized":
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

    def _shortcut_key(self, action_id: str) -> str:
        """Gibt das konfigurierte Tastenkürzel für eine GUI-Aktion zurück."""
        try:
            return load_shortcuts(self.settings).get(action_id, default_key(action_id))
        except Exception as exc:
            logger.debug("Shortcut %s konnte nicht geladen werden: %s", action_id, exc)
            return default_key(action_id)

    def _apply_shortcut(self, action: QAction, action_id: str) -> QAction:
        """Bindet ein QAction-Tastenkürzel an die zentrale Shortcut-Konfiguration."""
        key = self._shortcut_key(action_id)
        action.setShortcut(QKeySequence(key) if key else QKeySequence())
        action.setShortcutContext(Qt.ApplicationShortcut)
        if not hasattr(self, "_shortcut_actions"):
            self._shortcut_actions = {}
        self._shortcut_actions[action_id] = action
        return action

    def _apply_current_shortcuts_to_actions(self) -> None:
        """Aktualisiert alle bereits erzeugten QAction-Shortcuts nach Settings-Änderung."""
        for action_id, action in dict(getattr(self, "_shortcut_actions", {})).items():
            try:
                self._apply_shortcut(action, action_id)
            except Exception as exc:
                logger.debug(
                    "Shortcut-Aktion %s konnte nicht aktualisiert werden: %s",
                    action_id,
                    exc,
                )

    def _setup_shortcuts(self):
        """Richtet globale Tastenkürzel ein (konfigurierbar über Einstellungen)."""
        # Die shortcuts liegen auf den QActions selbst. Dadurch ändern sich Menüanzeige
        # und wirksames Tastenkürzel gemeinsam, statt alte hardcodierte Kürzel aktiv
        # zu lassen.
        self._apply_current_shortcuts_to_actions()

    def _create_menu(self):
        """Erstellt das Hamburger-Menü (Menüleiste)"""
        self._shortcut_actions = {}
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
        self._install_help_corner_button(menubar)

    def _install_help_corner_button(self, menubar: QMenuBar) -> None:
        """Setzt das sichtbare ``?`` rechts oben in die Menüleiste.

        Implementierung in ``views/help_launcher.py``. Der vorhandene Knopf wird
        bewusst wiederverwendet: ``_retranslate_ui`` leert die Menüleiste, das
        Corner-Widget überlebt das aber und darf nicht doppelt entstehen.
        """
        self.menu_help_button = install_help_corner_button(
            self,
            menubar,
            self._show_handbook,
            existing=getattr(self, "menu_help_button", None),
        )

    def _create_unified_action_toolbar(self) -> None:
        """Zentrale, kontextunabhängige Aktionen für die häufigsten Aufgaben.

        Alle Einstiege rufen dieselben Dialoge/Methoden auf. Damit gibt es für
        Buchungen, Fixkosten, Kategorien und Sparziele jeweils nur noch einen
        fachlichen Bedienweg, auch wenn die Aktion von verschiedenen Reitern
        aus gestartet wird.
        """
        toolbar = QToolBar(tr("menu.extras"), self)
        toolbar.setObjectName("unifiedActionToolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        def add_action(label: str, icon: str, callback, tip: str = "") -> QAction:
            action = QAction(get_icon(icon), label, self)
            if tip:
                action.setToolTip(tip)
                action.setStatusTip(tip)
            action.triggered.connect(lambda _checked=False, cb=callback: cb())
            toolbar.addAction(action)
            return action

        # Undo/Redo sind bewusst auch direkt in der Toolbar sichtbar. Dieselben
        # QAction-Objekte hängen im Bearbeiten-Menü und tragen die globalen
        # Shortcuts, damit Button, Menü und Ctrl+Z/Ctrl+Y garantiert denselben
        # Codepfad verwenden.
        self.undo_action.setIcon(get_icon("↩️"))
        self.redo_action.setIcon(get_icon("↪️"))
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)
        toolbar.addSeparator()

        self.action_quick_add_unified = add_action(
            tr("menu.quick_add"), "➕", self._show_quick_add, tr("menu.quick_add_tip")
        )
        self.action_fixcosts_unified = add_action(
            tr("cockpit.action_fixcosts"),
            "📅",
            self._tracking_add_fixcosts,
            tr("cockpit.action_fixcosts_tip"),
        )
        toolbar.addSeparator()
        self.action_categories_unified = add_action(
            tr("menu.category_manager"),
            "📁",
            self._show_category_manager,
            tr("menu.category_manager_tip"),
        )
        self.action_savings_unified = add_action(
            tr("menu.savings_goals"),
            "🎯",
            self._show_savings_goals,
            tr("savings.goal.toolbar_tip"),
        )
        toolbar.addSeparator()
        self.action_search_unified = add_action(
            tr("menu.search"), "🔍", self._show_global_search, tr("menu.search_tip")
        )
        self.addToolBar(Qt.TopToolBarArea, toolbar)
        self.unified_action_toolbar = toolbar

    def _reduce_duplicate_quick_actions(self) -> None:
        """Blendet redundante Schnelleingabe-Knöpfe in Analyse-/Verwaltungsreitern aus.

        Cockpit und Tracking behalten ihre kontextnahen Einstiege. Budget,
        Kategorien und Übersicht nutzen stattdessen die dauerhaft sichtbare
        zentrale Aktionsleiste.
        """
        for widget in (self.budget_tab, self.categories_tab, self.overview_tab):
            button = getattr(widget, "btn_quick_add", None)
            if button is not None:
                button.setVisible(False)

    def _install_edit_context_menus(self) -> None:
        """Rechtsklick auf freie Tab-Flächen zeigt die passenden Bearbeiten-Aktionen.

        Tabellen behalten ihre eigenen Kontextmenüs. Auf leeren Bereichen oder
        einfachen Reiterflächen bekommt der Nutzer direkt dieselben Aktionen wie
        im Menü "Bearbeiten".
        """
        widgets = [
            self.tabs,
            self.cockpit_tab,
            self.budget_tab,
            self.tracking_tab,
            self.overview_tab,
            self.savings_tab,
        ]

        # Cockpit: Rechtsklick soll auch auf Karten, Tabellen und leeren Panel-Flächen
        # funktionieren. Sonst landet der Klick bei Child-Widgets und das Menü wirkt
        # auf den Nutzer zufällig oder funktionslos.
        try:
            widgets.extend(self.cockpit_tab.findChildren(QFrame))
            widgets.extend(self.cockpit_tab.findChildren(QTableWidget))
        except Exception as fehler:
            _uebersprungen("_install_edit_context_menus", fehler)

        seen: set[int] = set()
        for widget in widgets:
            try:
                ident = id(widget)
                if ident in seen:
                    continue
                seen.add(ident)
                widget.setContextMenuPolicy(Qt.CustomContextMenu)
                widget.customContextMenuRequested.connect(
                    lambda pos, w=widget: self._show_edit_context_menu(
                        w.mapToGlobal(pos)
                    )
                )
            except Exception as e:
                logger.debug("Edit-Kontextmenü konnte nicht installiert werden: %s", e)

    def _show_edit_context_menu(self, global_pos: QPoint) -> None:
        """Zeigt ein zum aktiven Reiter passendes Rechtsklick-Menü.

        Für das Cockpit darf das Menü nicht die generischen
        ``Neu/Bearbeiten/Löschen``-Einträge anzeigen: Diese delegieren an
        Methoden, die das Cockpit bewusst nicht hat und wirken dadurch wie
        "macht nichts". Das Cockpit bekommt deshalb eigene Schnellaktionen.
        """
        if self.tabs.currentWidget() is self.cockpit_tab:
            self._show_cockpit_context_menu(global_pos)
            return

        try:
            self._update_edit_menu()
        except Exception as fehler:
            _uebersprungen("_show_edit_context_menu", fehler)
        menu = QMenu(self)
        last_sep = True
        for act in self.edit_menu.actions():
            if act.isSeparator():
                if not last_sep and menu.actions():
                    menu.addSeparator()
                    last_sep = True
                continue
            if not act.isVisible() or not act.isEnabled():
                continue
            menu.addAction(act)
            last_sep = False
        # End-Separators entfernen
        while menu.actions() and menu.actions()[-1].isSeparator():
            menu.removeAction(menu.actions()[-1])
        if menu.actions():
            menu.exec(global_pos)

    def _show_cockpit_context_menu(self, global_pos: QPoint) -> None:
        """Nutzbares Rechtsklick-Menü für das Cockpit."""
        menu = QMenu(self)

        def add(label_key: str, icon: str, callback) -> None:
            act = QAction(tr(label_key), self)
            act.setIcon(get_icon(icon))
            act.triggered.connect(lambda _checked=False, cb=callback: cb())
            menu.addAction(act)

        add("cockpit.action_quick_add", "➕", self._show_quick_add)
        add("cockpit.action_fixcosts", "📅", self._tracking_add_fixcosts)
        add("cockpit.action_budget_warnings", "🚨", self._check_budget_warnings)
        menu.addSeparator()
        add(
            "cockpit.action_check_budget", "💰", lambda: self._goto_tab(self.budget_tab)
        )
        add("cockpit.action_overview", "📈", lambda: self._goto_tab(self.overview_tab))
        add("cockpit.action_savings", "🎯", self._show_savings_goals)
        menu.addSeparator()
        add("cockpit.refresh", "🔄", self.cockpit_tab.refresh)
        add("cockpit.customize", "⚙️", self.cockpit_tab._show_customize_menu)
        add("cockpit.show_all", "🏠", self.cockpit_tab._show_all_panels)
        menu.addSeparator()
        fixed = QAction(tr("cockpit.layout_fixed"), self)
        fixed.setCheckable(True)
        fixed.setChecked(self.cockpit_tab.is_layout_fixed())
        fixed.setToolTip(tr("cockpit.layout_fixed_tip"))
        fixed.toggled.connect(self.cockpit_tab.set_layout_fixed)
        menu.addAction(fixed)
        reset = QAction(tr("cockpit.reset_layout"), self)
        reset.triggered.connect(self.cockpit_tab.reset_layout)
        menu.addAction(reset)

        menu.exec(global_pos)

    def _sync_cockpit_layout_action(self, fixed: bool) -> None:
        """Hält Ansicht-Menü und Cockpit-Dialog ohne Signalschleife synchron."""
        action = getattr(self, "_cockpit_layout_fixed_action", None)
        if action is None:
            return
        old = action.blockSignals(True)
        try:
            action.setChecked(bool(fixed))
        finally:
            action.blockSignals(old)

    # ── Menü-Sektionen ──────────────────────────────────────────

    def _create_file_menu(self, menubar: QMenuBar) -> None:
        """Datei-Menü: Speichern, Einstellungen, DB-Info, Beenden."""
        file_menu = menubar.addMenu(tr("menu.file"))

        save_action = QAction(tr("menu.save"), self)
        self._apply_shortcut(save_action, "save")
        save_action.setStatusTip(tr("menu.save_tip"))
        save_action.triggered.connect(self._save_budget)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        settings_action = QAction(tr("menu.settings"), self)
        self._apply_shortcut(settings_action, "settings")
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
        self._apply_shortcut(exit_action, "quit")
        exit_action.setStatusTip(tr("menu.exit_tip"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _create_view_menu(self, menubar: QMenuBar) -> None:
        """Ansicht-Menü: Tab-Navigation, Subtab-Sichtbarkeit, Vollbild."""
        view_menu = menubar.addMenu(tr("menu.view"))

        from views.ui_experience_menu import build_ui_experience_menu

        build_ui_experience_menu(self, view_menu)

        # Anzeigen-Untermenü (Tabs/Module ein- & ausblenden)
        anzeigen_menu = view_menu.addMenu(tr("menu.show"))

        # Hauptreiter ein-/ausblenden
        tabs_menu = anzeigen_menu.addMenu(tr("menu.show_tabs"))
        tabs_menu.setIcon(get_icon("🧭"))
        self._tab_visibility_actions = {}
        for tab_id, title in [
            (5, tr("tab.cockpit")),
            (0, tr("tab.budget")),
            (1, tr("tab.categories")),
            (2, tr("tab.tracking")),
            (3, tr("tab.overview")),
            (4, tr("tab.savings")),
            (6, tr("tab.account")),
        ]:
            act = QAction(title, self)
            act.setCheckable(True)
            act.setChecked(self.tabs.indexOf(self._tab_definitions[tab_id][0]) >= 0)
            act.toggled.connect(
                lambda checked, tid=tab_id: self._set_tab_visible(tid, checked)
            )
            tabs_menu.addAction(act)
            self._tab_visibility_actions[tab_id] = act

        # Cockpit → Bereiche ein/ausblenden
        cockpit_menu = anzeigen_menu.addMenu(tr("menu.cockpit_panels"))
        cockpit_menu.setIcon(get_icon("🏠"))
        self._cockpit_panel_actions = {}
        try:
            cockpit_cfg = self.settings.get("cockpit_visible_panels", {}) or {}
            for key, title in self.cockpit_tab.get_panel_specs():
                act = QAction(title, self)
                act.setCheckable(True)
                act.setChecked(bool(cockpit_cfg.get(key, True)))
                act.toggled.connect(
                    lambda checked, k=key: self.cockpit_tab.set_panel_visible(
                        k, checked
                    )
                )
                cockpit_menu.addAction(act)
                self._cockpit_panel_actions[key] = act
        except Exception:
            dummy = QAction(tr("lbl.keine_optionen_verfuegbar"), self)
            dummy.setEnabled(False)
            cockpit_menu.addAction(dummy)

        # Übersicht → Subtabs ein/ausblenden
        overview_menu = anzeigen_menu.addMenu(tr("menu.overview_subtabs"))
        overview_menu.setIcon(get_icon("📈"))
        self._overview_visibility_actions = {}

        vis = self.settings.get("overview_visible_subtabs", {}) or {}
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
                act.toggled.connect(
                    lambda checked, k=key: self._toggle_overview_subtab(k, checked)
                )
                overview_menu.addAction(act)
                self._overview_visibility_actions[key] = act
        else:
            dummy = QAction(tr("lbl.keine_optionen_verfuegbar"), self)
            dummy.setEnabled(False)
            overview_menu.addAction(dummy)

        # Cockpit-Layout: Automatik oder bewusst fixiertes Drag-and-drop.
        cockpit_layout_menu = view_menu.addMenu(tr("menu.cockpit_layout"))
        cockpit_layout_menu.setIcon(get_icon("↕"))
        fixed_layout = QAction(tr("cockpit.layout_fixed"), self)
        fixed_layout.setCheckable(True)
        fixed_layout.setChecked(self.cockpit_tab.is_layout_fixed())
        fixed_layout.setToolTip(tr("cockpit.layout_fixed_tip"))
        fixed_layout.toggled.connect(self.cockpit_tab.set_layout_fixed)
        cockpit_layout_menu.addAction(fixed_layout)
        self._cockpit_layout_fixed_action = fixed_layout

        customize_layout = QAction(tr("cockpit.customize"), self)
        customize_layout.triggered.connect(self.cockpit_tab._show_customize_menu)
        cockpit_layout_menu.addAction(customize_layout)

        reset_layout = QAction(tr("cockpit.reset_layout"), self)
        reset_layout.triggered.connect(self.cockpit_tab.reset_layout)
        cockpit_layout_menu.addAction(reset_layout)

        try:
            self.cockpit_tab.layout_mode_changed.connect(
                self._sync_cockpit_layout_action
            )
        except Exception as fehler:
            _uebersprungen("_create_view_menu", fehler)

        view_menu.addSeparator()

        # Zu Tabs wechseln
        goto_cockpit = QAction(tr("menu.goto_cockpit"), self)
        goto_cockpit.setIcon(get_icon("🏠"))
        self._apply_shortcut(goto_cockpit, "tab_cockpit")
        goto_cockpit.triggered.connect(lambda: self._goto_tab(self.cockpit_tab))
        # v2.2.16 (K7): Menueeintrag entfernt – die Sidebar ist die Navigation.
        # Die Action bleibt fensterweit registriert, damit der Shortcut weiter wirkt.
        self.addAction(goto_cockpit)

        goto_budget = QAction(tr("menu.goto_budget"), self)
        goto_budget.setIcon(get_icon("💰"))
        self._apply_shortcut(goto_budget, "tab_budget")
        goto_budget.triggered.connect(lambda: self._goto_tab(self.budget_tab))
        # v2.2.16 (K7): Menueeintrag entfernt – die Sidebar ist die Navigation.
        # Die Action bleibt fensterweit registriert, damit der Shortcut weiter wirkt.
        self.addAction(goto_budget)

        self.goto_categories_action = QAction(tr("menu.goto_categories"), self)
        self.goto_categories_action.setIcon(get_icon("📁"))
        self._apply_shortcut(self.goto_categories_action, "tab_categories")
        # Wenn der Experten-Tab sichtbar ist, dorthin wechseln; sonst Manager öffnen.
        self.goto_categories_action.triggered.connect(self._goto_categories_or_manager)
        # v2.2.16 (K7): siehe oben – Shortcut bleibt, Menueeintrag entfaellt.
        self.addAction(self.goto_categories_action)
        self._update_categories_menu_visibility()

        goto_tracking = QAction(tr("menu.goto_tracking"), self)
        goto_tracking.setIcon(get_icon("📊"))
        self._apply_shortcut(goto_tracking, "tab_tracking")
        goto_tracking.triggered.connect(lambda: self._goto_tab(self.tracking_tab))
        # v2.2.16 (K7): Menueeintrag entfernt – die Sidebar ist die Navigation.
        # Die Action bleibt fensterweit registriert, damit der Shortcut weiter wirkt.
        self.addAction(goto_tracking)

        goto_overview = QAction(tr("menu.goto_overview"), self)
        goto_overview.setIcon(get_icon("📈"))
        self._apply_shortcut(goto_overview, "tab_overview")
        goto_overview.triggered.connect(lambda: self._goto_tab(self.overview_tab))
        # v2.2.16 (K7): Menueeintrag entfernt – die Sidebar ist die Navigation.
        # Die Action bleibt fensterweit registriert, damit der Shortcut weiter wirkt.
        self.addAction(goto_overview)

        goto_savings = QAction(tr("menu.goto_savings"), self)
        goto_savings.setIcon(get_icon("🎯"))
        self._apply_shortcut(goto_savings, "tab_savings")
        goto_savings.triggered.connect(lambda: self._goto_tab(self.savings_tab))
        # v2.2.16 (K7): Menueeintrag entfernt – die Sidebar ist die Navigation.
        # Die Action bleibt fensterweit registriert, damit der Shortcut weiter wirkt.
        self.addAction(goto_savings)

        view_menu.addSeparator()

        view_menu.addSeparator()

        refresh_action = QAction(tr("menu.refresh"), self)
        self._apply_shortcut(refresh_action, "refresh")
        refresh_action.setStatusTip(tr("menu.refresh_tip"))
        refresh_action.triggered.connect(self._refresh_current_tab)
        view_menu.addAction(refresh_action)

        view_menu.addSeparator()

        fullscreen_action = QAction(tr("menu.fullscreen"), self)
        fullscreen_action.setIcon(get_icon("🖥️"))
        self._apply_shortcut(fullscreen_action, "fullscreen")
        fullscreen_action.setCheckable(True)
        fullscreen_action.setChecked(self.settings.get("window_is_fullscreen", False))
        fullscreen_action.toggled.connect(self._toggle_fullscreen)
        view_menu.addAction(fullscreen_action)

        maximize_action = QAction(tr("menu.maximize"), self)
        maximize_action.setIcon(get_icon("🔲"))
        self._apply_shortcut(maximize_action, "maximize")
        maximize_action.setCheckable(True)
        maximize_action.toggled.connect(self._toggle_maximize)
        view_menu.addAction(maximize_action)

        view_menu.addSeparator()

        # ── Tab-Leiste: Sichtbarkeit + Position ──────────────────────
        # v2.2.16 (K7): Tab-Leisten-Steuerung entfernt – die Sidebar ist die
        # Navigation; die alte Tab-Leiste ist dauerhaft ausgeblendet.

    def _create_extras_menu(self, menubar: QMenuBar) -> None:
        """Extras-Menü: Schnelleingabe, Suche, Manager, Export, Backup usw."""
        extras_menu = menubar.addMenu(tr("menu.extras"))

        quick_add_action = QAction(tr("menu.quick_add"), self)
        quick_add_action.setIcon(get_icon("⚡"))
        self._apply_shortcut(quick_add_action, "quick_add")
        quick_add_action.setStatusTip(tr("menu.quick_add_tip"))
        quick_add_action.triggered.connect(self._show_quick_add)
        extras_menu.addAction(quick_add_action)

        search_action = QAction(tr("menu.search"), self)
        search_action.setIcon(get_icon("🔍"))
        self._apply_shortcut(search_action, "search")
        search_action.setStatusTip(tr("menu.search_tip"))
        search_action.triggered.connect(self._show_global_search)
        extras_menu.addAction(search_action)

        import_action = QAction(tr("lifeplanner_import.menu"), self)
        import_action.setIcon(get_icon("📥"))
        import_action.setStatusTip(tr("lifeplanner_import.intro"))
        import_action.triggered.connect(self._show_lifeplanner_imports)
        extras_menu.addAction(import_action)

        # Direkt daneben, weil es dieselbe Bruecke ist - nur die andere
        # Richtung. Wer den Import kennt, findet die Freigabe.
        share_action = QAction(tr("bridge.share_menu"), self)
        share_action.setIcon(get_icon("📤"))
        share_action.setStatusTip(tr("bridge.share_hint"))
        share_action.triggered.connect(self._show_bridge_share)
        extras_menu.addAction(share_action)

        extras_menu.addSeparator()

        category_manager_action = QAction(tr("menu.category_manager"), self)
        category_manager_action.setIcon(get_icon("📁"))
        self._apply_shortcut(category_manager_action, "category_manager")
        category_manager_action.setStatusTip(tr("menu.category_manager_tip"))
        category_manager_action.triggered.connect(self._show_category_manager)
        extras_menu.addAction(category_manager_action)

        tags_manager_action = QAction(tr("menu.tags_manager"), self)
        tags_manager_action.setIcon(get_icon("🏷️"))
        self._apply_shortcut(tags_manager_action, "tags_manager")
        tags_manager_action.setStatusTip(tr("menu.tags_manager_tip"))
        tags_manager_action.triggered.connect(self._show_tags_manager)
        extras_menu.addAction(tags_manager_action)

        favorites_action = QAction(tr("menu.favorites"), self)
        favorites_action.setIcon(get_icon("⭐"))
        self._apply_shortcut(favorites_action, "favorites")
        favorites_action.setStatusTip(tr("menu.favorites_tip"))
        favorites_action.triggered.connect(self._show_favorites_dashboard)
        extras_menu.addAction(favorites_action)

        budget_warnings_action = QAction(tr("menu.budget_warnings"), self)
        budget_warnings_action.setIcon(get_icon("🚨"))
        self._apply_shortcut(budget_warnings_action, "budget_warnings")
        budget_warnings_action.setStatusTip(tr("menu.budget_warnings_tip"))
        budget_warnings_action.triggered.connect(lambda: self._check_budget_warnings())
        extras_menu.addAction(budget_warnings_action)

        extras_menu.addSeparator()

        export_action = QAction(tr("menu.export"), self)
        export_action.setIcon(get_icon("📤"))
        self._apply_shortcut(export_action, "export")
        export_action.setStatusTip(tr("menu.export_tip"))
        export_action.triggered.connect(self._show_export)
        extras_menu.addAction(export_action)

        extras_menu.addSeparator()

        savings_action = QAction(tr("menu.savings_goals"), self)
        savings_action.setIcon(get_icon("💰"))
        savings_action.triggered.connect(self._show_savings_goals)
        extras_menu.addAction(savings_action)

        # Backup & Datenbank-Verwaltung sind jetzt im Reiter „Konto" / unter
        # Einstellungen → „Konto & Daten" gebündelt (kein verstreuter Extras-Eintrag mehr).

        extras_menu.addSeparator()

        current_year_action = QAction(tr("menu.current_year"), self)
        self._apply_shortcut(current_year_action, "current_year")
        current_year_action.triggered.connect(self._set_current_year)
        extras_menu.addAction(current_year_action)

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

        account_data_action = QAction(tr("menu.account_data"), self)
        account_data_action.setIcon(get_icon("🗂️"))
        account_data_action.setStatusTip(tr("menu.account_data_tip"))
        account_data_action.triggered.connect(lambda: self._goto_tab(self.account_tab))
        account_menu.addAction(account_data_action)

        account_menu.addSeparator()

        sec_info = (
            f"{self._active_user.security_icon} "
            f"{self._active_user.display_name} — "
            f"{display_security_label(self._active_user.security)}"
        )
        info_action = QAction(sec_info, self)
        info_action.setEnabled(False)
        account_menu.addAction(info_action)
        self._account_info_action = info_action

    def _create_help_menu(self, menubar: QMenuBar) -> None:
        """Hilfe-Menü nach Desktop-Richtlinien (siehe ``views/help_menu``)."""
        self.help_menu = build_help_menu(self, menubar)

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

            if self._active_user is not None and getattr(
                self._active_user, "db_path", None
            ):
                dbp = Path(self._active_user.db_path)
            else:
                try:
                    dbp = configured_db_path(self.settings.database_path)
                except Exception:
                    dbp = Path("(unbekannt)")

            self._status_user_label.setText(
                trf(
                    "auto.views_main_window.667_user_value_0_adcf7358",
                    value_0=(user_name),
                )
            )
            self._status_db_label.setText(
                trf("auto.views_main_window.668_db_value_0_04d0a9b3", value_0=(dbp))
            )

            sb.addPermanentWidget(self._status_user_label)
            sb.addPermanentWidget(self._status_db_label, 1)
        except Exception as e:
            logger.warning("%s: %s", tr("lbl.statusbarinfo_konnte_nicht_gesetzt"), e)

    def _open_data_folder(self):
        """Öffnet den aktuellen Datenordner im Dateimanager."""
        try:
            folder = data_dir()
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
            self.statusBar().showMessage(
                trf("lbl.datenordner_geoeffnet_folder", folder=str(folder)), 3000
            )
        except Exception as e:
            show_warning(
                self,
                tr("auto.views_main_window.682_datenordner_6efcd047"),
                trf("msg.datenordner_fehler", e=str(e)),
            )

    def _apply_settings_to_tabs(self):
        """Wendet Einstellungen auf die Tabs an"""
        # Budget-Tab
        if hasattr(self.budget_tab, "chk_autosave"):
            self.budget_tab.chk_autosave.setChecked(self.settings.auto_save)

        if hasattr(self.budget_tab, "chk_ask_due"):
            self.budget_tab.chk_ask_due.setChecked(self.settings.ask_due)
        if hasattr(self.budget_tab, "set_category_drag_enabled"):
            self.budget_tab.set_category_drag_enabled(
                bool(self.settings.get("budget_overview_drag_drop", True))
            )

        # Tracking-Tab
        if hasattr(self.tracking_tab, "set_recent_days"):
            self.tracking_tab.set_recent_days(self.settings.recent_days)

    def _on_autosave_changed(self, checked: bool):
        """Speichert Auto-Save Einstellung wenn Checkbox geändert wird"""
        self.settings.auto_save = checked

    def _on_ask_due_changed(self, checked: bool):
        """Speichert Ask-Due Einstellung wenn Checkbox geändert wird"""
        self.settings.ask_due = checked

    def _load_tab_order(self):
        """Lädt Tabs in gespeicherter Reihenfolge und berücksichtigt ausgeblendete Reiter."""
        saved_order = list(self.settings.tab_order or [])
        default_order = [5, 0, 1, 2, 3, 4, 6]
        for tid in default_order:
            if tid not in saved_order:
                saved_order.append(tid)
        saved_order = [tid for tid in saved_order if tid in self._tab_definitions]
        for tab_id in saved_order:
            if not self._is_tab_visible(tab_id):
                continue
            widget, name = self._tab_definitions[tab_id]
            self.tabs.addTab(widget, name)
        # Schutz: Mindestens ein Reiter muss sichtbar bleiben.
        if self.tabs.count() == 0:
            self.tabs.addTab(self.cockpit_tab, tr("tab.cockpit"))
            vis = self._tab_visibility_config()
            vis["cockpit"] = True
            self.settings.set("tab_visibility", vis)

    def _apply_tab_icons(self) -> None:
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if hasattr(self, "cockpit_tab") and widget is self.cockpit_tab:
                self.tabs.setTabIcon(i, get_icon("🏠"))
            elif widget is self.categories_tab:
                self.tabs.setTabIcon(i, get_icon("📁"))
            elif widget is self.tracking_tab:
                self.tabs.setTabIcon(i, get_icon("📊"))
            elif hasattr(self, "savings_tab") and widget is self.savings_tab:
                self.tabs.setTabIcon(i, get_icon("🎯"))
            elif hasattr(self, "account_tab") and widget is self.account_tab:
                self.tabs.setTabIcon(i, get_icon("👤"))
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
            self._sync_sidebar_selection(index)

    def _goto_categories_or_manager(self) -> None:
        """Öffnet den Kategorien-Tab, falls sichtbar, sonst den Kategorien-Manager."""
        if self.tabs.indexOf(self.categories_tab) >= 0:
            self._goto_tab(self.categories_tab)
        else:
            self._show_category_manager()

    def _apply_ui_experience_mode(self, mode: str) -> None:
        from views.ui_experience_menu import apply_ui_experience_mode

        apply_ui_experience_mode(self, mode)

    def _sync_ui_experience_mode_actions(self) -> None:
        from views.ui_experience_menu import sync_ui_experience_mode_actions

        sync_ui_experience_mode_actions(self)

    def _tab_visibility_config(self) -> dict:
        defaults = {
            "cockpit": True,
            "budget": True,
            "categories": bool(self.settings.show_categories_tab),
            "tracking": True,
            "overview": True,
            "savings": True,
        }
        cfg = self.settings.get("tab_visibility", {}) or {}
        return {**defaults, **cfg}

    def _is_tab_visible(self, tab_id: int) -> bool:
        key = self._tab_visibility_keys.get(tab_id)
        if not key:
            return True
        if tab_id == 1 and not self.settings.show_categories_tab:
            return False
        return bool(self._tab_visibility_config().get(key, True))

    def _set_tab_visible(self, tab_id: int, visible: bool) -> None:
        """Blendet Hauptreiter ein/aus. Mindestens ein Reiter bleibt sichtbar."""
        if tab_id not in self._tab_definitions:
            return
        widget, name = self._tab_definitions[tab_id]
        idx = self.tabs.indexOf(widget)
        if not visible and idx >= 0 and self.tabs.count() <= 1:
            show_info(self, tr("cockpit.hide_tab_title"), tr("cockpit.keep_one_tab"))
            self._sync_tab_visibility_actions()
            return
        if tab_id == 1 and visible and not self.settings.show_categories_tab:
            self.settings.show_categories_tab = True
            if hasattr(self, "toggle_categories_action"):
                self.toggle_categories_action.blockSignals(True)
                self.toggle_categories_action.setChecked(True)
                self.toggle_categories_action.blockSignals(False)
        cfg = self._tab_visibility_config()
        cfg[self._tab_visibility_keys[tab_id]] = bool(visible)
        self.settings.set_many({"tab_visibility": cfg, "ui_experience_mode": "custom"})
        if visible and idx < 0:
            self._rebuild_tabs_keep_current(widget)
        elif not visible and idx >= 0:
            self.tabs.removeTab(idx)
        self._sync_tab_visibility_actions()
        self._sync_ui_experience_mode_actions()
        self._apply_tab_icons()
        self._save_tab_order()

    def _rebuild_tabs_keep_current(self, preferred_widget=None) -> None:
        current_widget = preferred_widget or self.tabs.currentWidget()
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)
        self._load_tab_order()
        self._apply_tab_icons()
        if current_widget:
            idx = self.tabs.indexOf(current_widget)
            if idx >= 0:
                self.tabs.setCurrentIndex(idx)

    def _sync_tab_visibility_actions(self) -> None:
        actions = getattr(self, "_tab_visibility_actions", {})
        for tid, act in actions.items():
            act.blockSignals(True)
            act.setChecked(self.tabs.indexOf(self._tab_definitions[tid][0]) >= 0)
            act.blockSignals(False)

    def _update_categories_menu_visibility(self) -> None:
        """Aktualisiert die Sichtbarkeit des Kategorien-Menüpunkts."""
        # Experten-Tab entfernt: Schnellzugriff bleibt sichtbar (oeffnet den Dialog).
        if hasattr(self, "goto_categories_action"):
            self.goto_categories_action.setVisible(True)

    def _toggle_categories_tab(self, checked: bool) -> None:
        """Schaltet den Kategorien-Tab ein/aus."""
        self.settings.show_categories_tab = checked
        cfg = self._tab_visibility_config()
        cfg["categories"] = bool(checked)
        self.settings.set_many({"tab_visibility": cfg, "ui_experience_mode": "custom"})
        self._rebuild_tabs_keep_current(self.categories_tab if checked else None)
        self.statusBar().showMessage(
            (
                tr("msg.categories_tab_enabled")
                if checked
                else tr("msg.categories_tab_disabled")
            ),
            2000,
        )
        self._update_categories_menu_visibility()
        self._sync_tab_visibility_actions()
        self._sync_ui_experience_mode_actions()

        # Toggle-Action synchronisieren (falls von extern aufgerufen)
        if hasattr(self, "toggle_categories_action"):
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
        default_order = [5, 0, 1, 2, 3, 4, 6]
        for tab_id in default_order:
            # Kategorien-Tab überspringen wenn nicht aktiviert
            if tab_id == 1 and not show_categories:
                continue
            widget, name = self._tab_definitions[tab_id]
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
        "east": QTabWidget.East,
        "west": QTabWidget.West,
    }

    def _apply_tab_position(self) -> None:
        """Setzt Tab-Position aus Settings.

        v2.0.32: Die frühere Default-Position links/west war auf Windows und
        unter DPI-/RDP-/Portable-Skalierung sehr anfällig für abgeschnittene
        vertikale Beschriftungen. Neuer sicherer Standard ist oben/north.
        Bestehende alte Default-Settings werden einmalig migriert; wer die
        Position danach bewusst ändert, behält seine Auswahl.
        """
        pos_key = self.settings.get("tab_position", None)
        migrated = bool(self.settings.get("tab_position_scaling_migrated_v2031", False))
        explicit = bool(self.settings.get("tab_position_user_selected", False))
        if not pos_key:
            pos_key = "north"
        elif pos_key == "west" and not explicit and not migrated:
            pos_key = "north"
            try:
                self.settings.set("tab_position", pos_key)
                self.settings.set("tab_position_scaling_migrated_v2031", True)
            except Exception as fehler:
                _uebersprungen("_apply_tab_position", fehler)
        qt_pos = self._TAB_POS_MAP.get(pos_key, QTabWidget.North)
        self.tabs.setTabPosition(qt_pos)
        try:
            self.tabs.tabBar().setUsesScrollButtons(True)
            self.tabs.tabBar().setElideMode(Qt.ElideNone)
        except Exception as fehler:
            _uebersprungen("_apply_tab_position", fehler)

    def _apply_tab_bar_visibility(self) -> None:
        """Zeigt/versteckt die Tab-Leiste gemäß Settings."""
        # v2.2.16 (K7): dauerhaft aus – Navigation laeuft ueber die Sidebar.
        self.tabs.tabBar().setVisible(False)

    def _on_tab_position_changed(self, pos_key: str) -> None:
        """Wird aufgerufen wenn Nutzer eine neue Tab-Position wählt."""
        self.settings.set("tab_position", pos_key)
        self.settings.set("tab_position_user_selected", True)
        self.settings.save()
        self._apply_tab_position()

    def _on_tab_bar_show_toggled(self, visible: bool) -> None:
        """Zeigt/versteckt die Tab-Leiste."""
        self.settings.set("tab_bar_visible", visible)
        self.settings.save()
        self._apply_tab_bar_visibility()

    def _show_settings(self):
        """Zeigt den Einstellungsdialog und wendet sichere Änderungen an.

        Ein Sprachwechsel bleibt absichtlich bis zum Neustart ausstehend
        (``language_changed`` / ``msg.language_restart_required``), damit keine
        gemischte Oberfläche entsteht.
        """
        from views.main_window_settings import show_settings

        show_settings(self)

    def _handle_data_directory_change(self, new_raw: str) -> bool:
        """Verarbeitet einen geänderten Datenordner inkl. optionaler Datenübernahme.

        Ablauf:
        - Liegen im alten Ordner Daten und ist der neue Ordner leer, wird die
          Übernahme (Kopieren mit Sicherheits-Backup) angeboten.
        - Bei Übernahme wird die aktive verschlüsselte Session vorher gesichert.
        - Der neue Speicherort wird erst nach einem Neustart wirksam.
        """
        from model.app_paths import data_dir, resolve_data_dir
        from model.data_location import (
            DataMigrationError,
            has_user_data,
            migrate_data_dir,
        )

        old_eff = data_dir()  # aktuell wirksamer (alter) Ordner – VOR dem Setzen
        new_eff = resolve_data_dir(new_raw)

        def _persist():
            self.settings.data_directory = new_raw

        # Kein echter Ortswechsel (z.B. nur Schreibweise) -> nur speichern.
        if old_eff.resolve() == new_eff.resolve():
            _persist()
            return True

        migrated = False
        if has_user_data(old_eff) and not has_user_data(new_eff):
            ask = QMessageBox.question(
                self,
                tr("settings.data_dir_migrate_title"),
                trf(
                    "settings.data_dir_migrate_question",
                    old=str(old_eff),
                    new=str(new_eff),
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if ask == QMessageBox.Yes:
                # Aktive verschlüsselte Session vor dem Kopieren auf Platte sichern.
                try:
                    sess = getattr(self, "_encrypted_session", None)
                    if sess is not None and hasattr(sess, "save"):
                        sess.save()
                except Exception as _e:
                    logger.debug(
                        "Session-Flush vor Datenübernahme fehlgeschlagen: %s", _e
                    )
                try:
                    result = migrate_data_dir(old_eff, new_eff, make_backup=True)
                    _persist()
                    migrated = True
                    show_info(
                        self,
                        tr("settings.data_dir_migrate_done_title"),
                        trf(
                            "settings.data_dir_migrate_done_msg",
                            count=len(result.copied),
                            backup=str(result.backup_path or "-"),
                            new=str(new_eff),
                        ),
                    )
                except DataMigrationError as exc:
                    show_warning(
                        self,
                        tr("settings.data_dir_migrate_failed_title"),
                        trf("settings.data_dir_migrate_failed_msg", error=str(exc)),
                    )
                    return False  # Einstellung NICHT ändern -> alte Daten bleiben aktiv
                except Exception as exc:
                    logger.exception("Datenübernahme fehlgeschlagen")
                    show_warning(
                        self,
                        tr("settings.data_dir_migrate_failed_title"),
                        trf("settings.data_dir_migrate_failed_msg", error=str(exc)),
                    )
                    return False
            else:
                _persist()
        elif has_user_data(new_eff):
            # Zielordner enthält bereits Daten -> diese werden nach Neustart genutzt.
            _persist()
            show_info(
                self,
                tr("settings.data_dir_changed_title"),
                tr("settings.data_dir_target_has_data_msg"),
            )
            return True
        else:
            _persist()

        if not migrated:
            try:
                show_info(
                    self,
                    tr("settings.data_dir_changed_title"),
                    tr("settings.data_dir_changed_msg"),
                )
            except Exception as _e:
                logger.debug(
                    "Datenordner-Hinweis konnte nicht angezeigt werden: %s", _e
                )
        return True

    def _change_theme(self, theme: str):
        """Ändert das Theme über Menü"""
        # Theme über Manager anwenden
        profile_name = "Standard Hell" if theme == "light" else "Standard Dunkel"
        self.theme_manager.apply_theme(profile_name=profile_name)
        try:
            if hasattr(self, "cockpit_tab") and hasattr(self.cockpit_tab, "refresh"):
                self.cockpit_tab.refresh()
        except Exception as exc:
            logger.debug("Cockpit nach Theme-Wechsel nicht aktualisierbar: %s", exc)

        # Settings aktualisieren für Kompatibilität
        self.settings.theme = theme

        # Radio-Buttons aktualisieren
        if hasattr(self, "action_light"):
            self.action_light.setChecked(theme == "light")
        if hasattr(self, "action_dark"):
            self.action_dark.setChecked(theme == "dark")

        self.statusBar().showMessage(f"Theme: {theme}", 2000)

    def _watch_system_color_scheme(self) -> None:
        """Auf den Hell/Dunkel-Wechsel des Betriebssystems reagieren.

        Ohne diese Verbindung greift die Einstellung "Wie das System" erst
        beim naechsten Start - und genau das ist die Situation, in der sie
        niemandem hilft. FPM, FreizeitManager und LifePlanner hatten die
        Verbindung laengst; hier fehlte sie als einzigem.
        """
        signal = getattr(QGuiApplication.styleHints(), "colorSchemeChanged", None)
        if signal is None:  # Qt aelter als 6.5
            return
        signal.connect(self._system_color_scheme_changed)

    def _system_color_scheme_changed(self, _scheme) -> None:
        """Nur handeln, wenn der Nutzer dem System auch folgen wollte."""
        gewaehlt = str(self.settings.get("theme", "light") or "light").lower()
        if gewaehlt not in ("system", "auto"):
            return
        self._apply_theme()

    def _apply_theme(self):
        """Wendet das aktuelle Theme an"""
        # Theme Manager verwenden
        self.theme_manager.apply_theme()
        self._apply_modern_shell_style()

        # Nach Theme-Wechsel: Typ-Farben/Badges neu anwenden
        try:
            if hasattr(self, "cockpit_tab") and hasattr(self.cockpit_tab, "refresh"):
                self.cockpit_tab.refresh()
            if hasattr(self, "tracking_tab") and hasattr(self.tracking_tab, "refresh"):
                self.tracking_tab.refresh()
            if hasattr(self, "overview_tab"):
                if hasattr(self.overview_tab, "refresh_data"):
                    self.overview_tab.refresh_data()
                elif hasattr(self.overview_tab, "refresh"):
                    self.overview_tab.refresh()
            if hasattr(self, "savings_tab") and hasattr(self.savings_tab, "refresh"):
                self.savings_tab.refresh()
        except Exception as e:
            logger.debug("if hasattr(self, 'tracking_tab') and hasattr(self.: %s", e)

    # ------------------------------------------------------------
    # Bearbeiten-Menü (dynamisch je nach aktivem Tab)
    # ------------------------------------------------------------
    def _setup_edit_menu(self):
        """Erstellt das Bearbeiten-Menü mit allen möglichen Actions"""
        self.edit_menu.clear()

        # Undo/Redo (immer verfügbar)
        self.undo_action = QAction(
            tr("auto.views_main_window.1037_undo_918f0844"), self
        )
        self._apply_shortcut(self.undo_action, "undo")
        self.undo_action.setShortcutContext(Qt.ApplicationShortcut)
        self.undo_action.triggered.connect(self._undo_global)
        self.edit_menu.addAction(self.undo_action)

        self.redo_action = QAction(
            tr("auto.views_main_window.1043_redo_2dcd731a"), self
        )
        self._apply_shortcut(self.redo_action, "redo")
        self.redo_action.setShortcutContext(Qt.ApplicationShortcut)
        self.redo_action.triggered.connect(self._redo_global)
        self.edit_menu.addAction(self.redo_action)

        self.edit_menu.addSeparator()

        self._update_undo_redo_actions()

        # === ALLGEMEINE AKTIONEN (immer sichtbar) ===
        self._edit_actions_general = []

        # Neu hinzufügen
        add_action = QAction(tr("btn.neu_hinzufuegen"), self)
        self._apply_shortcut(add_action, "edit_add")
        add_action.triggered.connect(self._edit_add)
        self.edit_menu.addAction(add_action)
        self._edit_actions_general.append(add_action)

        # Bearbeiten
        edit_action = QAction(
            tr("auto.views_main_window.1064_bearbeiten_4fc85ded"), self
        )
        edit_action.setIcon(get_icon("✏️"))
        self._apply_shortcut(edit_action, "edit_edit")
        edit_action.triggered.connect(self._edit_edit)
        self.edit_menu.addAction(edit_action)
        self._edit_actions_general.append(edit_action)

        # Löschen
        delete_action = QAction(tr("btn.loeschen"), self)
        self._apply_shortcut(delete_action, "edit_delete")
        delete_action.triggered.connect(self._edit_delete)
        self.edit_menu.addAction(delete_action)
        self._edit_actions_general.append(delete_action)

        self.edit_menu.addSeparator()

        # === BUDGET-TAB AKTIONEN ===
        self._edit_actions_budget = []

        budget_entry_action = QAction(
            tr("auto.views_main_window.1083_budget_erfassen_d622e1c6"), self
        )
        budget_entry_action.setIcon(get_icon("📝"))
        budget_entry_action.triggered.connect(self._budget_entry)
        self.edit_menu.addAction(budget_entry_action)
        self._edit_actions_budget.append(budget_entry_action)

        budget_edit_action = QAction(
            tr("auto.views_main_window.1089_budget_bearbeiten_45efb7d1"), self
        )
        budget_edit_action.setIcon(get_icon("✏️"))
        budget_edit_action.triggered.connect(self._budget_edit)
        self.edit_menu.addAction(budget_edit_action)
        self._edit_actions_budget.append(budget_edit_action)

        self.edit_menu.addSeparator()

        budget_seed_action = QAction(
            tr("auto.views_main_window.1097_zeilen_aus_kategorien_erzeugen_f04f27f9"),
            self,
        )
        budget_seed_action.setIcon(get_icon("🌱"))
        budget_seed_action.triggered.connect(self._budget_seed)
        self.edit_menu.addAction(budget_seed_action)
        self._edit_actions_budget.append(budget_seed_action)

        budget_copy_action = QAction(
            tr("auto.views_main_window.1103_jahr_kopieren_a5365b5b"), self
        )
        budget_copy_action.setIcon(get_icon("📋"))
        budget_copy_action.triggered.connect(self._budget_copy_year)
        self.edit_menu.addAction(budget_copy_action)
        self._edit_actions_budget.append(budget_copy_action)

        self.edit_menu.addSeparator()

        budget_remove_row_action = QAction(
            tr("auto.views_main_window.1111_budget_zeile_entfernen_2116ca10"), self
        )
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

        cat_new_main_action = QAction(
            tr("auto.views_main_window.1125_neue_hauptkategorie_4edd9c24"), self
        )
        cat_new_main_action.setIcon(get_icon("📁"))
        cat_new_main_action.triggered.connect(self._categories_new_main)
        self.edit_menu.addAction(cat_new_main_action)
        self._edit_actions_categories.append(cat_new_main_action)

        cat_new_sub_action = QAction(
            tr("auto.views_main_window.1131_neue_unterkategorie_51ea953c"), self
        )
        cat_new_sub_action.setIcon(get_icon("📂"))
        cat_new_sub_action.triggered.connect(self._categories_new_sub)
        self.edit_menu.addAction(cat_new_sub_action)
        self._edit_actions_categories.append(cat_new_sub_action)

        cat_delete_action = QAction(tr("btn.auswahl_loeschen"), self)
        cat_delete_action.triggered.connect(self._categories_delete)
        self.edit_menu.addAction(cat_delete_action)
        self._edit_actions_categories.append(cat_delete_action)

        self.edit_menu.addSeparator()

        cat_mass_edit_action = QAction(
            tr("auto.views_main_window.1144_massenbearbeitung_aa0c33a1"), self
        )
        cat_mass_edit_action.setIcon(get_icon("✏️"))
        cat_mass_edit_action.setStatusTip(tr("lbl.flags_fuer_mehrere_kategorien"))
        cat_mass_edit_action.triggered.connect(self._categories_mass_edit)
        self.edit_menu.addAction(cat_mass_edit_action)
        self._edit_actions_categories.append(cat_mass_edit_action)

        # === TRACKING-TAB AKTIONEN ===
        self._edit_actions_tracking = []

        self.edit_menu.addSeparator()

        fix_action = QAction(
            tr("auto.views_main_window.1156_fixkosten_buchen_61d1976c"), self
        )
        fix_action.setIcon(get_icon("📅"))
        self._apply_shortcut(fix_action, "book_fixcosts")
        fix_action.triggered.connect(self._tracking_add_fixcosts)
        self.edit_menu.addAction(fix_action)
        self._edit_actions_tracking.append(fix_action)

        # === ÜBERSICHT-TAB AKTIONEN ===
        self._edit_actions_overview = []

        refresh_overview_action = QAction(
            tr("auto.views_main_window.1166_daten_aktualisieren_6e5a0ee6"), self
        )
        refresh_overview_action.setIcon(get_icon("🔄"))
        self._apply_shortcut(refresh_overview_action, "refresh")
        refresh_overview_action.triggered.connect(self._overview_refresh)
        self.edit_menu.addAction(refresh_overview_action)
        self._edit_actions_overview.append(refresh_overview_action)

        # Initial aktualisieren
        self._update_edit_menu()

    def _on_tab_changed(self, index: int):
        """Wird aufgerufen wenn Tab gewechselt wird."""
        previous = getattr(self, "_last_tab_widget", None)
        current = self.tabs.currentWidget()

        # Sicherheits-Autosave beim Verlassen eines Tabs.
        # Besonders wichtig im verschlüsselten Modus: SQLite liegt im RAM; ohne
        # expliziten Session-Save wären UI-Änderungen bei nativem Qt-Crash weg.
        if previous is not None and previous is not current:
            self._save_widget_before_leave(previous, reason="Tabwechsel")

        self._last_tab_widget = current
        self._update_edit_menu()
        self._update_undo_redo_actions()

        # WICHTIG: Daten/Ansicht immer frisch halten.
        # Hintergrund: z.B. Budgetwarnungen/Übersicht wurden sonst erst nach
        # Neustart oder manuellem Refresh aktualisiert.
        self._refresh_current_tab_safe()

    def _save_widget_before_leave(self, widget, *, reason: str) -> None:
        """Speichert offene fachliche Änderungen eines Tabs robust und still.

        Aktuell hat vor allem der Budget-Tab editierbare Tabellenzellen, die erst
        beim Save in die DB geschrieben werden. Andere Dialoge/Modelle committen
        direkt; deren verschlüsselte Persistenz übernimmt der Commit-Hook.
        """
        try:
            if (
                widget is getattr(self, "budget_tab", None)
                and getattr(self.settings, "auto_save", True)
                and hasattr(self.budget_tab, "save")
            ):
                self.budget_tab.save()
                logger.debug("Budget-Tab vor %s gespeichert.", reason)
            # Auch wenn der Tab selbst nichts speichern musste: verschlüsselte
            # Session auf Disk bringen, falls kurz vorher Model-Commits liefen.
            self._save_encrypted_session()
        except Exception as exc:
            logger.warning(
                "Autosave vor %s fehlgeschlagen: %s", reason, exc, exc_info=True
            )

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
        if hasattr(tab, "refresh") and callable(getattr(tab, "refresh")):
            tab.refresh()
            return
        if hasattr(tab, "refresh_data") and callable(getattr(tab, "refresh_data")):
            tab.refresh_data()
            return
        if hasattr(tab, "load") and callable(getattr(tab, "load")):
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
        if hasattr(current, "add"):
            current.add()
        elif hasattr(current, "on_add"):
            current.on_add()

    def _edit_edit(self):
        """Bearbeiten - delegiert an aktuellen Tab"""
        current = self.tabs.currentWidget()
        if hasattr(current, "edit"):
            current.edit()
        elif hasattr(current, "on_edit"):
            current.on_edit()

    def _edit_delete(self):
        """Löschen - delegiert an aktuellen Tab"""
        current = self.tabs.currentWidget()
        if hasattr(current, "delete"):
            current.delete()
        elif hasattr(current, "on_delete"):
            current.on_delete()

    def _budget_copy_year(self):
        """Budget: Jahr kopieren"""
        if hasattr(self.budget_tab, "copy_year_dialog"):
            self.budget_tab.copy_year_dialog()

    def _budget_entry(self):
        """Budget: Erfassen Dialog"""
        if hasattr(self.budget_tab, "open_entry_dialog"):
            self.budget_tab.open_entry_dialog()

    def _budget_edit(self):
        """Budget: Bearbeiten Dialog"""
        if hasattr(self.budget_tab, "open_edit_dialog"):
            self.budget_tab.open_edit_dialog()

    def _budget_seed(self):
        """Budget: Zeilen aus Kategorien erzeugen"""
        if hasattr(self.budget_tab, "seed_from_categories"):
            self.budget_tab.seed_from_categories()

    def _budget_remove_row(self):
        """Budget: Zeile entfernen"""
        if hasattr(self.budget_tab, "remove_budget_row"):
            self.budget_tab.remove_budget_row()

    def _budget_remove_category(self):
        """Budget: Kategorie global löschen"""
        if hasattr(self.budget_tab, "delete_category_global"):
            self.budget_tab.delete_category_global()

    def _budget_adjust(self):
        """Budget: Anpassen Dialog"""
        if hasattr(self.budget_tab, "adjust_budget"):
            self.budget_tab.adjust_budget()

    def _categories_new_main(self):
        """Kategorien: Neue Hauptkategorie"""
        if hasattr(self.categories_tab, "add_root_category"):
            self.categories_tab.add_root_category()

    def _categories_new_sub(self):
        """Kategorien: Neue Unterkategorie"""
        if hasattr(self.categories_tab, "add_subcategory"):
            self.categories_tab.add_subcategory()

    def _categories_delete(self):
        """Kategorien: Auswahl löschen"""
        if hasattr(self.categories_tab, "delete_selected"):
            self.categories_tab.delete_selected()

    def _categories_mass_edit(self):
        """Kategorien: Massenbearbeitung"""
        if hasattr(self.categories_tab, "mass_edit"):
            self.categories_tab.mass_edit()

    def _categories_sort(self):
        """Kategorien: Sortierung ändern"""
        if hasattr(self.categories_tab, "change_sort"):
            self.categories_tab.change_sort()

    def _tracking_add_fixcosts(self):
        """Tracking: Fixkosten buchen"""
        if hasattr(self.tracking_tab, "add_fixcosts"):
            self.tracking_tab.add_fixcosts()

    def _overview_refresh(self):
        """Übersicht: Daten aktualisieren"""
        if hasattr(self.overview_tab, "refresh_data"):
            self.overview_tab.refresh_data()
        elif hasattr(self.overview_tab, "refresh"):
            self.overview_tab.refresh()

    def _open_budget_editor_from_overview(
        self, typ: str, category: str, year: int, month: int
    ) -> None:
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
        saved = self.settings.get("overview_visible_subtabs", None)
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
        if hasattr(self.overview_tab, "apply_subtab_visibility"):
            self.overview_tab.apply_subtab_visibility(vis)
        else:
            # Fallback: einzelne Tabs
            for k, on in vis.items():
                if hasattr(self.overview_tab, "set_subtab_visible"):
                    self.overview_tab.set_subtab_visible(k, bool(on))

        # Menü-Checkboxen synchronisieren
        if hasattr(self, "_overview_visibility_actions"):
            for k, act in self._overview_visibility_actions.items():
                act.blockSignals(True)
                act.setChecked(bool(vis.get(k, True)))
                act.blockSignals(False)

        # Normalisierte Map speichern
        if vis:
            self.settings.set("overview_visible_subtabs", vis)

    def _toggle_overview_subtab(self, key: str, checked: bool) -> None:
        """Callback aus dem Menü: ein/ausblenden + persistieren."""
        vis = self._get_overview_subtab_visibility()
        if not vis or key not in vis:
            return

        # Mindestens 1 Tab sichtbar lassen
        vis[key] = bool(checked)
        if not any(vis.values()):
            vis[key] = True
            if (
                hasattr(self, "_overview_visibility_actions")
                and key in self._overview_visibility_actions
            ):
                act = self._overview_visibility_actions[key]
                act.blockSignals(True)
                act.setChecked(True)
                act.blockSignals(False)
            self.statusBar().showMessage(
                tr("lbl.mindestens_ein_uebersichtreiter_muss"), 3000
            )
            return

        self.settings.set("overview_visible_subtabs", vis)
        if hasattr(self.overview_tab, "apply_subtab_visibility"):
            self.overview_tab.apply_subtab_visibility(vis)
        elif hasattr(self.overview_tab, "set_subtab_visible"):
            self.overview_tab.set_subtab_visible(key, bool(checked))

    def _save_budget(self):
        """Speichert das Budget inklusive verschlüsselter Session."""
        try:
            self._save_widget_before_leave(
                self.budget_tab, reason="manuelles Speichern"
            )
            self.statusBar().showMessage(tr("msg.budget_saved"), 3000)
            self._update_undo_redo_actions()
        except Exception as e:
            logger.error("Budget speichern fehlgeschlagen: %s", e, exc_info=True)
            show_warning(
                self, tr("dlg.hinweis"), trf("msg.fehler_beim_speichern_e", e=str(e))
            )

    def _refresh_current_tab(self):
        """Aktualisiert den aktuellen Tab"""
        current_widget = self.tabs.currentWidget()

        if hasattr(current_widget, "refresh"):
            current_widget.refresh()
            self.statusBar().showMessage(tr("msg.view_refreshed"), 2000)
        elif hasattr(current_widget, "load"):
            current_widget.load()
            self.statusBar().showMessage(tr("msg.view_refreshed"), 2000)

    def _update_undo_redo_actions(self) -> None:
        """Hält Undo/Redo zuverlässig auslösbar.

        Die Undo-Historie wird von mehreren Model-Instanzen geschrieben
        (Tracking, Kategorien, Import, Sparziele, Budget). Ein deaktiviertes
        QAction konnte deshalb veraltet bleiben, bis zufällig ein Tab-Wechsel
        stattfand. Für globale History-Aktionen ist ein sicherer No-op deutlich
        besser als ein fälschlich deaktivierter Button/Shortcut.
        """
        if hasattr(self, "undo_action"):
            self.undo_action.setEnabled(True)
            self.undo_action.setProperty("historyAvailable", self.undo_redo.can_undo())
        if hasattr(self, "redo_action"):
            self.redo_action.setEnabled(True)
            self.redo_action.setProperty("historyAvailable", self.undo_redo.can_redo())

    def _finish_active_editor_before_history(self) -> None:
        """Schließt einen laufenden Zell-Editor, bevor Undo/Redo auf die DB zugreift.

        Besonders unter Windows kann Ctrl+Z gedrückt werden, während Qt den
        letzten Zellwert noch im Editor hält. Durch das saubere Committen wird
        zuerst die gerade sichtbare Änderung in die History geschrieben und
        anschließend genau diese Änderung rückgängig gemacht.
        """
        current = self.tabs.currentWidget() if hasattr(self, "tabs") else None
        if current is getattr(self, "budget_tab", None):
            close_editor = getattr(self.budget_tab, "_close_table_editor", None)
            if callable(close_editor):
                try:
                    close_editor("Undo/Redo")
                except (RuntimeError, ValueError, TypeError) as exc:
                    logger.debug("Aktiver Budget-Editor vor Undo/Redo: %s", exc)

    def _undo_global(self) -> None:
        self._finish_active_editor_before_history()
        if self.undo_redo.undo():
            self._schedule_refresh_all_tabs(reason="undo")
            self.statusBar().showMessage(tr("history.undo_done"), 1800)
        else:
            self.statusBar().showMessage(tr("history.undo_empty"), 1800)
        self._update_undo_redo_actions()

    def _redo_global(self) -> None:
        self._finish_active_editor_before_history()
        if self.undo_redo.redo():
            self._schedule_refresh_all_tabs(reason="redo")
            self.statusBar().showMessage(tr("history.redo_done"), 1800)
        else:
            self.statusBar().showMessage(tr("history.redo_empty"), 1800)
        self._update_undo_redo_actions()

    def _set_current_year(self):
        """Setzt in allen Tabs das aktuelle Jahr"""
        current_year = date.today().year

        # Budget-Tab
        if hasattr(self.budget_tab, "year_spin"):
            self.budget_tab.year_spin.setValue(current_year)

        # Overview-Tab
        if hasattr(self.overview_tab, "year_combo"):
            for i in range(self.overview_tab.year_combo.count()):
                if self.overview_tab.year_combo.itemText(i) == str(current_year):
                    self.overview_tab.year_combo.setCurrentIndex(i)
                    break

        self.statusBar().showMessage(f"Jahr {current_year} geladen", 2000)

    def _show_db_info(self):
        """Zeigt Datenbank-Informationen und Migrations-Status"""
        from pathlib import Path

        from model.migrations import CURRENT_VERSION, get_migration_info

        try:
            # Aktive DB-Datei (für Anzeige & Größe)
            encrypted_session = getattr(self, "_encrypted_session", None)
            if encrypted_session is not None:
                active_file = Path(encrypted_session.enc_path)
            else:
                active_file = configured_db_path(self.settings.database_path)

            # Migrations-Info
            migration_info = get_migration_info(self.conn)

            # Statistiken via Model (kein raw SQL in View)
            from model.database_management_model import DatabaseManagementModel

            db_stats = DatabaseManagementModel(
                str(active_file), conn=self.conn
            ).get_database_statistics()

            db_size = db_stats.get("db_size_kb", 0)
            tables = db_stats.get("tables", [])
            budget_count = db_stats.get(tr("lbl.budgeteintraege"), 0)
            tracking_count = db_stats.get("Buchungen", 0)
            category_count = db_stats.get(tr("tab.categories"), 0)
            savings_count = db_stats.get(tr("dlg.savings_goals"), 0)
            years_b = [str(y) for y in db_stats.get("years_budget", [])]
            years_t = [str(y) for y in db_stats.get("years_tracking", [])]

            # Dialog aufbauen
            info = f"""{tr('db.info.title_html')}

<p><b>{tr('db.info.file')}:</b> {active_file.name}<br>
<b>{tr('db.info.path')}:</b> {active_file}<br>
<b>{tr('db.info.size')}:</b> {db_size:.1f} KB<br>
<b>{tr('db.info.schema')}:</b> {migration_info['current_version']} / {CURRENT_VERSION}</p>

<h4>{tr('db.info.migration_status')}</h4>
<p>"""

            if migration_info["needs_migration"]:
                info += f"<span style='color: orange;'>{tr('db.info.migration_needed')}</span><br>"
                if migration_info["missing_tables"]:
                    info += f"<b>{tr('db.info.missing_tables')}:</b> {', '.join(migration_info['missing_tables'])}"
            else:
                info += f"<span style='color: green;'>{tr('db.info.current')}</span>"

            no_years = tr("db.info.no_years")
            info += f"""</p>

<h4>{tr('db.info.data_stats')}</h4>
<ul>
<li>{tr('db.info.categories')}: {category_count}</li>
<li>{tr('db.info.budget_entries')}: {budget_count}</li>
<li>{tr('db.info.tracking_entries')}: {tracking_count}</li>
<li>{tr('db.info.savings_goals')}: {savings_count}</li>
</ul>

<p><b>{tr('db.info.budget_years')}:</b> {', '.join(years_b) if years_b else no_years}<br>
<b>{tr('db.info.tracking_years')}:</b> {', '.join(years_t) if years_t else no_years}</p>

<h4>{tr('db.info.available_tables')} ({len(tables)})</h4>
<p><small>{', '.join(tables)}</small></p>
"""

            msg = QMessageBox(self)
            msg.setWindowTitle(tr("dlg.db_info"))
            msg.setTextFormat(Qt.RichText)
            msg.setText(info)
            msg.exec()

        except Exception as e:
            show_warning(
                self, tr("dlg.hinweis"), trf("msg.fehler_beim_laden_der", e=str(e))
            )

    def _show_log_file(self, *, path: Path, title_key: str) -> None:
        """Öffnet eine Logdatei in einem eigenen Dialog (siehe ``views/main_window_diagnostics``)."""
        show_log_file(self, path=path, title_key=title_key)

    def _show_app_log(self) -> None:
        """Zeigt das Anwendungsprotokoll."""
        show_app_log(self)

    def _show_crash_log(self) -> None:
        """Zeigt das Absturzprotokoll."""
        show_crash_log(self)

    def _open_diagnostics_folder(self) -> None:
        """Öffnet den Diagnoseordner im Dateimanager."""
        open_diagnostics_folder(self)

    def _create_diagnostic_report(self) -> None:
        """Erstellt lokal ein Diagnose-ZIP ohne Datenbank/Backups."""
        create_diagnostic_report(self)

    def schedule_unclean_shutdown_prompt(
        self, previous_state: dict | None, *, delay_ms: int = 1200
    ) -> None:
        """Zeigt nach einem vermuteten Crash/Kill beim Neustart einen Diagnosehinweis."""
        if not previous_state:
            return
        timer = QTimer(self)
        timer.setSingleShot(True)

        def _show() -> None:
            try:
                if getattr(self, "_is_closing", False):
                    return
                self._show_unclean_shutdown_prompt(previous_state)
            except RuntimeError:
                logger.debug(
                    "Crash-Hinweis übersprungen: MainWindow wurde bereits zerstört."
                )
            except Exception:
                logger.exception("Crash-Hinweis konnte nicht angezeigt werden")
            finally:
                try:
                    timer.deleteLater()
                except Exception as fehler:
                    _uebersprungen("schedule_unclean_shutdown_prompt", fehler)

        timer.timeout.connect(_show)
        timer.start(max(0, int(delay_ms)))

    def _show_unclean_shutdown_prompt(self, previous_state: dict) -> None:
        started_at = str(
            previous_state.get("started_at") or tr("diagnostics.unknown_time")
        )
        reason = str(
            previous_state.get("exit_reason") or tr("diagnostics.unknown_reason")
        )
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(tr("diagnostics.unclean_title"))
        box.setText(tr("diagnostics.unclean_text"))
        box.setInformativeText(
            trf("diagnostics.unclean_info", started_at=started_at, reason=reason)
        )
        log_button = box.addButton(tr("diagnostics.show_log"), QMessageBox.ActionRole)
        report_button = box.addButton(
            tr("diagnostics.create_report"), QMessageBox.ActionRole
        )
        box.addButton(tr("diagnostics.ignore"), QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is log_button:
            self._show_app_log()
        elif box.clickedButton() is report_button:
            self._create_diagnostic_report()

    def _show_about(self):
        """Zeigt Über-Dialog"""
        dialog = AboutDialog(self)
        dialog.exec()

    def _show_handbook(self, start_topic_id: str | None = None):
        """Öffnet die In-App-Wissensdatenbank (Handbuch)."""
        from views.help_dialog import HelpDialog

        topic = start_topic_id if isinstance(start_topic_id, str) else None
        on_show_key = (
            self._show_restore_key_view if self._current_restore_key() else None
        )
        dialog = HelpDialog(
            self,
            start_topic_id=topic,
            on_show_key=on_show_key,
            on_open_mindmap=lambda parent=None: self._open_help_mindmap(),
            on_open_wiki_audit=lambda parent=None: self._open_wiki_audit(),
        )
        dialog.exec()

    def _help_file_candidates(self, rel_path: str) -> list[Path]:
        """Mögliche Orte für lokale Hilfedateien (siehe ``views/help_launcher``)."""
        return help_file_candidates(rel_path)

    def _open_help_file(
        self, rel_path: str, *, title_key: str = "menu.handbook"
    ) -> bool:
        """Öffnet eine lokale Hilfedatei (siehe ``views/help_launcher``)."""
        return open_help_file(self, rel_path, title_key=title_key)

    def _open_help_docs(self):
        """Öffnet die vollständige lokale HTML-Wissensdatenbank."""
        self._open_help_file("docs/help/index.html", title_key="menu.knowledge_base")

    def _open_help_mindmap(self):
        """Öffnet die direkt anzeigbare Mindmap / den Informations-Laufplan."""
        self._open_help_file("docs/help/mindmap.html", title_key="menu.help_mindmap")

    def _open_wiki_audit(self):
        self._open_help_file("docs/help/wiki-audit.html", title_key="menu.wiki_audit")

    def _current_restore_key(self) -> str | None:
        """Leitet den Restore-Key der aktuell geöffneten Datenbank ab.

        Der db_key steckt in der EncryptedSession. Ohne verschlüsselte Session
        (z. B. unverschlüsselte Alt-DB) gibt es keinen Restore-Key → None.
        """
        session = getattr(self, "_encrypted_session", None)
        if session is None:
            return None
        try:
            db_key = session.db_key
        except Exception:
            return None
        if not db_key:
            return None
        try:
            from model.crypto import db_key_to_restore_key

            return db_key_to_restore_key(db_key)
        except Exception:
            logger.exception("Restore-Key konnte nicht abgeleitet werden")
            return None

    def _show_restore_key_view(self, parent=None):
        """Zeigt den Restore-Key der aktuellen DB (aus der Hilfe heraus)."""
        key = self._current_restore_key()
        if not key:
            show_info(
                self,
                tr("restore_key.view_title"),
                tr("account.restorekey_nicht_verfuegbar"),
            )
            return
        from views.restore_key_dialog import RestoreKeyDialog

        RestoreKeyDialog(parent or self, restore_key=key).exec()

    def _show_account_management(self):
        """Zeigt den Kontoverwaltungs-Dialog."""
        if not self._active_user or not self._user_model:
            show_info(
                self,
                tr("auto.views_main_window.1577_info_a7110986"),
                tr(
                    "auto.views_main_window.1578_kontoverwaltung_ist_nur_bei_verschl_381922cb"
                ),
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
            self.setWindowTitle(
                trf(
                    "auto.views_main_window.1611_value_0_value_1_value_2_1814eaf1",
                    value_0=(base),
                    value_1=(icon),
                    value_2=(new_name),
                )
            )
            # Konto-Menü Info aktualisieren
            if hasattr(self, "_account_info_action"):
                self._account_info_action.setText(
                    trf(
                        "auto.views_main_window.1615_value_0_value_1_value_2_81323b29",
                        value_0=(icon),
                        value_1=(new_name),
                        value_2=(display_security_label(self._active_user.security)),
                    )
                )
            self.statusBar().showMessage(
                trf("lbl.anzeigename_geaendert_new_name", new_name=new_name), 3000
            )

    def _on_security_changed(self, new_security: str):
        """Aktualisiert den Fenstertitel nach Sicherheitsstufen-Wechsel."""
        if self._active_user:
            icon = self._active_user.security_icon
            name = self._active_user.display_name
            base = app_window_title()
            self.setWindowTitle(
                trf(
                    "auto.views_main_window.1625_value_0_value_1_value_2_1999fbaa",
                    value_0=(base),
                    value_1=(icon),
                    value_2=(name),
                )
            )
            # Konto-Menü Info aktualisieren
            if hasattr(self, "_account_info_action"):
                self._account_info_action.setText(
                    trf(
                        "auto.views_main_window.1629_value_0_value_1_value_2_943d4260",
                        value_0=(icon),
                        value_1=(name),
                        value_2=(display_security_label(self._active_user.security)),
                    )
                )
            self.statusBar().showMessage(
                trf(
                    "lbl.sicherheitsstufe_geaendert_self_active_usersecurity_label",
                    label=display_security_label(self._active_user.security),
                ),
                3000,
            )

    def _show_shortcuts(self):
        """Zeigt Tastenkürzel-Übersicht (F1)"""
        dialog = ShortcutsDialog(self, settings=self.settings)
        dialog.exec()

    def _update_lifeplanner_import_badge(self):
        """Aktualisiert nur den offenen Bridge-Zähler; keine Auto-Buchung."""
        try:
            from model.lifeplanner_import_service import pending_count

            count = pending_count(self.conn)
            button = getattr(self, "sidebar_import_button", None)
            if button is not None:
                suffix = f" ({count})" if count else ""
                button.setText(f"📥  {tr('lifeplanner_import.sidebar')}{suffix}")
                button.setProperty("hasPendingImports", bool(count))
            if count:
                self.statusBar().showMessage(
                    trf("lifeplanner_import.pending_status", count=count), 7000
                )
        except Exception as exc:
            logger.debug("LifePlanner import badge: %s", exc)

    def _show_lifeplanner_imports(self):
        """Öffnet die sichere FPM/LifePlanner-Review-Inbox."""
        dialog = LifePlannerImportDialog(self.conn, self)
        dialog.exec()
        if dialog.imported_count:
            self._save_encrypted_session()
            self._schedule_refresh_all_tabs(reason="lifeplanner_import", delay_ms=0)
        self._update_lifeplanner_import_badge()

    def _show_bridge_share(self):
        """Zeigt, was an FPM weitergegeben wird, und laesst es einzeln waehlen."""
        from views.bridge_share_dialog import BridgeShareDialog

        BridgeShareDialog(self.conn, self).exec()
        # Nach dem Schliessen schreiben, auch wenn der Nutzer "Jetzt senden"
        # nicht gedrueckt hat: Eine zurueckgenommene Freigabe soll nicht bis
        # zur naechsten Buchung in der Brueckendatei stehen bleiben.
        self._sync_bridge_outboxes_safely()

    def _show_quick_add(self):
        """Zeigt Schnelleingabe-Dialog (Strg+N)"""
        dialog = QuickAddDialog(self.conn, self)
        if dialog.exec() == QDialog.Accepted:
            self._save_encrypted_session()
            # Tracking-Tab aktualisieren
            if hasattr(self.tracking_tab, "refresh"):
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
        self._save_encrypted_session()
        # Nach Schließen: alle relevanten Einstiege aktualisieren.
        for widget in (
            getattr(self, "savings_tab", None),
            getattr(self, "overview_tab", None),
            getattr(self, "tracking_tab", None),
        ):
            try:
                if widget is not None and hasattr(widget, "refresh"):
                    widget.refresh()
            except Exception as exc:
                logger.debug("Sparziel-Refresh nach Dialog fehlgeschlagen: %s", exc)

    def _schedule_startup_auto_backup(self, *, delay_ms: int = 1200) -> None:
        """Plant die einmalige Start-Backup-Pruefung Qt-sicher ein.

        Der Callback laeuft nie direkt aus einem Dialog-``finished``-Signal.
        Gerade unter Fedora/Wayland ueber XCB kann synchrones Verschluesseln/
        ZIP-Schreiben im nativen Schliess-Stack eines QDialog zu einem
        Shiboken/Qt-Segfault ohne Python-Traceback fuehren.
        """
        if getattr(self, "_startup_auto_backup_done", False):
            return

        skip_requested = os.environ.get(
            "BM_SKIP_STARTUP_AUTO_BACKUP", ""
        ).strip().lower() in {"1", "true", "yes", "on"}
        if skip_requested:
            self._startup_auto_backup_done = True
            logger.warning(
                "Startup-Auto-Backup durch BM_SKIP_STARTUP_AUTO_BACKUP deaktiviert. "
                "Manuelle Backups bleiben verfuegbar."
            )
            return

        existing = getattr(self, "_startup_auto_backup_timer", None)
        try:
            if existing is not None and existing.isActive():
                return
        except RuntimeError:
            self._startup_auto_backup_timer = None

        timer = QTimer(self)
        timer.setSingleShot(True)
        self._startup_auto_backup_timer = timer

        def _run_safely() -> None:
            try:
                if QApplication.instance() is None:
                    return
                if getattr(self, "_is_closing", False):
                    return
                self._check_auto_backup()
            except RuntimeError:
                logger.debug(
                    "Auto-Backup uebersprungen: MainWindow wurde bereits zerstoert."
                )
            except Exception:
                logger.exception("Startup-Auto-Backup konnte nicht geprueft werden")
            finally:
                if getattr(self, "_startup_auto_backup_timer", None) is timer:
                    self._startup_auto_backup_timer = None
                try:
                    timer.deleteLater()
                except Exception as fehler:
                    _uebersprungen("_schedule_startup_auto_backup", fehler)

        timer.timeout.connect(_run_safely)
        safe_delay = max(250, int(delay_ms))
        logger.debug("Startup-Auto-Backup in %d ms eingeplant.", safe_delay)
        timer.start(safe_delay)

    def _check_auto_backup(self):
        """Prüft ob ein automatisches Backup fällig ist und erstellt es ggf."""
        if getattr(self, "_startup_auto_backup_done", False):
            return
        self._startup_auto_backup_done = True

        try:
            if not self.settings.get("auto_backup", False):
                return

            from datetime import datetime, timedelta

            from app_info import APP_NAME, APP_VERSION
            from model.restore_bundle import create_bundle

            backup_dir = configured_backups_dir(
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
                    src_db = configured_db_path(self.settings.database_path)

                if src_db.exists():
                    backup_dir.mkdir(parents=True, exist_ok=True)

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_name = f"budgetmanager_backup_auto_{timestamp}.bmr"
                    backup_path = backup_dir / backup_name

                    from model.app_paths import settings_path as _get_settings_path
                    from model.user_model import _users_file_path

                    _s_path = _get_settings_path()
                    _u_path = _users_file_path()
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
                    self.statusBar().showMessage(
                        f"Auto-Backup erstellt: {backup_name}", 5000
                    )

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
            db_path = str(configured_db_path(self.settings.database_path))
        dialog = BackupRestoreDialog(
            self,
            self.conn,
            db_path,
            self.settings,
            encrypted_session=encrypted_session,
            active_user=self._active_user,
        )
        dialog.exec()
        # Nach erfolgreichem Restore:
        # - Unverschlüsselt: Daten wurden direkt in die Live-Connection zurückgespielt
        #   → Tabs refreshen, KEIN Neustart nötig.
        # - Verschlüsselt: .enc auf Disk wurde ersetzt, In-Memory-DB ist noch alt
        #   → Neustart erforderlich.
        if getattr(dialog, "db_changed", False) and not getattr(
            dialog, "exit_requested", False
        ):
            if encrypted_session is None:
                try:
                    self._schedule_refresh_all_tabs(reason="restore dialog changed DB")
                    self.statusBar().showMessage(
                        tr("database.msg.restore_success"), 5000
                    )
                except Exception as e:
                    logger.warning("Tab-Refresh nach Restore fehlgeschlagen: %s", e)
            else:
                show_info(
                    self,
                    tr("auto.views_main_window.1788_neustart_erforderlich_288778eb"),
                    tr(
                        "auto.views_main_window.1789_bitte_starten_sie_die_anwendung_neu_e67d74c9"
                    ),
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
            db_path = str(configured_db_path(self.settings.database_path))

        dialog = DatabaseManagementDialog(
            db_path,
            parent=self,
            conn=self.conn,
            active_user=self._active_user,
            encrypted=encrypted_session is not None,
        )
        result = dialog.exec()

        # Nach Änderungen (Reset/Bereinigung): Encrypted Session auf Disk schreiben + Tabs refreshen
        if result == QDialog.Accepted or getattr(dialog, "data_changed", False):
            if encrypted_session is not None:
                try:
                    encrypted_session.save()
                except Exception as _e:
                    logger.warning(
                        "encrypted_session.save nach DB-Reset fehlgeschlagen: %s", _e
                    )
            self._schedule_refresh_all_tabs(reason="database management changed DB")
            self.statusBar().showMessage(
                tr("lbl.datenbankaenderungen_uebernommen"), 3000
            )

    def _show_category_manager(self):
        """Zeigt den Kategorien-Manager-Dialog (NEU v2.2.0)"""
        dialog = CategoryManagerDialog(self, conn=self.conn)
        dialog.categories_changed.connect(self._refresh_current_tab)
        dialog.exec()
        # Nach Schließen: Alle Tabs aktualisieren
        self._schedule_refresh_all_tabs(reason="category manager closed")

    def _show_tags_manager(self):
        """Öffnet den Tags-Manager (v2.4.0)"""
        dialog = TagsManagerDialog(self.conn, self)
        dialog.exec()

    def _show_favorites_dashboard(self):
        """Öffnet das Favoriten-Dashboard (v2.4.0)"""
        # Jahr/Monat aus Budget-Tab wenn vorhanden, sonst heute
        try:
            year = (
                int(self.budget_tab.year_spin.value())
                if hasattr(self.budget_tab, "year_spin")
                else None
            )
        except Exception:
            year = None
        from datetime import date as _date

        if year is None:
            year = _date.today().year
        month = _date.today().month
        dialog = FavoritesDashboardDialog(
            self.conn, current_year=year, current_month=month, parent=self
        )
        dialog.exec()

    def _retranslate_ui(self) -> None:
        """Aktualisiert alle UI-Labels nach einer Sprachänderung."""
        from utils.i18n import tr

        # Tab-Labels aktualisieren
        self._tab_definitions = {
            5: (self.cockpit_tab, tr("tab.cockpit")),
            0: (self.budget_tab, tr("tab.budget")),
            1: (self.categories_tab, tr("tab.categories")),
            2: (self.tracking_tab, tr("tab.tracking")),
            3: (self.overview_tab, tr("tab.overview")),
            4: (self.savings_tab, tr("tab.savings")),
            6: (self.account_tab, tr("tab.account")),
        }
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            for tab_id, (tab_widget, label) in self._tab_definitions.items():
                if widget is tab_widget:
                    self.tabs.setTabText(i, label)
                    break
        self._apply_tab_icons()
        # Menü-Einträge aktualisieren: Menüleiste leeren und komplett neu aufbauen.
        # (Hinweis: Es gab nie eine Methode `_setup_menus` — der frühere Aufruf
        # schlug still fehl, wodurch Menüs nach Sprachwechsel unverändert blieben.)
        try:
            self.menuBar().clear()
            self._create_menu()
            self._update_edit_menu()
            self._update_categories_menu_visibility()
            self._update_undo_redo_actions()
        except Exception as e:
            logger.warning("_retranslate_ui menu rebuild fehlgeschlagen: %s", e)
        # Status-Bar
        self.statusBar().showMessage(tr("msg.language_changed"), 2000)

    def _check_budget_warnings(self, year: int | None = None, month: int | None = None):
        """Prüft Budgetwarnungen und zeigt Anpassungsdialog (v2.4.0)"""
        from datetime import date

        # Jahr/Monat möglichst aus der UI ableiten, damit "Extras → Budgetwarnungen"
        # dasselbe zeigt wie die Übersicht (kein "nur über Klick in Übersicht").
        try:
            if year is None and hasattr(self.overview_tab, "year_combo"):
                year = int(self.overview_tab.year_combo.currentText())
        except Exception:
            year = None
        try:
            if month is None and hasattr(self.overview_tab, "month_combo"):
                idx = int(self.overview_tab.month_combo.currentIndex())
                # idx==0 ist "Gesamt": aktuelles Jahr → heutiger Monat,
                # vergangene/andere Jahre → Dezember. Sonst fragt Extras →
                # Budgetwarnungen im Jahr 2025 fälschlich Juli statt das ganze
                # abgeschlossene Jahr ab.
                if idx == 0:
                    selected_year = int(year) if year is not None else date.today().year
                    month = (
                        date.today().month if selected_year == date.today().year else 12
                    )
                else:
                    month = idx
        except Exception:
            month = None

        # Fallback: Budget-Tab Jahr, sonst heute
        try:
            if year is None:
                year = (
                    int(self.budget_tab.year_spin.value())
                    if hasattr(self.budget_tab, "year_spin")
                    else date.today().year
                )
        except Exception:
            year = date.today().year
        if month is None:
            month = date.today().month

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
        # Nicht synchron im QAction-/Dialog-Stack refreshen: budget_tab.load() baut
        # die QTableWidget-Zeilen neu auf. Wird das direkt nach einem Menü-Klick
        # oder Dialog-Exec gemacht, kann Qt6/Shiboken beim Zerstören alter
        # Zellobjekte nativ aborten. Deshalb immer in den nächsten Event-Loop-Tick.
        self._schedule_refresh_all_tabs(reason="budget warnings dialog closed")

    def _check_budget_warnings_from_overview(self):
        """Öffnet Budgetwarner mit Jahr/Monat aus der Übersicht."""
        from datetime import date

        year = None
        month = None
        try:
            if hasattr(self.overview_tab, "year_combo"):
                year = int(self.overview_tab.year_combo.currentText())
        except Exception:
            year = None
        try:
            if hasattr(self.overview_tab, "month_combo"):
                idx = int(self.overview_tab.month_combo.currentIndex())
                if idx == 0:
                    selected_year = int(year) if year is not None else date.today().year
                    month = (
                        date.today().month if selected_year == date.today().year else 12
                    )
                else:
                    month = idx
        except Exception:
            month = None
        self._check_budget_warnings(year=year, month=month)

    def _schedule_refresh_all_tabs(
        self, *, reason: str = "", delay_ms: int = 0
    ) -> None:
        """Plant einen kompletten Tab-Refresh stabil im Qt-Eventloop.

        Hintergrund: Nach Budgetwarnungs-/Vorschlagsdialogen und QAction-Menüs ist
        Qt noch mitten im Signal-/Menü-Stack. Ein synchrones `budget_tab.load()`
        löscht dann QTableWidgetItems/Editoren (`setRowCount(0)`) und kann unter
        PySide6/Qt6 nativ in Shiboken aborten. Der verzögerte Refresh läuft erst,
        wenn Dialog/Menu vollständig abgebaut sind.
        """
        if getattr(self, "_refresh_all_tabs_pending", False):
            return
        self._refresh_all_tabs_pending = True

        def _run() -> None:
            self._refresh_all_tabs_pending = False
            if getattr(self, "_is_closing", False):
                return
            self._refresh_all_tabs()

        try:
            logger.debug("Voll-Refresh geplant (%s).", reason)
            QTimer.singleShot(max(0, int(delay_ms)), _run)
        except Exception:
            self._refresh_all_tabs_pending = False
            self._refresh_all_tabs()

    def _refresh_all_tabs(self):
        """Aktualisiert alle Tabs nach Änderungen.

        Wichtig: Tabs implementieren nicht einheitlich `load()`.
        Für Stabilität bevorzugen wir `refresh()` und fallen auf `load()` zurück.
        """
        if getattr(self, "_refresh_all_tabs_running", False):
            self._schedule_refresh_all_tabs(
                reason="reentrant refresh skipped", delay_ms=0
            )
            return
        self._refresh_all_tabs_running = True
        try:
            for tab in [
                self.budget_tab,
                self.categories_tab,
                self.tracking_tab,
                self.overview_tab,
            ]:
                self._refresh_tab_widget(tab)
        except Exception:
            # Refresh darf nie die UI killen, aber wir wollen wenigstens eine Spur im Terminal.
            import traceback

            traceback.print_exc()
        finally:
            self._refresh_all_tabs_running = False
        # Ein Voll-Refresh folgt auf eine Datenaenderung. Genau dann soll die
        # Bruecke nachziehen, damit FPM den neuen Stand sieht.
        self._schedule_bridge_outbox_sync(reason="refresh_all_tabs")

    # ── Bruecke zu FPM ───────────────────────────────────────────────────
    def _schedule_bridge_outbox_sync(self, *, reason: str = "") -> None:
        """Schreibt Ausgabenvorschlaege und Sparziele traege in die Bruecke.

        Bis hierher geschah das nur, wenn jemand im LifePlanner-Dialog
        ausdruecklich darauf drueckte. Wer ein Sparziel anlegte und den Dialog
        nie oeffnete, dessen Ziel erreichte FPM nie - ohne Fehlermeldung, es
        blieb einfach leer. FPM haelt seine Seite umgekehrt seit jeher nach
        jeder Aenderung aktuell.

        Traege, weil beide Exporte die vollstaendigen Tabellen lesen. Mehrere
        Aenderungen kurz hintereinander sollen einen Lauf ergeben, nicht zehn.
        """
        if getattr(self, "_bridge_sync_pending", False):
            return
        self._bridge_sync_pending = True

        def _run() -> None:
            self._bridge_sync_pending = False
            self._sync_bridge_outboxes_safely()

        try:
            logger.debug("Bridge-Abgleich geplant (%s).", reason)
            QTimer.singleShot(1500, _run)
        except Exception:
            self._bridge_sync_pending = False
            self._sync_bridge_outboxes_safely()

    def _sync_bridge_outboxes_safely(self) -> None:
        """Ein Fehler hier bleibt folgenlos.

        Die Bruecke ist eine Spiegelung. Ein getrenntes Netzlaufwerk oder ein
        falsch gesetztes LIFEPLANNER_BRIDGE_DIR darf die Buchhaltung nicht
        stoeren - der Fehler gehoert ins Log, nicht vor den Nutzer.
        """
        if getattr(self, "_is_closing", False) and not getattr(
            self, "_bridge_sync_on_close", False
        ):
            return
        try:
            from model.lifeplanner_import_service import sync_default_outboxes

            expenses, savings = sync_default_outboxes(self.conn)
        except Exception:
            logger.warning(
                "Bridge-Outbox konnte nicht geschrieben werden", exc_info=True
            )
            return
        logger.debug(
            "Bridge-Outbox geschrieben: %s Ausgaben, %s Sparziele nach %s",
            expenses.count,
            savings.count,
            expenses.path.parent,
        )
        # Getrennt gefangen: Die Meldungen sind reine Anzeige. Fallen sie
        # aus, sollen die Outboxen oben trotzdem geschrieben sein.
        try:
            from model.lifeplanner_import_service import sync_host_notices

            anzahl = sync_host_notices(self.conn)
        except (OSError, sqlite3.Error, ValueError):
            logger.warning(
                "Meldungen fuer das Host-Dashboard konnten nicht geschrieben werden",
                exc_info=True,
            )
            return
        logger.debug("Host-Meldungen geschrieben: %s", anzahl)

    def _toggle_fullscreen(self, checked):
        """Toggle Vollbildmodus (F11)"""
        if checked:
            self.showFullScreen()
            self.statusBar().showMessage(tr("msg.fullscreen_enabled"), 2000)
        else:
            # Zurück zu Normal oder Maximiert
            if self.isMaximized():
                self.showMaximized()
            else:
                self.showNormal()
            self.statusBar().showMessage(tr("msg.fullscreen_disabled"), 2000)

        self.settings.set("window_is_fullscreen", checked)

    def _toggle_maximize(self, checked):
        """Toggle Maximiert-Modus (F10)"""
        if self.isFullScreen():
            # Wenn fullscreen, erst aus fullscreen
            self.showNormal()
            self.settings.set("window_is_fullscreen", False)

        if checked:
            self.showMaximized()
            self.statusBar().showMessage(tr("msg.window_maximized"), 2000)
        else:
            self.showNormal()
            self.statusBar().showMessage(tr("msg.window_normalized"), 2000)

        self.settings.set("window_is_maximized", checked)

    def changeEvent(self, event):
        """Wird aufgerufen wenn Fenster-State sich ändert (minimize, maximize, etc)"""
        from PySide6.QtGui import QWindowStateChangeEvent

        # Maximierungsstatus merken - nur wenn settings schon initialisiert ist
        if isinstance(event, QWindowStateChangeEvent) and hasattr(self, "settings"):
            self.settings.set("window_is_maximized", self.isMaximized())
        super().changeEvent(event)

    def prepare_for_update_exit(self) -> bool:
        """Prüft einen Update-Neustart, bevor der externe Updater startet.

        Wichtig unter Windows: Der Updater darf nicht bereits als detached
        Prozess laufen und *danach* erst auf einen abbrechbaren Speichern-
        Dialog treffen. Sonst wartet der Helfer auf eine App, die der Nutzer
        bewusst offen gelassen hat, und ältere Versionen versuchten nach dem
        Timeout sogar trotzdem zu kopieren.

        Auto-Save braucht keine Vorabfrage. Bei manuellem Speichern wird die
        Entscheidung hier einmal eingeholt und für den unmittelbar folgenden
        ``closeEvent`` vorgemerkt.
        """
        if hasattr(self, "settings") and self.settings.auto_save:
            return True
        if getattr(self, "_suppress_close_confirm", False):
            self._update_exit_preapproved = True
            return True

        reply = QMessageBox.question(
            self,
            tr("msg.confirm_exit"),
            tr("btn.moechten_sie_das_budget"),
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if reply == QMessageBox.Cancel:
            return False
        if reply == QMessageBox.Save:
            self._save_widget_before_leave(
                getattr(self, "budget_tab", None), reason=tr("btn.close")
            )
        self._update_exit_preapproved = True
        return True

    def closeEvent(self, event):
        """Wird beim Schließen des Fensters aufgerufen"""
        # Speichere Fenster-State BEVOR wir fragen (nur wenn settings existiert)
        if hasattr(self, "settings"):
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

        # Letzter Stand in die Bruecke. Wer ein Sparziel anlegt und gleich
        # schliesst, wartet sonst bis zum naechsten Start darauf, dass FPM es
        # sieht. Der traege Zeitgeber kaeme hier nicht mehr zum Zug.
        self._bridge_sync_on_close = True
        self._sync_bridge_outboxes_safely()

        # Der Update-Dialog hat die Save/Discard/Cancel-Entscheidung bereits
        # VOR dem Start des detached Updaters eingeholt. Nicht ein zweites Mal
        # fragen; damit kann "Abbrechen" nicht mehr nachträglich einen bereits
        # laufenden Windows-Updater zurücklassen.
        if getattr(self, "_update_exit_preapproved", False):
            self._update_exit_preapproved = False
            self._is_closing = True
            event.accept()
            return

        # Wenn Auto-Save aktiv: Einfach speichern und schließen
        if hasattr(self, "settings") and self.settings.auto_save:
            self._save_widget_before_leave(
                getattr(self, "budget_tab", None), reason=tr("btn.close")
            )
            self._is_closing = True
            event.accept()
            return

        # In Tests / headless: blockierenden Bestätigungsdialog überspringen.
        # exec() würde ohne Display ewig warten und den Prozess aufhängen.
        if getattr(self, "_suppress_close_confirm", False):
            self._is_closing = True
            event.accept()
            return

        # Wenn Auto-Save nicht aktiv: Einmal fragen ob gespeichert werden soll
        reply = QMessageBox.question(
            self,
            tr("msg.confirm_exit"),
            tr("btn.moechten_sie_das_budget"),
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )

        if reply == QMessageBox.Save:
            self._save_widget_before_leave(
                getattr(self, "budget_tab", None), reason=tr("btn.close")
            )
            self._is_closing = True
            event.accept()
        elif reply == QMessageBox.Discard:
            self._is_closing = True
            event.accept()
        else:  # Cancel
            self._is_closing = False
            event.ignore()

    def _save_encrypted_session(self):
        """Speichert verschlüsselte DB-Session falls vorhanden."""
        session = getattr(self, "_encrypted_session", None)
        if session:
            try:
                session.save()
            except Exception as e:
                logger.error(tr("msg.fehler_beim_speichern_der"), e)

    # =========================================================================
    # Setup-Assistent / Onboarding
    # =========================================================================
    def _start_setup_assistant(
        self, *, force: bool = False, db_existed_before: bool | None = None
    ) -> None:
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
                    db_path = configured_db_path(
                        self.settings.get("database_path", "budgetmanager.db")
                    )
                    db_existed = db_path.exists()
                except Exception:
                    db_existed = True

            dlg = SetupAssistantDialog(
                self, self.conn, self.settings, db_existed_before=db_existed
            )
            # Referenz behalten: verhindert, dass der Assistent je nach Qt/Python-
            # Lebensdauer nach dem Start sofort verschwindet.
            self._setup_assistant_dialog = dlg

            def _setup_finished(*_args) -> None:
                # WICHTIG: Nichts Schweres synchron im nativen finished-Signal
                # ausfuehren und die letzte Python-Referenz auf ``dlg`` hier noch
                # nicht entfernen. Diese Kombination lag im beobachteten
                # Fedora/Wayland+XCB-Absturzpfad nach "Fertig"; ohne nativen
                # Core-Stack bleibt sie die am staerksten belegte Ursache.
                if getattr(self, "_setup_assistant_finish_pending", False):
                    return
                self._setup_assistant_finish_pending = True

                timer = QTimer(self)
                timer.setSingleShot(True)
                self._setup_assistant_finalize_timer = timer

                def _finalize_after_native_close() -> None:
                    try:
                        # Der QDialog-Schliess-Stack ist jetzt verlassen. Den
                        # versteckten Assistenten erst hier zur Loeschung
                        # vormerken und danach die Python-Referenz freigeben.
                        try:
                            dlg.deleteLater()
                        except RuntimeError:
                            pass
                        if getattr(self, "_setup_assistant_dialog", None) is dlg:
                            self._setup_assistant_dialog = None

                        if getattr(
                            self, "_defer_startup_auto_backup_until_setup", False
                        ):
                            self._defer_startup_auto_backup_until_setup = False
                            logger.info(
                                "Setup-Assistent beendet; verschobenes "
                                "Auto-Backup wird zeitversetzt geprüft."
                            )
                            # Noch einen eigenen Event-Loop-Abstand lassen, damit
                            # deleteLater()/Fokus-/Fensterereignisse abgeschlossen
                            # sind, bevor Verschluesselung und ZIP-I/O beginnen.
                            self._schedule_startup_auto_backup(delay_ms=1500)
                    except RuntimeError:
                        logger.debug(
                            "Setup-Abschluss uebersprungen: MainWindow wurde zerstoert."
                        )
                    except Exception:
                        logger.exception(
                            "Setup-Abschluss konnte nicht finalisiert werden"
                        )
                    finally:
                        self._setup_assistant_finish_pending = False
                        if (
                            getattr(self, "_setup_assistant_finalize_timer", None)
                            is timer
                        ):
                            self._setup_assistant_finalize_timer = None
                        try:
                            timer.deleteLater()
                        except Exception as fehler:
                            _uebersprungen("_start_setup_assistant", fehler)

                timer.timeout.connect(_finalize_after_native_close)
                # 250 ms statt SingleShot(0): Unter XCB koennen nach closeEvent
                # noch native Fokus- und Destroy-Ereignisse nachlaufen.
                timer.start(250)

            dlg.finished.connect(_setup_finished)
            dlg.show()
            # Kein raise_()/activateWindow() beim Autostart: Unter Wayland/XCB kann
            # genau diese native Fokus-Aktivierung sporadisch segfaulten. Der
            # Assistent ist Kind des Hauptfensters und wird auch ohne Forcieren
            # sichtbar, bleibt aber stabiler.
            logger.info(
                "Setup-Assistent angezeigt (force=%s, db_existed_before=%s).",
                force,
                db_existed,
            )
        except Exception as e:
            logger.exception("Setup-Assistent konnte nicht gestartet werden")
            if getattr(self, "_defer_startup_auto_backup_until_setup", False):
                self._defer_startup_auto_backup_until_setup = False
                self._schedule_startup_auto_backup(delay_ms=750)
            QMessageBox.critical(
                self, tr("msg.error"), trf("msg.setup_assistent_fehler", e=str(e))
            )
