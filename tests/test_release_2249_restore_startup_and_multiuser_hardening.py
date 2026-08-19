from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from model.restore_bundle import (
    BundleIntegrityError,
    create_bundle,
    merge_user_snapshot_bytes,
    verify_bundle,
)


def _user(username: str, db_filename: str, *, default: bool = False) -> dict:
    return {
        "username": username,
        "display_name": username.title(),
        "security": "password",
        "db_filename": db_filename,
        "is_default": default,
    }


def test_empty_settings_file_is_hashed_and_bundle_verifies(tmp_path: Path) -> None:
    db = tmp_path / "account.enc"
    db.write_bytes(b"encrypted-placeholder")
    settings = tmp_path / "settings.json"
    settings.write_bytes(b"")

    bundle = create_bundle(
        source_db=db,
        out_path=tmp_path / "empty-settings.bmr",
        app="BudgetManager",
        app_version="2.2.49",
        settings_path=settings,
    )

    assert verify_bundle(bundle) == "database.enc"
    with zipfile.ZipFile(bundle) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["has_settings"] is True
        assert len(manifest["settings_sha256"]) == 64


def test_small_highly_compressible_legacy_db_is_not_false_positive(
    tmp_path: Path,
) -> None:
    db = tmp_path / "small.db"
    db.write_bytes(b"\0" * (1024 * 1024))
    bundle = create_bundle(
        source_db=db,
        out_path=tmp_path / "small.bmr",
        app="BudgetManager",
        app_version="2.2.49",
    )
    assert verify_bundle(bundle) == "database.db"


def test_invalid_sha256_format_is_rejected(tmp_path: Path) -> None:
    db = tmp_path / "account.enc"
    db.write_bytes(b"encrypted-placeholder")
    bundle = create_bundle(
        source_db=db,
        out_path=tmp_path / "good.bmr",
        app="BudgetManager",
        app_version="2.2.49",
    )
    bad = tmp_path / "bad-hash.bmr"
    with zipfile.ZipFile(bundle) as source, zipfile.ZipFile(
        bad, "w", zipfile.ZIP_DEFLATED
    ) as target:
        for name in source.namelist():
            data = source.read(name)
            if name == "manifest.json":
                manifest = json.loads(data)
                manifest["sha256"] = "not-a-hash"
                data = json.dumps(manifest).encode()
            target.writestr(name, data)
    with pytest.raises(BundleIntegrityError, match="SHA-256"):
        verify_bundle(bad)


def test_account_restore_merge_preserves_unrelated_local_accounts() -> None:
    existing = json.dumps(
        {"users": [_user("local", "local.enc", default=True)]}
    ).encode()
    incoming = json.dumps(
        {"users": [_user("restored", "restored.enc", default=True)]}
    ).encode()

    merged = json.loads(
        merge_user_snapshot_bytes(
            existing, incoming, source_db_name="restored.enc"
        ).decode()
    )
    assert [u["username"] for u in merged["users"]] == ["local", "restored"]
    assert merged["users"][0]["is_default"] is True
    assert merged["users"][1]["is_default"] is False


def test_account_restore_replaces_only_exact_same_account() -> None:
    existing = json.dumps(
        {
            "users": [
                _user("local", "local.enc"),
                {**_user("restored", "restored.enc", default=True), "old": True},
            ]
        }
    ).encode()
    incoming = json.dumps(
        {"users": [{**_user("restored", "restored.enc"), "new": True}]}
    ).encode()

    merged = json.loads(
        merge_user_snapshot_bytes(
            existing, incoming, source_db_name="restored.enc"
        ).decode()
    )
    assert len(merged["users"]) == 2
    restored = next(u for u in merged["users"] if u["username"] == "restored")
    assert restored.get("new") is True
    assert "old" not in restored
    assert restored["is_default"] is True


@pytest.mark.parametrize(
    "existing",
    [
        {"users": [_user("restored", "different.enc")]},
        {"users": [_user("different", "restored.enc")]},
    ],
)
def test_account_restore_rejects_partial_identity_collision(existing: dict) -> None:
    incoming = json.dumps({"users": [_user("restored", "restored.enc")]}).encode()
    with pytest.raises(ValueError, match="Konto-Kollision"):
        merge_user_snapshot_bytes(
            json.dumps(existing).encode(),
            incoming,
            source_db_name="restored.enc",
        )


def test_all_bmr_restore_paths_verify_and_stream_instead_of_reading_whole_db() -> None:
    startup = Path("views/startup_wizard.py").read_text(encoding="utf-8")
    backup = Path("views/backup_restore_dialog.py").read_text(encoding="utf-8")

    startup_extract = startup.split("    def _extract_bmr_to_temp", 1)[1]
    assert "verify_open_bundle(zf)" in startup_extract
    assert "copy_member_limited(zf, db_file, out, MAX_DB_BYTES)" in startup_extract
    assert "zf.read(db_file)" not in startup_extract

    backup_extract = backup.split("    def _extract_bmr_to_temp", 1)[1].split(
        "    def _atomic_copy", 1
    )[0]
    assert "verify_open_bundle(zf)" in backup_extract
    assert "copy_member_limited(zf, db_file, out, MAX_DB_BYTES)" in backup_extract
    assert "shutil.copyfileobj" not in backup_extract


def test_full_account_restore_merges_users_instead_of_replacing_all() -> None:
    source = Path("views/backup_restore_dialog.py").read_text(encoding="utf-8")
    body = source.split("    def _restore_full_account_bundle", 1)[1].split(
        "    def _restore_to_active", 1
    )[0]
    assert "merge_user_snapshot_bytes(" in body
    assert "existing_users_bytes = dest_users.read_bytes()" in body
