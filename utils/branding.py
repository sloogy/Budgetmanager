"""Zugriff auf die Markenbilder des BudgetManagers (Icon und Logo-Banner).

Die Bilder liegen unter ``resources/icons`` und muessen in drei Umgebungen
gefunden werden: im Quellbaum, im portablen Ordner und im PyInstaller-Onefile
(dort unter ``sys._MEIPASS``). Damit nicht jede Aufrufstelle diese Suche
wiederholt — und damit vor allem niemand ein Logo versehentlich verzerrt —
liegt beides hier zentral.

Alle Skalierungen halten das Seitenverhaeltnis (``Qt.KeepAspectRatio``) und
nutzen ``Qt.SmoothTransformation``. Die Bilder sind transparent; das bleibt
ueber die gesamte Kette erhalten.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QWidget

logger = logging.getLogger(__name__)

LOGO_RELATIVE_PATH = "resources/icons/budgetmanager-logo.png"
ICON_RELATIVE_PATH = "resources/icons/budgetmanager.png"


def _resolve_asset(relative_path: str) -> Path | None:
    """Sucht ``relative_path`` im Onefile-Bundle und im App-Verzeichnis."""
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / relative_path)
    try:
        from model.app_paths import resolve_in_app

        candidates.append(Path(resolve_in_app(relative_path)))
    except (ImportError, OSError, ValueError) as exc:
        logger.debug("resolve_in_app fuer %s nicht nutzbar: %s", relative_path, exc)
    candidates.append(Path(__file__).resolve().parent.parent / relative_path)

    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    logger.debug("Markenbild nicht gefunden: %s", relative_path)
    return None


def logo_path() -> Path | None:
    """Pfad zum breiten Logo-Banner (2172x724) oder ``None``."""
    return _resolve_asset(LOGO_RELATIVE_PATH)


def icon_path() -> Path | None:
    """Pfad zum quadratischen App-Icon oder ``None``."""
    return _resolve_asset(ICON_RELATIVE_PATH)


def _load(path: Path | None) -> QPixmap | None:
    if path is None:
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        logger.debug("Markenbild konnte nicht geladen werden: %s", path)
        return None
    return pixmap


def logo_pixmap(width: int, *, device_pixel_ratio: float = 1.0) -> QPixmap | None:
    """Logo-Banner auf ``width`` logische Pixel Breite, Seitenverhaeltnis erhalten.

    ``device_pixel_ratio`` sorgt dafuer, dass auf HiDPI-Anzeigen tatsaechlich
    mehr Bildpunkte gerendert werden; die logische Groesse bleibt ``width``.
    """
    source = _load(logo_path())
    if source is None:
        return None
    ratio = float(device_pixel_ratio)
    if ratio <= 0.0:
        ratio = 1.0
    target = max(1, int(round(width * ratio)))
    scaled = source.scaledToWidth(target, Qt.SmoothTransformation)
    scaled.setDevicePixelRatio(ratio)
    return scaled


def icon_pixmap(size: int, *, device_pixel_ratio: float = 1.0) -> QPixmap | None:
    """Quadratisches App-Icon mit ``size`` logischen Pixeln Kantenlaenge."""
    source = _load(icon_path())
    if source is None:
        return None
    ratio = float(device_pixel_ratio)
    if ratio <= 0.0:
        ratio = 1.0
    edge = max(1, int(round(size * ratio)))
    scaled = source.scaled(edge, edge, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    scaled.setDevicePixelRatio(ratio)
    return scaled


def _device_pixel_ratio(widget: QWidget | None) -> float:
    if widget is not None:
        try:
            return float(widget.devicePixelRatioF())
        except (RuntimeError, TypeError, ValueError):
            return 1.0
    return 1.0


def make_logo_label(parent: QWidget | None, width: int) -> QLabel | None:
    """Fertiges, zentriertes Logo-Label — oder ``None``, wenn kein Bild da ist.

    Gibt bewusst ``None`` zurueck statt eines leeren Labels: eine Marken-Flaeche
    ohne Bild soll im Layout gar keinen Platz belegen.
    """
    pixmap = logo_pixmap(width, device_pixel_ratio=_device_pixel_ratio(parent))
    if pixmap is None:
        return None
    label = QLabel(parent)
    label.setPixmap(pixmap)
    label.setAlignment(Qt.AlignCenter)
    label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    # Das Logo traegt den Programmnamen bereits als Text im Bild; fuer
    # Screenreader wird er hier noch einmal ausgesprochen.
    label.setAccessibleName("BudgetManager")
    return label


def make_icon_label(parent: QWidget | None, size: int) -> QLabel | None:
    """Fertiges Label mit dem quadratischen App-Icon oder ``None``."""
    pixmap = icon_pixmap(size, device_pixel_ratio=_device_pixel_ratio(parent))
    if pixmap is None:
        return None
    label = QLabel(parent)
    label.setPixmap(pixmap)
    label.setAlignment(Qt.AlignCenter)
    label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    label.setAccessibleName("BudgetManager")
    return label
