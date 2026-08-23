"""Hilfe-Menü der Menüleiste – Aufbau nach gängigen Desktop-Richtlinien.

Ausgelagert aus ``views/main_window.py`` (v2.2.38). Der frühere Aufbau war eine
flache Liste aus zwölf gleichrangigen Einträgen, in der Anwenderthemen
(Handbuch, Tastenkürzel) und Werkzeugthemen (Protokolle, Diagnosepakete)
unsortiert nebeneinander standen.

Angewandte Richtlinien (GNOME HIG, Windows App Design, Apple HIG – die drei
sind sich in diesen Punkten einig):

1. **Kurz halten.** Ein Menü soll auf einen Blick erfassbar sein. Selten
   gebrauchte Werkzeuge wandern in Untermenüs statt in die oberste Ebene.
2. **Gruppieren statt aufzählen.** Trennlinien bilden Sinnabschnitte:
   Nachschlagen · Lernen · Problembehandlung · Version · Über.
3. **Auslassungspunkte nur bei Rückfrage.** ``…`` steht ausschließlich vor
   Befehlen, die einen Dialog öffnen. Befehle, die sofort etwas ausführen –
   etwa einen Ordner öffnen – bekommen keine.
4. **Ein einheitliches Auslassungszeichen.** Vorher standen ``...`` (drei
   Punkte) und ``…`` (ein Zeichen) gemischt nebeneinander.
5. **Eindeutige Zugriffstasten.** Jeder Eintrag bekommt ein ``&`` auf einem
   innerhalb des Menüs eindeutigen Buchstaben.
6. **„Über" steht zuletzt**, „Nach Updates suchen" gehört ins Hilfe-Menü und
   nicht in eine Extras-Sammelkiste.
7. **Klartext statt Jargon.** „Crash-Log" und „Restore-Key" sind Fachbegriffe
   aus der Entwicklung, nicht aus der Anwendersprache.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMenu,
    QMenuBar,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app_info import APP_VERSION
from utils.i18n import tr, trf
from utils.icons import get_icon
from views.bank_import_dialog import BankImportDialog
from views.help_launcher import help_file_candidates

logger = logging.getLogger(__name__)


def _add(
    menu: QMenu,
    window: QWidget,
    label_key: str,
    icon: str,
    callback,
    *,
    tip_key: str | None = None,
    shortcut_id: str | None = None,
) -> QAction:
    """Legt einen Menüeintrag mit Beschriftung, Symbol, Statustext und Kürzel an."""
    action = QAction(tr(label_key), window)
    if icon:
        action.setIcon(get_icon(icon))
    if tip_key:
        action.setStatusTip(tr(tip_key))
        action.setToolTip(tr(tip_key))
    if shortcut_id and hasattr(window, "_apply_shortcut"):
        window._apply_shortcut(action, shortcut_id)
    action.triggered.connect(lambda _checked=False: callback())
    menu.addAction(action)
    return action


def _open_bank_import(window: QWidget) -> None:
    """Öffnet den lokalen Review-Import und aktualisiert danach Tracking/Tags."""
    conn = getattr(window, "conn", None)
    if conn is None:
        logger.warning("Bankimport ohne aktive Datenbankverbindung angefordert")
        return
    dialog = BankImportDialog(conn, window)
    if dialog.exec() != QDialog.Accepted:
        return
    tracking = getattr(window, "tracking_tab", None)
    if tracking is not None:
        try:
            tracking._reload_tags()
            tracking._reload_categories()
            tracking.refresh()
        except Exception as exc:
            logger.warning("Tracking nach Bankimport nicht vollständig aktualisiert: %s", exc)
    # Die übrigen Tabs dürfen ihre Summen nach dem Import ebenfalls neu lesen.
    refresh = getattr(window, "_refresh_all_tabs", None)
    if callable(refresh):
        try:
            refresh()
        except Exception as exc:
            logger.debug("Voll-Refresh nach Bankimport fehlgeschlagen: %s", exc)


def _build_bank_import_menu(window: QWidget, menubar: QMenuBar) -> QMenu:
    """Eigener Import-Bereich; getrennt von LifePlanner- und Hilfe-Funktionen."""
    import_menu = menubar.addMenu("&Import")
    action = QAction("Bank &PDF/CSV…", window)
    action.setIcon(get_icon("📥"))
    action.setStatusTip("Kontoauszug lokal lesen, prüfen, kategorisieren und importieren")
    action.triggered.connect(lambda _checked=False: _open_bank_import(window))
    import_menu.addAction(action)
    return import_menu


def build_help_menu(window: QWidget, menubar: QMenuBar) -> QMenu:
    """Baut das Hilfe-Menü auf und hängt es an die Menüleiste.

    Zusätzlich wird unmittelbar davor der eigenständige Bankimport-Bereich
    registriert. Er gehört fachlich nicht ins Hilfe-Menü, nutzt aber denselben
    zentralen Menüaufbau-Aufruf, damit ``MainWindow`` unverändert bleiben kann.

    Aufbau (fünf Gruppen, neun oberste Einträge, zwei Untermenüs)::

        Handbuch…                    F1
        Wissensdatenbank
        Visuelle Übersichten         ▸
        ─────────────────────────────
        Tastenkürzel…
        Erste Schritte…
        ─────────────────────────────
        Problembehandlung            ▸
        ─────────────────────────────
        Nach Updates suchen…
        Neuerungen in dieser Version…
        ─────────────────────────────
        Über Budgetmanager…
    """
    _build_bank_import_menu(window, menubar)
    menu = menubar.addMenu(tr("menu.help"))

    # ── Nachschlagen ────────────────────────────────────────────
    _add(
        menu,
        window,
        "menu.handbook",
        "📖",
        window._show_handbook,
        tip_key="menu.handbook_tip",
        shortcut_id="help",
    )
    _add(
        menu,
        window,
        "menu.knowledge_base",
        "🌐",
        window._open_help_docs,
        tip_key="menu.knowledge_base_tip",
    )

    visuals = menu.addMenu(tr("menu.help_visuals"))
    visuals.setIcon(get_icon("🧭"))
    visuals.setStatusTip(tr("menu.help_visuals_tip"))
    _add(
        visuals,
        window,
        "menu.help_mindmap",
        "🧭",
        window._open_help_mindmap,
        tip_key="menu.help_mindmap_tip",
    )
    _add(
        visuals,
        window,
        "menu.wiki_audit",
        "📊",
        window._open_wiki_audit,
        tip_key="menu.wiki_audit_tip",
    )

    menu.addSeparator()

    # ── Lernen ──────────────────────────────────────────────────
    _add(
        menu,
        window,
        "menu.shortcuts",
        "⌨️",
        window._show_shortcuts,
        tip_key="menu.shortcuts_tip",
        shortcut_id="shortcuts",
    )
    _add(
        menu,
        window,
        "menu.setup_assistant",
        "🚀",
        lambda: window._start_setup_assistant(force=True),
        tip_key="menu.setup_assistant_tip",
    )

    menu.addSeparator()

    # ── Problembehandlung ───────────────────────────────────────
    # Bewusst ein Untermenü: Protokolle und Diagnosepakete braucht man selten,
    # sie sollen die Sicht auf Handbuch und Tastenkürzel nicht verstellen.
    trouble = menu.addMenu(tr("menu.troubleshooting"))
    trouble.setIcon(get_icon("🧰"))
    trouble.setStatusTip(tr("menu.troubleshooting_tip"))
    _add(
        trouble,
        window,
        "menu.show_log",
        "📄",
        window._show_app_log,
        tip_key="menu.show_log_tip",
    )
    _add(
        trouble,
        window,
        "menu.show_crash_log",
        "💥",
        window._show_crash_log,
        tip_key="menu.show_crash_log_tip",
    )
    _add(
        trouble,
        window,
        "menu.open_diagnostics_folder",
        "📁",
        window._open_diagnostics_folder,
        tip_key="menu.open_diagnostics_folder_tip",
    )
    _add(
        trouble,
        window,
        "menu.create_diagnostic_report",
        "🧰",
        window._create_diagnostic_report,
        tip_key="menu.create_diagnostic_report_tip",
    )
    trouble.addSeparator()
    # Der Wiederherstellungsschlüssel ist eine Notfallmaßnahme. Er bleibt im
    # Hilfe-Menü erreichbar, gehört aber nicht neben das Handbuch.
    _add(
        trouble,
        window,
        "menu.show_restore_key",
        "🔑",
        window._show_restore_key_view,
        tip_key="menu.show_restore_key_tip",
    )

    menu.addSeparator()

    # ── Version ─────────────────────────────────────────────────
    _add(
        menu,
        window,
        "menu.updates",
        "⬆️",
        window._show_update_dialog,
        tip_key="menu.updates_tip",
        shortcut_id="updates",
    )
    _add(
        menu,
        window,
        "menu.release_notes",
        "🆕",
        lambda: show_release_notes(window),
        tip_key="menu.release_notes_tip",
    )

    menu.addSeparator()

    _add(menu, window, "menu.about", "ℹ️", window._show_about)
    return menu


def current_release_notes() -> str:
    """Liest den obersten Versionsabschnitt aus ``CHANGELOG.md``.

    Bewusst nur der oberste Abschnitt: „Neuerungen in dieser Version" soll die
    aktuelle Version zeigen und nicht die gesamte Projekthistorie.
    """
    for path in help_file_candidates("CHANGELOG.md"):
        try:
            if not path.exists():
                continue
            text = Path(path).read_text(encoding="utf-8")
        except Exception as exc:
            logger.debug("Changelog nicht lesbar (%s): %s", path, exc)
            continue
        sections = re.split(r"^## ", text, flags=re.MULTILINE)
        if len(sections) > 1:
            return ("## " + sections[1]).strip()
        return text.strip()
    return ""


def show_release_notes(window: QWidget) -> None:
    """Zeigt die Neuerungen der laufenden Version in einem Lesefenster."""
    notes = current_release_notes()
    dialog = QDialog(window)
    dialog.setWindowTitle(trf("help.release_notes_title", version=APP_VERSION))
    dialog.resize(720, 520)
    layout = QVBoxLayout(dialog)

    heading = QLabel(trf("help.release_notes_heading", version=APP_VERSION), dialog)
    heading.setWordWrap(True)
    heading.setTextInteractionFlags(Qt.TextSelectableByMouse)
    layout.addWidget(heading)

    viewer = QPlainTextEdit(dialog)
    viewer.setReadOnly(True)
    viewer.setPlainText(notes or tr("help.release_notes_missing"))
    layout.addWidget(viewer, 1)

    buttons = QDialogButtonBox(QDialogButtonBox.Close, dialog)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)
    dialog.exec()
