import os
from pathlib import Path

import pytest


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
    assert "self.cmb_bulk_tag = QComboBox()" in src
    assert "self.cmb_bulk_tag_action = QComboBox()" in src
    assert "self.cmb_bulk_use = QComboBox()" in src
    assert 'QPushButton("Auf Auswahl anwenden")' in src
    assert "self._apply_bulk_changes" in src


def test_tags_are_checkbox_dropdown_with_locked_category_tags():
    src = _source()
    assert "class CheckableTagCombo(QComboBox):" in src
    assert "item.setCheckable(True)" in src
    assert 'item.setText(f"🔒 {name}")' in src
    assert 'item.setToolTip("Pflicht-Tag der gewählten Kategorie")' in src
    assert "weitere vorhandene Tags lassen sich im Tag-Dropdown per" in src
    assert "Checkbox ergänzen" in src


def test_bulk_tags_can_be_added_or_removed_but_required_tags_stay_locked():
    src = _source()
    block = src.split("def _apply_bulk_changes", 1)[1]
    assert 'self.cmb_bulk_tag_action.addItem("Tag hinzufügen", "add")' in src
    assert 'self.cmb_bulk_tag_action.addItem("Tag entfernen", "remove")' in src
    assert "tag_combo.set_tag_checked(" in block
    assert "tag_combo.locked_tags()" in block
    assert "skipped_required_tag += 1" in block


def test_category_change_drops_old_required_tags_but_keeps_manual_tags():
    src = _source()
    block = src.split("def set_locked_tags", 1)[1].split("def set_tag_checked", 1)[0]
    assert "previous_locked" in block
    assert "selected_optional" in block
    assert "if self._key(name) not in previous_locked" in block


def test_checkable_tag_combo_runtime_preserves_only_optional_tags():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from views.bank_import_dialog import CheckableTagCombo

    app = QApplication.instance() or QApplication([])
    combo = CheckableTagCombo(
        ("Alt-Pflicht", "Neu-Pflicht", "Optional"),
        selected=("Optional",),
        locked=("Alt-Pflicht",),
    )
    try:
        assert combo.selected_tags() == ("Alt-Pflicht", "Optional")
        assert not combo.set_tag_checked("Alt-Pflicht", False)

        combo.set_locked_tags(("Neu-Pflicht",))
        assert combo.selected_tags() == ("Neu-Pflicht", "Optional")
        assert combo.locked_tags() == ("Neu-Pflicht",)

        assert combo.set_tag_checked("Optional", False)
        assert combo.selected_tags() == ("Neu-Pflicht",)
    finally:
        combo.deleteLater()
        app.processEvents()


def test_positive_twint_credit_type_dropdown_is_ai_only():
    src = _source()
    block = src.split("def _type_combo", 1)[1].split("def _populate", 1)[0]
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


def test_intro_explains_category_and_optional_tags():
    src = _source()
    assert "Kategorie-Tags werden automatisch übernommen" in src
    assert "weitere vorhandene Tags lassen sich im Tag-Dropdown per" in src
    assert "Checkbox ergänzen" in src
