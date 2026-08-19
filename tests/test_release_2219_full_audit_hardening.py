from __future__ import annotations

import sqlite3
from pathlib import Path

from model.migrations import _create_migration_backup


def test_rapid_migration_backups_are_unique_and_outside_release_tree(tmp_path: Path):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    backup_dir = tmp_path / "backups"
    first = Path(_create_migration_backup(str(db), str(backup_dir)))
    second = Path(_create_migration_backup(str(db), str(backup_dir)))

    assert first.is_file()
    assert second.is_file()
    assert first != second
    assert first.parent == backup_dir
    assert second.parent == backup_dir
    assert "data/backups" not in first.as_posix()
