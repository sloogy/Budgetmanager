from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_lifeplanner_module_release_assets_are_defined():
    manifest = json.loads((ROOT / "module.json").read_text(encoding="utf-8"))
    assert manifest["windows_executable"] == "BudgetManager/BudgetManager.exe"
    assert manifest["linux_executable"] == "BudgetManager/BudgetManager"
    assert (ROOT / "tools" / "build_lifeplanner_module.py").is_file()
    assert (ROOT / ".github" / "workflows" / "lifeplanner-module-release.yml").is_file()
