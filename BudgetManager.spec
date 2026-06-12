# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spec für BudgetManager.

Wird vom GitHub-Workflow (.github/workflows/build.yml) und für lokale Builds
verwendet:

    pyinstaller BudgetManager.spec --noconfirm

Erzeugt:
    dist/BudgetManager.exe   (Windows)
    dist/BudgetManager       (Linux)

WICHTIG — Nicht-Python-Assets müssen hier explizit gelistet sein,
sonst fehlen sie im Frozen-Build (siehe `datas`):
    - locales/   → Übersetzungen (utils/i18n.py erwartet sie relativ zum Bundle-Root)
    - data/default_categories.json → zentrale Default-Kategorien-Quelle
"""

import sys
from pathlib import Path

block_cipher = None

datas = [
    ("locales", "locales"),
    ("data/default_categories.json", "data"),
    # 25 mitgelieferte Theme-Profile — ThemeManager lädt sie aus
    # <bundle>/views/profiles (theme_manager.py: bundled_dir)
    ("views/profiles", "views/profiles"),
]

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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="BudgetManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=["vcruntime140.dll", "python3*.dll", "Qt6*.dll"],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
