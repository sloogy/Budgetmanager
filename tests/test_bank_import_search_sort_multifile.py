from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIALOG = ROOT / "views/bank_import_dialog.py"


def _source() -> str:
    return DIALOG.read_text(encoding="utf-8")


def test_bank_import_can_load_multiple_statements_in_one_review():
    src = _source()
    assert "QFileDialog.getOpenFileNames(" in src
    assert "self._transaction_digests" in src
    assert (
        "local_duplicates = self.service.duplicate_indexes(file_transactions, digest)"
        in src
    )
    assert "digests.extend(digest for _tx in file_transactions)" in src


def test_multifile_import_keeps_duplicate_identity_per_source_file():
    src = _source()
    block = src.split("def import_selected", 1)[1]
    assert "digest = self._digest_for_index(index)" in block
    assert "plan_groups[digest].append(item)" in block
    assert "self.service.import_items(plan, document_digest=digest)" in block
    assert "twint_groups" in block
    assert "ai_groups" in block


def test_import_review_has_global_search_without_changing_selection():
    src = _source()
    assert "self.search_input = QLineEdit()" in src
    assert 'self.search_input.setPlaceholderText(tr("search.placeholder"))' in src
    assert "self.search_input.textChanged.connect(self._apply_search_filter)" in src
    block = src.split("def _apply_search_filter", 1)[1].split("def open_file", 1)[0]
    assert "self.table.setRowHidden(" in block
    assert "tx.source_name" in block
    assert "selected_tags()" in block


def test_import_sorting_preserves_manual_review_state():
    src = _source()
    assert "self.cmb_sort = QComboBox()" in src
    assert "self._capture_row_states()" in src
    assert "self._restore_row_states(states)" in src
    assert '"category_asc"' in src
    assert '"tags_asc"' in src
    assert '"source_asc"' in src


def test_tag_dropdown_is_alphabetical_and_searchable():
    src = _source()
    combo = src.split("class CheckableTagCombo", 1)[1].split(
        "class BankImportDialog", 1
    )[0]
    assert "for name in sorted(tag_names, key=str.casefold):" in combo
    assert "def showPopup(self)" in combo
    assert "def _filter_items(self, text: str)" in combo
    assert "self.view().setRowHidden(" in combo
    assert 'line_edit.setPlaceholderText(tr("search.placeholder"))' in combo
