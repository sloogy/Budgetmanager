import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIALOG = ROOT / "views/bank_import_dialog_v3.py"


def _source() -> str:
    return DIALOG.read_text(encoding="utf-8")


def _kompakt() -> str:
    """Quelltext ohne Zeilenumbrueche und Mehrfach-Leerzeichen.

    Die Zusicherungen unten beschreiben eine fachliche Invariante, kein
    Zeilenlayout. Ohne diese Normalisierung bricht der Test, sobald black
    denselben Ausdruck anders umbricht - was er bei laengeren Namen tut.
    """

    return re.sub(r"\s+", " ", _source())


def test_twint_is_ai_only_pseudo_type_in_type_dropdown():
    src = _source()
    assert 'TYP_TWINT_AI = "TWINT (KI)"' not in src  # Konstante lebt im Modell.
    assert "combo.addItem(TYP_TWINT_AI, TYP_TWINT_AI)" in src
    assert "return ( TYP_TWINT_AI if is_twint_credit(tx)" in _kompakt()
    assert '"TWINT (KI) erzeugt niemals eine Budgetbuchung.' in src


def test_twint_ai_category_combo_contains_expense_and_income_categories():
    src = _source()
    block = src.split("def _ai_category_combo", 1)[1].split(
        "def _selected_ai_category", 1
    )[0]
    assert "for typ in (TYP_EXPENSES, TYP_INCOME):" in block
    assert "self.categories.list_names(typ)" in block
    assert 'f"{typ} · {name}"' in block


def test_twint_ai_has_zero_budget_effect_and_never_builds_budget_item():
    src = _source()
    amount_block = src.split("def _effective_amount", 1)[1].split(
        "def _apply_ai_policy", 1
    )[0]
    assert "if self._row_type(row) == TYP_TWINT_AI:" in amount_block
    assert 'return 0.0, "twint_ai"' in amount_block

    build_block = src.split("def _build_item", 1)[1].split("def import_selected", 1)[0]
    assert "if self._row_type(row) == TYP_TWINT_AI:" in build_block
    assert "return None" in build_block


def test_twint_ai_requires_real_category_before_learning():
    src = _source()
    block = src.split("def import_selected", 1)[1]
    assert "category_typ, category = self._selected_ai_category(row)" in block
    assert "Kategorie aus Einkommen oder Ausgaben wählen" in block
    assert "mark_classifications" in block


def test_already_marked_twint_is_not_reused_for_matching():
    src = _source()
    block = src.split("def _build_matches", 1)[1].split("def _ai_category_combo", 1)[0]
    assert "and index not in self.marked_twint_indexes" in block
    assert "or credit_index in self.marked_twint_indexes" in block


def test_tags_are_read_only_and_derived_from_selected_category():
    src = _source()
    assert 'QTableWidgetItem("Tags aus Kategorie")' in src
    assert "self.tags.get_tag_ids_for_category_name(category_typ, category)" in src
    assert "self.tags.get_tags_by_ids(tag_ids)" in src
    sync = src.split("def _sync_category_tags", 1)[1].split("def _category_changed", 1)[
        0
    ]
    assert "edit.setReadOnly(True)" in sync
    assert 'edit.setText(", ".join(names))' in sync
    raw = src.split("def _raw_tag_names", 1)[1].split("def _tag_names", 1)[0]
    assert "return self._tags_for_row(row)" in raw
