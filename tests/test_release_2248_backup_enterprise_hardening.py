from __future__ import annotations

import json
import os
import stat
import zipfile
from pathlib import Path

import pytest

from model.restore_bundle import (
    BundleIntegrityError,
    LegacyBundleIntegrityError,
    create_bundle,
    extract_settings,
    upgrade_legacy_bundle,
    verify_bundle,
)


def _create_complete_bundle(tmp_path: Path) -> Path:
    db = tmp_path / "christian.enc"
    db.write_bytes(b"encrypted-database" * 128)
    settings = tmp_path / "settings.json"
    settings.write_text('{"theme":"light"}\n', encoding="utf-8")
    users = tmp_path / "users.json"
    users.write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "christian",
                        "display_name": "Christian",
                        "security": "password",
                        "db_filename": "christian.enc",
                    },
                    {
                        "username": "other",
                        "display_name": "Other",
                        "security": "quick",
                        "db_filename": "other.enc",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return create_bundle(
        source_db=db,
        out_path=tmp_path / "complete.bmr",
        app="Budgetmanager",
        app_version="2.2.48",
        settings_path=settings,
        users_json_path=users,
    )


def _rewrite(bundle: Path, target: Path, mutator) -> Path:
    with zipfile.ZipFile(bundle, "r") as source, zipfile.ZipFile(
        target, "w", zipfile.ZIP_DEFLATED
    ) as dest:
        for name in source.namelist():
            dest.writestr(name, mutator(name, source.read(name)))
    return target


def test_complete_bundle_hashes_every_restorable_member_and_filters_account(
    tmp_path: Path,
) -> None:
    bundle = _create_complete_bundle(tmp_path)
    assert verify_bundle(bundle) == "database.enc"

    with zipfile.ZipFile(bundle, "r") as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        assert len(manifest["sha256"]) == 64
        assert len(manifest["settings_sha256"]) == 64
        assert len(manifest["users_sha256"]) == 64
        users = json.loads(archive.read("users.json").decode("utf-8"))["users"]
        assert [entry["username"] for entry in users] == ["christian"]


@pytest.mark.parametrize("member", ["settings.json", "users.json"])
def test_tampered_optional_members_are_rejected(tmp_path: Path, member: str) -> None:
    bundle = _create_complete_bundle(tmp_path)
    bad = _rewrite(
        bundle,
        tmp_path / f"tampered-{member}.bmr",
        lambda name, data: (b"{}\n" if name == member else data),
    )
    with pytest.raises(BundleIntegrityError):
        verify_bundle(bad)


def test_duplicate_members_are_rejected(tmp_path: Path) -> None:
    bundle = _create_complete_bundle(tmp_path)
    bad = tmp_path / "duplicates.bmr"
    with zipfile.ZipFile(bundle, "r") as source, zipfile.ZipFile(
        bad, "w", zipfile.ZIP_DEFLATED
    ) as dest:
        for name in source.namelist():
            dest.writestr(name, source.read(name))
        with pytest.warns(UserWarning, match="Duplicate name"):
            dest.writestr("settings.json", b"{}\n")
    with pytest.raises(BundleIntegrityError, match="Doppelte"):
        verify_bundle(bad)


def test_legacy_optional_hashes_require_upgrade(tmp_path: Path) -> None:
    current = _create_complete_bundle(tmp_path)

    def remove_optional_hashes(name: str, data: bytes) -> bytes:
        if name != "manifest.json":
            return data
        manifest = json.loads(data.decode("utf-8"))
        manifest.pop("settings_sha256", None)
        manifest.pop("users_sha256", None)
        return json.dumps(manifest).encode("utf-8")

    legacy = _rewrite(current, tmp_path / "legacy.bmr", remove_optional_hashes)
    with pytest.raises(LegacyBundleIntegrityError):
        verify_bundle(legacy)
    assert verify_bundle(legacy, allow_legacy_without_hash=True) == "database.enc"

    upgraded = upgrade_legacy_bundle(legacy, tmp_path / "upgraded.bmr")
    assert verify_bundle(upgraded) == "database.enc"


def test_settings_extraction_is_verified_atomic_and_private(tmp_path: Path) -> None:
    bundle = _create_complete_bundle(tmp_path)
    destination = tmp_path / "restored" / "settings.json"
    assert extract_settings(bundle, destination) is True
    assert json.loads(destination.read_text(encoding="utf-8")) == {"theme": "light"}
    assert not destination.with_suffix(".json.restore_tmp").exists()
    # Windows st_mode bildet keine ACLs ab und meldet normale Dateien als
    # 0666. Die exakte 0600-Prüfung ist deshalb ausschließlich POSIX-sinnig.
    if os.name != "nt":
        assert stat.S_IMODE(destination.stat().st_mode) & 0o077 == 0


def test_full_account_restore_streams_db_and_reuses_verified_bundle() -> None:
    source = Path("views/backup_restore_dialog.py").read_text(encoding="utf-8")
    assert "copy_member_limited(zf, db_file, tmp_db, MAX_DB_BYTES)" in source
    assert "tmp_db.write_bytes(zf.read(db_file))" not in source
    restore_body = source.split("    def _restore_from_path(", 1)[1].split(
        "    def _ask_restore_key", 1
    )[0]
    assert "self._prepare_verified_bundle(" in restore_body
