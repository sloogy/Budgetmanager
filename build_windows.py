from __future__ import annotations

# Build-Skript für BudgetManager Windows Installer
# Erstellt eine ausführbare EXE und ein Installer-Paket

import os
import sys
import subprocess
import shutil
from pathlib import Path

# Konfiguration
APP_NAME = "BudgetManager"
sys.path.insert(0, os.path.dirname(__file__))
import app_info
VERSION = app_info.APP_VERSION
MAIN_SCRIPT = "main.py"
ICON_FILE = "icon.ico"  # Optional: Icon-Datei

def clean_build_dirs():
    """Entfernt alte Build-Verzeichnisse"""
    print("🧹 Bereinige alte Build-Verzeichnisse...")
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  ✓ {dir_name} gelöscht")

def create_spec_file():
    """Erstellt eine PyInstaller .spec Datei mit allen Dependencies"""
    print("📝 Erstelle PyInstaller Spec-Datei...")
    
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

a = Analysis(
    ['{MAIN_SCRIPT}'],
    pathex=[],
    binaries=[],
    datas=[
        ('README.md',    '.'),
        ('CHANGELOG.md', '.'),
        ('LICENSE.txt',  '.'),
        ('locales',          'locales'),
        ('data',             'data'),
        ('views/profiles',   'views/profiles'),
        ('updater',          'updater'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'sqlite3',
        'openpyxl',
        'openpyxl.cell._writer',
        'PySide6.QtCharts',
        'PySide6.QtSvg',
        'openpyxl.styles.borders',
        'openpyxl.drawing.image',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['tkinter'],
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
    name='{APP_NAME}',
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
    icon='{ICON_FILE}' if os.path.exists('{ICON_FILE}') else None,
)
"""
    
    with open(f"{APP_NAME}.spec", "w", encoding="utf-8") as f:
        f.write(spec_content)
    
    print(f"  ✓ {APP_NAME}.spec erstellt")

def build_exe():
    """Erstellt die EXE mit PyInstaller"""
    print("🔨 Baue EXE mit PyInstaller...")
    
    try:
        # Prüfe ob PyInstaller installiert ist
        subprocess.run(["pyinstaller", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ PyInstaller nicht gefunden. Installiere mit: pip install pyinstaller")
        return False
    
    # PyInstaller ausführen
    cmd = [
        "pyinstaller",
        "--clean",
        "--noconfirm",
        f"{APP_NAME}.spec"
    ]
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print(f"  ✓ EXE erfolgreich erstellt: dist/{APP_NAME}.exe")
        return True
    else:
        print("❌ Fehler beim Erstellen der EXE")
        return False

def copy_additional_files():
    """Kopiert zusätzliche Dateien ins dist-Verzeichnis"""
    print("📋 Kopiere zusätzliche Dateien...")
    
    files_to_copy = [
        'README.md',
        'CHANGELOG.md',
        'LICENSE.txt',
            ]
    
    dist_dir = Path('dist')
    for file in files_to_copy:
        if os.path.exists(file):
            shutil.copy2(file, dist_dir / file)
            print(f"  ✓ {file} kopiert")
        else:
            print(f"  ⚠ {file} nicht gefunden")

def create_license_if_missing():
    """Erstellt eine Basis-Lizenz-Datei falls nicht vorhanden"""
    if not os.path.exists('LICENSE.txt'):
        print("📄 Erstelle LICENSE.txt...")
        with open('LICENSE.txt', 'w', encoding='utf-8') as f:
            f.write(f"""BudgetManager {VERSION}
Copyright (c) 2024-2025

MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
""")
        print("  ✓ LICENSE.txt erstellt")

def build_installer():
    """Baut den Installer mit Inno Setup (falls verfügbar)"""
    print("📦 Baue Installer mit Inno Setup...")
    
    # Suche nach Inno Setup Compiler
    inno_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]
    
    iscc_path = None
    for path in inno_paths:
        if os.path.exists(path):
            iscc_path = path
            break
    
    if not iscc_path:
        print("⚠ Inno Setup nicht gefunden. Installer wird übersprungen.")
        print("  Hinweis: Inno Setup kann von https://jrsoftware.org/isinfo.php heruntergeladen werden")
        return False
    
    # Inno Setup Script ausführen
    iss_file = "installer/budgetmanager_setup.iss"
    if not os.path.exists(iss_file):
        print(f"❌ Installer-Skript nicht gefunden: {iss_file}")
        return False
    
    cmd = [iscc_path, iss_file]
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("  ✓ Installer erfolgreich erstellt")
        return True
    else:
        print("❌ Fehler beim Erstellen des Installers")
        return False

def main():
    print(f"""
╔════════════════════════════════════════════════════╗
║  BudgetManager {VERSION} - Build Skript           ║
╚════════════════════════════════════════════════════╝
""")
    
    # Schritt 1: Bereinigung
    clean_build_dirs()
    
    # Schritt 2: Lizenz erstellen falls nötig
    create_license_if_missing()
    
    # Schritt 3: Spec-Datei erstellen
    create_spec_file()
    
    # Schritt 4: EXE bauen
    if not build_exe():
        print("\n❌ Build fehlgeschlagen!")
        return 1
    
    # Schritt 5: Zusätzliche Dateien kopieren
    copy_additional_files()

    # Schritt 6: Installer erstellen
    build_installer()
    
    print(f"""
╔════════════════════════════════════════════════════╗
║  ✓ Build erfolgreich abgeschlossen!               ║
╚════════════════════════════════════════════════════╝

Ausgabe-Dateien:
  • dist/{APP_NAME}.exe
  • installer_output/{APP_NAME}_Setup_{VERSION}.exe (falls Inno Setup verfügbar)

Nächste Schritte:
  1. Teste die EXE: dist/{APP_NAME}.exe
  2. Teste den Installer auf einem Clean-System
  3. Erstelle Release-Notes
""")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
