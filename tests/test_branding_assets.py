"""Verhaltenstests fuer Markenbilder, Icons und den Startbildschirm.

Bewusst ohne Pillow: die Icons sind ausgelieferte Programmbestandteile und
muessen auch dort pruefbar sein, wo das Erzeugungswerkzeug nicht installiert
ist. PNG- und ICO-Kopfdaten liest deshalb die Standardbibliothek.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ICON_DIR = ROOT / "resources" / "icons"
PNG_SIZES = (16, 32, 48, 64, 128, 256, 512)
EXPECTED_ICO_SIZES = {16, 32, 48, 64, 128, 256}


def _png_size(path: Path) -> tuple[int, int]:
    """Breite/Hoehe aus dem IHDR-Block eines PNG."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} ist kein PNG"
    assert data[12:16] == b"IHDR", f"{path.name} hat keinen IHDR-Block"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _png_has_alpha(path: Path) -> bool:
    """True, wenn der PNG-Farbtyp einen Alphakanal traegt (4 oder 6)."""
    data = path.read_bytes()
    colour_type = data[25]
    return colour_type in (4, 6)


def _ico_sizes(path: Path) -> set[tuple[int, int]]:
    """Alle im ICONDIR gemeldeten Aufloesungen (0 bedeutet 256)."""
    data = path.read_bytes()
    reserved, image_type, count = struct.unpack("<HHH", data[:6])
    assert reserved == 0 and image_type == 1, f"{path.name} ist keine .ico"
    sizes: set[tuple[int, int]] = set()
    for index in range(count):
        offset = 6 + index * 16
        width = data[offset] or 256
        height = data[offset + 1] or 256
        sizes.add((width, height))
    return sizes


# ── Quellbilder ──────────────────────────────────────────────────


def test_markenquellbilder_liegen_im_repo():
    source = ICON_DIR / "budgetmanager-source.png"
    logo = ICON_DIR / "budgetmanager-logo.png"

    assert source.is_file(), "Ohne Quellbild sind die Icons nicht reproduzierbar"
    assert logo.is_file(), "Ohne Logo-Banner gibt es keinen Startbildschirm"

    width, height = _png_size(source)
    assert width == height, "Das Icon-Quellbild muss quadratisch sein"
    assert width >= 512, "Das Quellbild muss groesser sein als die groesste Ausgabe"
    assert _png_has_alpha(source)

    logo_width, logo_height = _png_size(logo)
    assert logo_width > logo_height, "Das Logo-Banner ist ein breites Bild"
    assert _png_has_alpha(logo)


# ── Erzeugte Icons ───────────────────────────────────────────────


@pytest.mark.parametrize("size", PNG_SIZES)
def test_icon_png_hat_die_erwartete_kantenlaenge(size: int):
    path = ICON_DIR / f"budgetmanager-{size}.png"
    assert path.is_file()
    assert _png_size(path) == (size, size)
    assert _png_has_alpha(path), "Icons muessen transparent bleiben"


def test_generisches_app_icon_ist_quadratisch_und_gross():
    path = ICON_DIR / "budgetmanager.png"
    width, height = _png_size(path)
    assert width == height
    assert width >= max(PNG_SIZES)
    assert _png_has_alpha(path)


def test_ico_traegt_alle_ueblichen_aufloesungen():
    path = ICON_DIR / "budgetmanager.ico"
    assert path.is_file()
    sizes = _ico_sizes(path)
    assert len(sizes) >= len(EXPECTED_ICO_SIZES), "Die .ico muss mehrere Groessen haben"
    for edge in EXPECTED_ICO_SIZES:
        assert (edge, edge) in sizes, f"{edge}px fehlt in der .ico"


