"""
tools/create_icon.py
--------------------
Erstellt icon.ico im Projektroot fuer BudgetManager.

Benoetigt: pip install Pillow

Ausfuehren (aus dem Projektroot):
    python tools/create_icon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Fehler: Pillow ist nicht installiert.")
    print("Installiere mit: pip install Pillow")
    sys.exit(1)


# Icon-Groessen fuer multi-size .ico (Windows benoetigt alle)
ICO_SIZES = [256, 128, 64, 48, 32, 16]

# Ausgabepfad: immer relativ zum Projektroot (Elternverzeichnis von tools/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "icon.ico"


def draw_icon(size: int) -> Image.Image:
    """
    Erstellt ein einzelnes quadratisches Icon in der gewuenschten Groesse.

    Design:
    - Hintergrund: Blau (#2563EB, identisch mit BudgetManager-Akzentfarbe)
    - Symbol:      Weisses Euro-Zeichen '€' zentriert
    - Kanten:      Leicht abgerundet (durch Maske)
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Abgerundetes Rechteck als Hintergrund
    radius = max(4, size // 8)
    bg_color = (37, 99, 235, 255)      # #2563EB
    draw.rounded_rectangle([(0, 0), (size - 1, size - 1)], radius=radius, fill=bg_color)

    # Symbol-Schriftgroesse: ca. 60 % der Icon-Groesse
    symbol = "€"
    font_size = max(8, int(size * 0.60))

    font: ImageFont.ImageFont | ImageFont.FreeTypeFont
    try:
        # Versuche eine serifenlose Systemschrift zu laden (Linux/Windows)
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except OSError:
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except OSError:
            # Fallback: eingebaute Bitmap-Schrift (kein TrueType noetig)
            font = ImageFont.load_default()

    # Textgroesse ermitteln und Symbol zentrieren
    bbox = draw.textbbox((0, 0), symbol, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2 - bbox[0]
    y = (size - text_h) // 2 - bbox[1]

    draw.text((x, y), symbol, fill=(255, 255, 255, 255), font=font)

    return img


def create_ico() -> None:
    """Erzeugt alle Groessen und speichert als multi-size .ico."""
    print(f"Erstelle icon.ico ({', '.join(str(s) for s in ICO_SIZES)} px) ...")

    frames: list[Image.Image] = []
    for size in ICO_SIZES:
        frame = draw_icon(size)
        # ICO benoetigt RGB(A)-Bilder; RGBA ist korrekt fuer Transparenz
        frames.append(frame)

    # Erstes Frame speichern, alle anderen als append_images
    frames[0].save(
        OUTPUT_PATH,
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=frames[1:],
    )

    print(f"Gespeichert: {OUTPUT_PATH}")
    print("Fertig. Fuege icon.ico jetzt in build_windows.py und")
    print("installer/budgetmanager_setup.iss ein (siehe docs/create_icon.md).")


if __name__ == "__main__":
    create_ico()
