from __future__ import annotations

from pathlib import Path
import sys

def app_dir() -> Path:
    """Basisordner der App (portable).

    - PyInstaller (frozen): Ordner, in dem die EXE liegt
    - Dev/Source: Projekt-Root (eine Ebene über /model)
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]

def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def data_dir() -> Path:
    return ensure_dir(app_dir() / "data")

def backups_dir() -> Path:
    return ensure_dir(data_dir() / "backups")

def exports_dir() -> Path:
    return ensure_dir(data_dir() / "exports")

def db_path() -> Path:
    return data_dir() / "budgetmanager.db"

def settings_path() -> Path:
    return data_dir() / "budgetmanager_settings.json"

def resolve_in_app(path_str: str) -> Path:
    """Erlaubt absolute Pfade, relative Pfade werden relativ zu app_dir() aufgelöst."""
    p = Path(path_str).expanduser()
    if p.is_absolute():
        return p
    return (app_dir() / p).resolve()
