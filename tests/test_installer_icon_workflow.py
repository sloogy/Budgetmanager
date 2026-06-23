from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_app_icon_assets_and_build_config_are_wired():
    assert (ROOT / "resources" / "icons" / "budgetmanager.ico").is_file()
    assert (ROOT / "resources" / "icons" / "budgetmanager.png").is_file()

    spec = (ROOT / "BudgetManager.spec").read_text(encoding="utf-8")
    assert 'icon="resources/icons/budgetmanager.ico"' in spec
    assert '("resources/icons", "resources/icons")' in spec

    main = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "_apply_application_icon(app)" in main

    iss = (ROOT / "installer" / "budgetmanager_setup.iss").read_text(encoding="utf-8")
    assert "SourceDir=.." in iss
    assert "SetupIconFile=resources\\icons\\budgetmanager.ico" in iss
    assert '"install_type": "windows_installer"' in iss
    assert '"data_directory": "' in iss
    assert "SettingsFile := DataDir + '\\budgetmanager_settings.json'" in iss
    assert "{app}\\data\\budgetmanager_settings.json" not in iss
    assert "CloseApplications=force" in iss
    assert "RestartApplications=no" in iss
    assert "InstallerUpdateMode" in iss
    assert "ExpandConstant('{param:DATA_DIR|}')" in iss
    assert "ShouldSkipPage(PageID: Integer)" in iss
    assert "PreviousDataDir := ExistingDataDirFromMarker" in iss


def test_github_workflow_builds_windows_installer_and_publishes_manifest_asset():
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    assert "installer:" in workflow
    assert "choco install innosetup" in workflow
    assert "installer\\budgetmanager_setup.iss" in workflow
    assert "BudgetManager_Setup_${VERSION}.exe" in workflow
    assert "windows_installer" in workflow

    for rel in ["latest.json.template", "docs/latest.json.template"]:
        data = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        assert data["assets"]["windows_installer"]["type"] == "installer"


def test_updater_has_different_asset_paths_for_installer_direct_and_portable(monkeypatch, tmp_path):
    import updater.common as common

    monkeypatch.setattr(common, "app_dir", lambda: tmp_path)
    monkeypatch.setattr(common, "current_exe_filename", lambda: "BudgetManager.exe")
    monkeypatch.setattr(common, "_is_frozen", lambda: True)
    assert common.preferred_asset_keys("windows")[:3] == ["direct_windows_exe", "windows", "portable_zip"]

    (tmp_path / "installation.json").write_text('{"install_type":"windows_installer","data_directory":"%s"}' % (tmp_path / "data"), encoding="utf-8")
    keys = common.preferred_asset_keys("windows")
    assert keys[0] == "windows_installer"

    (tmp_path / "installation.json").unlink()
    monkeypatch.setattr(common, "current_exe_filename", lambda: "BudgetManager-v2.0.28-windows.exe")
    keys = common.preferred_asset_keys("windows")
    assert "direct_windows_exe" in keys



def test_update_check_stages_windows_installer_asset(monkeypatch, tmp_path):
    import hashlib
    import updater.check_update as check_update
    from updater.common import AssetInfo, Manifest

    setup_sha = hashlib.sha256(b"setup-exe").hexdigest()

    writes = []
    cached = tmp_path / "cache" / "update_2.0.34.zip"
    staging = tmp_path / "staging" / "2.0.34"

    monkeypatch.setattr(check_update, "read_current_version", lambda: "2.0.33")
    monkeypatch.setattr(check_update, "detect_platform_key", lambda: "windows")
    monkeypatch.setattr(check_update, "preferred_asset_keys", lambda _platform: ["windows_installer"])
    monkeypatch.setattr(
        check_update,
        "fetch_manifest",
        lambda *_args, **_kwargs: Manifest(
            version="2.0.34",
            release_tag="v2.0.34",
            channel="stable",
            assets={
                "windows_installer": AssetInfo(
                    url="https://example.invalid/BudgetManager_Setup_2.0.34.exe",
                    sha256=setup_sha,
                    asset_type="installer",
                )
            },
        ),
    )
    monkeypatch.setattr(check_update, "cache_zip_path", lambda remote: cached)
    monkeypatch.setattr(
        check_update,
        "download_file",
        lambda _url, dest: (dest.parent.mkdir(parents=True, exist_ok=True), dest.write_bytes(b"setup-exe")),
    )
    monkeypatch.setattr(check_update, "staging_dir_for", lambda _remote: staging)
    monkeypatch.setattr(
        check_update,
        "write_staged_marker",
        lambda remote, manifest, asset: (staging / "_update_marker.json").write_text(
            '{"asset_type":"installer"}', encoding="utf-8"
        ),
    )
    monkeypatch.setattr(check_update, "write_check_result", lambda data: writes.append(dict(data)))

    assert check_update.main() == 0
    assert (staging / "BudgetManager_Setup_2.0.34.exe").read_bytes() == b"setup-exe"
    assert writes[-1]["asset_key"] == "windows_installer"
    assert writes[-1]["asset_type"] == "installer"


def test_installer_apply_uses_waiting_batch_and_preserves_data_dir():
    import updater.apply_update as apply_update

    batch = apply_update._build_windows_installer_helper_batch(
        setup=Path(r"C:\Users\me\BudgetManager_Setup_2.0.34.exe"),
        app_root=Path(r"C:\Program Files\BudgetManager"),
        data_dir=Path(r"D:\BudgetManagerData"),
        wait_exe="BudgetManager.exe",
        log_path=Path(r"D:\BudgetManagerData\updates\installer_update_apply.log"),
    )

    assert "tasklist" in batch
    assert "BudgetManager.exe" in batch
    assert "/SILENT" in batch
    assert "/CLOSEAPPLICATIONS" in batch
    assert "/UPDATE_MODE=1" in batch
    assert '/DATA_DIR="%DATADIR%"' in batch
    assert r"D:\BudgetManagerData" in batch
    assert "start \"\" \"%LAUNCHPATH%\"" in batch
