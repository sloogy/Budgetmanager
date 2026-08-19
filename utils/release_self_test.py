"""Installationsnaher GUI-Selbsttest für CI, Installer und Support."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import traceback


def _pixmap_render_metrics(pixmap) -> dict[str, object]:
    """Prüft, ob ein Widget wirklich gezeichnet wurde und nicht einfarbig leer ist."""
    image = pixmap.toImage()
    if image.isNull() or image.width() < 640 or image.height() < 400:
        raise RuntimeError(f"Ungültiges Fensterbild: {image.width()}x{image.height()}")
    # Ein dichtes, aber günstiges Raster erkennt schwarze/transparent-leere
    # Fenster zuverlässig, ohne plattformabhängige Pixel-Referenzen zu erzwingen.
    x_step = max(1, image.width() // 32)
    y_step = max(1, image.height() // 20)
    colours: set[int] = set()
    opaque_samples = 0
    sample_count = 0
    for y in range(0, image.height(), y_step):
        for x in range(0, image.width(), x_step):
            pixel = image.pixelColor(x, y)
            colours.add(pixel.rgba())
            opaque_samples += int(pixel.alpha() > 0)
            sample_count += 1
    if len(colours) < 8:
        raise RuntimeError(
            f"Fensterbild ist nahezu einfarbig ({len(colours)} Stichprobenfarben)"
        )
    if opaque_samples < max(1, int(sample_count * 0.95)):
        raise RuntimeError("Fensterbild enthält zu viele transparente Bereiche")
    return {
        "width": image.width(),
        "height": image.height(),
        "sample_colours": len(colours),
        "opaque_ratio": round(opaque_samples / max(1, sample_count), 4),
    }


def _save_screenshot(pixmap, directory: Path, filename: str) -> dict[str, object]:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    if not pixmap.save(str(path), "PNG"):
        raise RuntimeError(f"Screenshot konnte nicht gespeichert werden: {path.name}")
    raw = path.read_bytes()
    if len(raw) < 10_000:
        raise RuntimeError(
            f"Screenshot ist unplausibel klein: {path.name} ({len(raw)} Bytes)"
        )
    return {
        "file": path.name,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def run_release_self_test() -> int:
    """Startet die echte Hauptoberfläche kurz und beendet sich reproduzierbar.

    Optional erzeugt ``BM_SELF_TEST_SCREENSHOT_DIR`` pro Hauptbereich ein PNG.
    Die Bilder dienen als CI-Artefakt und werden zusätzlich auf Größe,
    Deckkraft und ausreichende Farbvielfalt geprüft. So fallen leere/schwarze
    Fenster und grobe Rendering-Rückschritte bereits vor dem Release auf.
    """

    result: dict[str, object] = {
        "ok": False,
        "platform": sys.platform,
        "qt_platform": os.environ.get("QT_QPA_PLATFORM", ""),
        "scale": os.environ.get("QT_SCALE_FACTOR", "1"),
    }
    connection: sqlite3.Connection | None = None
    window = None
    try:
        from PySide6.QtGui import QAccessible
        from PySide6.QtWidgets import QApplication

        from app_info import APP_VERSION
        from model.migrations import migrate_all
        from utils.notifications import show_info
        from views.main_window import MainWindow

        app = QApplication.instance() or QApplication(
            ["BudgetManager", "--release-self-test"]
        )
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        migrate_all(connection)

        window = MainWindow(connection)
        window._suppress_close_confirm = True
        window.resize(1280, 800)
        window.show()
        app.processEvents()

        screenshot_dir_raw = os.environ.get("BM_SELF_TEST_SCREENSHOT_DIR", "").strip()
        screenshot_dir = Path(screenshot_dir_raw) if screenshot_dir_raw else None
        render_checks: list[dict[str, object]] = []
        screenshots: list[dict[str, object]] = []

        tabs = window.tabs
        for index in range(tabs.count()):
            tabs.setCurrentIndex(index)
            app.processEvents()
            pixmap = window.grab()
            metrics = _pixmap_render_metrics(pixmap)
            metrics["tab_index"] = index
            metrics["tab_title"] = tabs.tabText(index)
            render_checks.append(metrics)
            if screenshot_dir is not None:
                safe_title = (
                    "".join(
                        ch.lower() if ch.isalnum() else "_"
                        for ch in tabs.tabText(index)
                    ).strip("_")
                    or f"tab_{index}"
                )
                shot = _save_screenshot(
                    pixmap, screenshot_dir, f"{index:02d}_{safe_title}.png"
                )
                shot["tab_index"] = index
                screenshots.append(shot)

        show_info(window, "Release-Selbsttest", "Nicht-modale Statusmeldung aktiv")
        app.processEvents()

        accessible_targets = [window, tabs, window.statusBar()]
        accessible_interfaces = sum(
            1
            for widget in accessible_targets
            if QAccessible.queryAccessibleInterface(widget)
        )
        if not window.isVisible():
            raise RuntimeError("Hauptfenster wurde nicht sichtbar")
        if tabs.count() < 4:
            raise RuntimeError(f"Zu wenige Hauptbereiche: {tabs.count()}")
        if accessible_interfaces != len(accessible_targets):
            raise RuntimeError(
                "Accessibility-Interfaces unvollständig: "
                f"{accessible_interfaces}/{len(accessible_targets)}"
            )

        result.update(
            {
                "ok": True,
                "version": APP_VERSION,
                "tabs": tabs.count(),
                "accessible_interfaces": accessible_interfaces,
                "window_size": [window.width(), window.height()],
                "render_checks": render_checks,
                "screenshots": screenshots,
            }
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1
    finally:
        if window is not None:
            try:
                window.close()
                window.deleteLater()
            except Exception:
                pass
        if connection is not None:
            connection.close()
