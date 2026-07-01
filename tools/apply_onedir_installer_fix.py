from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

# ── 1) BudgetManager.spec auf onedir/COLLECT umstellen ─────────────
spec_path = ROOT / "BudgetManager.spec"
spec = spec_path.read_text(encoding="utf-8")

spec = spec.replace(
    "Erzeugt:\n"
    "    dist/BudgetManager.exe   (Windows)\n"
    "    dist/BudgetManager       (Linux)\n",
    "Erzeugt:\n"
    "    dist/BudgetManager/BudgetManager.exe   (Windows onedir)\n"
    "    dist/BudgetManager/BudgetManager       (Linux onedir)\n",
)

new_exe_block = """exe = EXE(
    pyz,
    a.scripts,
    [],
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
"""

spec = re.sub(r"exe = EXE\([\s\S]*?\)\s*$", new_exe_block, spec)
spec_path.write_text(spec, encoding="utf-8")


# ── 2) Installer packt dist/BudgetManager/* statt Einzel-EXE ───────
iss_path = ROOT / "installer" / "budgetmanager_setup.iss"
iss = iss_path.read_text(encoding="utf-8")
iss = iss.replace(
    "; - PyInstaller EXE im dist/ Ordner",
    "; - PyInstaller onedir-Build im dist\\BudgetManager\\ Ordner",
)
iss = iss.replace(
    'Source: "dist\\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion',
    'Source: "dist\\BudgetManager\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs',
)
iss_path.write_text(iss, encoding="utf-8")


