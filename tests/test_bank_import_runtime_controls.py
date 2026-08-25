from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "views/bank_import_dialog_runtime.py"
V4 = ROOT / "views/bank_import_dialog_v4.py"
HELP_MENU = ROOT / "views/help_menu.py"


def test_help_menu_uses_runtime_bank_import_dialog():
    src = HELP_MENU.read_text(encoding="utf-8")
    assert "from views.bank_import_dialog_runtime import BankImportDialog" in src


def test_runtime_routes_to_simplified_v4_dialog():
    src = RUNTIME.read_text(encoding="utf-8")
    assert "from views.bank_import_dialog_v4 import BankImportDialog" in src
    assert "class BankImportDialog(" not in src


def test_v4_has_one_selection_source_only():
    src = V4.read_text(encoding="utf-8")
    assert "SelectionMode.NoSelection" in src
    assert "self.states[index].use" in src
    assert "self._checked_indexes()" in src
    assert "selectedRows()" not in src
    assert "QTableWidgetSelectionRange" not in src


def test_v4_shift_and_ctrl_a_work_on_visible_checkboxes():
    src = V4.read_text(encoding="utf-8")
    assert "Qt.KeyboardModifier.ShiftModifier" in src
    assert "if self.table.isRowHidden(current):" in src
    assert "QKeySequence.StandardKey.SelectAll" in src
    assert "self._set_visible_checked(True)" in src


def test_v4_optional_tags_are_hidden_behind_one_dialog_and_can_be_created_inline():
    src = V4.read_text(encoding="utf-8")
    assert "class TagSelectionDialog(QDialog):" in src
    assert 'self.tags_model.create_tag(name, action_text="")' in src
    assert "self.btn_tags.clicked.connect(self._edit_tags_for_checked)" in src
    assert "COL_TAGS" not in src
