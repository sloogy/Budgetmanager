# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spec für BudgetManager.

Wird vom GitHub-Workflow (.github/workflows/build.yml) und für lokale Builds
verwendet:

    pyinstaller BudgetManager.spec --noconfirm

Erzeugt:
    dist/BudgetManager/BudgetManager.exe   (Windows onedir)
    dist/BudgetManager/BudgetManager       (Linux onedir)

WICHTIG — Nicht-Python-Assets müssen hier explizit gelistet sein,
sonst fehlen sie im Frozen-Build (siehe `datas`):
    - locales/   → Übersetzungen (utils/i18n.py erwartet sie relativ zum Bundle-Root)
    - data/default_categories.json → zentrale Default-Kategorien-Quelle
    - docs/help/ → lokale HTML-Hilfe/Wissensdatenbank inkl. Mindmap
"""

import sys
from pathlib import Path

block_cipher = None

_update_public_key = Path("resources/update_signing_public_key.b64")

datas = [
    ("locales", "locales"),
    ("data/default_categories.json", "data"),
    ("docs/help", "docs/help"),
    ("resources/icons", "resources/icons"),
    ("version.json", "."),
    # Quelle für „Hilfe → Neuerungen in dieser Version" (views/help_menu.py).
    # Ohne diesen Eintrag bleibt der Dialog im Frozen-Build leer.
    ("CHANGELOG.md", "."),
    # 25 mitgelieferte Theme-Profile — ThemeManager lädt sie aus
    # <bundle>/views/profiles (theme_manager.py: bundled_dir)
    ("views/profiles", "views/profiles"),
]

# Vorab-Releases werden bis zum finalen Release bewusst ohne Signatur gebaut.
# Sobald der Public Key materialisiert wurde, wird er automatisch eingebettet.
if _update_public_key.is_file():
    datas.append((str(_update_public_key), "resources"))
else:
    print("Hinweis: Build ohne Update-Signatur/Public-Key (Vorab-Release).")

# Qt-eigene Übersetzungen (qtbase_<lang>.qm) – nötig für lokalisierte native
# Kontextmenüs (Kopieren/Einfügen/…). Werden nach PySide6/translations gelegt,
# passend zur Suche in utils/qt_translator.py (_MEIPASS/PySide6/translations).
try:
    from PySide6.QtCore import QLibraryInfo
    _qt_tr_dir = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    _bundled = set()
    if _qt_tr_dir.is_dir():
        for _qm in _qt_tr_dir.glob("qt*_*.qm"):
            # nur qtbase_/qt_ Kataloge der unterstützten Sprachen einpacken
            if _qm.stem.split("_", 1)[-1] in ("de", "en", "fr"):
                datas.append((str(_qm), "PySide6/translations"))
                _bundled.add(_qm.name)
    # Build-Zeit-Nachweis (R2): fehlen die Kernkataloge, laut warnen.
    _required = {"qtbase_de.qm", "qtbase_fr.qm"}
    _missing = _required - _bundled
    if _missing:
        print("WARNUNG (R2): Qt-Übersetzungen fehlen im Build:", sorted(_missing))
        print("  → native Kontextmenüs (Kopieren/Einfügen) blieben in DE/FR englisch.")
        print("  → Pruefe die Qt-Installation:", _qt_tr_dir)
    else:
        print("OK (R2): Qt-Uebersetzungen gebundelt:", sorted(_bundled))
except Exception as _e:  # pragma: no cover
    print("Hinweis: Qt-Übersetzungen nicht gefunden:", _e)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Dev-/Build-Tools nie einpacken
        "pytest", "black", "mypy", "pyinstaller",
        # matplotlib ist optional und groß — nur einpacken, wenn wirklich genutzt
        "matplotlib",
        "tkinter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Laufzeitoptionen des eingebetteten Interpreters (dritte Position von EXE).
#
# -X utf8=1 entspricht PYTHONUTF8=1. Ohne diese Zeile startet der gebaute
# Stand im Legacy-Modus: Auf einer deutschen Windows-Installation ist
# locale.getpreferredencoding() dann cp1252, nicht UTF-8. PYTHONUTF8 stand
# bisher ausschliesslich in den CI-Env-Bloecken und in keiner Zeile
# Produktivcode - beim Nutzer galt es also nie. Als Option im Build und nicht
# als Umgebungsvariable, weil die drei Startwege (Doppelklick auf die EXE,
# Startmenue-Verknuepfung, Neustart durch den Updater) keine Variablen setzen.
runtime_options = [("X utf8=1", None, "OPTION")]

exe = EXE(
    pyz,
    a.scripts,
    runtime_options,
    exclude_binaries=True,
    name="BudgetManager",
    icon="resources/icons/budgetmanager.ico",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="BudgetManager",
)
