from __future__ import annotations

import os
from pathlib import Path

from updater import apply_update
from utils import atomic_write

ROOT = Path(__file__).resolve().parents[1]


def test_windows_portable_update_never_copies_after_wait_timeout() -> None:
    batch = apply_update._build_windows_helper_batch(
        src_root=Path(r"C:\staging\BudgetManager"),
        dst_dir=Path(r"C:\BudgetManager"),
        wait_exe="BudgetManager.exe",
        launch_exe="BudgetManager.exe",
        log_path=Path(r"C:\BudgetManager\updates\update_apply.log"),
    )
    assert "if %_tries% GEQ 150 goto stillrunning" in batch
    assert "if %_tries% GEQ 150 goto copyphase" not in batch
    assert "Es wurden KEINE Programmdateien ersetzt" in batch
    assert "exit /b 13" in batch


def test_windows_installer_update_never_starts_setup_after_wait_timeout() -> None:
    batch = apply_update._build_windows_installer_helper_batch(
        setup=Path(r"C:\staging\BudgetManager_Setup.exe"),
        app_root=Path(r"C:\Program Files\BudgetManager"),
        data_dir=Path(r"D:\BudgetManagerData"),
        wait_exe="BudgetManager.exe",
        log_path=Path(r"D:\BudgetManagerData\updates\installer_update_apply.log"),
    )
    assert "if %_tries% GEQ 150 goto stillrunning" in batch
    assert "if %_tries% GEQ 150 goto installphase" not in batch
    assert "Das Setup wurde NICHT gestartet" in batch
    assert "exit /b 13" in batch


def test_atomic_temp_name_is_unique_inside_same_process(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    first = atomic_write._temp_path(target)
    second = atomic_write._temp_path(target)
    assert first != second
    assert str(os.getpid()) in first.name
    assert str(os.getpid()) in second.name


def test_update_preflight_happens_before_detached_updater_start() -> None:
    source = (ROOT / "views" / "update_dialog.py").read_text(encoding="utf-8")
    method = source[source.index("    def _apply(self)") :]
    preflight = method.index("prepare_for_update_exit")
    detached_start = method.index("QProcess.startDetached")
    assert preflight < detached_start


def test_shutdown_does_not_reenter_mainwindow_closeevent_after_qt_loop() -> None:
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    shutdown = source[source.index("        rc = app.exec()") :]
    cleanup = shutdown[: shutdown.index("        return rc")]
    code_only = "\n".join(
        line for line in cleanup.splitlines() if not line.lstrip().startswith("#")
    )
    assert "win.close()" not in code_only
    assert "win.deleteLater()" in cleanup


def test_excel_worker_has_safe_app_quit_join() -> None:
    source = (ROOT / "views" / "setup_assistant_dialog.py").read_text(encoding="utf-8")
    assert "app.aboutToQuit.connect(self._wait_for_excel_worker_on_quit)" in source
    assert "thread.quit()" in source
    assert "thread.wait()" in source
    assert "if thread is not None and thread.isRunning():" in source
