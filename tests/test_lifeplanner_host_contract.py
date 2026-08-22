from pathlib import Path


def test_lifeplanner_data_dir_has_priority(monkeypatch, tmp_path):
    from model import app_paths

    host_dir = tmp_path / "lifeplanner-profile" / "budgetmanager"
    monkeypatch.setenv("BUDGETMANAGER_DATA_DIR", str(host_dir))

    assert app_paths.data_dir() == host_dir.resolve()
    assert (
        app_paths.settings_path() == host_dir.resolve() / "budgetmanager_settings.json"
    )
    assert app_paths.db_path() == host_dir.resolve() / "budgetmanager.db"


def test_standalone_default_remains_unchanged(monkeypatch):
    from model import app_paths

    monkeypatch.delenv("BUDGETMANAGER_DATA_DIR", raising=False)
    assert app_paths.data_dir().name == "data"


def test_module_manifest_matches_budgetmanager_version():
    import json

    from app_info import APP_VERSION

    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "module.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "lifeplanner.module.v2"
    assert manifest["id"] == "budgetmanager"
    assert manifest["version"] == APP_VERSION
    assert manifest["requires_host"] == ">=0.5.15,<0.6"
    assert manifest["environment"]["BUDGETMANAGER_DATA_DIR"] == "{module_data_dir}"
    assert manifest["environment"]["LIFEPLANNER_BRIDGE_DIR"] == "{bridge_dir}"
    published = {entry["file"] for entry in manifest["bridge"]["publishes"]}
    assert "budgetmanager_to_fpm.jsonl" in published
    assert "budgetmanager_savings_goals.jsonl" in published


def test_central_updater_guard_is_present_in_both_update_entry_points():
    root = Path(__file__).resolve().parents[1]
    main_window = (root / "views/main_window.py").read_text(encoding="utf-8")
    about_dialog = (root / "views/main_window_dialogs.py").read_text(encoding="utf-8")
    assert main_window.count("LIFEPLANNER_CENTRAL_UPDATER") >= 2
    assert "LIFEPLANNER_CENTRAL_UPDATER" in about_dialog
