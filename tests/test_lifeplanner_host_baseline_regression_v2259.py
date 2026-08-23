import json
from pathlib import Path

from app_info import APP_VERSION
from model import app_paths
from model.lifeplanner_import_service import default_bridge_dir

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_and_host_paths(monkeypatch, tmp_path):
    manifest = json.loads((ROOT / "module.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "lifeplanner.module.v2"
    assert manifest["id"] == "budgetmanager"
    assert manifest["version"] == APP_VERSION
    assert manifest["requires_host"] == ">=0.5.15,<1.0"
    monkeypatch.setenv("BUDGETMANAGER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LIFEPLANNER_BRIDGE_DIR", str(tmp_path / "bridge"))
    assert app_paths.data_dir() == (tmp_path / "data").resolve()
    assert default_bridge_dir() == (tmp_path / "bridge").resolve()


def test_central_updater_suppresses_internal_startup_check():
    source = (ROOT / "views" / "main_window.py").read_text(encoding="utf-8")
    schedule = source[
        source.index("def schedule_startup_update_check") : source.index(
            "def _start_startup_update_check"
        )
    ]
    manual = source[
        source.index("def _show_update_dialog") : source.index(
            "def _schedule_refresh_all_tabs"
        )
    ]
    assert "LIFEPLANNER_CENTRAL_UPDATER" in schedule
    assert "LIFEPLANNER_CENTRAL_UPDATER" in manual
