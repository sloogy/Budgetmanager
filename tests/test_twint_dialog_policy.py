from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIALOG = ROOT / "views/bank_import_dialog.py"


def _source() -> str:
    return DIALOG.read_text(encoding="utf-8")


def test_twint_is_ai_only_pseudo_type_in_type_dropdown():
    src = _source()
    assert 'TYP_TWINT_AI = "TWINT (KI)"' not in src  # Konstante lebt im Modell.
    assert "combo.addItem(TYP_TWINT_AI, TYP_TWINT_AI)" in src
    assert "return TYP_TWINT_AI if is_twint_credit(tx)" in src
    assert '"TWINT (KI) erzeugt niemals eine Budgetbuchung."' in src


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

    build_block = src.split("def _build_item", 1)[1].split(
        "def import_selected", 1
    )[0]
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
    block = src.split("def _build_matches", 1)[1].split(
        "def _category_token", 1
    )[0]
    assert "and index not in self.marked_twint_indexes" in block
    assert "or credit_index in self.marked_twint_indexes" in block
