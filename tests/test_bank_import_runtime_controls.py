from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "views/bank_import_dialog_runtime.py"
HELP_MENU = ROOT / "views/help_menu.py"


def _runtime_source() -> str:
    return RUNTIME.read_text(encoding="utf-8")


def test_help_menu_uses_runtime_bank_import_dialog():
    src = HELP_MENU.read_text(encoding="utf-8")
    assert "from views.bank_import_dialog_runtime import BankImportDialog" in src


def test_import_can_create_tags_inline_with_existing_tag_model_rules():
    src = _runtime_source()
    assert 'QPushButton(tr("tags.create_inline"))' in src
    assert "QInputDialog.getText(" in src
    assert "self.tags.name_exists(name)" in src
    assert "self.tags.create_tag(name, action_text=action_text.strip())" in src
    assert "self._reload_tag_controls(preferred=name)" in src


def test_new_tag_is_reloaded_into_row_and_bulk_dropdowns():
    src = _runtime_source()
    block = src.split("def _reload_tag_controls", 1)[1].split(
        "def _set_visible_import_checked", 1
    )[0]
    assert "self.tags.list_all()" in block
    assert "CheckableTagCombo(" in block
    assert "selected=selected" in block
    assert "locked=fixed" in block
    assert "self.cmb_bulk_tag.clear()" in block
    assert "self.cmb_bulk_tag.addItem(tag_name, tag_name)" in block


def test_select_all_and_deselect_all_only_touch_visible_import_rows():
    src = _runtime_source()
    assert 'QPushButton(tr("btn.select_all"))' in src
    assert 'QPushButton(tr("btn.deselect_all"))' in src
    block = src.split("def _set_visible_import_checked", 1)[1].split(
        "def _drop_hidden_selection", 1
    )[0]
    assert "if self.table.isRowHidden(row):" in block
    assert "ItemIsUserCheckable" in block
    assert "item.setCheckState(state)" in block


def test_shift_and_mass_edit_drop_filtered_rows_from_selection():
    src = _runtime_source()
    assert "self.table.itemSelectionChanged.connect(self._drop_hidden_selection)" in src
    hidden_block = src.split("def _drop_hidden_selection", 1)[1].split(
        "def _apply_search_filter", 1
    )[0]
    assert "self.table.isRowHidden(row)" in hidden_block
    assert "QTableWidgetSelectionRange(" in hidden_block
    assert "False," in hidden_block

    filter_block = src.split("def _apply_search_filter", 1)[1].split(
        "def _selected_rows", 1
    )[0]
    assert "super()._apply_search_filter(_text)" in filter_block
    assert "self._drop_hidden_selection()" in filter_block

    selected_block = src.split("def _selected_rows", 1)[1]
    assert "super()._selected_rows()" in selected_block
    assert "if not self.table.isRowHidden(row)" in selected_block
