# Icon erstellen fuer BudgetManager (Windows)

## Problem

Die App nutzt Unicode-Zeichen als UI-Symbole (keine Bilddateien).
Fuer den Windows-Installer (Inno Setup) und die EXE-Datei (PyInstaller)
wird jedoch eine binaere `icon.ico`-Datei benoetigt.

Ohne diese Datei wird `SetupIconFile` im `.iss`-Skript auskommentiert
und PyInstaller verwendet das Standard-Python-Icon.

---

## Loesung: icon.ico per Python generieren

### Voraussetzung

```
pip install Pillow
```

Pillow ist die einzige externe Abhaengigkeit. Das Skript benoetigt
keine weiteren Bibliotheken und laeuft auf Linux, macOS und Windows.

---

### Skript ausfuehren

Aus dem **Projektroot** ausfuehren:

```bash
python tools/create_icon.py
```

Das Skript erstellt `icon.ico` direkt im Projektroot.

---

### Was das Skript tut (`tools/create_icon.py`)

```python
# Auszug – vollstaendiges Skript: tools/create_icon.py

ICO_SIZES = [256, 128, 64, 48, 32, 16]   # alle Windows-relevanten Groessen

def draw_icon(size: int) -> Image.Image:
    # Blauer Hintergrund (#2563EB) mit abgerundeten Ecken
    # Weisses Euro-Zeichen '€' zentriert
    ...

frames[0].save(
    "icon.ico",
    format="ICO",
    sizes=[(s, s) for s in ICO_SIZES],
    append_images=frames[1:],
)
```

**Design-Entscheidungen:**

| Eigenschaft     | Wert                          |
|-----------------|-------------------------------|
| Hintergrundfarbe| `#2563EB` (BudgetManager-Blau)|
| Symbol          | `€` (weiss, ~60 % der Groesse)|
| Ecken           | Abgerundet (`radius = size/8`)|
| Transparenz     | RGBA (korrekte ICO-Transparenz)|
| Groessen        | 256, 128, 64, 48, 32, 16 px   |

Das Symbol kann in `draw_icon()` von `"€"` auf `"B"` (oder ein anderes
Zeichen) geaendert werden, ohne den Rest des Skripts zu modifizieren.

---

## icon.ico in den Build-Prozess einbinden

### 1. PyInstaller (`build_windows.py`)

Die Datei `build_windows.py` prueft bereits, ob `icon.ico` vorhanden ist:

```python
# build_windows.py, Zeile 93 (im generierten .spec)
icon='{ICON_FILE}' if os.path.exists('{ICON_FILE}') else None,
```

Sobald `icon.ico` im Projektroot liegt, wird das Icon **automatisch**
beim naechsten `python build_windows.py` eingebunden. Es ist keine
weitere Aenderung noetig.

Zur Kontrolle: `ICON_FILE = "icon.ico"` ist bereits auf Zeile 16
in `build_windows.py` definiert.

---

### 2. Inno Setup (`installer/budgetmanager_setup.iss`)

Zeile 33 im `.iss`-Skript ist aktuell auskommentiert:

```ini
;SetupIconFile=icon.ico  ; Auskommentiert – icon.ico muss erst erstellt werden
```

Nach dem Generieren von `icon.ico` das Semikolon entfernen:

```ini
SetupIconFile=icon.ico
```

Das Icon erscheint dann im Installer-Fenster, in der
Systemsteuerung ("Programme und Funktionen") und auf dem Desktop-Symbol
des Installers selbst.

---

## Alternative: ImageMagick (`convert`)

Wer Pillow nicht installieren moechte, kann ImageMagick verwenden.
`convert` ist auf Linux haeufig vorinstalliert; auf Windows als separates
Paket verfuegbar (https://imagemagick.org).

### PNG zu ICO konvertieren

```bash
# Schritt 1: PNG erstellen (beliebiges Bildbearbeitungsprogramm)
# Schritt 2: PNG zu multi-size ICO konvertieren
convert input.png \
  -define icon:auto-resize=256,128,64,48,32,16 \
  icon.ico
```

### Direkt ein einfaches Icon per convert erzeugen

```bash
convert \
  -size 256x256 xc:"#2563EB" \
  -fill white -font DejaVu-Sans-Bold -pointsize 160 \
  -gravity center -annotate 0 "€" \
  -define icon:auto-resize=256,128,64,48,32,16 \
  icon.ico
```

**Hinweis:** `convert` heisst unter neueren ImageMagick-Versionen (7+)
auf Windows `magick convert` oder einfach `magick`.

---

## Verzeichnisstruktur nach dem Generieren

```
BudgetManager/
├── icon.ico                 <-- neu erstellt
├── tools/
│   └── create_icon.py       <-- dieses Skript
├── build_windows.py         <-- liest icon.ico automatisch
└── installer/
    └── budgetmanager_setup.iss  <-- SetupIconFile einkommentieren
```

---

## Troubleshooting

| Problem | Loesung |
|---|---|
| `ModuleNotFoundError: PIL` | `pip install Pillow` |
| Symbol wird als Kaestchen angezeigt | Pillow nutzt Fallback-Font; Ergebnis ist funktional, aber weniger schoen. TrueType-Font installieren oder Symbol in `draw_icon()` anpassen. |
| ICO funktioniert nicht im Installer | Sicherstellen, dass die Datei wirklich im **Projektroot** liegt (gleiche Ebene wie `main.py`). |
| `convert: command not found` | ImageMagick installieren: `sudo dnf install imagemagick` / `sudo apt install imagemagick` |
