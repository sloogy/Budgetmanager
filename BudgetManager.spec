# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Dokumentation
        ('README.md',    '.'),
        ('CHANGELOG.md', '.'),
        ('LICENSE.txt',  '.'),

        # Sprachdateien (PFLICHT – ohne diese startet die App auf Englisch-Fallback)
        ('locales',          'locales'),

        # Standard-Kategorien für DB-Reset und Erststart (KEIN c.enc/users.json!)
        ('data/default_categories.json', 'data'),

        # Theme-Profile (25 vordefinierte + benutzerdefinierte)
        ('views/profiles',   'views/profiles'),

        # Updater-Modul
        ('updater',          'updater'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtCharts',
        'PySide6.QtSvg',
        'sqlite3',
        'openpyxl',
        'openpyxl.cell._writer',
        'openpyxl.styles.borders',
        'openpyxl.drawing.image',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy'],
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
    name='BudgetManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)
