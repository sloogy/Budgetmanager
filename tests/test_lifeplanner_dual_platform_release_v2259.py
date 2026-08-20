from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_lifeplanner_module_release_assets_are_defined():
    manifest = json.loads((ROOT / "module.json").read_text(encoding="utf-8"))
    assert manifest["windows_executable"] == "BudgetManager/BudgetManager.exe"
    assert manifest["linux_executable"] == "BudgetManager/BudgetManager"
    assert (ROOT / "tools" / "build_lifeplanner_module.py").is_file()


def test_lifeplanner_release_uses_the_single_budgetmanager_tag_workflow():
    workflows = ROOT / ".github" / "workflows"
    assert not (workflows / "lifeplanner-module-release.yml").exists()
    assert not (workflows / "lifeplanner-contract.yml").exists()

    budgetmanager_release = (workflows / "build.yml").read_text(encoding="utf-8")
    assert "tools/build_lifeplanner_module.py" in budgetmanager_release
    assert "--allow-unsigned" in budgetmanager_release
    assert "LIFEPLANNER_UPDATE_PRIVATE_KEY_B64" not in budgetmanager_release
    assert "windows-x86_64" in budgetmanager_release
    assert "linux-x86_64" in budgetmanager_release
    assert "release/*.lpmodule*" in budgetmanager_release
