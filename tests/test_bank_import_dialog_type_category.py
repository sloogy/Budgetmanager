from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIALOG = ROOT / "views/bank_import_dialog_v2.py"


def _source() -> str:
    return DIALOG.read_text(encoding="utf-8")


def test_type_is_rendered_as_combo_box_not_plain_text_item():
    src = _source()
    assert "self._type_combo(self._default_type(tx), row)" in src
    assert "currentIndexChanged.connect" in src
    assert "self.table.setItem(row, self.COL_TYPE, QTableWidgetItem(typ))" not in src


def test_category_is_rebuilt_after_type_change():
    src = _source()
    type_change = src.split("def _type_changed", 1)[1].split("def _populate", 1)[0]
    assert "self._set_prediction_for_row(row, replace_tags=True)" in type_change
    prediction = src.split("def _set_prediction_for_row", 1)[1].split(
        "def _type_changed", 1
    )[0]
    assert "typ = self._row_type(row)" in prediction
    assert "self._category_combo(typ, prediction.category)" in prediction


def test_import_uses_selected_type_instead_of_transaction_sign():
    src = _source()
    build = src.split("def _build_item", 1)[1].split("def import_selected", 1)[0]
    assert "typ = self._row_type(row)" in build
    assert "TYP_INCOME if tx.amount > 0 else TYP_EXPENSES" not in build


def test_credit_card_adapter_is_selected_before_generic_reader():
    src = _source()
    open_block = src.split("def open_file", 1)[1].split("def _build_matches", 1)[0]
    assert "if is_credit_card_csv(path):" in open_block
    assert "load_credit_card_csv" in open_block
    assert "load_transactions" in open_block
