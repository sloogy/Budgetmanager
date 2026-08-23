from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIALOG = ROOT / "views/bank_import_dialog.py"


def _source() -> str:
    return DIALOG.read_text(encoding="utf-8")


def test_bank_import_supports_ctrl_shift_and_select_all_multi_selection():
    src = _source()
    assert "SelectionMode.ExtendedSelection" in src
    assert "Strg+Mausklick" in src
    assert "Umschalt+Mausklick" in src
    assert "Strg+A" in src
    assert "selectedRows()" in src


def test_bulk_editor_uses_dropdowns_for_mass_editable_fields():
    src = _source()
    assert "self.cmb_bulk_type = QComboBox()" in src
    assert "self.cmb_bulk_category = QComboBox()" in src
    assert "self.cmb_bulk_use = QComboBox()" in src
    assert 'QPushButton("Auf Auswahl anwenden")' in src
    assert "self._apply_bulk_changes" in src


def test_positive_twint_credit_type_dropdown_is_ai_only():
    src = _source()
    block = src.split("def _type_combo", 1)[1].split("def _selected_rows", 1)[0]
    assert "is_twint_credit(self.transactions[tx_index])" in block
    assert "combo.addItem(TYP_TWINT_AI, TYP_TWINT_AI)" in block
    assert "return super()._type_combo(typ, row)" in block


def test_bulk_edit_preserves_twint_credit_safety_policy():
    src = _source()
    block = src.split("def _apply_bulk_changes", 1)[1]
    assert "is_twint_credit(self.transactions[tx_index])" in block
    assert "wanted_type != TYP_TWINT_AI" in block
    assert "skipped_policy += 1" in block


def test_twint_netting_requires_explicit_review_opt_in():
    src = _source()
    assert "self.chk_net_twint.setChecked(False)" in src
    assert "TWINT-Verrechnung ist bewusst Opt-in" in src


def test_intro_matches_category_derived_read_only_tags():
    src = _source()
    assert "Tags werden automatisch aus der gewählten" in src
    assert "Kategorie übernommen" in src
