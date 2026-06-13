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

from updater.common import (
    app_dir,
    backup_current_zip,
    current_exe_filename,
    enable_utf8_console,
    find_staged_root,
    is_windows,
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
    # sortiert grob lexikographisch; Versionsvergleich erfolgt im Check
    versions.sort()
    return versions[-1]


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
    """Gibt die gestagete App-Binary zurück, falls das Update aus genau dieser
    einen Binary besteht (Single-Binary-Update, der Normalfall bei one-file
    PyInstaller-Builds). Sonst None (dann: Full-Tree-Update)."""
    target_name = current_exe_filename()
    candidate = src_root / target_name
    if candidate.is_file():
        return candidate
    return None


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
    target_exe: str,
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
    exe = target_exe
    exe_path = str(dst_dir / target_exe)
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
set "EXEPATH=__EXEPATH__"

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
start "" "%EXEPATH%"

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
        .replace("__EXEPATH__", exe_path)
    )


def _apply_via_windows_helper(src_root: Path) -> int:
    """Windows-Pfad: Backup erstellen, Helfer-Batch schreiben und starten.

    Der Batch wartet auf das Ende dieses (und des GUI-)Prozesses, ersetzt dann
    die Dateien und startet die App neu. Diese Funktion kehrt sofort zurück,
    damit der aktuelle Prozess sich beenden kann.
    """
    target_exe = current_exe_filename()
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
    batch_text = _build_windows_helper_batch(src_root, dst_dir, target_exe, log_path)

    # Batch als UTF-8 schreiben (chcp 65001 im Skript setzt passende Codepage).
    batch_path.write_text(batch_text, encoding="utf-8")

    print("⟲ Starte externen Update-Helfer (Windows)...")
    print("   Die App schließt sich jetzt; das Update wird im Hintergrund angewendet.")

    # Detached starten, eigenes Konsolenfenster (gibt dem Nutzer Feedback).
    creationflags = 0
    DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
    CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
    creationflags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NEW_CONSOLE

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
    v = latest_staged_version()
    if not v:
        print("❌ Kein vorbereitetes Update gefunden. Erst ausführen: python -m updater.check_update")
        return 2

    staging_dir = staging_dir_for(v)
    if not staging_dir.exists():
        print(f"❌ Staging-Ordner fehlt: {staging_dir}")
        return 3

    src_root = find_staged_root(staging_dir)
    marker = read_marker(staging_dir)

    print("BudgetManager Updater (portable) – APPLY")
    print(f"App-Ordner: {app_dir()}")
    print(f"Vorbereitete Version: {v}")
    if marker.get("download_url"):
        print(f"Quelle: {marker.get('download_url')}")

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
        target_path = app_dir() / current_exe_filename()
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
