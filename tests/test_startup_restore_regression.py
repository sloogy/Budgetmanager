from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_setup_assistant_restore_uses_supported_backup_dialog_api():
    """Regression: Der geführte Setup-Assistent darf BackupRestoreDialog
    nicht mehr mit dem alten, nicht existierenden restore_path-Argument öffnen.
    """
    src = Path("views/setup_assistant_dialog.py").read_text(encoding="utf-8")
    method_src = src.split("    def _do_restore_backup", 1)[1].split(
        "    def _do_reset_database", 1
    )[0]
    assert "restore_path=" not in method_src
    assert "restore_external_path(path)" in src

    backup_src = Path("views/backup_restore_dialog.py").read_text(encoding="utf-8")
    assert "def restore_external_path" in backup_src


def test_startup_import_bmr_quick_user_requires_restore_key_even_if_users_json_exists(
    tmp_path, monkeypatch
):
    """Security regression: Ein .bmr darf den Restore-Key nicht durch
    users.json umgehen. Alte Quick-Backups können users.json mit DB-Key
    enthalten; der Erststart-Import muss trotzdem nach dem Restore-Key fragen.
    """
    import pytest

    pytest.importorskip("PySide6")

    from model.crypto import db_key_to_restore_key, decrypt_db_from_file, save_memory_db
    from model.restore_bundle import create_bundle
    from model.user_model import SECURITY_QUICK, UserModel, _users_file_path
    from views.startup_wizard import StartupWizard

    old_app = tmp_path / "old_app"
    new_app = tmp_path / "new_app"

    monkeypatch.setenv("BUDGETMANAGER_APP_DIR", str(old_app))
    old_um = UserModel()
    old_user, _ = old_um.create_user("Alter Quick User", SECURITY_QUICK, "")
    old_key = old_user.get_db_key("")
    old_db_path = old_user.db_path
    old_salt = old_user.salt

    conn = decrypt_db_from_file(old_db_path, old_key)
    try:
        conn.execute("CREATE TABLE startup_restore_marker (value TEXT)")
        conn.execute("INSERT INTO startup_restore_marker(value) VALUES ('aus-backup')")
        save_memory_db(conn, old_db_path, old_key, old_salt)
    finally:
        conn.close()

    bundle = tmp_path / "quick_backup_with_legacy_users_json.bmr"
    create_bundle(
        source_db=old_db_path,
        out_path=bundle,
        app="BudgetManager",
        app_version="test",
        note="legacy quick backup",
        users_json_path=_users_file_path(),
    )

    monkeypatch.setenv("BUDGETMANAGER_APP_DIR", str(new_app))
    new_um = UserModel()
    new_user, _ = new_um.create_user("Neuer User", SECURITY_QUICK, "")
    new_key = new_user.get_db_key("")

    wiz = StartupWizard.__new__(StartupWizard)
    asked = {"count": 0}

    def no_key():
        asked["count"] += 1
        return None

    wiz._ask_restore_key = no_key
    with pytest.raises(ValueError):
        wiz._restore_into_user(bundle, new_user, new_key)
    assert asked["count"] == 1

    restore_key = db_key_to_restore_key(old_key)
    wiz._ask_restore_key = lambda: restore_key
    wiz._restore_into_user(bundle, new_user, new_key)

    restored = decrypt_db_from_file(new_user.db_path, new_key)
    try:
        value = restored.execute("SELECT value FROM startup_restore_marker").fetchone()[
            0
        ]
    finally:
        restored.close()

    assert value == "aus-backup"
