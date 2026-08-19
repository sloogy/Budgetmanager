from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_normal_backup_calls_embed_users_json_for_full_backup() -> None:
    """Backups sind wieder vollständige Konto-Backups.

    users.json wird gespeichert, aber nicht mehr als automatische
    Entschlüsselungs-Abkürzung beim Startup-Restore verwendet.
    """
    for rel in (
        "views/backup_restore_dialog.py",
        "views/main_window.py",
        "settings_dialog.py",
    ):
        src = _read(rel)
        assert "users_json_path=" in src, rel


def test_startup_restore_does_not_use_bundle_users_json_as_key() -> None:
    src = _read("views/startup_wizard.py")
    assert "_candidate_db_keys_from_bundle_users" not in src
    assert "Bundle-users.json wird nicht als Schlüssel verwendet" in src
    assert "restore_key_to_db_key(restore_key)" in src


def test_restore_dialog_restores_users_only_after_explicit_question() -> None:
    src = _read("views/backup_restore_dialog.py")
    body = src.split("    def _ask_restore_options", 1)[1].split(
        "    def restore_external_path", 1
    )[0]
    assert "restore_users = False" in body
    assert "dlg.restore_users_question" in body
    assert "bundle_user_security_modes" in body
    assert "QMessageBox.No" in body
    assert "backup.users_not_restored_security_note" in body
