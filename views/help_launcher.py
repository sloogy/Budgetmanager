"""Hilfe-Einstiege: Corner-Knopf der Menüleiste und lokale Hilfedateien.

Ausgelagert aus ``views/main_window.py`` (v2.2.37). Zwei Gründe:

1. **Fachliche Bündelung.** Alle Wege in die Hilfe – das sichtbare ``?`` oben
   rechts und das Auffinden der mitgelieferten HTML-Dateien – liegen jetzt an
   einer Stelle statt verstreut im Hauptfenster.
2. **Architektur-Gate.** ``views/main_window.py`` steht an der 3500-Zeilen-
   Grenze. Neue Hilfe-Funktionen gehören deshalb hierher.

Das Modul ist bewusst schlank und ohne Zustand: es kennt kein ``MainWindow``,
sondern bekommt Fenster und Menüleiste übergeben.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMenuBar, QToolButton, QWidget

from model.app_paths import resolve_in_app
from utils.i18n import tr, trf
from utils.notifications import show_warning

logger = logging.getLogger(__name__)


def help_file_candidates(rel_path: str) -> list[Path]:
    """Mögliche Orte für lokale Hilfedateien in Source, Portable und PyInstaller."""
    candidates: list[Path] = []
    try:
        candidates.append(resolve_in_app(rel_path))
    except Exception:
        pass
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / rel_path)
    candidates.append(Path(__file__).resolve().parents[1] / rel_path)
    return candidates


def install_help_corner_button(
    window: QWidget, menubar: QMenuBar, on_click, existing: QToolButton | None = None
) -> QToolButton:
    """Setzt ein sichtbares ``?`` ganz rechts in die Menüleiste.

    Ort: ``Qt.TopRightCorner`` der Menüleiste – optisch also direkt links neben
    Minimieren/Maximieren/Schließen der Fensterdekoration. Damit ist der
    Hilfe-Einstieg dort, wo er erwartet wird (oben rechts), und zusätzlich
    weiterhin über ``Hilfe → Handbuch`` erreichbar.

    Bewusste Entscheidungen:

    1. **Reines ASCII ``?``** statt Emoji oder Icon-Theme. Unter Fedora/GNOME
       ohne Emoji-Schrift bleiben Emoji-Glyphen sonst leer, und Icon-Themes
       liefern nicht auf jedem System ein ``help``-Icon.
    2. **Widget wird nur einmal erzeugt.** Beim Sprachwechsel ruft
       ``_retranslate_ui`` ``menuBar().clear()`` + ``_create_menu()`` auf.
       ``clear()`` entfernt nur Aktionen, nicht das Corner-Widget – ein erneutes
       ``QToolButton``-Erzeugen würde bei jedem Sprachwechsel ein verwaistes
       Widget hinterlassen. Der Aufrufer reicht den vorhandenen Knopf über
       ``existing`` herein; dann wird er nur neu beschriftet.

    Gibt den (ggf. wiederverwendeten) Knopf zurück.
    """
    button = existing
    if button is None:
        button = QToolButton(menubar)
        button.setObjectName("menuBarHelpButton")
        button.setText("?")
        button.setCursor(Qt.PointingHandCursor)
        button.setFocusPolicy(Qt.TabFocus)
        button.setAutoRaise(False)
        button.clicked.connect(on_click)
    tip = tr("menu.help_corner_tip")
    button.setToolTip(tip)
    button.setStatusTip(tip)
    button.setAccessibleName(tr("menu.help_corner_a11y"))
    button.setAccessibleDescription(tip)
    if menubar.cornerWidget(Qt.TopRightCorner) is not button:
        menubar.setCornerWidget(button, Qt.TopRightCorner)
    button.setVisible(True)
    return button


def open_help_file(
    window: QWidget, rel_path: str, *, title_key: str = "menu.handbook"
) -> bool:
    """Öffnet eine lokale Hilfedatei im Browser/Standardprogramm.

    Probiert alle Kandidatenpfade der Reihe nach; erst wenn keiner existiert,
    erscheint eine Warnung. So funktionieren Source-, Portable- und
    PyInstaller-Layout ohne Sonderfall im Aufrufer.
    """
    for path in help_file_candidates(rel_path):
        try:
            if path.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
                status = window.statusBar() if hasattr(window, "statusBar") else None
                if status:
                    status.showMessage(trf("msg.help_opened", path=str(path)), 3000)
                return True
        except Exception as exc:
            logger.debug("Help candidate failed %s: %s", path, exc)
    show_warning(window, tr(title_key), tr("msg.help_not_found"))
    return False
