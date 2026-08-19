"""Lokale Diagnose- und Crash-Reporting-Helfer.

Die Funktionen in diesem Modul sind bewusst Qt-frei, damit sie auch in Tests,
CLI-/Updater-Pfaden und vor dem GUI-Start sicher verwendbar sind.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sqlite3
import sys
import tempfile
from typing import cast
import zipfile

from app_info import APP_NAME, APP_VERSION
from model.app_paths import app_dir, data_dir, installation_marker_path, settings_path

LOG_FILENAME = "budgetmanager.log"
CRASH_LOG_FILENAME = "budgetmanager_crash.log"
RUNTIME_STATE_FILENAME = "runtime_state.json"
DIAGNOSTICS_DIRNAME = "diagnostics"
TAIL_BYTES_DEFAULT = 400_000

_SECRET_EXACT_KEYS = {
    "password",
    "passwort",
    "passwd",
    "pwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_token",
    "api_key",
    "apikey",
    "pin",
    "salt",
    "db_key",
    "database_key",
    "restore_key",
}
_SECRET_SUFFIXES = tuple(
    f"_{name}"
    for name in (
        "password",
        "passwort",
        "passwd",
        "pwd",
        "secret",
        "token",
        "api_token",
        "api_key",
        "apikey",
        "pin",
        "salt",
        "db_key",
        "database_key",
        "restore_key",
    )
)
_SECRET_PREFIXES = tuple(f"{name}_" for name in _SECRET_EXACT_KEYS)

_APPLICATION_LOG_PREFIX_RE = re.compile(
    r"^(?P<prefix>\d{4}-\d{2}-\d{2}[^\[]*\[[A-Z ]+\]\s+[^:]+:)"
)
_SAFE_TRACEBACK_LINE_RE = re.compile(
    r'^\s*File "[^"]+", line \d+, in [A-Za-z0-9_<>.]+\s*$'
)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def log_file_path() -> Path:
    return data_dir() / LOG_FILENAME


def crash_log_file_path() -> Path:
    return data_dir() / CRASH_LOG_FILENAME


def runtime_state_path() -> Path:
    return data_dir() / RUNTIME_STATE_FILENAME


def diagnostics_dir() -> Path:
    p = data_dir() / DIAGNOSTICS_DIRNAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(str(tmp_path), str(path))
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass


def _pid_alive(pid: int | None) -> bool:
    from model.process_utils import is_pid_alive

    return is_pid_alive(pid)


def previous_state_was_unclean(state: dict | None) -> bool:
    """True, wenn der letzte bekannte Lauf nicht sauber beendet wurde.

    ``app_running=True`` ist der klassische Crash-/Kill-Fall. Zusätzlich wird
    ``last_exit_clean=False`` ausgewertet, damit auch Startfehler sichtbar
    bleiben, bei denen die App den Zustand noch schreiben konnte.
    """
    if not isinstance(state, dict) or not state:
        return False
    if bool(state.get("app_running")):
        # Dieser Check wird nach erfolgreichem Single-Instance-Lock ausgeführt.
        # Wenn wir den Lock bekommen haben, läuft die alte Instanz nicht mehr;
        # eine zusätzliche PID-Prüfung erzeugt nur False-Negatives durch
        # PID-Reuse nach Reboot/Crash. Deshalb gilt app_running=True hier als
        # unclean, unabhängig davon, ob die alte PID inzwischen neu vergeben ist.
        return True
    return state.get("last_exit_clean") is False


def mark_app_started(
    *, version: str = APP_VERSION, argv: list[str] | None = None
) -> dict | None:
    """Markiert den aktuellen Lauf als aktiv und gibt ggf. den unclean Vorzustand zurück."""
    path = runtime_state_path()
    previous = _read_json(path)
    unclean_previous = previous if previous_state_was_unclean(previous) else None
    state = {
        "app_name": APP_NAME,
        "version": version,
        "pid": os.getpid(),
        "app_running": True,
        "last_exit_clean": False,
        "started_at": _now_iso(),
        "closed_at": None,
        "exit_reason": "running",
        "argv": list(argv if argv is not None else sys.argv),
    }
    _write_json_atomic(path, state)
    return unclean_previous


def mark_app_exited(
    *, clean: bool, reason: str = "normal", version: str = APP_VERSION
) -> None:
    """Speichert den Exit-Zustand für die Neustartdiagnose."""
    path = runtime_state_path()
    state = _read_json(path)
    state.update(
        {
            "app_name": APP_NAME,
            "version": version,
            "pid": os.getpid(),
            "app_running": False,
            "last_exit_clean": bool(clean),
            "closed_at": _now_iso(),
            "exit_reason": str(reason or ("normal" if clean else "error")),
        }
    )
    _write_json_atomic(path, state)


def read_text_tail(path: Path, *, max_bytes: int = TAIL_BYTES_DEFAULT) -> str:
    """Liest das Ende einer Textdatei robust und UI-freundlich."""
    try:
        p = Path(path)
        if not p.exists():
            return ""
        size = p.stat().st_size
        with p.open("rb") as fh:
            if size > max_bytes:
                fh.seek(-max_bytes, os.SEEK_END)
                raw = fh.read()
                prefix = f"… gekürzt: letzte {max_bytes // 1000} KB von {size // 1000} KB …\n\n".encode(
                    "utf-8"
                )
            else:
                raw = fh.read()
                prefix = b""
        return (prefix + raw).decode("utf-8", errors="replace")
    except Exception as exc:
        return f"Logdatei konnte nicht gelesen werden: {exc}"


def _normalise_key(key: object) -> str:
    return str(key).strip().lower().replace("-", "_").replace(" ", "_")


def _key_is_secret(key: object) -> bool:
    name = _normalise_key(key)
    return (
        name in _SECRET_EXACT_KEYS
        or name.endswith(_SECRET_SUFFIXES)
        or name.startswith(_SECRET_PREFIXES)
    )


def _mask_paths(value: object):
    """Maskiert benutzerspezifische Pfadanteile für Support-ZIPs.

    Die Diagnose soll nützlich bleiben, aber keine vollständigen Home-Pfade wie
    ``C:/Users/<user>/...`` oder ``/home/christian/...`` weitergeben.
    """
    if isinstance(value, dict):
        return {key: _mask_paths(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_mask_paths(child) for child in value]
    if not isinstance(value, str):
        return value
    text = value
    candidates: list[str] = []
    try:
        home = str(Path.home())
        if home:
            candidates.append(home)
    except Exception:
        pass
    for env_name in ("USERPROFILE", "HOME"):
        raw = os.environ.get(env_name)
        if raw:
            candidates.append(raw)
    # Windows-Form zusätzlich normalisieren, falls der Pfad in JSON mit / oder Backslash auftaucht.
    for raw in list(candidates):
        candidates.append(raw.replace("\\", "/"))
        candidates.append(raw.replace("/", "\\"))
    for raw in sorted(set(candidates), key=len, reverse=True):
        if raw and len(raw) > 2:
            text = text.replace(raw, "<home>")
    return text


def _sanitize(value):
    if isinstance(value, dict):
        out = {}
        for key, child in value.items():
            if _key_is_secret(key):
                out[key] = "<removed>"
            else:
                out[key] = _sanitize(child)
        return _mask_paths(out)
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    return _mask_paths(value)


def sanitized_settings() -> dict:
    return cast(dict, _sanitize(_read_json(settings_path())))


def system_info() -> dict:
    info: dict[str, object] = {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "created_at": _now_iso(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "executable": sys.executable,
        "frozen": bool(getattr(sys, "frozen", False)),
        "app_dir": str(app_dir()),
        "data_dir": str(data_dir()),
        "qt_qpa_platform_env": os.environ.get("QT_QPA_PLATFORM", ""),
        "qt_scale_factor": os.environ.get("QT_SCALE_FACTOR", ""),
        "desktop_session": os.environ.get("XDG_SESSION_TYPE", ""),
        "wayland_display_present": bool(os.environ.get("WAYLAND_DISPLAY")),
        "display_present": bool(os.environ.get("DISPLAY")),
    }
    try:
        from PySide6 import __version__ as pyside_version
        from PySide6.QtCore import qVersion
        from PySide6.QtGui import QGuiApplication

        info["pyside_version"] = pyside_version
        info["qt_version"] = qVersion()
        app = QGuiApplication.instance()
        if isinstance(app, QGuiApplication):
            info["qt_platform_name"] = app.platformName()
            screen = app.primaryScreen()
            if screen is not None:
                geo = screen.availableGeometry()
                info["primary_screen"] = {
                    "width": geo.width(),
                    "height": geo.height(),
                    "device_pixel_ratio": screen.devicePixelRatio(),
                    "logical_dpi": round(screen.logicalDotsPerInch(), 2),
                }
    except Exception as exc:
        info["qt_runtime_info_error"] = f"{type(exc).__name__}: {exc}"
    return cast(dict[str, object], _sanitize(info))


def database_health(connection: sqlite3.Connection | None) -> dict:
    """Technische DB-Gesundheit ohne Finanzdaten, Namen oder Kommentare."""
    if connection is None:
        return {"available": False, "reason": "no_active_connection"}
    result: dict[str, object] = {"available": True, "checked_at": _now_iso()}
    try:
        quick = connection.execute("PRAGMA quick_check(1)").fetchone()
        result["quick_check"] = str(quick[0] if quick else "unknown")
    except Exception as exc:
        result["quick_check"] = "error"
        result["quick_check_error"] = f"{type(exc).__name__}: {exc}"
    pragma_readers = (
        (
            "schema_user_version",
            lambda: connection.execute("PRAGMA user_version").fetchone(),
        ),
        (
            "schema_version",
            lambda: connection.execute("PRAGMA schema_version").fetchone(),
        ),
        ("page_count", lambda: connection.execute("PRAGMA page_count").fetchone()),
        (
            "freelist_count",
            lambda: connection.execute("PRAGMA freelist_count").fetchone(),
        ),
        (
            "foreign_keys_enabled",
            lambda: connection.execute("PRAGMA foreign_keys").fetchone(),
        ),
        (
            "journal_mode",
            lambda: connection.execute("PRAGMA journal_mode").fetchone(),
        ),
    )
    for key, read_pragma in pragma_readers:
        try:
            row = read_pragma()
            result[key] = row[0] if row else None
        except Exception as exc:
            result[f"{key}_error"] = f"{type(exc).__name__}: {exc}"
    try:
        row = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()
        result["application_table_count"] = int(row[0] if row else 0)
    except Exception as exc:
        result["application_table_count_error"] = f"{type(exc).__name__}: {exc}"
    try:
        violations = connection.execute("PRAGMA foreign_key_check").fetchmany(21)
        result["foreign_key_violations"] = min(len(violations), 20)
        result["foreign_key_violations_truncated"] = len(violations) > 20
    except Exception as exc:
        result["foreign_key_check_error"] = f"{type(exc).__name__}: {exc}"
    return cast(dict[str, object], _sanitize(result))


def _resource_file_path(filename: str) -> Path | None:
    """Findet mitgelieferte Ressourcen in Source/Portable und PyInstaller-Onefile."""
    candidates = [app_dir() / filename]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(str(meipass)) / filename)
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except Exception:
            continue
    return None


def _add_file_if_exists(
    zf: zipfile.ZipFile,
    path: Path,
    arcname: str,
    manifest: list[str],
    read_errors: list[str],
    *,
    required: bool = False,
) -> bool:
    try:
        if path.is_file():
            zf.write(path, arcname)
            manifest.append(f"ADDED {arcname} <- {_mask_paths(str(path))}")
            return True
        msg = f"MISSING {arcname} <- {_mask_paths(str(path))}"
        manifest.append(msg)
        if required:
            read_errors.append(msg)
        return False
    except Exception as exc:
        msg = f"ERROR {arcname} <- {_mask_paths(str(path))}: {exc}"
        manifest.append(msg)
        read_errors.append(msg)
        return False


def _sanitize_application_log(text: str) -> str:
    """Reduziert ein App-Log auf technische Metadaten ohne Nutzdaten.

    Kategorien, Beträge, Kommentare und externe IDs können in frei
    formulierten Logmeldungen vorkommen. Eine Schlüsselwortliste könnte solche
    Werte nie zuverlässig erkennen. Darum bleiben nur Zeit, Level, Logger und
    sichere Traceback-Rahmen erhalten; der eigentliche Meldungstext wird
    konsequent ersetzt.
    """
    sanitized: list[str] = []
    for raw_line in text.splitlines():
        line = str(_mask_paths(raw_line))
        prefix = _APPLICATION_LOG_PREFIX_RE.match(line)
        if prefix:
            sanitized.append(f"{prefix.group('prefix')} <message redacted>")
        elif not line.strip():
            sanitized.append("")
        elif _SAFE_TRACEBACK_LINE_RE.match(line):
            sanitized.append(line)
        elif line.strip() in {
            "Traceback (most recent call last):",
            "During handling of the above exception, another exception occurred:",
        }:
            sanitized.append(line)
        else:
            sanitized.append("<redacted>")
    return "\n".join(sanitized) + ("\n" if text.endswith("\n") else "")


def _add_sanitized_text_file(
    zf: zipfile.ZipFile,
    path: Path,
    arcname: str,
    manifest: list[str],
    read_errors: list[str],
    *,
    required: bool = False,
    application_log: bool = False,
) -> bool:
    try:
        if not path.is_file():
            msg = f"MISSING {arcname} <- {_mask_paths(str(path))}"
            manifest.append(msg)
            if required:
                read_errors.append(msg)
            return False
        text = read_text_tail(path)
        sanitized = (
            _sanitize_application_log(text)
            if application_log
            else str(_mask_paths(text))
        )
        zf.writestr(arcname, sanitized)
        manifest.append(f"ADDED {arcname} <- {_mask_paths(str(path))} (sanitized)")
        return True
    except Exception as exc:
        msg = f"ERROR {arcname} <- {_mask_paths(str(path))}: {exc}"
        manifest.append(msg)
        read_errors.append(msg)
        return False


def _add_sanitized_json_file(
    zf: zipfile.ZipFile,
    path: Path,
    arcname: str,
    manifest: list[str],
    read_errors: list[str],
) -> bool:
    try:
        if not path.is_file():
            manifest.append(f"MISSING {arcname} <- {_mask_paths(str(path))}")
            return False
        data = _read_json(path)
        zf.writestr(
            arcname,
            json.dumps(_sanitize(data), ensure_ascii=False, indent=2, sort_keys=True),
        )
        manifest.append(f"ADDED {arcname} <- {_mask_paths(str(path))} (sanitized)")
        return True
    except Exception as exc:
        msg = f"ERROR {arcname} <- {_mask_paths(str(path))}: {exc}"
        manifest.append(msg)
        read_errors.append(msg)
        return False


def _version_json_payload() -> str:
    payload = {
        "app_name": APP_NAME,
        "version": APP_VERSION,
        "source": "app_info fallback",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def create_diagnostic_report_zip(
    *, connection: sqlite3.Connection | None = None
) -> Path:
    """Erstellt lokal einen Diagnosebericht als ZIP ohne Datenbank/Backups.

    Der Bericht enthält ein MANIFEST und ggf. READ_ERRORS, damit fehlende Logs
    nicht still verschwinden. Datenbank-, Backup- und Exportdateien werden nie
    automatisch aufgenommen.
    """
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    data_root = data_dir()
    app_root = app_dir()
    out = diagnostics_dir() / f"budgetmanager_diagnostics_{APP_VERSION}_{stamp}.zip"
    manifest: list[str] = [
        f"BudgetManager Diagnosebericht {APP_VERSION}",
        f"created_at={_now_iso()}",
        f"data_dir={_mask_paths(str(data_root))}",
        f"app_dir={_mask_paths(str(app_root))}",
        "",
    ]
    read_errors: list[str] = []

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Logs inklusive Rotation, aber keine DB-/Backup-/Exportdaten.
        _add_sanitized_text_file(
            zf,
            data_root / LOG_FILENAME,
            LOG_FILENAME,
            manifest,
            read_errors,
            required=True,
            application_log=True,
        )
        for idx in range(1, 6):
            _add_sanitized_text_file(
                zf,
                data_root / f"{LOG_FILENAME}.{idx}",
                f"{LOG_FILENAME}.{idx}",
                manifest,
                read_errors,
                application_log=True,
            )
        _add_sanitized_text_file(
            zf,
            data_root / CRASH_LOG_FILENAME,
            CRASH_LOG_FILENAME,
            manifest,
            read_errors,
        )
        _add_sanitized_json_file(
            zf,
            data_root / RUNTIME_STATE_FILENAME,
            RUNTIME_STATE_FILENAME,
            manifest,
            read_errors,
        )
        _add_sanitized_json_file(
            zf, installation_marker_path(), "installation.json", manifest, read_errors
        )

        version_file = _resource_file_path("version.json")
        if version_file is not None:
            _add_file_if_exists(zf, version_file, "version.json", manifest, read_errors)
        else:
            zf.writestr("version.json", _version_json_payload())
            manifest.append("ADDED version.json <- app_info fallback")

        zf.writestr(
            "system_info.json",
            json.dumps(system_info(), ensure_ascii=False, indent=2, sort_keys=True),
        )
        manifest.append("ADDED system_info.json <- generated (sanitized)")
        zf.writestr(
            "budgetmanager_settings.sanitized.json",
            json.dumps(
                sanitized_settings(), ensure_ascii=False, indent=2, sort_keys=True
            ),
        )
        manifest.append(
            "ADDED budgetmanager_settings.sanitized.json <- settings (sanitized)"
        )
        zf.writestr(
            "database_health.json",
            json.dumps(
                database_health(connection),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
        )
        manifest.append(
            "ADDED database_health.json <- active connection (technical metadata only)"
        )
        zf.writestr(
            "README.txt",
            "BudgetManager Diagnosebericht. Enthält datensparsam bereinigte "
            "Logs, System-/Versionsinfos "
            "und bereinigte Einstellungen. Enthält bewusst keine Datenbank, "
            "keine Backups und keine Exportdaten. Die DB-Prüfung enthält nur "
            "technische Statuswerte und Zähler. Benutzerspezifische Home-Pfade "
            "werden als <home> maskiert. Freie Meldungstexte im App-Log werden "
            "zum Schutz von Kategorien, Beträgen und Kommentaren entfernt.\n",
        )
        manifest.append("ADDED README.txt <- generated")
        if read_errors:
            zf.writestr("READ_ERRORS.txt", "\n".join(read_errors) + "\n")
            manifest.append("ADDED READ_ERRORS.txt <- generated")
        zf.writestr("MANIFEST.txt", "\n".join(manifest) + "\n")
    return out


def remove_old_diagnostic_reports(*, keep: int = 10) -> None:
    """Hält den Diagnoseordner klein. Fehler werden bewusst ignoriert."""
    try:
        reports = sorted(
            diagnostics_dir().glob("budgetmanager_diagnostics_*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in reports[int(keep) :]:
            try:
                old.unlink()
            except Exception:
                pass
    except Exception:
        pass