# ── 3) GitHub Actions: Windows/Linux als onedir-Artefakt ───────────
workflow_path = ROOT / ".github" / "workflows" / "build.yml"
workflow = """name: Build Executables

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: windows-latest
            artifact_name: BudgetManager-windows
            pyinstaller_output: dist/BudgetManager

          - os: ubuntu-latest
            artifact_name: BudgetManager-linux
            pyinstaller_output: dist/BudgetManager

    runs-on: ${{ matrix.os }}

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r requirements-build.txt
          python -m pip install -r requirements-dev.txt
          python -m pip install --force-reinstall "black==26.5.1"

      - name: Install Qt offscreen dependencies (Linux)
        if: runner.os == 'Linux'
        run: sudo apt-get update && sudo apt-get install -y libegl1 libgl1 libxkbcommon-x11-0 libdbus-1-3 libfontconfig1

      - name: Check version consistency
        run: python tools/sync_version.py --check

      - name: Verify Qt translation catalogs
        run: python tools/verify_qt_translations.py

      - name: Compile all sources
        run: python -m compileall -q . -x '_attic|__pycache__|.venv|venv'

      - name: Check model formatting
        run: |
          python -m black --version
          python -m black --check model/

      - name: Type-check model layer
        run: python -m mypy model/

      - name: Run core tests
        shell: bash
        env:
          QT_QPA_PLATFORM: offscreen
          PYTHONUTF8: "1"
          PYTHONIOENCODING: utf-8
          PYTHONDONTWRITEBYTECODE: "1"
        run: |
          python -m pytest tests/ -v -ra --tb=short

      - name: Clean generated test artifacts
        run: python tools/clean_release_tree.py

      - name: Verify lint and release procedure
        run: python tools/lint_procedure_check.py

      - name: Build with PyInstaller
        run: pyinstaller BudgetManager.spec --noconfirm --clean

      - name: Validate PyInstaller onedir output
        shell: bash
        run: |
          test -d "${{ matrix.pyinstaller_output }}"
          test -f "${{ matrix.pyinstaller_output }}/BudgetManager.exe" || test -f "${{ matrix.pyinstaller_output }}/BudgetManager"
          test -d "${{ matrix.pyinstaller_output }}/_internal"
          ls -lah "${{ matrix.pyinstaller_output }}"

      - name: Upload onedir artifact
        uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.artifact_name }}
          path: ${{ matrix.pyinstaller_output }}/**
          if-no-files-found: error

  installer:
    needs: build
    runs-on: windows-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Download Windows onedir artifact
        uses: actions/download-artifact@v4
        with:
          name: BudgetManager-windows
          path: dist/BudgetManager/

      - name: Prepare installer input
        shell: pwsh
        run: |
          if (-not (Test-Path "dist\\BudgetManager\\BudgetManager.exe")) {
            throw "dist\\BudgetManager\\BudgetManager.exe fehlt; Installer kann nicht gebaut werden."
          }
          if (-not (Test-Path "dist\\BudgetManager\\_internal")) {
            throw "dist\\BudgetManager\\_internal fehlt; Build ist nicht onedir."
          }

      - name: Install Inno Setup
        shell: pwsh
        run: |
          choco install innosetup --no-progress -y

      - name: Build Windows installer
        shell: pwsh
        run: |
          $candidates = @(
            "${env:ProgramFiles(x86)}\\Inno Setup 6\\ISCC.exe",
            "${env:ProgramFiles}\\Inno Setup 6\\ISCC.exe",
            "${env:ProgramFiles(x86)}\\Inno Setup 7\\ISCC.exe",
            "${env:ProgramFiles}\\Inno Setup 7\\ISCC.exe"
          )
          $iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
          if (-not $iscc) { throw "ISCC.exe nicht gefunden." }
          & $iscc "installer\\budgetmanager_setup.iss"
          $setup = Get-ChildItem -Path . -Filter "BudgetManager_Setup_*.exe" -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 1
          if (-not $setup) { throw "Installer-EXE wurde nicht erzeugt." }
          Copy-Item -Force $setup.FullName "BudgetManager_Setup.exe"

      - name: Upload installer artifact
        uses: actions/upload-artifact@v4
        with:
          name: BudgetManager_Setup.exe
          path: BudgetManager_Setup.exe
          if-no-files-found: error

  manifest:
    needs: [build, installer]
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Download Windows artifact
        uses: actions/download-artifact@v4
        with:
          name: BudgetManager-windows
          path: artifacts/windows/

      - name: Download Linux artifact
        uses: actions/download-artifact@v4
        with:
          name: BudgetManager-linux
          path: artifacts/linux/

      - name: Download Windows installer artifact
        uses: actions/download-artifact@v4
        with:
          name: BudgetManager_Setup.exe
          path: artifacts/windows/

      - name: Build release assets + updater manifest
        shell: bash
        run: |
          TAG="${{ github.ref_name }}"
          VERSION="${TAG#v}"
          BASE="https://github.com/${{ github.repository }}/releases/download/${TAG}"

          python tools/build_release_assets.py \\
            --version "${VERSION}" \\
            --release-tag "${TAG}" \\
            --base-url "${BASE}" \\
            --windows-build-dir artifacts/windows \\
            --linux-build-dir artifacts/linux \\
            --out-dir release_assets \\
            --require-installer

          echo "Release assets:"
          ls -lah release_assets

      - name: Verify updater manifest stays updater-safe
        shell: bash
        run: |
          python - <<'PY'
          import json
          import zipfile
          from pathlib import Path

          data = json.loads(Path('release_assets/latest.json').read_text(encoding='utf-8'))
          assets = data['assets']
          assert assets['windows']['type'] == 'portable-zip', assets['windows']
          assert assets['linux']['type'] == 'portable-zip', assets['linux']
          assert assets['windows']['url'].endswith('-portable-windows.zip'), assets['windows']
          assert assets['linux']['url'].endswith('-portable-linux.zip'), assets['linux']
          assert assets['windows_installer']['type'] == 'installer', assets['windows_installer']
          assert assets['windows_installer_zip']['type'] == 'installer-zip'
          assert Path('release_assets/SHA256SUMS.txt').is_file()

          with zipfile.ZipFile(next(Path('release_assets').glob('*-portable-windows.zip'))) as zf:
              names = set(zf.namelist())
              assert 'BudgetManager.exe' in names
              assert 'start-windows.cmd' in names
              assert 'data/.keep' in names
              assert any(n.startswith('_internal/') for n in names), 'Windows-ZIP ohne _internal/'
          with zipfile.ZipFile(next(Path('release_assets').glob('*-portable-linux.zip'))) as zf:
              names = set(zf.namelist())
              assert 'BudgetManager' in names
              assert 'start-linux.sh' in names
              assert 'data/.keep' in names
              assert any(n.startswith('_internal/') for n in names), 'Linux-ZIP ohne _internal/'
          print('latest.json und portable ZIPs OK')
          PY

      - name: Upload to GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          generate_release_notes: true
          files: release_assets/*
"""
workflow_path.write_text(workflow, encoding="utf-8")


