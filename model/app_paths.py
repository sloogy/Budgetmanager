from __future__ import annotations

from pathlib import Path
import json
import os
import sys


def app_dir() -> Path:
    """Basisordner der App (portable).

    - PyInstaller (frozen): Ordner, in dem die EXE liegt
    - Dev/Source: Projekt-Root (eine Ebene über /model)
    - Tests/Tools: optionaler Override via BUDGETMANAGER_APP_DIR
    """
    override = os.environ.get("BUDGETMANAGER_APP_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def portable_data_dir() -> Path:
    """Fester, portabler Datenordner neben dem Programm ({app}/data).

    Dies ist der Bootstrap-Ort: Die Einstellungsdatei liegt IMMER hier, damit
    der optionale, frei wählbare Datenordner überhaupt erst aus ihr gelesen
    werden kann (sonst Henne-Ei-Problem).
    """
    return app_dir() / "data"


def settings_path() -> Path:
    """Pfad zur Einstellungsdatei – immer im portablen Ordner ({app}/data).

    Bewusst NICHT an data_dir() gekoppelt: data_dir() kann aus dieser Datei
    umgeleitet werden, daher muss die Datei selbst an einem festen Ort liegen.
    """
    return ensure_dir(portable_data_dir()) / "budgetmanager_settings.json"


def resolve_data_dir(raw: str | None) -> Path:
    """Löst einen 'data_directory'-Rohwert in einen konkreten Pfad auf.

    - nicht-leerer Wert: absoluter Pfad wird genutzt, relativer relativ zu app_dir()
    - leer/None: portabler Standard ({app}/data)

    Liest bewusst NICHTS von der Platte – reine Pfadlogik, dadurch testbar und
    auch für Vorschau-/Migrationszwecke nutzbar.
    """
    if raw and str(raw).strip():
        p = Path(str(raw).strip()).expanduser()
        if not p.is_absolute():
            p = (app_dir() / p).resolve()
        return p
    return portable_data_dir()


def _read_data_directory_override() -> Path | None:
    """Liest den optionalen 'data_directory'-Wert aus der portablen Settings-Datei.

    Rückgabe:
        - absoluter Pfad, wenn ein nicht-leerer Wert gesetzt ist
        - None, wenn nichts gesetzt ist (-> portabler Default)

    Bewusst ohne Import der Settings-Klasse (vermeidet Import-Zyklus
    app_paths <-> settings) und bewusst fehlertolerant: bei jedem Problem
    wird auf den portablen Ordner zurückgefallen.
    """
    settings_file = portable_data_dir() / "budgetmanager_settings.json"
    try:
        if not settings_file.is_file():
            return None
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        raw = data.get("data_directory")
        if not raw or not str(raw).strip():
            return None
        return resolve_data_dir(raw)
    except Exception:
        return None


def data_dir() -> Path:
    """Aktiver Datenordner (DB, Backups, Exporte, verschlüsselte .enc-Dateien).

    - Ist in den Einstellungen ein 'data_directory' gesetzt, wird dieser genutzt.
    - Sonst der portable Ordner neben dem Programm ({app}/data).

    Die Einstellungsdatei selbst liegt unabhängig davon immer portabel
    (siehe settings_path()).
    """
    override = _read_data_directory_override()
    base = override if override is not None else portable_data_dir()
    return ensure_dir(base)


def backups_dir() -> Path:
    return ensure_dir(data_dir() / "backups")


def exports_dir() -> Path:
    return ensure_dir(data_dir() / "exports")


def db_path() -> Path:
    return data_dir() / "budgetmanager.db"


_DEFAULT_DB_SETTINGS = {"", "budgetmanager.db", "data/budgetmanager.db", "./data/budgetmanager.db"}
_DEFAULT_BACKUP_SETTINGS = {"", "backups", "data/backups", "./data/backups"}


def configured_db_path(setting_value: str | None) -> Path:
    """DB-Pfad aus Settings, aber Default folgt dem aktiven data_dir().

    Historisch stand in den Settings ``data/budgetmanager.db``. Seit dem frei
    wählbaren Datenordner muss genau dieser Default relativ zum aktiven
    Datenordner aufgelöst werden. Nur echte Nutzer-Sonderpfade werden weiterhin
    unverändert respektiert.
    """
    raw = str(setting_value or "").strip().replace("\\", "/")
    if raw in _DEFAULT_DB_SETTINGS:
        return db_path()
    return resolve_in_app(str(setting_value or ""))


def configured_backups_dir(setting_value: str | None) -> Path:
    """Backup-Ordner aus Settings, aber Default folgt dem aktiven data_dir()."""
    raw = str(setting_value or "").strip().replace("\\", "/")
    if raw in _DEFAULT_BACKUP_SETTINGS:
        return backups_dir()
    return ensure_dir(resolve_in_app(str(setting_value or "")))


def resolve_in_app(path_str: str) -> Path:
    """Erlaubt absolute Pfade, relative Pfade werden relativ zu app_dir() aufgelöst."""
    p = Path(path_str).expanduser()
    if p.is_absolute():
        return p
    return (app_dir() / p).resolve()
