import os
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

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
    assert "credit_state.use = not self._is_learned(credit_index)" in init
    assert "use=not self._is_learned(index) and all(preferred)" in init


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


# ---------------------------------------------------------------------------
# Verhaltenstests gegen die echte V4-Klasse (Offscreen-Qt, echte SQLite-DB).
# Die Zusicherungen oben pruefen Quelltext; B1 konnte genau deshalb unbemerkt
# ausgeliefert werden. Alles ab hier fuehrt den Dialog wirklich aus.
# ---------------------------------------------------------------------------

DIGEST = "a" * 64
KATEGORIE = "Testkategorie"


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    yield QApplication.instance() or QApplication([])


@pytest.fixture
def conn():
    from model.category_model import CategoryModel
    from model.migrations import migrate_all
    from model.typ_constants import TYP_EXPENSES, TYP_INCOME

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate_all(connection)
    categories = CategoryModel(connection)
    categories.create(TYP_EXPENSES, KATEGORIE)
    categories.create(TYP_INCOME, KATEGORIE)
    yield connection
    connection.close()


def _tx(index: int, *, description: str, amount: str, tag: date | None = None):
    from model.bank_statement_reader import BankTransaction

    return BankTransaction(
        source_kind="csv",
        source_name="konto.csv",
        source_index=index,
        booking_date=tag or date(2026, 3, 17),
        amount=Decimal(amount),
        currency="CHF",
        description=description,
        counterparty="",
        raw={},
    )


@pytest.fixture
def make_dialog(qapp, conn):
    from views.bank_import_dialog_v4 import BankImportDialog, LoadedSource

    erzeugte = []

    def _factory(transactions):
        dialog = BankImportDialog(conn)
        dialog.sources = [
            LoadedSource("konto.csv", DIGEST, "Bank-CSV/PDF", list(transactions), set())
        ]
        dialog._rebuild_from_sources()
        erzeugte.append(dialog)
        return dialog

    yield _factory
    for dialog in erzeugte:
        dialog.deleteLater()
    qapp.processEvents()


def _kategorie_setzen(dialog, typ: str, name: str) -> None:
    token = dialog._category_token(typ, name)
    position = dialog.cmb_bulk_category.findData(token)
    assert position >= 0, f"Kategorie {typ}/{name} fehlt im Massen-Dropdown"
    dialog.cmb_bulk_category.setCurrentIndex(position)
    dialog._bulk_set_category()


def _haken_setzen(dialog, row: int) -> None:
    from PySide6.QtCore import Qt

    item = dialog.table.item(row, dialog.COL_USE)
    item.setCheckState(Qt.CheckState.Checked)


def _import_bestaetigen(monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    import views.bank_import_dialog_v4 as v4

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes),
    )
    monkeypatch.setattr(v4, "show_info", lambda *args, **kwargs: None)
    monkeypatch.setattr(v4, "show_warning", lambda *args, **kwargs: None)


def test_v4_erkennt_alten_twint_ai_marker_und_bietet_die_zeile_nicht_erneut_an(
    conn, make_dialog
):
    """B1: ``marker_kind='twint_ai'`` aus 3.0.3-3.0.6 muss sichtbar bleiben."""
    from PySide6.QtCore import Qt

    from model.twint_import_policy import BankImportMarkerStore
    from model.typ_constants import TYP_EXPENSES
    from utils.i18n import tr

    tx = _tx(0, description="Migros Zuerich", amount="-45.20")

    ohne_marker = make_dialog([tx])
    assert ohne_marker._checked_indexes() == [0]
    assert ohne_marker.ai_marker_indexes == set()

    BankImportMarkerStore(conn).mark_classifications(
        [(tx, TYP_EXPENSES, KATEGORIE)], DIGEST, marker_kind="twint_ai"
    )

    mit_marker = make_dialog([tx])
    assert mit_marker.ai_marker_indexes == {0}
    assert mit_marker._checked_indexes() == []
    assert mit_marker._status_text(0) == tr("bank_import_v4.status_learned")
    assert mit_marker.states[0].category == KATEGORIE
    haken = mit_marker.table.item(0, mit_marker.COL_USE)
    assert haken.checkState() == Qt.CheckState.Unchecked
    assert not (haken.flags() & Qt.ItemFlag.ItemIsUserCheckable)


