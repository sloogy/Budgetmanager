from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

from packaging import version as _version

from updater.common import (
    app_dir,
    backup_current_zip,
    current_exe_filename,
    enable_utf8_console,
    stable_exe_filename,
    update_target_exe_filename,
    find_staged_root,
    installation_marker_path,
    is_windows,
    read_check_result,
    staging_dir_for,
    updates_dir,
)


EXCLUDE = (
    "data",        # DB, Settings, Backups
    "updates",     # update cache/backups behalten
    ".git",
    "__pycache__",
)


def read_marker(staging: Path) -> dict:
    marker = staging / "_update_marker.json"
    if marker.exists():
        import json
        return json.loads(marker.read_text(encoding="utf-8"))
    return {}


def latest_staged_version() -> str | None:
    staging_root = updates_dir() / "staging"
    if not staging_root.exists():
        return None
    versions = [p.name for p in staging_root.iterdir() if p.is_dir()]
    if not versions:
        return None

    def _key(v: str):
        try:
            return _version.parse(v)
        except Exception:
            return _version.parse("0")

    versions.sort(key=_key)
    return versions[-1]


def _staging_has_content(version_str: str) -> bool:
    """True, wenn der Staging-Ordner dieser Version existiert und nicht leer ist."""
    d = staging_dir_for(version_str)
    return d.is_dir() and any(d.iterdir())


def target_staged_version() -> str | None:
    """Bestimmt die anzuwendende Staging-Version.

    Bevorzugt die Version, die der letzte ``check_update`` tatsächlich gestaged
    hat (aus ``updates/last_check.json``: ``staged_version`` bzw. ``remote``).
    Das verhindert, dass ein alter, höher nummerierter Staging-Ordner (z.B. ein
    Beta-Rest ``2.1.0``) angewendet wird, obwohl gerade ``2.0.9`` vorbereitet
    wurde. Fällt sicher auf die höchste vorhandene Staging-Version zurück, falls
    kein/kein gültiges Prüfergebnis vorliegt.
    """
    res = read_check_result()
    preferred = res.get("staged_version") or res.get("remote")
    if isinstance(preferred, str) and preferred.strip():
        preferred = preferred.strip()
        if _staging_has_content(preferred):
            return preferred
        logger.warning(
            "Bevorzugte Update-Version %s aus last_check.json hat keinen "
            "gestageten Inhalt – fallback auf höchste Staging-Version.",
            preferred,
        )
    return latest_staged_version()


def remove_paths(target: Path, exclude: tuple[str, ...]) -> None:
    """Entfernt alles im App-Ordner außer exclude.

    Fehler werden NICHT mehr verschluckt, sondern protokolliert – sonst
    scheitern Updates lautlos (z.B. gesperrte Dateien unter Windows).
    """
    for item in target.iterdir():
        if item.name in exclude:
            continue
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        except OSError as e:
            logger.warning("Konnte '%s' nicht entfernen: %s", item, e)
            raise


def copy_new(src_root: Path, dst_root: Path, exclude: tuple[str, ...]) -> None:
    for item in src_root.iterdir():
        if item.name in exclude:
            continue
        dst = dst_root / item.name
        if item.is_dir():
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(item, dst)
        else:
            shutil.copy2(item, dst)


# ──────────────────────────────────────────────────────────────────────────
# Binary-Replace-Erkennung
# ──────────────────────────────────────────────────────────────────────────
def _staged_target_binary(src_root: Path) -> Path | None:
    """Gibt die gestagete App-Binary zurück, wenn sie direkt erkennbar ist.

    Unterstützt sowohl den aktuell laufenden Namen als auch den stabilen
    Zielnamen. Damit können alte versionierte Portable-Builds sauber auf
    ``BudgetManager.exe``/``BudgetManager`` migriert werden.
    """
    for target_name in dict.fromkeys((
        update_target_exe_filename(),
        current_exe_filename(),
        stable_exe_filename(),
    )):
        candidate = src_root / target_name
        if candidate.is_file():
            return candidate
    return None


def _launch_exe_filename(src_root: Path) -> str:
    """Bestimmt die Binary, die nach dem Update gestartet werden soll."""
    preferred = update_target_exe_filename()
    if (src_root / preferred).is_file() or (app_dir() / preferred).exists():
        return preferred
    stable = stable_exe_filename()
    if (src_root / stable).is_file() or (app_dir() / stable).exists():
        return stable
    return current_exe_filename()


