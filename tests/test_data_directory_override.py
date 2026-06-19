"""Regression: frei wählbarer Datenordner (data_directory) in model.app_paths.

Qt-frei. Prüft:
- Ohne Einstellung -> portabler Ordner ({app}/data)
- Mit gesetztem absolutem data_directory -> dieser Ordner
- Leerer Wert -> portabel
- Relativer Wert -> relativ zu app_dir aufgelöst
- settings_path() bleibt IMMER portabel (Bootstrap, kein Zirkelbezug)
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _fresh_app_paths(monkeypatch, app_dir: Path):
    monkeypatch.setenv("BUDGETMANAGER_APP_DIR", str(app_dir))
    import model.app_paths as ap
    importlib.reload(ap)
    return ap


def _write_settings(app_dir: Path, payload: dict) -> None:
    data_dir = app_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "budgetmanager_settings.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_data_dir_defaults_to_portable_when_unset(monkeypatch, tmp_path):
    ap = _fresh_app_paths(monkeypatch, tmp_path)
    assert ap.data_dir() == (tmp_path / "data")
    assert ap.portable_data_dir() == (tmp_path / "data")


def test_data_dir_uses_absolute_override(monkeypatch, tmp_path):
    app_dir = tmp_path / "app"
    target = tmp_path / "woanders" / "BudgetManager"
    _write_settings(app_dir, {"data_directory": str(target)})
    ap = _fresh_app_paths(monkeypatch, app_dir)
    assert ap.data_dir() == target
    assert target.is_dir()  # data_dir() legt den Ordner an
    # DB/Backups/Exporte folgen dem gewählten Ordner
    assert ap.backups_dir() == target / "backups"
    assert ap.db_path() == target / "budgetmanager.db"


def test_empty_data_directory_is_portable(monkeypatch, tmp_path):
    app_dir = tmp_path / "app"
    _write_settings(app_dir, {"data_directory": "   "})
    ap = _fresh_app_paths(monkeypatch, app_dir)
    assert ap.data_dir() == (app_dir / "data")


def test_relative_data_directory_resolved_against_app_dir(monkeypatch, tmp_path):
    app_dir = tmp_path / "app"
    _write_settings(app_dir, {"data_directory": "userdata/budget"})
    ap = _fresh_app_paths(monkeypatch, app_dir)
    assert ap.data_dir() == (app_dir / "userdata" / "budget").resolve()


def test_settings_path_always_portable(monkeypatch, tmp_path):
    app_dir = tmp_path / "app"
    target = tmp_path / "woanders"
    _write_settings(app_dir, {"data_directory": str(target)})
    ap = _fresh_app_paths(monkeypatch, app_dir)
    # Datenordner ist umgeleitet ...
    assert ap.data_dir() == target
    # ... aber die Settings-Datei bleibt portabel im {app}/data Ordner.
    assert ap.settings_path() == app_dir / "data" / "budgetmanager_settings.json"


def test_broken_settings_file_falls_back_to_portable(monkeypatch, tmp_path):
    app_dir = tmp_path / "app"
    data_dir = app_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "budgetmanager_settings.json").write_text("{ kaputt", encoding="utf-8")
    ap = _fresh_app_paths(monkeypatch, app_dir)
    assert ap.data_dir() == data_dir


def _cleanup(monkeypatch):
    # app_paths nach den Tests in sauberen Zustand zurückbringen
    monkeypatch.delenv("BUDGETMANAGER_APP_DIR", raising=False)
    import model.app_paths as ap
    importlib.reload(ap)


def test_configured_default_db_and_backups_follow_data_directory(monkeypatch, tmp_path):
    app_dir = tmp_path / "app"
    target = tmp_path / "custom_data"
    _write_settings(app_dir, {"data_directory": str(target)})
    ap = _fresh_app_paths(monkeypatch, app_dir)

    assert ap.configured_db_path("data/budgetmanager.db") == target / "budgetmanager.db"
    assert ap.configured_db_path("budgetmanager.db") == target / "budgetmanager.db"
    assert ap.configured_backups_dir("data/backups") == target / "backups"
    assert ap.configured_backups_dir("backups") == target / "backups"


def test_configured_explicit_paths_stay_explicit(monkeypatch, tmp_path):
    app_dir = tmp_path / "app"
    target = tmp_path / "custom_data"
    explicit_db = tmp_path / "explicit" / "finance.sqlite"
    explicit_backup = tmp_path / "explicit" / "bm_backups"
    _write_settings(app_dir, {"data_directory": str(target)})
    ap = _fresh_app_paths(monkeypatch, app_dir)

    assert ap.configured_db_path(str(explicit_db)) == explicit_db
    assert ap.configured_backups_dir(str(explicit_backup)) == explicit_backup


def test_account_data_hub_only_accepts_applied_data_dir_changes():
    src = (ROOT / "views" / "account_data_hub.py").read_text(encoding="utf-8")
    assert "applied = handler(new_raw)" in src
    assert "if applied is not False" in src
    assert "resolve_data_dir(raw)" in src


def test_data_dir_handler_returns_success_flag():
    src = (ROOT / "views" / "main_window.py").read_text(encoding="utf-8")
    assert "def _handle_data_directory_change(self, new_raw: str) -> bool" in src
    assert "return False  # Einstellung NICHT ändern" in src
    assert "return True" in src
