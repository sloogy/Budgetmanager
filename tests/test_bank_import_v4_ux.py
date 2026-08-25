from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V4 = ROOT / "views/bank_import_dialog_v4.py"


def _source() -> str:
    return V4.read_text(encoding="utf-8")


def test_v4_main_table_is_reduced_to_seven_columns():
    src = _source()
    assert "self.table = QTableWidget(0, 7)" in src
    for name in (
        "COL_USE",
        "COL_DATE",
        "COL_TEXT",
        "COL_AMOUNT",
        "COL_CATEGORY",
        "COL_SOURCE",
        "COL_STATUS",
    ):
        assert name in src
    assert "COL_TYPE" not in src
    assert "COL_AI" not in src
    assert "COL_EFFECTIVE" not in src


def test_v4_type_follows_category_instead_of_needing_a_type_dropdown():
    src = _source()
    block = src.split("def _category_changed", 1)[1].split("def _item_clicked", 1)[0]
    assert "state.category_typ = typ" in block
    assert "state.typ = typ" in block
    assert "SearchableCategoryCombo" in src


def test_v4_review_filters_make_open_cases_the_primary_workflow():
    src = _source()
    assert 'for key in ("all", "review", "ready", "duplicates", "twint")' in src
    assert "if not state.category:" in src
    assert 'return "review"' in src
    assert "status_twint_review" in src
    assert "review_hint" in src


def test_v4_multifile_source_menu_can_remove_an_accidentally_loaded_file():
    src = _source()
    assert "QFileDialog.getOpenFileNames(" in src
    assert "self.sources: list[LoadedSource]" in src
    assert "def _rebuild_sources_menu" in src
    assert "def _remove_source" in src
    assert (
        "self.sources = [source for source in self.sources if source.path != path]"
        in src
    )


def test_v4_keeps_per_file_digest_for_duplicate_safety_and_atomic_import():
    src = _source()
    assert "self._transaction_digests" in src
    assert "duplicates = self.service.duplicate_indexes(transactions, digest)" in src
    block = src.split("def import_selected", 1)[1]
    assert "plan_groups[digest].append(item)" in block
    assert "self.service.import_items(items, document_digest=digest)" in block
    assert "twint_groups[digest].append" in block


def test_v4_twint_is_still_ai_only_and_netting_is_opt_in():
    src = _source()
    assert "self.act_net_twint.setChecked(False)" in src
    assert "state.typ == TYP_TWINT_AI" in src
    build = src.split("def _build_item", 1)[1].split("def import_selected", 1)[0]
    assert "state.typ == TYP_TWINT_AI" in build
    assert "return None" in build
    assert "marker_store.mark_classifications" in src


def test_v4_sorting_preserves_review_state_by_sorting_only_view_order():
    src = _source()
    block = src.split("def _sort_view", 1)[1].split("def _rebuild_sources_menu", 1)[0]
    # Ohne Leerraum vergleichen: die Zusicherung gilt der Sortierung ueber
    # _view_order, nicht dem Zeilenumbruch, den black in den Aufruf setzt.
    compact = "".join(block.split())
    assert "self._view_order=sorted(range(len(self.transactions))" in compact
    assert "self.states[index]" in block
    assert "self._populate_table()" in block


def test_v4_rejects_same_file_digest_inside_one_review():
    src = _source()
    block = src.split("def _add_paths", 1)[1].split("def _rebuild_from_sources", 1)[0]
    assert "known_digests" in block
    assert "if digest in known_digests:" in block
    assert "same_file_already_loaded" in block


def test_v4_twint_match_can_reuse_expense_category_without_blocking_main_import():
    src = _source()
    init = src.split("def _initialize_states", 1)[1].split("def _populate_table", 1)[0]
    assert 'prediction_method = "twint_match"' in init
    assert "credit_state.category = expense_state.category" in init
    assert "credit_state.use = credit_index not in self.marked_twint_indexes" in init
    assert "use=index not in self.marked_twint_indexes and all(preferred)" in init


def test_v4_bulk_tag_dialog_uses_tristate_to_preserve_mixed_rows():
    src = _source()
    assert "ItemIsUserTristate" in src
    assert "Qt.CheckState.PartiallyChecked" in src
    block = src.split("def _edit_tags_for_checked", 1)[1].split(
        "def _twint_option_changed", 1
    )[0]
    assert "selected_any" in block
    assert "selected_all" in block
    assert "decision == Qt.CheckState.Checked" in block
    assert "decision == Qt.CheckState.Unchecked" in block
