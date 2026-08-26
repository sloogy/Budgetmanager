"""
tools/create_icon.py
--------------------
Leitet saemtliche App-Icons des BudgetManagers aus dem Marken-Quellbild ab.

Quelle : resources/icons/budgetmanager-source.png (quadratisch, transparent)
Ziele  : resources/icons/budgetmanager-{16,32,48,64,128,256,512}.png
         resources/icons/budgetmanager.png   (1024 px, Linux/Qt)
         resources/icons/budgetmanager.ico   (Mehrfachaufloesung, Windows)

Frueher zeichnete dieses Skript ein Platzhalter-Icon selbst. Seit die Suite
ein echtes Markenbild hat, waere ein gezeichneter Ersatz falsch: die Icons
muessen aus genau dem Bild entstehen, das auch im Logo-Banner steckt. Das
Quellbild liegt deshalb unskaliert im Repo — damit bleibt jede Groesse
reproduzierbar erzeugbar, ohne externe Datei.

Benoetigt: pip install Pillow

Ausfuehren (aus dem Projektroot):
    python tools/create_icon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Fehler: Pillow ist nicht installiert.")
    print("Installiere mit: pip install Pillow")
    sys.exit(1)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = PROJECT_ROOT / "resources" / "icons"
SOURCE_PATH = ICON_DIR / "budgetmanager-source.png"

# Einzel-PNGs, die Qt/Linux-Desktops und der Installer ausliefern.
PNG_SIZES = (16, 32, 48, 64, 128, 256, 512)

# Groesse der generischen budgetmanager.png (App-Icon fuer Qt/Linux).
MAIN_PNG_SIZE = 1024

# Mehrfachaufloesung im .ico. Windows waehlt je nach Kontext eine davon.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def load_source() -> Image.Image:
    """Laedt das Quellbild und stellt RGBA sowie quadratische Kanten sicher."""
    if not SOURCE_PATH.is_file():
        raise FileNotFoundError(
            f"Quellbild fehlt: {SOURCE_PATH}\n"
            "Ohne das Markenbild koennen die Icons nicht erzeugt werden."
        )
    source = Image.open(SOURCE_PATH)
    source = source.convert("RGBA")
    if source.width != source.height:
        # Nicht zuschneiden: auf ein transparentes Quadrat zentrieren, damit
        # kein Bildteil verloren geht und nichts verzerrt wird.
        edge = max(source.width, source.height)
        canvas = Image.new("RGBA", (edge, edge), (0, 0, 0, 0))
        canvas.paste(
            source, ((edge - source.width) // 2, (edge - source.height) // 2), source
        )
        source = canvas
    return source


def scaled(source: Image.Image, size: int) -> Image.Image:
    """Skaliert das Quellbild transparenzerhaltend auf ``size`` x ``size``."""
    return source.resize((size, size), Image.LANCZOS)


def write_pngs(source: Image.Image) -> list[Path]:
    written: list[Path] = []
    for size in PNG_SIZES:
        target = ICON_DIR / f"budgetmanager-{size}.png"
        scaled(source, size).save(target, format="PNG")
        written.append(target)

    main_png = ICON_DIR / "budgetmanager.png"
    scaled(source, MAIN_PNG_SIZE).save(main_png, format="PNG")
    written.append(main_png)
    return written


def write_ico(source: Image.Image) -> Path:
    """Schreibt eine .ico mit allen Groessen aus :data:`ICO_SIZES`."""
    target = ICON_DIR / "budgetmanager.ico"
    largest = scaled(source, max(ICO_SIZES))
    largest.save(target, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
    return target


def create_icons() -> int:
    source = load_source()
    print(f"Quellbild: {SOURCE_PATH.name} ({source.width}x{source.height})")

    for path in write_pngs(source):
        print(f"  geschrieben: {path.relative_to(PROJECT_ROOT)}")

    ico = write_ico(source)
    print(
        f"  geschrieben: {ico.relative_to(PROJECT_ROOT)} "
        f"({', '.join(str(s) for s in ICO_SIZES)} px)"
    )
    print("Fertig.")
    return 0


def main() -> int:
    try:
        return create_icons()
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Fehler: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
