from pathlib import Path


def _budget_tab_source() -> str:
    return (Path(__file__).resolve().parents[1] / "views" / "tabs" / "budget_tab.py").read_text(encoding="utf-8")


def test_budget_table_has_deterministic_editor_lifecycle_guard():
    src = _budget_tab_source()
    assert "def safe_close_active_editor" in src
    assert "self.closeEditor(editor, QAbstractItemDelegate.EndEditHint.NoHint)" in src
    assert "QCoreApplication.sendPostedEvents(editor, 0)" in src
    assert "QEvent.Type.DeferredDelete" in src


def test_budget_reload_save_and_apply_close_active_editor_first():
    src = _budget_tab_source()
    assert 'self._close_table_editor("Budget-Tabelle neu laden")' in src
    assert 'self._close_table_editor("Budget speichern")' in src
    assert 'self._close_table_editor("Budget-Anfrage anwenden")' in src
    assert 'self.typ_cb.blockSignals(True)' in src
