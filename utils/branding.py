"""Zugriff auf die Markenbilder des BudgetManagers (Icon und Logo-Banner).

Die Bilder liegen unter ``resources/icons`` und muessen in drei Umgebungen
gefunden werden: im Quellbaum, im portablen Ordner und im PyInstaller-Onefile
(dort unter ``sys._MEIPASS``). Damit nicht jede Aufrufstelle diese Suche
wiederholt — und damit vor allem niemand ein Logo versehentlich verzerrt —
liegt beides hier zentral.

Alle Skalierungen halten das Seitenverhaeltnis (``Qt.KeepAspectRatio``) und
nutzen ``Qt.SmoothTransformation``. Die Bilder sind transparent; das bleibt
ueber die gesamte Kette erhalten.

Das Banner gibt es zweimal. Der Schriftzug ist zur Haelfte dunkelblau; auf den
dunklen Themes des Programms - die Fensterfarben gehen bis #050505 - waere das
halbe Wort weg. Welche Fassung genommen wird, entscheidet hier die
Fensterfarbe der Palette, nicht die Aufrufstelle: sonst muesste jeder Dialog
dieselbe Fallunterscheidung noch einmal treffen und einer wuerde sie
vergessen.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QWidget

logger = logging.getLogger(__name__)

LOGO_RELATIVE_PATH = "resources/icons/budgetmanager-logo.png"
LOGO_HELL_RELATIVE_PATH = "resources/icons/budgetmanager-logo-hell.png"
ICON_RELATIVE_PATH = "resources/icons/budgetmanager.png"

#: Ab welcher Helligkeit der Fensterfarbe die dunkle Schrift noch lesbar ist.
#: ``QColor.lightnessF`` liefert 0.0 bis 1.0; die Mitte trennt die hellen
#: Themes (ab #f0f2f5) sauber von den dunklen (bis #050505).
HELLIGKEITS_GRENZE = 0.5


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


def _palette_ist_dunkel(widget: QWidget | None) -> bool:
    """Rueckfall: die Fensterfarbe der Qt-Palette.

    Greift nur, wenn das Theme keine Auskunft gibt - etwa in einem Test, der
    einzelne Widgets ohne ThemeManager baut, oder im Splash, der vor dem
    ersten geladenen Profil steht.
    """
    palette: QPalette | None = None
    if widget is not None:
        try:
            palette = widget.palette()
        except RuntimeError:
            palette = None
    if palette is None:
        app = QApplication.instance()
        if app is None:
            return False
        palette = app.palette()
    try:
        return palette.color(QPalette.Window).lightnessF() < HELLIGKEITS_GRENZE
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return False


def _hat_theme_manager(widget: QWidget | None) -> bool:
    """Ob ueber ``widget`` ein aktives Designprofil erreichbar ist.

    ``views.ui_colors.ui_colors`` liefert die hellen Standardfarben sowohl
    dann, wenn ein helles Profil aktiv ist, als auch dann, wenn gar keines
    erreichbar ist. Fuer die Bannerwahl sind das zwei verschiedene Faelle:
    im zweiten ist die Qt-Palette die bessere Auskunft. Deshalb wird hier
    vorher gefragt, ob ueberhaupt ein ThemeManager dranhaengt.
    """
    if widget is None:
        return False
    try:
        fenster = widget.window()
    except (AttributeError, RuntimeError):
        return False
    return getattr(fenster, "theme_manager", None) is not None


def untergrund_ist_dunkel(widget: QWidget | None = None) -> bool:
    """True, wenn auf diese Flaeche die helle Bannerfassung gehoert.

    Massgeblich ist die Panelfarbe des aktiven Designprofils, nicht die
    Qt-Palette: Der ThemeManager setzt ausschliesslich ein Stylesheet und nie
    eine ``QPalette``. Wer im Hauptfenster die Palette fragte, bekaeme die
    Farben des Desktops - auf einem dunklen Desktop mit hellem Profil also
    genau die falsche Antwort.

    Umgekehrt gilt dasselbe: Anmeldedialog, Erststart-Assistent und
    Startbildschirm laufen, bevor das Hauptfenster ein Profil anwendet. Dort
    ist die Palette nicht der Notnagel, sondern die richtige Auskunft - sie
    beschreibt genau die Flaeche, auf der das Banner dann liegt.
    """
    if _hat_theme_manager(widget):
        try:
            from PySide6.QtGui import QColor

            from views.ui_colors import ui_colors

            farbe = QColor(ui_colors(widget).bg_panel)
            if farbe.isValid():
                return farbe.lightnessF() < HELLIGKEITS_GRENZE
        except (ImportError, RuntimeError, TypeError, ValueError) as exc:
            logger.debug("Themefarbe nicht ermittelbar, nutze Palette: %s", exc)
    return _palette_ist_dunkel(widget)


def logo_path(*, fuer_dunklen_untergrund: bool = False) -> Path | None:
    """Pfad zum breiten Logo-Banner oder ``None``.

    Fehlt die helle Fassung, kommt die dunkle zurueck: ein schlecht lesbares
    Logo ist immer noch besser als eine leere Flaeche.
    """
    if fuer_dunklen_untergrund:
        hell = _resolve_asset(LOGO_HELL_RELATIVE_PATH)
        if hell is not None:
            return hell
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


def logo_pixmap(
    width: int,
    *,
    device_pixel_ratio: float = 1.0,
    fuer_dunklen_untergrund: bool | None = None,
) -> QPixmap | None:
    """Logo-Banner auf ``width`` logische Pixel Breite, Seitenverhaeltnis erhalten.

    ``device_pixel_ratio`` sorgt dafuer, dass auf HiDPI-Anzeigen tatsaechlich
    mehr Bildpunkte gerendert werden; die logische Groesse bleibt ``width``.

    ``fuer_dunklen_untergrund`` waehlt die Bannerfassung; ``None`` fragt die
    Palette der Anwendung.
    """
    if fuer_dunklen_untergrund is None:
        fuer_dunklen_untergrund = untergrund_ist_dunkel()
    source = _load(logo_path(fuer_dunklen_untergrund=fuer_dunklen_untergrund))
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
    pixmap = logo_pixmap(
        width,
        device_pixel_ratio=_device_pixel_ratio(parent),
        fuer_dunklen_untergrund=untergrund_ist_dunkel(parent),
    )
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
