from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_budget_warning_refresh_is_deferred_after_dialog_exec():
    src = (ROOT / "views" / "main_window.py").read_text(encoding="utf-8")
    assert "def _schedule_refresh_all_tabs" in src
    assert (
        "dlg.exec()\n        # Nicht synchron im QAction-/Dialog-Stack refreshen" in src
    )
    assert (
        'self._schedule_refresh_all_tabs(reason="budget warnings dialog closed")' in src
    )


def test_budget_tab_load_blocks_signals_and_reentrant_rebuilds():
    src = (ROOT / "views" / "tabs" / "budget_tab.py").read_text(encoding="utf-8")
    assert "self._loading_budget_table = False" in src
    assert "self._reload_budget_table_again = False" in src
    assert 'if getattr(self, "_loading_budget_table", False):' in src
    assert "_prev_block = self.table.blockSignals(True)" in src
    assert "self.table.blockSignals(_prev_block)" in src
    assert "QTimer.singleShot(0, self.load)" in src


def test_adjustment_dialog_uses_scheduled_parent_refresh():
    src = (ROOT / "views" / "budget_adjustment_dialog.py").read_text(encoding="utf-8")
    assert "from PySide6.QtCore import Qt, QTimer" in src
    assert 'hasattr(parent, "_schedule_refresh_all_tabs")' in src
    assert (
        'parent._schedule_refresh_all_tabs(reason="budget adjustment applied")' in src
    )
