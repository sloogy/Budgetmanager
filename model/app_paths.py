from __future__ import annotations

import json
import os
import sys
from pathlib import Path

INSTALL_TYPES_WITH_EXTERNAL_DATA = {"windows_installer", "installer"}
SETTINGS_FILENAME = "budgetmanager_settings.json"
INSTALLATION_MARKER = "installation.json"


def app_dir() -> Path:
    """Basisordner der App.

    - PyInstaller (frozen): Ordner, in dem die EXE/Binary liegt
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


def _environment_data_dir() -> Path | None:
    """Host-/Launcher-Override für ausschließlich den Nutzerdatenordner.

    ``BUDGETMANAGER_DATA_DIR`` ist der explizite Standalone-/Launcher-Schalter.
    ``LIFEPLANNER_MODULE_DATA_DIR`` ist der generische Hostvertrag. Anders als
    ``BUDGETMANAGER_APP_DIR`` verändern beide weder Ressourcen- noch Updaterpfade.
    """
    raw = (
        os.environ.get("BUDGETMANAGER_DATA_DIR", "").strip()
        or os.environ.get("LIFEPLANNER_MODULE_DATA_DIR", "").strip()
    )
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path.resolve()


def portable_data_dir() -> Path:
    """Portabler Datenordner neben dem Programm ({app}/data).

    Dieser Pfad ist der Standard für Source- und Portable-ZIP-Nutzung. Eine
    Windows-Installer-Installation kann per ``installation.json`` einen externen
    Datenordner vorgeben; dann landen Settings, DB, Nutzerregister, Backups und
    Updates gemeinsam dort.
    """
    return app_dir() / "data"


def installation_marker_path() -> Path:
    """Pfad zum optionalen Installer-Marker neben der App."""
    return app_dir() / INSTALLATION_MARKER


def _read_installation_marker() -> dict:
    """Liest ``installation.json`` fehlertolerant.

    Portable Builds enthalten keinen Marker. Der Windows-Installer schreibt den
    Marker in den Programmordner, damit die App ihren gewählten Datenordner auch
    dann findet, wenn die Settings-Datei selbst dort liegt.
    """
    try:
        marker = installation_marker_path()
        if not marker.is_file():
            return {}
        data = json.loads(marker.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _installer_data_dir() -> Path | None:
    """Datenordner aus Installer-Marker oder None bei Portable/Source."""
    data = _read_installation_marker()
    install_type = str(data.get("install_type", "")).strip().lower()
    if install_type not in INSTALL_TYPES_WITH_EXTERNAL_DATA:
        return None
    raw = str(data.get("data_directory", "") or "").strip()
    if not raw:
        return None
    return resolve_data_dir(raw, default_to_installer=False)


def resolve_data_dir(raw: str | None, *, default_to_installer: bool = True) -> Path:
    """Löst einen 'data_directory'-Rohwert in einen konkreten Pfad auf.

    - nicht-leerer Wert: absoluter Pfad wird genutzt, relativer relativ zu app_dir()
    - leer/None: Installer-Default aus installation.json, sonst {app}/data

    Diese Funktion liest höchstens den kleinen Installer-Marker, aber keine
    Settings-Datei. Dadurch bleibt sie testbar und vermeidet Import-Zyklen.
    """
    if raw and str(raw).strip():
        p = Path(str(raw).strip()).expanduser()
        if not p.is_absolute():
            p = (app_dir() / p).resolve()
        return p
    if default_to_installer:
        installer_dir = _installer_data_dir()
        if installer_dir is not None:
            return installer_dir
    return portable_data_dir()


def settings_path() -> Path:
    """Pfad zur Einstellungsdatei.

    Portable/Source:
        {app}/data/budgetmanager_settings.json

    Windows-Installer:
        {gewählter Datenordner}/budgetmanager_settings.json

    Damit verteilt der Installer Nutzerdaten nicht mehr über Programmordner,
    Dokumente und AppData. Der kleine ``installation.json``-Marker im
    Programmordner ist nur der Bootstrap-Hinweis auf den gewählten Datenordner.
    """
    environment_dir = _environment_data_dir()
    if environment_dir is not None:
        return ensure_dir(environment_dir) / SETTINGS_FILENAME
    installer_dir = _installer_data_dir()
    base = installer_dir if installer_dir is not None else portable_data_dir()
    return ensure_dir(base) / SETTINGS_FILENAME


def _settings_candidates() -> list[Path]:
    """Settings-Kandidaten in Prioritätsreihenfolge.

    Bei neuen Installer-Builds liegt die Datei im gewählten Datenordner. Der
    alte portable Ort bleibt als Legacy-Fallback lesbar, damit bestehende
    Installationen beim ersten Start nicht hart zurückfallen.
    """
    primary = settings_path()
    legacy = portable_data_dir() / SETTINGS_FILENAME
    if primary == legacy:
        return [primary]
    return [primary, legacy]


def _read_data_directory_override() -> Path | None:
    """Liest den optionalen 'data_directory'-Wert aus der Settings-Datei.

    Rückgabe:
        - absoluter Pfad, wenn ein nicht-leerer Wert gesetzt ist
        - Installer-Datenordner, wenn installiert und kein Override vorhanden ist
        - None, wenn nichts gesetzt ist (-> portabler Default)

    Bewusst ohne Import der Settings-Klasse (vermeidet Import-Zyklus
    app_paths <-> settings) und bewusst fehlertolerant.
    """
    installer_dir = _installer_data_dir()
    for settings_file in _settings_candidates():
        try:
            if not settings_file.is_file():
                continue
            data = json.loads(settings_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            raw = data.get("data_directory")
            if raw is not None and str(raw).strip():
                return resolve_data_dir(raw)
            if installer_dir is not None:
                return installer_dir
            return None
        except Exception:
            continue
    return installer_dir


def data_dir() -> Path:
    """Aktiver Datenordner (DB, Nutzer, Backups, Exporte, Updates).

    - Installer: gewählter Datenordner aus installation.json/Settings
    - Portable/Source: {app}/data oder ein in Settings gesetzter Override
    """
    environment_dir = _environment_data_dir()
    if environment_dir is not None:
        return ensure_dir(environment_dir)
    override = _read_data_directory_override()
    base = override if override is not None else portable_data_dir()
    return ensure_dir(base)


def backups_dir() -> Path:
    return ensure_dir(data_dir() / "backups")


def exports_dir() -> Path:
    return ensure_dir(data_dir() / "exports")


def updates_dir() -> Path:
    """Update-Cache im aktiven Datenordner.

    Für Installer-Installationen ist das wichtig, weil der Programmordner nicht
    als Schreibort für laufende Cache-/Staging-Dateien dienen soll.
    """
    return ensure_dir(data_dir() / "updates")


def db_path() -> Path:
    return data_dir() / "budgetmanager.db"


_DEFAULT_DB_SETTINGS = {
    "",
    "budgetmanager.db",
    "data/budgetmanager.db",
    "./data/budgetmanager.db",
}
_DEFAULT_BACKUP_SETTINGS = {"", "backups", "data/backups", "./data/backups"}


def configured_db_path(setting_value: str | None) -> Path:
    """DB-Pfad aus Settings, aber Default folgt dem aktiven data_dir()."""
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
