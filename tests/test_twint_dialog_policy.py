from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIALOG = ROOT / "views/bank_import_dialog.py"


def _source() -> str:
    return DIALOG.read_text(encoding="utf-8")


def test_twint_rows_are_visibly_mark_only():
    src = _source()
    assert "TWINT-Erstattung (nicht buchen)" in src
    assert "— nur markieren, keine Kategorie —" in src
    assert "TWINT-Eingänge werden ausdrücklich nicht als Einkommen gebucht." in src


def test_twint_rows_never_build_budget_import_items():
    src = _source()
    block = src.split("def _build_item", 1)[1].split("def import_selected", 1)[0]
    assert "if index in self.twint_credit_indexes:" in block
    assert "return None" in block


def test_already_marked_twint_is_not_reused_for_matching():
    src = _source()
    block = src.split("def _build_matches", 1)[1].split("def _type_changed", 1)[0]
    assert "and index not in self.marked_twint_indexes" in block
    assert "or credit_index in self.marked_twint_indexes" in block


def test_twint_selection_is_not_forced_back_on_during_refresh():
    src = _source()
    block = src.split("def _apply_twint_policy", 1)[1].split(
        "def _refresh_effective_view", 1
    )[0]
    unmarked = block.split("else:", 1)[1]
    assert "setCheckState(Qt.Checked)" not in unmarked
