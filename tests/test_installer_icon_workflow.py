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
    assert common.preferred_asset_keys("windows")[:2] == ["windows", "portable_zip"]

    (tmp_path / "installation.json").write_text('{"install_type":"windows_installer"}', encoding="utf-8")
    keys = common.preferred_asset_keys("windows")
    assert keys[0] == "windows_installer"

    monkeypatch.setattr(common, "current_exe_filename", lambda: "BudgetManager-v2.0.28-windows.exe")
    keys = common.preferred_asset_keys("windows")
    assert "direct_windows_exe" in keys
