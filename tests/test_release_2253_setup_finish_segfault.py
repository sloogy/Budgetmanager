from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_setup_finished_never_runs_backup_inside_qdialog_finished_signal() -> None:
    src = _source("views/main_window.py")
    start = src.index("            def _setup_finished(*_args) -> None:")
    end = src.index("            dlg.finished.connect(_setup_finished)", start)
    block = src[start:end]

    assert "self._check_auto_backup()" not in block
    assert "timer = QTimer(self)" in block
    assert "timer.start(250)" in block
    assert "dlg.deleteLater()" in block
    assert "self._schedule_startup_auto_backup(delay_ms=1500)" in block


def test_startup_auto_backup_uses_one_parent_bound_scheduler() -> None:
    window_src = _source("views/main_window.py")
    main_src = _source("main.py")

    assert "def _schedule_startup_auto_backup(" in window_src
    assert "timer = QTimer(self)" in window_src
    assert "timer.timeout.connect(_run_safely)" in window_src
    assert "self._startup_auto_backup_timer = timer" in window_src
    assert "BM_SKIP_STARTUP_AUTO_BACKUP" in window_src
    assert "win._schedule_startup_auto_backup(delay_ms=500)" in main_src
    assert "backup_timer = QTimer(win)" not in main_src


def test_setup_finish_is_idempotent_and_accepts_dialog() -> None:
    src = _source("views/setup_assistant_dialog.py")
    start = src.index("    def _finish(self) -> None:")
    end = src.index("    def closeEvent", start)
    block = src[start:end]

    assert "if self._finishing:" in block
    assert "return" in block
    assert "self.accept()" in block
    assert "self.close()" not in block
