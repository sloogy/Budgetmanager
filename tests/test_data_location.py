"""Regression: Datenübernahme (model.data_location). Qt-frei.

Prüft Allowlist-Erkennung, Sicherheits-Backup, Kopieren (kein Verschieben),
sowie die Schutzregeln (leere Quelle, nicht-leeres Ziel, gleicher Pfad).
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest

from model.data_location import (
    DataMigrationError,
    has_user_data,
    list_user_data,
    migrate_data_dir,
)


def _seed_old(d: Path):
    d.mkdir(parents=True, exist_ok=True)
    (d / "christian.enc").write_bytes(b"ENCRYPTED")
    (d / "users.json").write_text('{"users": []}', encoding="utf-8")
    (d / "budgetmanager_settings.json").write_text(
        "{}", encoding="utf-8"
    )  # NICHT migrieren
    (d / "budgetmanager.log").write_text("log", encoding="utf-8")  # NICHT migrieren
    backups = d / "backups"
    backups.mkdir()
    (backups / "budgetmanager_backup_2026.bmr").write_bytes(b"BMR")


def test_list_user_data_uses_allowlist(tmp_path):
    old = tmp_path / "old"
    _seed_old(old)
    names = {p.name for p in list_user_data(old)}
    assert names == {"christian.enc", "users.json", "backups"}
    # Einstellungsdatei und Log sind bewusst NICHT dabei
    assert "budgetmanager_settings.json" not in names
    assert "budgetmanager.log" not in names
    assert has_user_data(old) is True
    assert has_user_data(tmp_path / "leer") is False


def test_migrate_copies_and_creates_backup_and_keeps_source(tmp_path):
    old = tmp_path / "old"
    new = tmp_path / "new"
    _seed_old(old)

    result = migrate_data_dir(old, new, make_backup=True)

    # Kopiert: .enc, users.json, backups-Ordner
    assert set(result.copied) == {"christian.enc", "users.json", "backups"}
    assert (new / "christian.enc").read_bytes() == b"ENCRYPTED"
    assert (new / "users.json").is_file()
    assert (new / "backups" / "budgetmanager_backup_2026.bmr").read_bytes() == b"BMR"

    # Quelle bleibt erhalten (kein Verschieben)
    assert (old / "christian.enc").is_file()
    assert (old / "users.json").is_file()

    # Einstellungsdatei wurde NICHT mitkopiert
    assert not (new / "budgetmanager_settings.json").exists()

    # Sicherheits-Backup existiert und enthält die Nutzerdaten
    assert result.backup_path is not None
    bp = Path(result.backup_path)
    assert bp.exists() and bp.suffix == ".zip"
    with zipfile.ZipFile(bp) as zf:
        arcs = set(zf.namelist())
    assert "christian.enc" in arcs
    assert "users.json" in arcs
    assert any(a.startswith("backups/") for a in arcs)
    assert result.total_bytes > 0


def test_migrate_refuses_empty_source(tmp_path):
    old = tmp_path / "leer"
    old.mkdir()
    with pytest.raises(DataMigrationError):
        migrate_data_dir(old, tmp_path / "ziel")


def test_migrate_refuses_non_empty_target(tmp_path):
    old = tmp_path / "old"
    new = tmp_path / "new"
    _seed_old(old)
    new.mkdir()
    (new / "fremd.enc").write_bytes(b"X")  # Ziel hat bereits Nutzerdaten
    with pytest.raises(DataMigrationError):
        migrate_data_dir(old, new)


def test_migrate_refuses_same_dir(tmp_path):
    old = tmp_path / "old"
    _seed_old(old)
    with pytest.raises(DataMigrationError):
        migrate_data_dir(old, old)


def test_migration_rejects_nested_source_and_target(tmp_path):
    old = tmp_path / "old"
    old.mkdir()
    (old / "users.json").write_text("{}", encoding="utf-8")

    nested_target = old / "backups" / "new_data"
    parent_target = tmp_path

    import pytest

    with pytest.raises(DataMigrationError):
        migrate_data_dir(old, nested_target)
    with pytest.raises(DataMigrationError):
        migrate_data_dir(old, parent_target)
