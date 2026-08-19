from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path

import pytest


def test_safe_extract_rejects_readme_only_payload(tmp_path):
    from updater.common import (
        safe_extract_zip,
        validate_staged_payload,
        find_staged_root,
    )

    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", "not an application")
    staging = tmp_path / "staging"
    safe_extract_zip(archive, staging)
    with pytest.raises(ValueError, match="Startpunkt"):
        validate_staged_payload(find_staged_root(staging), "portable-zip")


def test_safe_extract_rejects_path_traversal(tmp_path):
    from updater.common import safe_extract_zip

    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", "x")
    with pytest.raises(ValueError, match="Unsicherer Pfad"):
        safe_extract_zip(archive, tmp_path / "staging")
    assert not (tmp_path / "escape.txt").exists()


def test_apply_rejects_tampered_staging(tmp_path):
    from updater.apply_update import _verify_staging
    from updater.common import staged_tree_sha256

    staging = tmp_path / "2.2.12"
    root = staging / "BudgetManager"
    (root / "_internal").mkdir(parents=True)
    (root / "_internal" / "lib.so").write_text("lib", encoding="utf-8")
    (root / "BudgetManager").write_text("original", encoding="utf-8")
    marker = {
        "asset_type": "portable-zip",
        "tree_sha256": staged_tree_sha256(root),
    }
    (root / "BudgetManager").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="veraendert"):
        _verify_staging(staging, root, marker)


def test_check_update_rebuilds_existing_staging(monkeypatch, tmp_path):
    import updater.check_update as check_update
    import updater.common as common
    from updater.common import AssetInfo, Manifest

    archive = tmp_path / "asset.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("BudgetManager/BudgetManager", "fresh")
        zf.writestr("BudgetManager/_internal/lib.so", "lib")
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    staging = tmp_path / "staging" / "2.2.12"
    staging.mkdir(parents=True)
    (staging / "malware.py").write_text("bad", encoding="utf-8")

    monkeypatch.setattr(check_update, "read_current_version", lambda: "2.2.11")
    monkeypatch.setattr(check_update, "detect_platform_key", lambda: "linux")
    monkeypatch.setattr(
        check_update,
        "fetch_manifest",
        lambda *_a, **_k: Manifest(
            version="2.2.12",
            release_tag="v2.2.12",
            channel="stable",
            assets={
                "linux": AssetInfo(
                    url="https://invalid/update.zip",
                    sha256=sha,
                    asset_type="portable-zip",
                )
            },
        ),
    )
    monkeypatch.setattr(
        check_update, "cache_zip_path", lambda _v: tmp_path / "cache.zip"
    )
    monkeypatch.setattr(
        check_update, "download_file", lambda _u, d: d.write_bytes(archive.read_bytes())
    )
    monkeypatch.setattr(check_update, "staging_dir_for", lambda _v: staging)
    monkeypatch.setattr(common, "staging_dir_for", lambda _v: staging)
    monkeypatch.setattr(check_update, "write_check_result", lambda _d: None)
    monkeypatch.setattr(check_update, "prune_other_staging", lambda *_a: None)

    assert check_update.main() == 0
    assert not (staging / "malware.py").exists()
    assert (staging / "BudgetManager" / "BudgetManager").read_text() == "fresh"


def test_transactional_full_tree_rolls_back_on_activation_failure(
    monkeypatch, tmp_path
):
    import updater.apply_update as apply_update

    app = tmp_path / "app"
    src = tmp_path / "src"
    updates = app / "updates"
    app.mkdir()
    src.mkdir()
    updates.mkdir()
    (app / "BudgetManager").write_text("old-bin")
    (app / "_internal").mkdir()
    (app / "_internal" / "old.txt").write_text("old")
    (src / "BudgetManager").write_text("new-bin")
    (src / "_internal").mkdir()
    (src / "_internal" / "new.txt").write_text("new")
    monkeypatch.setattr(apply_update, "updates_dir", lambda: updates)

    real_replace = os.replace
    calls = {"n": 0}

    def flaky_replace(a, b):
        calls["n"] += 1
        # old binary, old internal, new binary, then fail activating new internal
        if calls["n"] == 4:
            raise OSError("simulated failure")
        return real_replace(a, b)

    monkeypatch.setattr(apply_update.os, "replace", flaky_replace)

    with pytest.raises(OSError, match="simulated"):
        apply_update._transactional_full_tree_update(
            src, app, exclude=("data", "updates")
        )
    assert (app / "BudgetManager").read_text() == "old-bin"
    assert (app / "_internal" / "old.txt").read_text() == "old"


def test_import_copy_is_secured_in_source():
    src = Path("views/backup_restore_dialog.py").read_text(encoding="utf-8")
    assert (
        "shutil.copy2(file_path, import_path)\n                secure_file(import_path)"
        in src
    )
    assert "restore_rollback" in src
