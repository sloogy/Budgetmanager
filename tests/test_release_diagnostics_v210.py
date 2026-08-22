from __future__ import annotations

import json
import zipfile
from pathlib import Path

from model import diagnostics
from model.app_paths import app_dir, data_dir, settings_path


def test_runtime_state_detects_unclean_previous_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BUDGETMANAGER_APP_DIR", str(tmp_path))
    state_file = diagnostics.runtime_state_path()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {
                "app_running": True,
                "last_exit_clean": False,
                "pid": 99999999,
                "started_at": "2026-01-01T12:00:00",
                "exit_reason": "running",
            }
        ),
        encoding="utf-8",
    )

    previous = diagnostics.mark_app_started(version="2.1.0", argv=["BudgetManager"])
    assert previous is not None
    assert previous["app_running"] is True

    diagnostics.mark_app_exited(clean=True, reason="test_exit", version="2.1.0")
    current = json.loads(state_file.read_text(encoding="utf-8"))
    assert current["app_running"] is False
    assert current["last_exit_clean"] is True
    assert current["exit_reason"] == "test_exit"
    assert diagnostics.previous_state_was_unclean(current) is False


def test_diagnostic_report_zip_contains_only_diagnostics_not_user_database(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("BUDGETMANAGER_APP_DIR", str(tmp_path))
    data = data_dir()
    data.mkdir(parents=True, exist_ok=True)
    diagnostics.log_file_path().write_text("normal log", encoding="utf-8")
    diagnostics.crash_log_file_path().write_text("crash log", encoding="utf-8")
    diagnostics.runtime_state_path().write_text(
        '{"last_exit_clean": false}', encoding="utf-8"
    )
    settings_path().write_text(
        json.dumps(
            {
                "theme": "dark",
                "password": "secret",
                "nested": {"api_token": "secret-token"},
            }
        ),
        encoding="utf-8",
    )
    (app_dir() / "version.json").write_text('{"version":"2.1.0"}', encoding="utf-8")
    (data / "budgetmanager.db").write_text("must not be included", encoding="utf-8")
    (data / "backups").mkdir(parents=True, exist_ok=True)
    (data / "backups" / "backup.db").write_text(
        "must not be included", encoding="utf-8"
    )

    report = diagnostics.create_diagnostic_report_zip()
    assert report.exists()
    assert report.parent == data / "diagnostics"

    with zipfile.ZipFile(report) as zf:
        names = set(zf.namelist())
        assert "budgetmanager.log" in names
        assert "budgetmanager_crash.log" in names
        assert "system_info.json" in names
        assert "budgetmanager_settings.sanitized.json" in names
        assert not any(name.endswith(".db") for name in names)
        assert not any(name.startswith("backups/") for name in names)
        app_log = zf.read("budgetmanager.log").decode("utf-8")
        assert "normal log" not in app_log
        assert "<redacted>" in app_log
        sanitized = json.loads(
            zf.read("budgetmanager_settings.sanitized.json").decode("utf-8")
        )
        assert sanitized["password"] == "<removed>"
        assert sanitized["nested"]["api_token"] == "<removed>"
        assert sanitized["theme"] == "dark"


def test_help_menu_contains_diagnostic_actions_and_i18n_keys() -> None:
    # Der Menueaufbau liegt seit v2.2.38 in views/help_menu.py; die
    # Diagnose-Ausloeser bleiben Methoden des Hauptfensters.
    src = Path("views/main_window.py").read_text(encoding="utf-8")
    src += Path("views/help_menu.py").read_text(encoding="utf-8")
    for needle in [
        "menu.show_log",
        "menu.show_crash_log",
        "menu.open_diagnostics_folder",
        "menu.create_diagnostic_report",
        "schedule_unclean_shutdown_prompt",
    ]:
        assert needle in src

    for lang in ["de", "en", "fr"]:
        data = json.loads(Path(f"locales/{lang}.json").read_text(encoding="utf-8"))
        menu = data["menu"]
        diag = data["diagnostics"]
        for key in [
            "show_log",
            "show_crash_log",
            "open_diagnostics_folder",
            "create_diagnostic_report",
        ]:
            assert key in menu
        for key in [
            "unclean_title",
            "show_log",
            "create_report",
            "report_created_text",
        ]:
            assert key in diag


def test_unclean_previous_run_does_not_use_pid_liveness(monkeypatch) -> None:
    def _boom(_pid):
        raise AssertionError(
            "PID liveness must not be consulted for crash prompt state"
        )

    monkeypatch.setattr(diagnostics, "_pid_alive", _boom)
    assert (
        diagnostics.previous_state_was_unclean({"app_running": True, "pid": 1}) is True
    )


def test_sanitizer_redacts_real_secrets_without_substring_overmatch() -> None:
    sanitized = diagnostics._sanitize(
        {
            "api_token": "secret-token",
            "db_key": "secret-key",
            "password": "secret-password",
            "column_mapping": {"amount": "Betrag"},
            "spinbox_value": 7,
        }
    )
    assert sanitized["api_token"] == "<removed>"
    assert sanitized["db_key"] == "<removed>"
    assert sanitized["password"] == "<removed>"
    assert sanitized["column_mapping"] == {"amount": "Betrag"}
    assert sanitized["spinbox_value"] == 7


def test_diagnostic_report_zip_writes_manifest_and_read_errors_for_missing_main_log(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("BUDGETMANAGER_APP_DIR", str(tmp_path))
    report = diagnostics.create_diagnostic_report_zip()
    with zipfile.ZipFile(report) as zf:
        names = set(zf.namelist())
        assert "MANIFEST.txt" in names
        assert "READ_ERRORS.txt" in names
        assert "version.json" in names
        assert "budgetmanager.log" not in names
        errors = zf.read("READ_ERRORS.txt").decode("utf-8")
        assert "MISSING budgetmanager.log" in errors


def test_diagnostic_report_masks_home_paths_in_runtime_and_system_info(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("BUDGETMANAGER_APP_DIR", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    data = data_dir()
    data.mkdir(parents=True, exist_ok=True)
    diagnostics.log_file_path().write_text("normal log", encoding="utf-8")
    diagnostics.runtime_state_path().write_text(
        json.dumps(
            {"argv": [str(tmp_path / "BudgetManager.exe")], "app_running": True}
        ),
        encoding="utf-8",
    )
    report = diagnostics.create_diagnostic_report_zip()
    with zipfile.ZipFile(report) as zf:
        runtime_state = zf.read("runtime_state.json").decode("utf-8")
        system_info = zf.read("system_info.json").decode("utf-8")
        assert str(tmp_path) not in runtime_state
        assert str(tmp_path) not in system_info
        assert "<home>" in runtime_state
        assert "<home>" in system_info


def test_diagnostic_report_redacts_app_log_user_data_and_crash_paths(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("BUDGETMANAGER_APP_DIR", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    data = data_dir()
    data.mkdir(parents=True, exist_ok=True)
    private_message = "Hochzeit Budget=12345.67 Kommentar=privat"
    diagnostics.log_file_path().write_text(
        "2026-08-19 12:00:00,000 [ERROR   ] model.tracking: " + private_message + "\n",
        encoding="utf-8",
    )
    private_frame = tmp_path / "BudgetManager" / "views" / "overview.py"
    diagnostics.crash_log_file_path().write_text(
        f'  File "{private_frame}", line 42, in refresh\n',
        encoding="utf-8",
    )

    report = diagnostics.create_diagnostic_report_zip()
    with zipfile.ZipFile(report) as zf:
        app_log = zf.read("budgetmanager.log").decode("utf-8")
        crash_log = zf.read("budgetmanager_crash.log").decode("utf-8")
        assert private_message not in app_log
        assert "<message redacted>" in app_log
        assert str(tmp_path) not in crash_log
        assert "<home>" in crash_log