# ── 4) Release-Asset-Builder: onedir komplett zippen ───────────────
assets_path = ROOT / "tools" / "build_release_assets.py"
assets = assets_path.read_text(encoding="utf-8")

insert_after = """def _copy_file(src: Path, dst: Path, executable: bool = False) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    if executable:
        try:
            mode = os.stat(dst).st_mode
            os.chmod(dst, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            pass
"""

helper = insert_after + '''

def _copy_bundle_contents(src_dir: Path, dst_dir: Path) -> None:
    """Kopiert einen PyInstaller-onedir-Bundle-Ordner in ein portables ZIP-Arbeitsverzeichnis.

    Installer-Artefakte werden bewusst ausgeschlossen, weil der Manifest-Job
    Windows-Bundle und Setup-EXE im selben artifacts/windows-Ordner sammelt.
    """
    dst_dir.mkdir(parents=True, exist_ok=True)
    excluded_names = {
        "BudgetManager_Setup.exe",
        "BudgetManager_Setup.zip",
        "SHA256SUMS.txt",
        "latest.json",
    }
    for src in sorted(src_dir.rglob("*")):
        rel = src.relative_to(src_dir)
        if any(part.startswith("BudgetManager_Setup_") for part in rel.parts):
            continue
        if src.name in excluded_names:
            continue
        dst = dst_dir / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
'''

assets = assets.replace(insert_after, helper)

assets = re.sub(
    r"def _create_portable_windows_zip\(out_dir: Path, version: str, windows_exe: Path\) -> Path:[\s\S]*?def _create_portable_linux_zip",
    """def _create_portable_windows_zip(out_dir: Path, version: str, windows_exe: Path) -> Path:
    work = out_dir / "_portable_windows"
    if work.exists():
        shutil.rmtree(work)

    _copy_bundle_contents(windows_exe.parent, work)

    (work / "data" / "backups").mkdir(parents=True, exist_ok=True)
    (work / "data" / ".keep").touch()
    (work / "data" / "backups" / ".keep").touch()
    _write_windows_starter(work / "start-windows.cmd")
    _write_portable_readme(work / "README.txt", version, "windows")
    zip_path = out_dir / f"BudgetManager-v{version}-portable-windows.zip"
    _write_zip(zip_path, work)
    shutil.rmtree(work)
    return zip_path


def _create_portable_linux_zip""",
    assets,
)

assets = re.sub(
    r"def _create_portable_linux_zip\(out_dir: Path, version: str, linux_binary: Path\) -> Path:[\s\S]*?def _create_installer_zip",
    """def _create_portable_linux_zip(out_dir: Path, version: str, linux_binary: Path) -> Path:
    work = out_dir / "_portable_linux"
    if work.exists():
        shutil.rmtree(work)

    _copy_bundle_contents(linux_binary.parent, work)

    (work / "data" / "backups").mkdir(parents=True, exist_ok=True)
    (work / "data" / ".keep").touch()
    (work / "data" / "backups" / ".keep").touch()
    _write_linux_starter(work / "start-linux.sh")
    _write_portable_readme(work / "README.txt", version, "linux")
    zip_path = out_dir / f"BudgetManager-v{version}-portable-linux.zip"
    _write_zip(zip_path, work)
    shutil.rmtree(work)
    return zip_path


def _create_installer_zip""",
    assets,
)

assets_path.write_text(assets, encoding="utf-8")


