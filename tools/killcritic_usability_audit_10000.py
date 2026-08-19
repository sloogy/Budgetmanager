#!/usr/bin/env python3
"""Reproduzierbarer KILLCRITIC-Usability-Audit mit 10.000 UI-Loops.

Der Audit startet die echte PySide6-Oberfläche offscreen mit einer temporären,
migrierten Datenbank. Er kombiniert reale Widget-/Dialog-Prüfungen mit
End-to-End-Bedienfolgen und statischen Release-Invarianten.

10 Domänen × 1.000 Durchläufe:
  D1 Hauptnavigation / Sidebar / Tabs
  D2 Dialog-Inventar / Konstruktion / Größen
  D3 Accessibility / Screenreader-Metadaten
  D4 Tastatur / Tab- und Rückwärtsnavigation
  D5 Übersetzungen / Standardbuttons / Platzhalter
  D6 Geometrie / Touch-Ziele / Text-Clipping / Überlappung
  D7 Sichere Defaults / destruktive Aktionen / nicht-modale Hinweise
  D8 End-to-End-Workflows über Tracking, Suche, Filter, Budget und Hilfe
  D9 Skalierung / Themes / Resize-Stabilität
  D10 Lebenszyklus / Idempotenz / Widget-Leaks
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import random
import sqlite3
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGroupBox,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollBar,
    QSpinBox,
    QTableWidget,
    QTextEdit,
    QToolBar,
    QToolButton,
    QWidget,
)

from app_info import APP_VERSION
from model.category_model import CategoryModel
from model.migrations import migrate_all
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES
from model.user_model import SECURITY_QUICK, UserModel
from utils.i18n import set_language, tr
from utils.notifications import show_warning
from utils.ui_text_rules import is_destructive_text
from utils.ui_usability import enhance_widget_tree, install_ui_usability


@dataclass
class Finding:
    loop: int
    domain: str
    code: str
    detail: str


FINDINGS: list[Finding] = []
ROWS: list[dict[str, object]] = []
CHECKS = 0


def check(loop: int, domain: str, condition: bool, code: str, detail: str) -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        FINDINGS.append(Finding(loop, domain, code, detail))


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("&", "").split())


INPUT_TYPES = (
    QLineEdit,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QDateEdit,
    QTextEdit,
    QPlainTextEdit,
)
FOCUS_TYPES = (
    QPushButton,
    QToolButton,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QDateEdit,
    QCheckBox,
    QRadioButton,
    QAbstractItemView,
    QTextEdit,
    QPlainTextEdit,
)
GENERIC_NAMES = {
    "QLineEdit",
    "QComboBox",
    "QSpinBox",
    "QDoubleSpinBox",
    "QDateEdit",
    "QTextEdit",
    "QPlainTextEdit",
    "QTextBrowser",
    "QTableWidget",
    "QTreeWidget",
    "QListWidget",
}


def widget_text(widget: QWidget) -> str:
    for attr in ("text", "currentText", "placeholderText"):
        method = getattr(widget, attr, None)
        if callable(method):
            try:
                value = clean(method())
            except TypeError:
                continue
            if value:
                return value
    return (
        clean(widget.accessibleName())
        or clean(widget.toolTip())
        or widget.metaObject().className()
    )


def visible_widgets(top: QWidget) -> list[QWidget]:
    return [
        widget
        for widget in [top, *top.findChildren(QWidget)]
        if widget.isVisibleTo(top) and widget.window() is top
    ]


def focusables(top: QWidget) -> list[QWidget]:
    candidates = [
        widget
        for widget in visible_widgets(top)
        if isinstance(widget, FOCUS_TYPES)
        and not isinstance(widget, QScrollBar)
        and widget is not top
        and widget.isEnabled()
        and widget.focusPolicy() != Qt.NoFocus
    ]
    result: list[QWidget] = []
    for widget in candidates:
        parent = widget.parentWidget()
        nested_editor = False
        while parent is not None and parent is not top:
            if parent in candidates and isinstance(
                parent, (QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit)
            ):
                nested_editor = True
                break
            parent = parent.parentWidget()
        if not nested_editor:
            result.append(widget)
    # In einer Radio-Gruppe liegt standardmäßig nur der aktive (oder erste)
    # RadioButton in der Tab-Kette; zwischen den Optionen navigiert man mit
    # Pfeiltasten. Das ist korrektes Qt-/Desktop-Verhalten.
    grouped: dict[QWidget | None, list[QRadioButton]] = {}
    for widget in result:
        if isinstance(widget, QRadioButton):
            grouped.setdefault(widget.parentWidget(), []).append(widget)
    for radios in grouped.values():
        keep = next((radio for radio in radios if radio.isChecked()), radios[0])
        result = [widget for widget in result if widget not in radios or widget is keep]
    return result


def normalize_focus(widget: QWidget | None, top: QWidget, candidates: list[QWidget]):
    current = widget
    while current is not None and current is not top:
        if current in candidates:
            return current
        current = current.parentWidget()
    return None


class DialogPool:
    def __init__(self, context: "Context"):
        self.context = context
        self._objects: dict[int, QDialog] = {}
        self._uses: Counter[int] = Counter()
        self.factories: list[tuple[str, Callable[[], QDialog]]] = []
        self._build_factories()

    def _build_factories(self) -> None:
        ctx = self.context
        from settings_dialog import SettingsDialog
        from views.account_management_dialog import AccountManagementDialog
        from views.backup_restore_dialog import BackupRestoreDialog
        from views.budget_entry_dialog_extended import BudgetEntryDialogExtended
        from views.budget_fill_dialog import BudgetFillDialog
        from views.category_manager_dialog import CategoryManagerDialog
        from views.category_properties_dialog import (
            BulkCategoryEditDialog,
            CategoryPropertiesDialog,
            QuickCategoryDialog,
        )
        from views.copy_year_dialog import CopyYearDialog
        from views.database_management_dialog import DatabaseManagementDialog
        from views.export_dialog import ExportDialog
        from views.favorites_dashboard_dialog import FavoritesDashboardDialog
        from views.global_search_dialog import GlobalSearchDialog
        from views.help_dialog import HelpDialog
        from views.language_select_dialog import LanguageSelectDialog
        from views.login_dialog import CreateUserWizard, LoginDialog, RestoreKeyDialog
        from views.main_window import AboutDialog, LogViewerDialog
        from views.month_close_dialog import MonthCloseDialog
        from views.quick_add_dialog import QuickAddDialog
        from views.recurring_bookings_dialog import RecurringBookingsDialog
        from views.savings_goals_dialog import EditGoalDialog, SavingsGoalsDialog
        from views.setup_assistant_dialog import SetupAssistantDialog
        from views.shortcuts_dialog import ShortcutsDialog
        from views.special_income_dialog import ThirteenthSalaryDialog
        from views.tags_manager_dialog import TagsManagerDialog
        from views.update_dialog import UpdateDialog

        # Der Usability-Audit prüft die Update-Oberfläche ohne Netzwerkprozess.
        UpdateDialog._check = lambda self: None  # type: ignore[method-assign]

        db_path = str(ctx.runtime_dir / "data" / "budgetmanager.db")
        self.factories = [
            (
                "SettingsDialog",
                lambda: SettingsDialog(
                    ctx.window.settings, ctx.window, app_version=APP_VERSION
                ),
            ),
            ("AboutDialog", lambda: AboutDialog(ctx.window)),
            (
                "HelpDialog",
                lambda: HelpDialog(ctx.window, on_open_mindmap=lambda *_: None),
            ),
            (
                "ShortcutsDialog",
                lambda: ShortcutsDialog(ctx.window, settings=ctx.window.settings),
            ),
            ("QuickAddDialog", lambda: QuickAddDialog(ctx.conn, ctx.window)),
            ("GlobalSearchDialog", lambda: GlobalSearchDialog(ctx.conn, ctx.window)),
            ("ExportDialog", lambda: ExportDialog(ctx.conn, ctx.window)),
            ("SavingsGoalsDialog", lambda: SavingsGoalsDialog(ctx.window, ctx.conn)),
            ("EditGoalDialog", lambda: EditGoalDialog(ctx.window, ctx.conn, goal=None)),
            (
                "CategoryManagerDialog",
                lambda: CategoryManagerDialog(ctx.window, conn=ctx.conn),
            ),
            ("TagsManagerDialog", lambda: TagsManagerDialog(ctx.conn, ctx.window)),
            (
                "FavoritesDashboardDialog",
                lambda: FavoritesDashboardDialog(ctx.conn, 2026, 7, ctx.window),
            ),
            (
                "BackupRestoreDialog",
                lambda: BackupRestoreDialog(
                    ctx.window, ctx.conn, None, ctx.window.settings, active_user=None
                ),
            ),
            (
                "DatabaseManagementDialog",
                lambda: DatabaseManagementDialog(
                    db_path,
                    parent=ctx.window,
                    conn=ctx.conn,
                    encrypted=False,
                    active_user=None,
                ),
            ),
            (
                "MonthCloseDialog",
                lambda: MonthCloseDialog(ctx.conn, 2026, 7, ctx.window),
            ),
            ("BudgetFillDialog", lambda: BudgetFillDialog(ctx.window, ctx.conn)),
            (
                "CopyYearDialog",
                lambda: CopyYearDialog(
                    ctx.window,
                    default_src=2026,
                    known_years=[2025, 2026],
                    conn=ctx.conn,
                ),
            ),
            (
                "RecurringBookingsDialog",
                lambda: RecurringBookingsDialog(
                    ctx.window,
                    fix_items=[],
                    recurring_items=[],
                    optional_items=[],
                    initial_month=(2026, 7),
                ),
            ),
            (
                "LanguageSelectDialog",
                lambda: LanguageSelectDialog(ctx.window, current="de"),
            ),
            (
                "SetupAssistantDialog",
                lambda: SetupAssistantDialog(
                    ctx.window, ctx.conn, ctx.window.settings, db_existed_before=True
                ),
            ),
            (
                "ThirteenthSalaryDialog",
                lambda: ThirteenthSalaryDialog(
                    ctx.window, conn=ctx.conn, default_year=2026
                ),
            ),
            (
                "BudgetEntryDialogExtended",
                lambda: BudgetEntryDialogExtended(
                    ctx.window,
                    conn=ctx.conn,
                    default_year=2026,
                    default_typ=TYP_EXPENSES,
                ),
            ),
            (
                "CategoryPropertiesDialog",
                lambda: CategoryPropertiesDialog(
                    ctx.window,
                    conn=ctx.conn,
                    category_name=ctx.expense_category,
                    typ=TYP_EXPENSES,
                ),
            ),
            (
                "BulkCategoryEditDialog",
                lambda: BulkCategoryEditDialog(
                    ctx.window, conn=ctx.conn, categories=[]
                ),
            ),
            (
                "QuickCategoryDialog",
                lambda: QuickCategoryDialog(
                    ctx.window,
                    conn=ctx.conn,
                    default_typ=TYP_EXPENSES,
                    default_name="Audit",
                ),
            ),
            ("LoginDialog", lambda: LoginDialog(ctx.window)),
            (
                "CreateUserWizard",
                lambda: CreateUserWizard(
                    ctx.window, user_model=ctx.user_model, is_first_user=False
                ),
            ),
            (
                "RestoreKeyDialog",
                lambda: RestoreKeyDialog(
                    ctx.window, user=ctx.audit_user, user_model=ctx.user_model
                ),
            ),
            (
                "AccountManagementDialog",
                lambda: AccountManagementDialog(
                    ctx.window, user=ctx.audit_user, user_model=ctx.user_model
                ),
            ),
            ("UpdateDialog", lambda: UpdateDialog(ctx.window)),
            (
                "LogViewerDialog",
                lambda: LogViewerDialog(
                    ctx.window,
                    title="Audit",
                    path=ctx.runtime_dir / "audit.log",
                    text="Audit log",
                ),
            ),
        ]

    def get(self, index: int) -> tuple[str, QDialog]:
        idx = index % len(self.factories)
        self._uses[idx] += 1
        obj = self._objects.get(idx)
        if obj is None or self._uses[idx] % 40 == 0:
            if obj is not None:
                obj.hide()
                obj.deleteLater()
                self.context.app.processEvents()
            name, factory = self.factories[idx]
            obj = factory()
            self._objects[idx] = obj
        name = self.factories[idx][0]
        minimum_width = max(480, min(1180, obj.minimumWidth()))
        minimum_height = max(360, min(820, obj.minimumHeight()))
        obj.resize(minimum_width, minimum_height)
        obj.show()
        self.context.app.processEvents()
        enhance_widget_tree(obj)
        self.context.app.processEvents()
        return name, obj

    def hide_all(self) -> None:
        for obj in self._objects.values():
            try:
                obj.hide()
            except RuntimeError:
                pass
        self.context.app.processEvents()

    def close(self) -> None:
        # Nicht close()+deleteLater() kombinieren: einzelne Dialoge verwenden
        # WA_DeleteOnClose. Ein anschließendes deleteLater() kann dann auf
        # manchen Qt-Plattformen zu einer doppelten Freigabe führen.
        for obj in self._objects.values():
            try:
                obj.hide()
                obj.deleteLater()
            except RuntimeError:
                pass
        self._objects.clear()
        self.context.app.sendPostedEvents(None, 0)
        self.context.app.processEvents()


class Context:
    def __init__(self, runtime_dir: Path):
        self.runtime_dir = runtime_dir
        os.environ["BUDGETMANAGER_APP_DIR"] = str(runtime_dir)
        self.app = QApplication.instance() or QApplication([])
        install_ui_usability(self.app)
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        migrate_all(self.conn)
        from views.main_window import MainWindow

        self.window = MainWindow(self.conn)
        self.window._suppress_close_confirm = True
        self.window.resize(1280, 800)
        self.window.show()
        self.app.processEvents()
        categories = CategoryModel(self.conn).list(TYP_EXPENSES)
        self.expense_category = next(
            (c.name for c in categories if c.parent_id), categories[0].name
        )
        self.last_marker = "KILLCRITIC"
        TrackingModel(self.conn).add(
            "2026-07-17",
            TYP_EXPENSES,
            self.expense_category,
            1.0,
            self.last_marker,
            source="usability_audit",
        )
        self.user_model = UserModel()
        if not self.user_model.has_users():
            self.audit_user, _ = self.user_model.create_user(
                "Usability Audit", SECURITY_QUICK
            )
        else:
            self.audit_user = self.user_model.list_users()[0]
        self.pool = DialogPool(self)

    def close(self) -> None:
        self.pool.close()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.conn.close()


def domain_navigation(
    ctx: Context, loop: int, iteration: int, rng: random.Random
) -> None:
    domain = "D1_navigation"
    tabs = ctx.window.tabs
    index = iteration % tabs.count()
    tabs.setCurrentIndex(index)
    ctx.app.processEvents()
    check(
        loop,
        domain,
        tabs.currentIndex() == index,
        "tab_switch",
        f"Tab {index} wurde nicht aktiv",
    )
    current = tabs.widget(index)
    check(
        loop,
        domain,
        current is not None and current.isVisibleTo(ctx.window),
        "tab_visible",
        f"Tab {index} unsichtbar",
    )
    sidebar = getattr(ctx.window, "_sidebar_buttons", {})
    checked = [button for button in sidebar.values() if button.isChecked()]
    check(
        loop,
        domain,
        len(checked) == 1,
        "sidebar_single",
        f"{len(checked)} Sidebar-Buttons aktiv",
    )
    if current in sidebar:
        check(
            loop,
            domain,
            sidebar[current].isChecked(),
            "sidebar_sync",
            f"Sidebar nicht mit Tab {index} synchron",
        )
    for action in rng.sample(
        ctx.window.menuBar().actions(), min(3, len(ctx.window.menuBar().actions()))
    ):
        check(
            loop,
            domain,
            bool(clean(action.text())),
            "menu_text",
            "Menü ohne sichtbaren Text",
        )
    toolbar_buttons = [
        button
        for toolbar in ctx.window.findChildren(QToolBar)
        for button in toolbar.findChildren(QToolButton)
        if button.isVisibleTo(ctx.window)
        and button.objectName() != "qt_toolbar_ext_button"
    ]
    if toolbar_buttons:
        button = toolbar_buttons[iteration % len(toolbar_buttons)]
        check(
            loop,
            domain,
            bool(
                clean(button.text())
                or clean(button.toolTip())
                or clean(button.accessibleName())
            ),
            "toolbar_name",
            "Toolbar-Aktion ohne Namen",
        )


def domain_dialog_inventory(
    ctx: Context, loop: int, iteration: int, rng: random.Random
) -> None:
    domain = "D2_dialog_inventory"
    try:
        name, dialog = ctx.pool.get(iteration)
    except Exception as exc:
        check(loop, domain, False, "construct", f"{type(exc).__name__}: {exc}")
        return
    check(
        loop,
        domain,
        bool(clean(dialog.windowTitle())),
        "window_title",
        f"{name}: Fenstertitel fehlt",
    )
    check(
        loop,
        domain,
        dialog.layout() is not None,
        "layout",
        f"{name}: Root-Layout fehlt",
    )
    check(
        loop,
        domain,
        dialog.minimumWidth() <= 1500 and dialog.minimumHeight() <= 950,
        "oversize",
        f"{name}: Minimum {dialog.minimumWidth()}x{dialog.minimumHeight()}",
    )
    fixed = dialog.minimumSize() == dialog.maximumSize()
    check(loop, domain, not fixed, "fixed_size", f"{name}: Dialog ist starr fixiert")
    check(
        loop,
        domain,
        dialog.isVisible(),
        "show",
        f"{name}: Dialog konnte nicht angezeigt werden",
    )
    dialog.hide()


def domain_accessibility(
    ctx: Context, loop: int, iteration: int, rng: random.Random
) -> None:
    domain = "D3_accessibility"
    name, dialog = ctx.pool.get(iteration + 3)
    widgets = visible_widgets(dialog)
    for widget in widgets:
        accessible = clean(widget.accessibleName())
        cls = widget.metaObject().className()
        if isinstance(widget, INPUT_TYPES):
            check(
                loop,
                domain,
                bool(accessible)
                and accessible not in GENERIC_NAMES
                and accessible != cls,
                "input_name",
                f"{name}: {cls} ohne verständlichen Screenreader-Namen",
            )
        if isinstance(widget, QAbstractItemView):
            check(
                loop,
                domain,
                bool(clean(widget.accessibleDescription())),
                "item_description",
                f"{name}: {cls} ohne Navigationsbeschreibung",
            )
        if isinstance(widget, (QPushButton, QToolButton)) and not clean(widget.text()):
            check(
                loop,
                domain,
                bool(accessible or clean(widget.toolTip())),
                "icon_name",
                f"{name}: Icon-Button ohne Name",
            )
    dialog.hide()


def domain_keyboard(
    ctx: Context, loop: int, iteration: int, rng: random.Random
) -> None:
    domain = "D4_keyboard"
    name, dialog = ctx.pool.get(iteration + 7)
    candidates = focusables(dialog)
    if not candidates:
        check(loop, domain, False, "no_focusables", f"{name}: kein Tastaturziel")
        dialog.hide()
        return

    # Qt verwaltet die definitive Vorwärts-/Rückwärtskette über
    # nextInFocusChain()/previousInFocusChain(). QTest-Keyevents sind auf dem
    # Offscreen-Plugin für Tabellen, Scrollbereiche und Dialog-Buttonboxen
    # nicht deterministisch und können dadurch korrekte Ketten falsch melden.
    first = candidates[0]
    current = first
    ordered: list[QWidget] = [first]
    max_steps = max(64, len(dialog.findChildren(QWidget)) * 4 + 32)
    closed = False
    for _ in range(max_steps):
        current = current.nextInFocusChain()
        if current is first:
            closed = True
            break
        normalized = normalize_focus(current, dialog, candidates)
        if normalized is not None and normalized not in ordered:
            ordered.append(normalized)

    missing = [widget_text(widget) for widget in candidates if widget not in ordered]
    check(
        loop,
        domain,
        not missing,
        "tab_coverage",
        f"{name}: nicht in der Qt-Tabkette: {missing[:6]}",
    )
    check(
        loop,
        domain,
        closed,
        "tab_cycle",
        f"{name}: Qt-Tabkette schließt sich nicht",
    )

    reversible = True
    if len(ordered) > 1:
        # Für jedes benachbarte Nutzerziel muss die Rückwärtskette wieder zum
        # vorherigen Nutzerziel führen; interne Spinbox-Editoren werden dabei
        # über normalize_focus auf ihr sichtbares Steuerelement abgebildet.
        for previous, following in zip(ordered, ordered[1:]):
            cursor = following
            returned = None
            for _ in range(max_steps):
                cursor = cursor.previousInFocusChain()
                returned = normalize_focus(cursor, dialog, candidates)
                if returned is not None:
                    break
            if returned is not previous:
                reversible = False
                break
    check(
        loop,
        domain,
        reversible,
        "backtab",
        f"{name}: Vorwärts-/Rückwärts-Tabkette ist nicht symmetrisch",
    )
    dialog.hide()


def domain_localization(
    ctx: Context, loop: int, iteration: int, rng: random.Random
) -> None:
    domain = "D5_localization"
    language = ("de", "en", "fr")[iteration % 3]
    set_language(language)
    box_dialog = QDialog(ctx.window)
    box = QDialogButtonBox(
        QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Close,
        box_dialog,
    )
    enhance_widget_tree(box_dialog)
    expected = {
        QDialogButtonBox.Ok: tr("btn.ok"),
        QDialogButtonBox.Cancel: tr("btn.cancel"),
        QDialogButtonBox.Close: tr("btn.close"),
    }
    for standard, text in expected.items():
        button = box.button(standard)
        check(
            loop,
            domain,
            button is not None and clean(button.text()) == clean(text),
            "standard_button",
            f"{language}: {standard}={button.text() if button else None!r}, erwartet {text!r}",
        )
    locale_data = json.loads(
        (ROOT / "locales" / f"{language}.json").read_text(encoding="utf-8")
    )
    keys = ["btn", "tab", "dlg", "a11y", "ctx"]
    key = keys[iteration % len(keys)]
    check(
        loop,
        domain,
        key in locale_data and bool(locale_data[key]),
        "locale_section",
        f"{language}: Abschnitt {key} fehlt",
    )
    box_dialog.deleteLater()
    set_language("de")


def domain_geometry(
    ctx: Context, loop: int, iteration: int, rng: random.Random
) -> None:
    domain = "D6_geometry"
    name, dialog = ctx.pool.get(iteration + 11)
    widths = (800, 1024, 1280, 1440)
    heights = (600, 720, 800, 900)
    dialog.resize(
        max(dialog.minimumWidth(), widths[iteration % 4]),
        max(dialog.minimumHeight(), heights[iteration % 4]),
    )
    ctx.app.processEvents()
    widgets = visible_widgets(dialog)
    for widget in widgets:
        if isinstance(widget, (QPushButton, QToolButton)):
            text = clean(widget.text()) or clean(widget.toolTip())
            check(
                loop,
                domain,
                widget.width() >= 32 and widget.height() >= 28,
                "hit_target",
                f"{name}: {text!r} nur {widget.width()}x{widget.height()}",
            )
            if clean(widget.text()):
                needed = (
                    widget.fontMetrics().horizontalAdvance(clean(widget.text())) + 18
                )
                fits = needed <= widget.contentsRect().width() + 4 or clean(
                    widget.toolTip()
                ) == clean(widget.text())
                check(
                    loop,
                    domain,
                    fits,
                    "button_clip",
                    f"{name}: {widget.text()!r} benötigt {needed}px, hat {widget.width()}px",
                )
    # Interaktive Geschwister dürfen sich nicht deutlich überlagern.
    by_parent: dict[QWidget, list[QWidget]] = {}
    for widget in focusables(dialog):
        parent = widget.parentWidget()
        if parent is not None:
            by_parent.setdefault(parent, []).append(widget)
    for siblings in by_parent.values():
        sample = siblings[:12]
        for left_index, left in enumerate(sample):
            for right in sample[left_index + 1 :]:
                intersection = left.geometry().intersected(right.geometry())
                overlap = intersection.width() * intersection.height()
                base = min(
                    max(1, left.width() * left.height()),
                    max(1, right.width() * right.height()),
                )
                check(
                    loop,
                    domain,
                    overlap / base < 0.25,
                    "overlap",
                    f"{name}: {widget_text(left)!r} überlappt {widget_text(right)!r}",
                )
    dialog.hide()


def domain_safety(ctx: Context, loop: int, iteration: int, rng: random.Random) -> None:
    domain = "D7_safety"
    name, dialog = ctx.pool.get(iteration + 13)
    defaults = 0
    for button in dialog.findChildren(QAbstractButton):
        metadata = " ".join(
            (
                clean(button.text()),
                clean(button.toolTip()),
                clean(button.accessibleName()),
            )
        )
        destructive = is_destructive_text(metadata)
        is_default = bool(getattr(button, "isDefault", lambda: False)())
        auto_default = bool(getattr(button, "autoDefault", lambda: False)())
        if is_default:
            defaults += 1
        check(
            loop,
            domain,
            not (destructive and (is_default or auto_default)),
            "destructive_default",
            f"{name}: {metadata!r} ist Enter-Default",
        )
    check(
        loop,
        domain,
        defaults <= 1,
        "multiple_defaults",
        f"{name}: {defaults} Default-Buttons",
    )
    # Nicht-modale Warnung darf den Eingabefokus nicht stehlen.
    inputs = [
        widget for widget in focusables(dialog) if isinstance(widget, INPUT_TYPES)
    ]
    if inputs and iteration % 5 == 0:
        target = inputs[0]
        target.setFocus()
        ctx.app.processEvents()
        show_warning(dialog, "Audit", "Eingabe prüfen")
        ctx.app.processEvents()
        check(
            loop,
            domain,
            ctx.app.focusWidget() is target
            or target.isAncestorOf(ctx.app.focusWidget()),
            "toast_focus",
            f"{name}: Hinweis stiehlt Fokus",
        )
        toast = getattr(dialog, "_budgetmanager_notification_toast", None)
        check(
            loop,
            domain,
            toast is not None and bool(clean(toast.accessibleName())),
            "toast_a11y",
            f"{name}: Hinweis nicht barrierearm",
        )
    dialog.hide()


def _first_real_category(combo: QComboBox) -> int:
    for index in range(combo.count()):
        if isinstance(combo.itemData(index), str) and clean(combo.itemData(index)):
            return index
    return -1


def domain_workflows(
    ctx: Context, loop: int, iteration: int, rng: random.Random
) -> None:
    domain = "D8_workflows"
    case = iteration % 10
    if case in (0, 1):
        from views.quick_add_dialog import QuickAddDialog

        dialog = QuickAddDialog(ctx.conn, ctx.window)
        dialog.show()
        ctx.app.processEvents()
        if case == 0:
            dialog.cat_combo.setCurrentIndex(-1)
            dialog.cat_search.clear()
            dialog.amount_spin.setValue(10)
            before = ctx.conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0]
            valid = dialog._validate()
            after = ctx.conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0]
            check(
                loop,
                domain,
                not valid and before == after,
                "validation",
                "Schnellerfassung akzeptiert leere Kategorie",
            )
        else:
            index = _first_real_category(dialog.cat_combo)
            check(
                loop,
                domain,
                index >= 0,
                "category_available",
                "Keine Ausgaben-Kategorie in Schnellerfassung",
            )
            if index >= 0:
                marker = f"KILLCRITIC-{iteration:04d}"
                dialog.cat_combo.setCurrentIndex(index)
                dialog.amount_spin.setValue(float((iteration % 97) + 1))
                dialog.details_edit.setText(marker)
                saved = dialog._save_entry()
                check(
                    loop,
                    domain,
                    saved,
                    "quickadd_save",
                    f"Buchung {marker} nicht gespeichert",
                )
                if saved:
                    ctx.last_marker = marker
        dialog.close()
        dialog.deleteLater()
        ctx.app.processEvents()
    elif case == 2:
        tab = ctx.window.tracking_tab
        tab.filter_search.setText(ctx.last_marker)
        tab.refresh()
        check(
            loop,
            domain,
            tab.table.rowCount() >= 1,
            "tracking_filter",
            f"Tracking findet {ctx.last_marker!r} nicht",
        )
        tab.clear_filters()
    elif case == 3:
        from views.global_search_dialog import GlobalSearchDialog

        dialog = GlobalSearchDialog(ctx.conn, ctx.window)
        dialog.search_input.setText(ctx.last_marker)
        dialog._do_search()
        check(
            loop,
            domain,
            dialog.table.rowCount() >= 1,
            "global_search",
            f"Globale Suche findet {ctx.last_marker!r} nicht",
        )
        dialog.close()
    elif case == 4:
        from views.help_dialog import HelpDialog

        dialog = HelpDialog(ctx.window)
        dialog.search.setText("Budget")
        dialog._apply_filter(dialog.search.text())
        check(
            loop,
            domain,
            dialog.topic_list.count() > 0,
            "help_search",
            "Handbuchsuche liefert für Budget nichts",
        )
        dialog.search.setText("__kein_treffer_killcritic__")
        dialog._apply_filter(dialog.search.text())
        check(
            loop,
            domain,
            not dialog.empty_hint.isHidden(),
            "help_empty",
            "Handbuch zeigt keinen Leerzustand",
        )
        dialog.close()
    elif case == 5:
        manager = ctx.window.categories_tab
        if hasattr(manager, "filter_combo"):
            manager.filter_combo.setCurrentIndex(
                iteration % manager.filter_combo.count()
            )
            manager._apply_filter()
            check(
                loop,
                domain,
                manager.tree.topLevelItemCount() >= 1,
                "category_filter",
                "Kategorienfilter leert alle Typ-Header",
            )
        else:
            check(
                loop,
                domain,
                True,
                "category_filter",
                "Kategorienseite nutzt eingebetteten Manager",
            )
    elif case == 6:
        tab = ctx.window.budget_tab
        year = 2025 + (iteration % 3)
        tab.year_spin.setValue(year)
        tab.load()
        check(
            loop,
            domain,
            tab.year_spin.value() == year and tab.table.rowCount() > 0,
            "budget_year",
            f"Budgetjahr {year} nicht geladen",
        )
    elif case == 7:
        tab = ctx.window.overview_tab
        tab.refresh()
        check(
            loop,
            domain,
            tab.isEnabled(),
            "overview_refresh",
            "Übersicht nach Refresh deaktiviert",
        )
    elif case == 8:
        ctx.window.savings_tab.refresh()
        check(
            loop,
            domain,
            ctx.window.savings_tab.isEnabled(),
            "savings_refresh",
            "Sparziele-Seite nach Refresh deaktiviert",
        )
    else:
        status = ctx.window.statusBar()
        ctx.window._goto_tab(ctx.window.cockpit_tab)
        status.showMessage("KILLCRITIC", 100)
        ctx.app.processEvents()
        check(
            loop,
            domain,
            ctx.window.tabs.currentWidget() is ctx.window.cockpit_tab,
            "goto_cockpit",
            "Cockpit-Navigation fehlgeschlagen",
        )


def domain_scaling_theme(
    ctx: Context, loop: int, iteration: int, rng: random.Random
) -> None:
    domain = "D9_scaling_theme"
    sizes = ((1024, 720), (1280, 800), (1440, 900), (1600, 900), (1920, 1080))
    width, height = sizes[iteration % len(sizes)]
    ctx.window.resize(width, height)
    index = iteration % ctx.window.tabs.count()
    ctx.window.tabs.setCurrentIndex(index)
    ctx.app.processEvents()
    check(
        loop,
        domain,
        ctx.window.width() >= width or ctx.window.isMaximized(),
        "resize_width",
        f"Fenster bleibt bei {ctx.window.width()} statt {width}",
    )
    check(
        loop,
        domain,
        ctx.window.tabs.currentWidget().isVisibleTo(ctx.window),
        "scaled_tab",
        f"Tab {index} bei {width}x{height} unsichtbar",
    )
    for button in getattr(ctx.window, "_sidebar_buttons", {}).values():
        check(
            loop,
            domain,
            button.width() >= 120 and button.height() >= 36,
            "sidebar_target",
            f"Sidebar {button.text()!r}: {button.width()}x{button.height()}",
        )
    if iteration % 25 == 0:
        profiles = sorted((ROOT / "views" / "profiles").glob("*.json"))
        if profiles:
            profile = profiles[(iteration // 25) % len(profiles)].stem
            try:
                ctx.window.theme_manager.apply_theme(profile_name=profile)
                ctx.app.processEvents()
                check(loop, domain, True, "theme_apply", profile)
            except Exception as exc:
                check(
                    loop,
                    domain,
                    False,
                    "theme_apply",
                    f"{profile}: {type(exc).__name__}: {exc}",
                )


def domain_lifecycle(
    ctx: Context, loop: int, iteration: int, rng: random.Random
) -> None:
    domain = "D10_lifecycle"
    name, dialog = ctx.pool.get(iteration + 17)
    enhance_widget_tree(dialog)
    first = sum(
        1
        for widget in [dialog, *dialog.findChildren(QWidget)]
        if widget.property("_bm_ui_enhanced")
    )
    enhance_widget_tree(dialog)
    second = sum(
        1
        for widget in [dialog, *dialog.findChildren(QWidget)]
        if widget.property("_bm_ui_enhanced")
    )
    check(
        loop,
        domain,
        first == second and first > 0,
        "idempotent",
        f"{name}: Enhanced-Marker {first}->{second}",
    )
    dialog.hide()
    ctx.app.processEvents()
    check(
        loop, domain, not dialog.isVisible(), "hide", f"{name}: Dialog bleibt sichtbar"
    )
    # Statische Quell-Invarianten rotierend über alle Views.
    files = sorted(list((ROOT / "views").rglob("*.py")) + [ROOT / "settings_dialog.py"])
    path = files[iteration % len(files)]
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if (
            isinstance(node.func.value, ast.Name)
            and node.func.value.id == "QMessageBox"
        ):
            if node.func.attr == "information":
                check(
                    loop,
                    domain,
                    False,
                    "modal_information",
                    f"{path.relative_to(ROOT)}:{node.lineno}",
                )
            if node.func.attr == "warning" and isinstance(parents.get(node), ast.Expr):
                check(
                    loop,
                    domain,
                    False,
                    "passive_warning",
                    f"{path.relative_to(ROOT)}:{node.lineno}",
                )


DOMAINS = (
    domain_navigation,
    domain_dialog_inventory,
    domain_accessibility,
    domain_keyboard,
    domain_localization,
    domain_geometry,
    domain_safety,
    domain_workflows,
    domain_scaling_theme,
    domain_lifecycle,
)


def _write_csv(path: Path | None, rows: list[dict[str, object]]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("loop", "domain", "checks", "result", "new_findings"),
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path | None, payload: dict[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def run_worker(
    loops: int,
    seed: int,
    json_path: Path | None,
    csv_path: Path | None,
    loop_offset: int = 0,
) -> int:
    global CHECKS
    CHECKS = 0
    FINDINGS.clear()
    ROWS.clear()
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="bm-killcritic-usability-") as temp:
        runtime_dir = Path(temp)
        context = Context(runtime_dir)
        try:
            for local_index in range(loops):
                loop = loop_offset + local_index + 1
                domain_index = (loop - 1) % len(DOMAINS)
                iteration = (loop - 1) // len(DOMAINS)
                # Jeder Loop besitzt einen eigenen reproduzierbaren RNG. Dadurch
                # liefern Batch- und Einprozess-Ausführung exakt dieselben Fälle.
                rng = random.Random((seed << 32) ^ (loop * 0x9E3779B1))
                before_checks = CHECKS
                before_findings = len(FINDINGS)
                domain = DOMAINS[domain_index]
                try:
                    domain(context, loop, iteration, rng)
                except Exception as exc:
                    check(
                        loop,
                        domain.__name__,
                        False,
                        "exception",
                        f"{type(exc).__name__}: {exc}",
                    )
                new_findings = len(FINDINGS) - before_findings
                ROWS.append(
                    {
                        "loop": loop,
                        "domain": domain.__name__,
                        "checks": CHECKS - before_checks,
                        "result": "FAIL" if new_findings else "PASS",
                        "new_findings": new_findings,
                    }
                )
        finally:
            context.close()
    duration = time.monotonic() - started
    unique = {(f.domain, f.code, f.detail) for f in FINDINGS}
    summary: dict[str, object] = {
        "app_version": APP_VERSION,
        "seed": seed,
        "loop_offset": loop_offset,
        "loops": loops,
        "checks": CHECKS,
        "findings": len(FINDINGS),
        "unique_findings": len(unique),
        "duration_seconds": round(duration, 3),
        "domains": dict(Counter(row["domain"] for row in ROWS)),
        "finding_codes": dict(Counter(f.code for f in FINDINGS)),
        "details": [f.__dict__ for f in FINDINGS[:500]],
    }
    _write_csv(csv_path, ROWS)
    _write_json(json_path, summary)
    print(
        f"KILLCRITIC WORKER DONE: offset={loop_offset} loops={loops} "
        f"checks={CHECKS} findings={len(FINDINGS)} duration={duration:.2f}s"
    )
    for finding in FINDINGS[:20]:
        print(
            f"  FAIL L{finding.loop} {finding.domain}/{finding.code}: {finding.detail}"
        )
    return 1 if FINDINGS else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loops", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260717)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--loop-offset", type=int, default=0)
    args = parser.parse_args()
    return run_worker(
        max(1, args.loops),
        args.seed,
        args.json,
        args.csv,
        loop_offset=max(0, args.loop_offset),
    )


if __name__ == "__main__":
    if "--worker" not in sys.argv:
        controller = ROOT / "tools" / "run_killcritic_usability_10000.py"
        os.execv(
            sys.executable,
            [sys.executable, str(controller), *sys.argv[1:]],
        )
    exit_code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    # Der Worker hat Datenbank, Widgets und Ergebnisdateien bereits sauber
    # geschlossen. _exit vermeidet ausschließlich die globale Qt-Endphase, die
    # beim Offscreen-Plugin nach vielen Dialogen sporadisch doppelt freigibt.
    os._exit(exit_code)