def _restart_after_update(src_root: Path) -> None:
    """Startet die App nach einem erfolgreichen Linux/DEV-Update neu.

    In Tests oder explizit deaktiviertem Modus wird nicht neu gestartet, damit
    CI-Läufe nicht hängen bleiben.
    """
    if os.environ.get("BM_UPDATER_NO_RESTART") or os.environ.get("PYTEST_CURRENT_TEST"):
        return
    try:
        if getattr(sys, "frozen", False):
            exe = app_dir() / _launch_exe_filename(src_root)
            if exe.exists():
                subprocess.Popen([str(exe)], cwd=str(app_dir()), close_fds=True)
        else:
            subprocess.Popen([sys.executable, str(app_dir() / "main.py")], cwd=str(app_dir()), close_fds=True)
    except Exception as e:
        logger.warning("App-Neustart nach Update fehlgeschlagen: %s", e)


def _replace_binary_inplace(new_binary: Path, target_path: Path) -> None:
    """Ersetzt eine Binary atomar (für Linux/DEV).

    Unter Linux darf die laufende Binary umbenannt/ersetzt werden, solange sie
    nicht zum Schreiben geöffnet wird. Wir schreiben die neue Datei daher als
    separate '.new'-Datei und schieben sie per os.replace() an ihren Platz.
    """
    tmp = target_path.with_name(target_path.name + ".new")
    if tmp.exists():
        tmp.unlink()
    shutil.copy2(new_binary, tmp)
    # Ausführbar machen (Linux/macOS)
    try:
        mode = os.stat(tmp).st_mode
        os.chmod(tmp, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError as e:
        logger.debug("chmod fehlgeschlagen: %s", e)
    os.replace(tmp, target_path)  # atomarer rename über die alte Datei


# ──────────────────────────────────────────────────────────────────────────
# Windows: Externer Batch-Helfer (löst die EXE-Selbstsperre)
# ──────────────────────────────────────────────────────────────────────────
def _build_windows_helper_batch(
    src_root: Path,
    dst_dir: Path,
    wait_exe: str,
    launch_exe: str,
    log_path: Path,
) -> str:
    """Erzeugt den Inhalt eines Batch-Skripts, das das Update anwendet.

    Ablauf des Batches:
      1. Wartet, bis KEIN Prozess der App-EXE mehr läuft (die laufende EXE
         kann sich unter Windows nicht selbst überschreiben).
      2. Kopiert die gestageten Dateien per robocopy in den App-Ordner
         (data/ und updates/ bleiben unangetastet). robocopys Retry
         überbrückt verbleibende kurze Datei-Sperren.
      3. Startet die App neu.
      4. Löscht sich selbst.
    """
    src = str(src_root)
    dst = str(dst_dir)
    exe = wait_exe
    launch = launch_exe
    launch_path = str(dst_dir / launch_exe)
    log = str(log_path)

    # WICHTIG: keine geschweiften Klammern im Batch (Format-Konflikte vermeiden).
    # Pfade immer in Anführungszeichen (Leerzeichen/Umlaute).
    template = r"""@echo off
setlocal enableextensions
chcp 65001 >nul 2>&1
title BudgetManager Update

set "LOGFILE=__LOG__"
set "SRC=__SRC__"
set "DST=__DST__"
set "EXENAME=__EXE__"
set "LAUNCHEXE=__LAUNCHEXE__"
set "LAUNCHPATH=__LAUNCHPATH__"

echo [%DATE% %TIME%] Update gestartet > "%LOGFILE%"
echo.
echo   BudgetManager wird aktualisiert - bitte warten...
echo.

rem --- 1) Warten bis die Anwendung vollstaendig beendet ist ---
set /a _tries=0
:waitloop
tasklist /FI "IMAGENAME eq %EXENAME%" 2>nul | find /I "%EXENAME%" >nul 2>&1
if errorlevel 1 goto copyphase
set /a _tries+=1
if %_tries% GEQ 150 goto copyphase
ping -n 2 127.0.0.1 >nul 2>&1
goto waitloop

:copyphase
if /I NOT "%EXENAME%"=="%LAUNCHEXE%" (
  if exist "%DST%\%EXENAME%" del /f /q "%DST%\%EXENAME%" >> "%LOGFILE%" 2>&1
)
echo [%DATE% %TIME%] Kopiere neue Dateien... >> "%LOGFILE%"
rem robocopy: /E inkl. Unterordner, data+updates ausschliessen,
rem /R Retries + /W Wartezeit ueberbruecken kurzzeitige Sperren.
robocopy "%SRC%" "%DST%" /E /XD data updates .git __pycache__ /R:30 /W:1 /NP /NJH /NJS >> "%LOGFILE%" 2>&1
set "RC=%ERRORLEVEL%"
echo [%DATE% %TIME%] robocopy Rueckgabecode=%RC% >> "%LOGFILE%"

rem robocopy: Codes 0-7 = Erfolg, ab 8 = Fehler
if %RC% GEQ 8 goto failed

echo [%DATE% %TIME%] Update erfolgreich angewendet. >> "%LOGFILE%"
echo.
echo   Update abgeschlossen. App wird neu gestartet.
timeout /t 2 /nobreak >nul 2>&1
start "" "%LAUNCHPATH%"

rem --- Selbstloeschung des Batch-Skripts ---
(goto) 2>nul & del "%~f0"
exit /b 0

:failed
echo [%DATE% %TIME%] FEHLER beim Kopieren (Code %RC%). >> "%LOGFILE%"
echo.
echo   Update fehlgeschlagen (robocopy-Code %RC%).
echo   Ein Rollback-Backup liegt in: updates\backup
echo   Details siehe: "%LOGFILE%"
echo.
pause
exit /b 1
"""
    return (
        template
        .replace("__LOG__", log)
        .replace("__SRC__", src)
        .replace("__DST__", dst)
        .replace("__EXE__", exe)
        .replace("__LAUNCHEXE__", launch)
        .replace("__LAUNCHPATH__", launch_path)
    )




def _read_installation_marker() -> dict:
    """Liest den Installer-Marker neben der App, falls vorhanden."""
    try:
        import json

        marker = installation_marker_path()
        if not marker.is_file():
            return {}
        data = json.loads(marker.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.debug("installation.json konnte nicht gelesen werden: %s", e)
        return {}


def _windows_cmd_quote(value: str) -> str:
    """Escaping fuer Werte, die in set "NAME=..." landen."""
    return (
        value.replace("^", "^^")
        .replace("&", "^&")
        .replace("|", "^|")
        .replace("<", "^<")
        .replace(">", "^>")
        .replace('\"', '\\\"')
    )


def _build_windows_installer_helper_batch(
    setup: Path,
    app_root: Path,
    data_dir: Path | None,
    wait_exe: str,
    log_path: Path,
) -> str:
    """Batch-Helfer fuer installierte Windows-Versionen.

    Der Installer darf erst starten, wenn die laufende App wirklich beendet ist,
    sonst kann die neue EXE nicht sauber ersetzt werden. Danach wird das Setup
    im Update-Modus gestartet und der bisherige Datenordner explizit uebergeben.
    """
    data = str(data_dir) if data_dir is not None else ""
    template = r'''@echo off
setlocal enableextensions
chcp 65001 >nul 2>&1
title BudgetManager Installer-Update

set "LOGFILE=__LOG__"
set "SETUP=__SETUP__"
set "APPDIR=__APPDIR__"
set "DATADIR=__DATADIR__"
set "EXENAME=__EXE__"
set "LAUNCHPATH=__LAUNCHPATH__"

echo [%DATE% %TIME%] Installer-Update gestartet > "%LOGFILE%"
echo.
echo   BudgetManager Installer-Update wird vorbereitet - bitte warten...
echo.

rem --- 1) Warten bis BudgetManager beendet ist ---
set /a _tries=0
:waitloop
tasklist /FI "IMAGENAME eq %EXENAME%" 2>nul | find /I "%EXENAME%" >nul 2>&1
if errorlevel 1 goto installphase
set /a _tries+=1
if %_tries% GEQ 150 goto installphase
ping -n 2 127.0.0.1 >nul 2>&1
goto waitloop

:installphase
echo [%DATE% %TIME%] Starte Setup: %SETUP% >> "%LOGFILE%"
echo   Starte Setup im Update-Modus...
"%SETUP%" /SP- /SILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /DIR="%APPDIR%" /DATA_DIR="%DATADIR%" /UPDATE_MODE=1 /LOG="%LOGFILE%.setup.log"
set "RC=%ERRORLEVEL%"
echo [%DATE% %TIME%] Setup Rueckgabecode=%RC% >> "%LOGFILE%"
if not "%RC%"=="0" goto failed

echo [%DATE% %TIME%] Installer-Update erfolgreich. >> "%LOGFILE%"
echo.
echo   Update abgeschlossen. App wird neu gestartet.
timeout /t 2 /nobreak >nul 2>&1
if exist "%LAUNCHPATH%" start "" "%LAUNCHPATH%"
(goto) 2>nul & del "%~f0"
exit /b 0

:failed
echo [%DATE% %TIME%] FEHLER beim Installer-Update: %RC% >> "%LOGFILE%"
echo.
echo   Installer-Update fehlgeschlagen (Code %RC%).
echo   Details siehe: "%LOGFILE%"
echo.
pause
exit /b %RC%
'''
    launch_path = str(app_root / stable_exe_filename())
    return (
        template
        .replace("__LOG__", _windows_cmd_quote(str(log_path)))
        .replace("__SETUP__", _windows_cmd_quote(str(setup)))
        .replace("__APPDIR__", _windows_cmd_quote(str(app_root)))
        .replace("__DATADIR__", _windows_cmd_quote(data))
        .replace("__EXE__", _windows_cmd_quote(wait_exe))
        .replace("__LAUNCHPATH__", _windows_cmd_quote(launch_path))
    )


def _apply_via_windows_installer(src_root: Path, marker: dict) -> int:
    """Startet eine gestagete Setup-EXE fuer installierte Windows-Versionen.

    Dieser Pfad ersetzt keine Dateien selbst. Er startet nach App-Ende den echten
    Inno-Installer, damit Programmpfad, Uninstaller und Startmenue-Eintraege
    korrekt aktualisiert werden.
    """
    if not is_windows():
        print("❌ Installer-Updates sind nur unter Windows erlaubt.")
        return 10
    candidates = sorted(src_root.rglob("BudgetManager_Setup*.exe"))
    if not candidates:
        candidates = sorted(src_root.rglob("*.exe"))
    if not candidates:
        print("❌ Keine Setup-EXE im Staging gefunden.")
        return 11

    setup = candidates[0]
    install_info = _read_installation_marker()
    raw_data_dir = str(install_info.get("data_directory", "") or "").strip()
    data_dir = Path(raw_data_dir) if raw_data_dir else None
    upd = updates_dir()
    log_path = upd / "installer_update_apply.log"
    batch_path = upd / "apply_installer_update.bat"
    batch_text = _build_windows_installer_helper_batch(
        setup=setup,
        app_root=app_dir(),
        data_dir=data_dir,
        wait_exe=current_exe_filename(),
        log_path=log_path,
    )
    batch_path.write_text(batch_text, encoding="utf-8")

    print(f"⟲ Starte Windows-Installer-Update: {setup.name}")
    print("   Die App schließt sich jetzt. Danach startet das Setup im Update-Modus.")

    CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
    creationflags = CREATE_NEW_PROCESS_GROUP | CREATE_NEW_CONSOLE
    try:
        subprocess.Popen(
            ["cmd.exe", "/c", str(batch_path)],
            cwd=str(upd),
            close_fds=True,
            creationflags=creationflags,
        )
    except Exception as e:
        logger.exception("Windows-Installer-Helfer konnte nicht gestartet werden")
        print(f"❌ Windows-Installer-Helfer konnte nicht gestartet werden: {e}")
        return 12
    return 0

def _apply_via_windows_helper(src_root: Path) -> int:
    """Windows-Pfad: Backup erstellen, Helfer-Batch schreiben und starten.

    Der Batch wartet auf das Ende dieses (und des GUI-)Prozesses, ersetzt dann
    die Dateien und startet die App neu. Diese Funktion kehrt sofort zurück,
    damit der aktuelle Prozess sich beenden kann.
    """
    target_exe = current_exe_filename()
    launch_exe = _launch_exe_filename(src_root)
    dst_dir = app_dir()
    upd = updates_dir()

    # Rollback-Backup (ZIP) – Lesen der laufenden EXE ist unter Windows erlaubt.
    try:
        backup_dir = upd / "backup"
        b = backup_current_zip(backup_dir, label="win", exclude_names=EXCLUDE)
        print(f"✓ Rollback-Backup erstellt: {b}")
    except Exception as e:
        logger.warning("Rollback-Backup fehlgeschlagen (fahre fort): %s", e)
        print(f"⚠️  Rollback-Backup fehlgeschlagen: {e}")

    log_path = upd / "update_apply.log"
    batch_path = upd / "apply_update.bat"
    batch_text = _build_windows_helper_batch(src_root, dst_dir, target_exe, launch_exe, log_path)

    # Batch als UTF-8 schreiben (chcp 65001 im Skript setzt passende Codepage).
    batch_path.write_text(batch_text, encoding="utf-8")

    print("⟲ Starte externen Update-Helfer (Windows)...")
    print("   Es öffnet sich ein eigenes Konsolenfenster, das den Fortschritt zeigt.")
    print("   Die App schließt sich jetzt; danach werden die Dateien ersetzt und die App neu gestartet.")

    # Eigenes Konsolenfenster, damit der Nutzer unter Windows sieht, was passiert.
    # Wichtig: DETACHED_PROCESS NICHT mit CREATE_NEW_CONSOLE kombinieren; diese
    # Kombination ist unter Windows fehleranfällig und kann das Fenster verhindern.
    CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
    creationflags = CREATE_NEW_PROCESS_GROUP | CREATE_NEW_CONSOLE

    try:
        subprocess.Popen(
            ["cmd.exe", "/c", str(batch_path)],
            cwd=str(upd),
            close_fds=True,
            creationflags=creationflags,
        )
    except Exception as e:
        logger.exception("Update-Helfer konnte nicht gestartet werden")
        print(f"❌ Update-Helfer konnte nicht gestartet werden: {e}")
        return 7

    return 0


def main() -> int:
    enable_utf8_console()
    v = target_staged_version()
    if not v:
        print("❌ Kein vorbereitetes Update gefunden. Erst ausführen: python -m updater.check_update")
        return 2

    staging_dir = staging_dir_for(v)
    if not staging_dir.exists():
        print(f"❌ Staging-Ordner fehlt: {staging_dir}")
        return 3

    src_root = find_staged_root(staging_dir)
    marker = read_marker(staging_dir)

    print("BudgetManager Updater – APPLY")
    print(f"App-Ordner: {app_dir()}")
    print(f"Vorbereitete Version: {v}")
    if marker.get("download_url"):
        print(f"Quelle: {marker.get('download_url')}")

    if str(marker.get("asset_type", "")).strip().lower() == "installer":
        return _apply_via_windows_installer(src_root, marker)

    # ── Windows: Selbstsperre der laufenden EXE über externen Helfer lösen ──
    if is_windows():
        return _apply_via_windows_helper(src_root)

    # ── Linux / DEV: in-process anwenden ──
    target_binary = _staged_target_binary(src_root)

    # Rollback-Backup (ZIP)
    backup_dir = updates_dir() / "backup"
    try:
        b = backup_current_zip(backup_dir, label=v, exclude_names=EXCLUDE)
        print(f"✓ Rollback-Backup erstellt: {b}")
    except Exception as e:
        logger.warning("Rollback-Backup fehlgeschlagen (fahre fort): %s", e)
        print(f"⚠️  Rollback-Backup fehlgeschlagen: {e}")

    if target_binary is not None:
        # Single-Binary-Update: nur die Binary atomar ersetzen (sicher, da
        # der restliche App-Ordner nicht angefasst wird).
        target_path = app_dir() / update_target_exe_filename()
        print(f"⟲ Ersetze Binary: {target_path.name}")
        try:
            _replace_binary_inplace(target_binary, target_path)
        except OSError as e:
            print(f"❌ Binary konnte nicht ersetzt werden: {e}")
            logger.exception("Binary-Replace fehlgeschlagen")
            return 8
        # Eventuelle Zusatzdateien (außer Binaries/data/updates) mitnehmen.
        for item in src_root.iterdir():
            if item.name in EXCLUDE or item.name == target_binary.name:
                continue
            if item.is_file() and item.suffix.lower() in {".exe", ""} and item.name.startswith("BudgetManager"):
                # andere Plattform-Binaries überspringen
                continue
            try:
                dst = app_dir() / item.name
                if item.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst, ignore_errors=True)
                    shutil.copytree(item, dst)
                else:
                    shutil.copy2(item, dst)
            except OSError as e:
                logger.warning("Zusatzdatei '%s' nicht kopiert: %s", item, e)
    else:
        # Full-Tree-Update
        print("⟲ Ersetze Programmdateien (data/ bleibt bestehen)...")
        try:
            remove_paths(app_dir(), exclude=EXCLUDE)
            copy_new(src_root, app_dir(), exclude=EXCLUDE)
        except OSError as e:
            print(f"❌ Update fehlgeschlagen: {e}")
            logger.exception("Full-Tree-Update fehlgeschlagen")
            return 9

    print("✓ Update angewendet.")
    print("Starte die App jetzt neu.")
    _restart_after_update(src_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