# ── 5) Updater: portable ZIP bevorzugen, keine rohe Onefile-EXE mehr ─
common_path = ROOT / "updater" / "common.py"
common = common_path.read_text(encoding="utf-8")
common = common.replace(
    """        elif _is_frozen():
            # Standalone-EXE und portable Onefile-Builds können am robustesten
            # ueber das direkte Windows-EXE-Asset aktualisiert werden.
            keys.append("direct_windows_exe")
        keys.extend(["windows", "portable_zip"])""",
    """        # Ab v2.1.2 werden Windows-Builds als PyInstaller-onedir ausgeliefert.
        # Eine rohe Einzel-EXE ist ohne _internal/python312.dll nicht lauffähig.
        keys.extend(["windows", "portable_zip"])""",
)
common = common.replace(
    """    elif platform_key == "linux":
        if _is_frozen():
            keys.append("direct_linux_binary")
        keys.extend(["linux", "portable_zip"])""",
    """    elif platform_key == "linux":
        # Auch Linux-onedir braucht seine _internal-Abhängigkeiten.
        keys.extend(["linux", "portable_zip"])""",
)
common_path.write_text(common, encoding="utf-8")


# ── 6) Budget-Tab Windows-Crash: Zelle erst im nächsten Eventloop zurücksetzen ─
budget_tab_path = ROOT / "views" / "tabs" / "budget_tab.py"
budget_tab = budget_tab_path.read_text(encoding="utf-8")

new_budget_methods = '''    def _handle_leaf_ask_due(self, item: QTableWidgetItem, r: int, c: int, month: int, typ: str, cat: str) -> None:
        """Leaf-Zelle mit Detaildialog.

        Windows/PySide-Stabilität:
        Im itemChanged-Signal wird kein Dialog geöffnet und die aktive Zelle
        nicht sofort umgeschrieben. Beides passiert erst im nächsten
        Event-Loop-Tick, wenn commitData/closeEditor abgeschlossen sind.
        """
        try:
            typed = parse_amount(item.text())
        except Exception:
            typed = 0.0
        if typ == TYP_EXPENSES and typed < 0:
            typed = abs(typed)

        if getattr(self, "_ask_due_dialog_pending", False):
            return
        self._ask_due_dialog_pending = True

        year = int(self.year_spin.value())
        prev = self._get_db_value(typ, cat, month)

        QTimer.singleShot(
            0,
            lambda row=r, col=c, y=year, t=typ, ca=cat, mo=month, am=float(typed), old=float(prev): (
                self._restore_cell_and_open_leaf_dialog(row, col, y, t, ca, mo, am, old)
            ),
        )

    def _restore_cell_and_open_leaf_dialog(
        self,
        r: int,
        c: int,
        year: int,
        typ: str,
        cat: str,
        month: int,
        typed: float,
        prev: float,
    ) -> None:
        """Setzt die Zelle zurück und öffnet danach stabil den Detaildialog."""
        try:
            if not self.isVisible():
                self._ask_due_dialog_pending = False
                return

            item = self.table.item(r, c)
            if item is not None:
                previous_internal = self._internal_change
                self._internal_change = True
                self.table.blockSignals(True)
                try:
                    item.setText(fmt_amount(prev))
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                finally:
                    self.table.blockSignals(False)
                    self._internal_change = previous_internal

            self._open_leaf_ask_due_dialog(year, typ, cat, month, typed)

        except RuntimeError:
            self._ask_due_dialog_pending = False
        except Exception:
            self._ask_due_dialog_pending = False
            logger.exception("Budget-Detaildialog konnte nicht stabil geöffnet werden")
            QMessageBox.critical(self, tr("msg.error"), tr("msg.error"))

'''

budget_tab = re.sub(
    r"    def _handle_leaf_ask_due\(self, item: QTableWidgetItem, r: int, c: int, month: int, typ: str, cat: str\) -> None:[\s\S]*?(?=    def _open_leaf_ask_due_dialog)",
    new_budget_methods,
    budget_tab,
)
budget_tab_path.write_text(budget_tab, encoding="utf-8")

print("Onedir-Installer-Fix angewendet.")
