"""Qt/DPI- und Layout-Helfer fuer robuste Skalierung.

Warum diese Datei existiert:
- Windows 125/150 %, Linux Wayland/X11 und portable Builds melden DPI sehr
  unterschiedlich.
- Harte Fenster-/Widget-Groessen koennen auf kleinen oder skalierten Displays
  abgeschnitten wirken.

Die Helfer sind bewusst konservativ: Sie erzwingen keinen festen Scale-Factor,
sondern lassen Qt die Plattform-DPI nutzen und runden nicht grob auf/ab.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def configure_qt_scaling_environment() -> None:
    """Vor ``QApplication`` aufrufen.

    Best Practice fuer Qt 6 / PySide6:
    - Keine feste globale Skalierung erzwingen (kein QT_SCALE_FACTOR setzen).
    - Keine alten Qt5-Auto-Scale-Variablen in Qt6 erzwingen; Qt6 kann HiDPI
      selbst. Alte Variablen koennen in Frozen-/RDP-Szenarien falsche Groessen
      beguenstigen.
    - Fractional Scaling nicht auf 100/200 % wegrunden.
    """
    try:
        # Keine absolute Skalierung setzen. Diese Qt-Variablen aktivieren nur
        # HiDPI-/Screen-DPI-Nutzung und behalten damit Windows/Linux/RDP-
        # Systemskalierung bei. QT_SCALE_FACTOR bleibt bewusst unangetastet.
        os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
        os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
        os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")

        for key in ("QT_SCALE_FACTOR", "QT_FONT_DPI", "QT_AUTO_SCREEN_SCALE_FACTOR"):
            if os.environ.get(key):
                logger.info("%s ist gesetzt: %s", key, os.environ.get(key))

        try:
            from PySide6.QtCore import Qt
            from PySide6.QtGui import QGuiApplication

            QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
                Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
            )
        except Exception as exc:  # pragma: no cover - abhaengig von Qt-Version
            logger.debug(
                "High-DPI-Rounding-Policy konnte nicht gesetzt werden: %s", exc
            )
    except Exception as exc:  # pragma: no cover
        logger.debug("Qt-Skalierungsumgebung konnte nicht vorbereitet werden: %s", exc)


def clamp_geometry_to_available_screen(
    x: int, y: int, width: int, height: int, *, margin_ratio: float = 0.96
) -> tuple[int, int, int, int]:
    """Fenstergeometrie in den sichtbaren Desktopbereich klemmen.

    Gibt ``(x, y, width, height)`` in logischen Qt-Pixeln zurueck. Hilft gegen
    gespeicherte Geometrien von anderen Monitoren/DPI-Stufen und gegen portable
    Wechsel zwischen Windows/Linux/Displays.
    """
    try:
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QApplication

        screen = QApplication.screenAt(QPoint(int(x), int(y)))
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return int(x), int(y), int(width), int(height)

        rect = screen.availableGeometry()
        max_w = max(720, int(rect.width() * margin_ratio))
        max_h = max(520, int(rect.height() * margin_ratio))

        # Mindestgroessen bewusst niedriger als frueher: auf 150%-Windows/RDP
        # bleiben sonst Dialoge/Fenster groesser als der logische Bildschirm und
        # werden abgeschnitten. Groesser darf das Fenster natuerlich bleiben,
        # solange der Screen es hergibt.
        safe_min_w = min(980, max_w)
        safe_min_h = min(680, max_h)
        width = min(max(safe_min_w, int(width)), max_w)
        height = min(max(safe_min_h, int(height)), max_h)

        if (
            x < rect.left()
            or y < rect.top()
            or x + width > rect.right()
            or y + height > rect.bottom()
        ):
            x = rect.left() + max(0, (rect.width() - width) // 2)
            y = rect.top() + max(0, (rect.height() - height) // 2)

        return int(x), int(y), int(width), int(height)
    except Exception as exc:  # pragma: no cover
        logger.debug("Geometrie-Clamp fehlgeschlagen: %s", exc)
        return int(x), int(y), int(width), int(height)