def test_v4_bulkaktion_setzt_zeile_auf_nur_lernen_und_wieder_zurueck(make_dialog):
    """B2: manueller Weg zu ``TWINT (KI)`` ohne Typ-Dropdown je Zeile."""
    from model.twint_import_policy import TYP_TWINT_AI
    from model.typ_constants import TYP_EXPENSES
    from utils.i18n import tr

    dialog = make_dialog([_tx(0, description="Coop Bern", amount="-30.00")])
    _kategorie_setzen(dialog, TYP_EXPENSES, KATEGORIE)
    assert dialog.states[0].typ == TYP_EXPENSES
    assert dialog.btn_learn_only.text() == tr("bank_import_v4.learn_only")

    dialog._toggle_learn_only()
    assert dialog.states[0].typ == TYP_TWINT_AI
    assert dialog._effective_amount(0) == (0.0, "twint_ai")
    assert dialog._build_item(0) is None
    assert dialog.btn_learn_only.text() == tr("bank_import_v4.book_again")

    dialog._toggle_learn_only()
    assert dialog.states[0].typ == TYP_EXPENSES
    assert dialog._build_item(0) is not None


def test_v4_import_lernt_manuelle_zeile_als_twint_ai_ohne_budgetbuchung(
    monkeypatch, conn, make_dialog
):
    """B2: der Import muss den manuellen Fall als ``twint_ai`` speichern."""
    from model.twint_import_policy import BankImportMarkerStore
    from model.typ_constants import TYP_EXPENSES

    tx = _tx(0, description="Coop Bern", amount="-30.00")
    dialog = make_dialog([tx])
    _kategorie_setzen(dialog, TYP_EXPENSES, KATEGORIE)
    dialog._toggle_learn_only()

    _import_bestaetigen(monkeypatch)
    dialog.import_selected()

    store = BankImportMarkerStore(conn)
    assert store.is_marked(tx, DIGEST, marker_kind="twint_ai")
    assert not store.is_marked(tx, DIGEST, marker_kind="twint_credit")
    assert conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM ai_twint_memory").fetchone()[0] == 1


def test_v4_echter_twint_eingang_bleibt_twint_credit(monkeypatch, conn, make_dialog):
    """Die Sicherheitsregel bleibt: echte TWINT-Eingaenge sind nie umschaltbar."""
    from model.twint_import_policy import TYP_TWINT_AI, BankImportMarkerStore
    from model.typ_constants import TYP_EXPENSES

    tx = _tx(0, description="TWINT Gutschrift Anna", amount="25.00")
    dialog = make_dialog([tx])
    assert dialog.states[0].typ == TYP_TWINT_AI

    _haken_setzen(dialog, 0)
    _kategorie_setzen(dialog, TYP_EXPENSES, KATEGORIE)
    dialog._toggle_learn_only()
    assert dialog.states[0].typ == TYP_TWINT_AI

    _import_bestaetigen(monkeypatch)
    dialog.import_selected()

    store = BankImportMarkerStore(conn)
    assert store.is_marked(tx, DIGEST, marker_kind="twint_credit")
    assert not store.is_marked(tx, DIGEST, marker_kind="twint_ai")
    assert conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 0


def test_v4_sortierung_kennt_betrag_aufsteigend_und_tags(make_dialog):
    from utils.i18n import tr

    dialog = make_dialog(
        [
            _tx(0, description="Alpha", amount="-90.00"),
            _tx(1, description="Beta", amount="-10.00"),
        ]
    )

    beschriftungen: list[str] = []
    for action in dialog.btn_options.menu().actions():
        untermenue = action.menu()
        if untermenue is not None:
            beschriftungen = [eintrag.text() for eintrag in untermenue.actions()]
    assert tr("bank_import_v4.sort_amount_asc") in beschriftungen
    assert tr("bank_import_v4.sort_tags_asc") in beschriftungen

    dialog._sort_view("amount_asc")
    assert dialog._view_order == [1, 0]
    dialog._sort_view("amount_desc")
    assert dialog._view_order == [0, 1]

    dialog.states[0].manual_tags = {"Zebra"}
    dialog.states[1].manual_tags = {"Anker"}
    dialog._sort_view("tags_asc")
    assert dialog._view_order == [1, 0]


def test_v4_suche_findet_betrag_und_anzeigedatum(make_dialog):
    dialog = make_dialog(
        [
            _tx(0, description="Alpha", amount="-90.00", tag=date(2026, 3, 17)),
            _tx(1, description="Beta", amount="-10.00", tag=date(2026, 4, 2)),
        ]
    )

    dialog.search_input.setText("17.03.2026")
    assert not dialog.table.isRowHidden(0)
    assert dialog.table.isRowHidden(1)

    dialog.search_input.setText("10.00 CHF")
    assert dialog.table.isRowHidden(0)
    assert not dialog.table.isRowHidden(1)