def test_icons_stammen_aus_demselben_motiv():
    """Alle Groessen sollen dasselbe Bild zeigen, nicht verschiedene Motive."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage

    edge = 32
    reference = QImage(str(ICON_DIR / "budgetmanager-256.png")).scaled(
        edge, edge, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
    )
    variant = QImage(str(ICON_DIR / f"budgetmanager-{edge}.png"))
    assert not reference.isNull() and not variant.isNull()

    abweichung = 0
    for y in range(edge):
        for x in range(edge):
            abweichung += abs(
                reference.pixelColor(x, y).alpha() - variant.pixelColor(x, y).alpha()
            )
    mittel = abweichung / (edge * edge)
    assert (
        mittel < 12
    ), f"32px und 256px zeigen offenbar verschiedene Motive (Delta {mittel:.1f})"


# ── Logo im Programm ─────────────────────────────────────────────


def test_logo_behaelt_sein_seitenverhaeltnis(v4_app):
    from utils.branding import logo_path, logo_pixmap

    source_width, source_height = _png_size(logo_path())
    pixmap = logo_pixmap(480)
    assert pixmap is not None and not pixmap.isNull()
    assert pixmap.width() == 480

    erwartet = source_height / source_width
    tatsaechlich = pixmap.height() / pixmap.width()
    assert abs(erwartet - tatsaechlich) < 0.01


def test_logo_wird_fuer_hidpi_hoeher_aufgeloest_gerendert(v4_app):
    from utils.branding import logo_pixmap

    einfach = logo_pixmap(480, device_pixel_ratio=1.0)
    doppelt = logo_pixmap(480, device_pixel_ratio=2.0)
    assert einfach is not None and doppelt is not None

    # Mehr echte Bildpunkte, aber dieselbe logische Groesse.
    assert doppelt.width() == 2 * einfach.width()
    assert doppelt.devicePixelRatio() == pytest.approx(2.0)
    assert doppelt.width() / doppelt.devicePixelRatio() == pytest.approx(480)


def test_logo_label_verzerrt_nicht(v4_app):
    from utils.branding import make_logo_label

    label = make_logo_label(None, 300)
    assert label is not None
    pixmap = label.pixmap()
    assert pixmap.width() == 300
    assert pixmap.height() < pixmap.width()


def test_ueber_dialog_zeigt_das_logo(v4_app):
    from PySide6.QtWidgets import QLabel

    from views.main_window_dialogs import AboutDialog

    dialog = AboutDialog()
    try:
        mit_bild = [
            child
            for child in dialog.findChildren(QLabel)
            if not child.pixmap().isNull()
        ]
        assert mit_bild, "Der Ueber-Dialog soll eine Marken-Flaeche haben"
        assert dialog.sizeHint().width() > 0
    finally:
        dialog.deleteLater()


# ── Startbildschirm ──────────────────────────────────────────────


def test_splash_erscheint_und_verschwindet_mit_dem_hauptfenster(v4_app):
    from PySide6.QtWidgets import QWidget

    from views.startup_splash import StartupSplash

    splash = StartupSplash.start(v4_app)
    try:
        assert splash.is_visible(), "Der Startbildschirm muss beim Start sichtbar sein"

        window = QWidget()
        window.show()
        splash.finish(window)

        assert not splash.is_visible()
        assert splash.widget() is None
        assert StartupSplash._active is None
        window.close()
    finally:
        StartupSplash.close_active()


def test_splash_weicht_einem_modalen_dialog(v4_app):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QDialog

    from views.startup_splash import StartupSplash

    splash = StartupSplash.start(v4_app)
    try:
        assert splash.is_visible()

        sichtbar_waehrend_dialog: list[bool] = []
        dialog = QDialog()
        QTimer.singleShot(
            0,
            lambda: (
                sichtbar_waehrend_dialog.append(splash.is_visible()),
                dialog.accept(),
            ),
        )
        dialog.exec()
        v4_app.processEvents()

        assert sichtbar_waehrend_dialog == [
            False
        ], "Der Startbildschirm darf nicht ueber einem Dialog liegen"
        assert splash.is_visible(), "Danach soll er das Laden weiter ueberbruecken"
    finally:
        StartupSplash.close_active()


def test_splash_laesst_sich_ohne_referenz_und_mehrfach_schliessen(v4_app):
    from views.startup_splash import StartupSplash

    splash = StartupSplash.start(v4_app)
    StartupSplash.close_active()
    assert not splash.is_visible()

    # Idempotent: ein zweiter Aufruf darf nicht scheitern.
    StartupSplash.close_active()
    splash.close()
    splash.finish(None)
    assert StartupSplash._active is None


def test_startfehler_schliesst_den_splash(v4_app):
    """Der Notausgang aus main.py muss den Splash auch ohne Referenz raeumen."""
    import main as main_module
    from views.startup_splash import StartupSplash

    splash = StartupSplash.start(v4_app)
    try:
        main_module._close_startup_splash()
        assert not splash.is_visible()
        assert StartupSplash._active is None
    finally:
        StartupSplash.close_active()
