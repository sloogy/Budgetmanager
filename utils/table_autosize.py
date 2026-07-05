"""Table autosizing helpers.

Ziel: Wenn die Schriftgröße im Design-Profil geändert wird, sollen Tabellen
automatisch passend aussehen (Row-Height/Header-Height), ohne dass der Nutzer
alles manuell ziehen muss.

Wir greifen bewusst *konservativ* ein:
- nur Default-Section-Size (Header/Rows)
- keine aggressiven resizeColumnsToContents() (kann bei vielen Zeilen langsam sein)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from PySide6.QtWidgets import (
    QApplication,
    QTableView,
    QTableWidget,
    QTreeView,
    QWidget,
)
from PySide6.QtGui import QFontMetrics


def _calc_row_height(font_metrics: QFontMetrics) -> int:
    # Basis: Text-Höhe + etwas Padding
    return max(18, int(font_metrics.height() * 1.6))


def _apply_to_table_like(w: QWidget, row_h: int) -> None:
    # v2.1.4 BUG-FIX: Der Horizontal-Header wird bewusst NICHT mehr angefasst.
    # Die Default-Section-Size steuert dort die Standard-SPALTENBREITE (nicht
    # die Header-Höhe!). Der frühere Code setzte damit bei jeder Theme-/
    # Schriftänderung aus den Einstellungen alle Spaltenbreiten auf die
    # Zeilenhöhe (~30px) zurück. Zusätzlich wurde der Resize-Modus aller
    # Tabellen global auf Interactive gezwungen und überschrieb so die pro
    # Tabelle konfigurierten Modi (Stretch/ResizeToContents). Beides
    # verursachte "springende" Tabellenbreiten nach Einstellungsänderungen.
    # Es wird nur noch die Zeilenhöhe (Vertikal-Header) an die Schrift angepasst.
    try:
        if isinstance(w, (QTableWidget, QTableView)):
            vh = w.verticalHeader()
            if vh:
                vh.setDefaultSectionSize(row_h)
            return

        if isinstance(w, QTreeView):
            # TreeViews profitieren ebenfalls von einer passenden Row-Höhe
            try:
                w.setUniformRowHeights(True)
            except Exception as e:
                logger.debug("w.setUniformRowHeights(True): %s", e)
            try:
                w.setIconSize(w.iconSize())
            except Exception as e:
                logger.debug("w.setIconSize(w.iconSize()): %s", e)
    except Exception as e:
        logger.debug("w.setIconSize(w.iconSize()): %s", e)


def autosize_all_tables(app: QApplication | None = None) -> None:
    """Passt Default-Row/Header-Height für *alle* Tabellen im laufenden UI an."""
    if app is None:
        app = QApplication.instance()
    if app is None:
        return

    fm = QFontMetrics(app.font())
    row_h = _calc_row_height(fm)

    for w in app.allWidgets():
        _apply_to_table_like(w, row_h)
