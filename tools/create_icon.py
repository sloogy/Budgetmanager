"""
tools/create_icon.py
--------------------
Leitet saemtliche Markenbilder des BudgetManagers aus den beiden Quellbildern ab.

Quellen:
    resources/icons/budgetmanager-source.png       (quadratisches Motiv)
    resources/icons/budgetmanager-logo-source.png  (breites Banner mit Schriftzug)

Ziele:
    resources/icons/budgetmanager-{16,32,48,64,128,256,512}.png
    resources/icons/budgetmanager.png       (1024 px, Linux/Qt)
    resources/icons/budgetmanager.ico       (Mehrfachaufloesung, Windows)
    resources/icons/budgetmanager-logo.png  (Banner, randlos zugeschnitten)

Warum die Quellbilder nicht direkt ausgeliefert werden
------------------------------------------------------
Die gelieferten Marken-PNGs tragen ungleiche transparente Raender: Beim
Banner sassen 37 Bildpunkte ueber und 119 unter dem Motiv, links 112 und
rechts 90. Wer so ein Bild in eine Flaeche fester Hoehe legt, bekommt ein
Logo, das zu klein wirkt und sichtbar nach oben rutscht - obwohl das Layout
korrekt zentriert. Genau deshalb passiert hier zweierlei:

* ``trimmed`` schneidet die transparenten Raender weg. Danach ist die
  Bildkante die Motivkante, und ``scaledToWidth`` fuellt die Flaeche wirklich.
* ``square`` setzt das Icon-Motiv anschliessend mittig auf ein transparentes
  Quadrat mit gleichem Rand ringsum. Ein Icon darf nicht randlos sein - in
  16 px klebt es sonst an der Kante - aber der Rand muss auf allen vier
  Seiten gleich sein, sonst haengt das Symbol in der Taskleiste schief.

Frueher zeichnete dieses Skript ein Platzhalter-Icon selbst. Seit die Suite
ein echtes Markenbild hat, waere ein gezeichneter Ersatz falsch: die Icons
muessen aus genau dem Bild entstehen, das auch im Logo-Banner steckt. Beide
Quellbilder liegen deshalb unskaliert im Repo - damit bleibt jede Ausgabe
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
LOGO_SOURCE_PATH = ICON_DIR / "budgetmanager-logo-source.png"
LOGO_PATH = ICON_DIR / "budgetmanager-logo.png"

# Einzel-PNGs, die Qt/Linux-Desktops und der Installer ausliefern.
PNG_SIZES = (16, 32, 48, 64, 128, 256, 512)

# Groesse der generischen budgetmanager.png (App-Icon fuer Qt/Linux).
MAIN_PNG_SIZE = 1024

# Mehrfachaufloesung im .ico. Windows waehlt je nach Kontext eine davon.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

# Rand je Seite des quadratischen Icons, als Anteil der Kantenlaenge.
# 2 % sind bei 16 px noch kein ganzer Bildpunkt und bei 512 px rund 10 - das
# Motiv fuellt die Flaeche, stoesst aber nirgends an.
ICON_MARGIN_RATIO = 0.02

# Ab welchem Alphawert ein Bildpunkt als Motiv zaehlt.
#
# Die gelieferten PNGs tragen ueber das ganze Blatt einen Schleier mit Alpha 1
# bis 3 - unsichtbar, aber fuer ``getbbox`` deckend. Ein Zuschnitt auf
# "Alpha > 0" schnitte deshalb gar nichts weg: beim Icon-Motiv meldete er
# 1165x1184 statt der tatsaechlichen 843x978. Alles ab Alpha 8 gehoert zum
# Bild; zwischen 8 und 128 verschiebt sich der Rahmen um hoechstens einen
# Bildpunkt, die Schwelle ist also unkritisch gewaehlt.
ALPHA_SCHWELLE = 8


def _load(path: Path, beschreibung: str) -> Image.Image:
    if not path.is_file():
        raise FileNotFoundError(
            f"Quellbild fehlt: {path}\nOhne {beschreibung} laesst sich nichts erzeugen."
        )
    return Image.open(path).convert("RGBA")


def motiv_rahmen(image: Image.Image, *, schwelle: int = ALPHA_SCHWELLE) -> tuple[int, int, int, int] | None:
    """Der Rahmen um alles, was sichtbar zum Motiv gehoert.

    Gemessen wird gegen :data:`ALPHA_SCHWELLE`, nicht gegen Null - warum,
    steht dort.
    """
    maske = image.getchannel("A").point(lambda wert: 255 if wert > schwelle else 0)
    return maske.getbbox()


def trimmed(image: Image.Image) -> Image.Image:
    """Schneidet die unsichtbaren Raender weg.

    Ist nichts sichtbar oder fuellt das Motiv das Blatt bereits, bleibt das
    Bild wie es ist.
    """
    box = motiv_rahmen(image)
    if box is None or box == (0, 0, image.width, image.height):
        return image
    return image.crop(box)


def square(image: Image.Image, *, margin_ratio: float = ICON_MARGIN_RATIO) -> Image.Image:
    """Setzt ``image`` mittig auf ein transparentes Quadrat mit gleichem Rand.

    Nicht zuschneiden und nicht verzerren: das Motiv behaelt sein
    Seitenverhaeltnis, die laengere Kante bestimmt die Groesse.
    """
    longest = max(image.width, image.height)
    # Der Rand kommt beidseitig dazu, deshalb geht er zweimal in die Kante ein.
    edge = int(round(longest / max(1e-6, 1.0 - 2.0 * margin_ratio)))
    canvas = Image.new("RGBA", (edge, edge), (0, 0, 0, 0))
    canvas.paste(image, ((edge - image.width) // 2, (edge - image.height) // 2), image)
    return canvas


def load_icon_source() -> Image.Image:
    """Das Icon-Motiv, randlos zugeschnitten und mittig auf ein Quadrat gesetzt."""
    return square(trimmed(_load(SOURCE_PATH, "das Markenbild")))


def load_logo_source() -> Image.Image:
    """Das Banner, randlos zugeschnitten."""
    return trimmed(_load(LOGO_SOURCE_PATH, "das Logo-Banner"))


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


def write_logo(source: Image.Image) -> Path:
    """Schreibt das ausgelieferte Banner (zugeschnitten, sonst unveraendert)."""
    source.save(LOGO_PATH, format="PNG")
    return LOGO_PATH


def create_icons() -> int:
    icon_source = load_icon_source()
    print(f"Icon-Quelle : {SOURCE_PATH.name} -> {icon_source.width}x{icon_source.height}")

    for path in write_pngs(icon_source):
        print(f"  geschrieben: {path.relative_to(PROJECT_ROOT)}")

    ico = write_ico(icon_source)
    print(
        f"  geschrieben: {ico.relative_to(PROJECT_ROOT)} "
        f"({', '.join(str(s) for s in ICO_SIZES)} px)"
    )

    logo_source = load_logo_source()
    logo = write_logo(logo_source)
    print(f"Logo-Quelle : {LOGO_SOURCE_PATH.name} -> {logo_source.width}x{logo_source.height}")
    print(f"  geschrieben: {logo.relative_to(PROJECT_ROOT)}")
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
