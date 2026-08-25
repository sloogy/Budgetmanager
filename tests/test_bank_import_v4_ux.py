from datetime import date
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
# Die Zusicherungen oben pruefen Quelltext; genau deshalb konnte der
# twint_ai-Fehler unbemerkt ausgeliefert werden. Alles ab hier fuehrt den
# Dialog wirklich aus. Das Geruest steht in tests/conftest.py.
# ---------------------------------------------------------------------------


def test_v4_erkennt_alten_twint_ai_marker_und_bietet_die_zeile_nicht_erneut_an(
    v4_conn, v4_dialog, v4_tx
):
    """B1: ``marker_kind='twint_ai'`` aus 3.0.3-3.0.6 muss sichtbar bleiben."""
    from PySide6.QtCore import Qt

    from model.twint_import_policy import BankImportMarkerStore
    from model.typ_constants import TYP_EXPENSES
    from tests.conftest import V4_DIGEST, V4_KATEGORIE
    from utils.i18n import tr

    tx = v4_tx(0, description="Migros Zuerich", amount="-45.20")

    ohne_marker = v4_dialog([tx])
    assert ohne_marker._checked_indexes() == [0]
    assert ohne_marker.ai_marker_indexes == set()

    BankImportMarkerStore(v4_conn).mark_classifications(
        [(tx, TYP_EXPENSES, V4_KATEGORIE)], V4_DIGEST, marker_kind="twint_ai"
    )

    mit_marker = v4_dialog([tx])
    assert mit_marker.ai_marker_indexes == {0}
    assert mit_marker._checked_indexes() == []
    assert mit_marker._status_text(0) == tr("bank_import_v4.status_learned")
    assert mit_marker.states[0].category == V4_KATEGORIE
    haken = mit_marker.table.item(0, mit_marker.COL_USE)
    assert haken.checkState() == Qt.CheckState.Unchecked
    assert not (haken.flags() & Qt.ItemFlag.ItemIsUserCheckable)


def test_v4_bulkaktion_setzt_zeile_auf_nur_lernen_und_wieder_zurueck(
    v4_dialog, v4_tx, v4_helfer
):
    """B2: manueller Weg zu ``TWINT (KI)`` ohne Typ-Dropdown je Zeile."""
    from model.twint_import_policy import TYP_TWINT_AI
    from model.typ_constants import TYP_EXPENSES
    from tests.conftest import V4_KATEGORIE
    from utils.i18n import tr

    dialog = v4_dialog([v4_tx(0, description="Coop Bern", amount="-30.00")])
    v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE)
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
    v4_conn, v4_dialog, v4_tx, v4_helfer, v4_import_bestaetigen
):
    """B2: der Import muss den manuellen Fall als ``twint_ai`` speichern."""
    from model.twint_import_policy import BankImportMarkerStore
    from model.typ_constants import TYP_EXPENSES
    from tests.conftest import V4_DIGEST, V4_KATEGORIE

    tx = v4_tx(0, description="Coop Bern", amount="-30.00")
    dialog = v4_dialog([tx])
    v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE)
    dialog._toggle_learn_only()

    v4_import_bestaetigen()
    dialog.import_selected()

    store = BankImportMarkerStore(v4_conn)
    assert store.is_marked(tx, V4_DIGEST, marker_kind="twint_ai")
    assert not store.is_marked(tx, V4_DIGEST, marker_kind="twint_credit")
    assert v4_conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 0
    assert v4_conn.execute("SELECT COUNT(*) FROM ai_twint_memory").fetchone()[0] == 1


def test_v4_echter_twint_eingang_bleibt_twint_credit(
    v4_conn, v4_dialog, v4_tx, v4_helfer, v4_import_bestaetigen
):
    """Die Sicherheitsregel bleibt: echte TWINT-Eingaenge sind nie umschaltbar."""
    from model.twint_import_policy import TYP_TWINT_AI, BankImportMarkerStore
    from model.typ_constants import TYP_EXPENSES
    from tests.conftest import V4_DIGEST, V4_KATEGORIE

    tx = v4_tx(0, description="TWINT Gutschrift Anna", amount="25.00")
    dialog = v4_dialog([tx])
    assert dialog.states[0].typ == TYP_TWINT_AI

    v4_helfer.haken_setzen(dialog, 0)
    v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE)
    dialog._toggle_learn_only()
    assert dialog.states[0].typ == TYP_TWINT_AI

    v4_import_bestaetigen()
    dialog.import_selected()

    store = BankImportMarkerStore(v4_conn)
    assert store.is_marked(tx, V4_DIGEST, marker_kind="twint_credit")
    assert not store.is_marked(tx, V4_DIGEST, marker_kind="twint_ai")
    assert v4_conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 0


def test_v4_sortierung_kennt_betrag_aufsteigend_und_tags(v4_dialog, v4_tx):
    from utils.i18n import tr

    dialog = v4_dialog(
        [
            v4_tx(0, description="Alpha", amount="-90.00"),
            v4_tx(1, description="Beta", amount="-10.00"),
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


def test_v4_suche_findet_betrag_und_anzeigedatum(v4_dialog, v4_tx):
    dialog = v4_dialog(
        [
            v4_tx(
                0, description="Alpha", amount="-90.00", booking_date=date(2026, 3, 17)
            ),
            v4_tx(
                1, description="Beta", amount="-10.00", booking_date=date(2026, 4, 2)
            ),
        ]
    )

    dialog.search_input.setText("17.03.2026")
    assert not dialog.table.isRowHidden(0)
    assert dialog.table.isRowHidden(1)

    dialog.search_input.setText("10.00 CHF")
    assert dialog.table.isRowHidden(0)
    assert not dialog.table.isRowHidden(1)


# ── Aus tests/test_bank_import_search_sort_multifile.py portiert ─────────────
# Dort waren es Quelltext-Zusicherungen gegen die geloeschte Kette A.


def test_v4_haelt_die_duplikat_identitaet_je_quelldatei_getrennt(
    v4_conn, v4_dialog, v4_tx, v4_helfer, v4_import_bestaetigen
):
    """Zwei Dateien in einem Review, aber getrennte Digests und Batches."""
    from model.bank_import_service import external_id
    from model.typ_constants import TYP_EXPENSES
    from tests.conftest import V4_DIGEST, V4_DIGEST_ZWEI, V4_KATEGORIE

    erste = v4_tx(0, description="Alpha", amount="-10.00", source_name="a.csv")
    zweite = v4_tx(0, description="Beta", amount="-20.00", source_name="b.csv")
    dialog = v4_dialog(
        [],
        quellen=[
            (V4_DIGEST, "a.csv", [erste]),
            (V4_DIGEST_ZWEI, "b.csv", [zweite]),
        ],
    )
    assert dialog._digest_for_index(0) == V4_DIGEST
    assert dialog._digest_for_index(1) == V4_DIGEST_ZWEI

    v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE)
    v4_import_bestaetigen()
    dialog.import_selected()

    gespeichert = {
        str(row[0])
        for row in v4_conn.execute(
            "SELECT external_id FROM bank_import_state"
        ).fetchall()
    }
    assert external_id(erste, V4_DIGEST) in gespeichert
    assert external_id(zweite, V4_DIGEST_ZWEI) in gespeichert
    assert external_id(zweite, V4_DIGEST) not in gespeichert


def test_v4_suche_aendert_die_auswahl_nicht(v4_dialog, v4_tx):
    """Die Suche blendet nur aus; angehakte Zeilen bleiben angehakt."""
    dialog = v4_dialog(
        [
            v4_tx(0, description="Alpha", amount="-10.00"),
            v4_tx(1, description="Beta", amount="-20.00"),
        ]
    )
    vorher = dialog._checked_indexes()
    assert vorher == [0, 1]

    dialog.search_input.setText("Alpha")
    assert dialog.table.isRowHidden(1)
    assert dialog._checked_indexes() == vorher

    dialog.search_input.setText("")
    assert not dialog.table.isRowHidden(1)
    assert dialog._checked_indexes() == vorher


def test_v4_sortierung_erhaelt_den_manuellen_pruefstand(v4_dialog, v4_tx, v4_helfer):
    """Sortiert wird nur die Ansicht, nie der Zustand der Zeilen."""
    from model.typ_constants import TYP_EXPENSES
    from tests.conftest import V4_KATEGORIE

    dialog = v4_dialog(
        [
            v4_tx(0, description="Alpha", amount="-90.00"),
            v4_tx(1, description="Beta", amount="-10.00"),
        ]
    )
    v4_helfer.haken_setzen(dialog, 1, False)
    v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE)
    dialog.states[0].manual_tags = {"Ferien"}

    dialog._sort_view("amount_asc")

    assert dialog._view_order == [1, 0]
    assert dialog.states[0].category == V4_KATEGORIE
    assert dialog.states[0].manual_tags == {"Ferien"}
    assert dialog.states[0].use is True
    assert dialog.states[1].use is False
    assert dialog._checked_indexes() == [0]


def test_v4_tag_dialog_ist_alphabetisch_und_durchsuchbar(v4_app, v4_conn):
    """Ersetzt den Laufzeittest des geloeschten CheckableTagCombo."""
    from model.tags_model import TagsModel
    from views.bank_import_dialog_v4 import TagSelectionDialog

    tags = TagsModel(v4_conn)
    for name in ("zebra", "Anker", "mitte"):
        tags.create_tag(name, action_text="")

    dialog = TagSelectionDialog(tags, selected_all=set(), selected_any=set())
    try:
        sichtbar = [dialog.list.item(row).text() for row in range(dialog.list.count())]
        assert sichtbar == sorted(sichtbar, key=str.casefold)

        dialog.search.setText("ank")
        versteckt = {
            dialog.list.item(row).text(): dialog.list.item(row).isHidden()
            for row in range(dialog.list.count())
        }
        assert versteckt["Anker"] is False
        assert versteckt["zebra"] is True
    finally:
        dialog.deleteLater()
        v4_app.processEvents()


# ── Aus tests/test_bank_import_dialog_type_category.py portiert ─────────────
# Die drei Typ-Combo-Zusicherungen von dort pruefen ein Steuerelement, das V4
# bewusst nicht hat (die Kategorie bestimmt den Typ). Sie sind ersatzlos
# entfallen; die Leseradapter-Invariante steht hier als Verhaltenstest.


def _kreditkarten_csv(pfad) -> None:
    pfad.write_text(
        "TransactionId;CardId;Date;ValutaDate;Amount;Currency;;OriginalAmount;"
        "OriginalCurrency;MerchantName;MerchantPlace;MerchantCountry;StateType;"
        "Details;Type;Exchange Rate\n"
        "TX-123;CARD-1;21.08.2026;22.08.2026;-19.85;CHF;;21.30;EUR;"
        "COOP;Winterthur;CH;BOOKED;Mittagessen;PURCHASE;0.9319\n",
        encoding="utf-8",
    )


def _bank_csv(pfad) -> None:
    pfad.write_text(
        "Datum;Buchungstext;Whg;Betrag Detail;ZKB-Referenz;Referenznummer;"
        "Belastung CHF;Gutschrift CHF;Valuta;Saldo CHF;Zahlungszweck;Details\n"
        "23.08.2026;Kartenzahlung;CHF;10,00;ZKB-1;REF-1;10,00;;24.08.2026;"
        "1'000,00;Migros Einkauf;Filiale Winterthur\n",
        encoding="utf-8",
    )


def test_v4_waehlt_den_kreditkarten_adapter_vor_dem_allgemeinen_leser(
    v4_dialog, tmp_path
):
    """Eine Kreditkarten-CSV darf nicht im generischen CSV-Leser landen."""
    pfad = tmp_path / "kreditkarte.csv"
    _kreditkarten_csv(pfad)

    dialog = v4_dialog([], quellen=[])
    dialog._add_paths([str(pfad)])

    assert len(dialog.sources) == 1
    quelle = dialog.sources[0]
    assert quelle.source_format == "Kreditkarten-CSV"
    assert len(dialog.transactions) == 1
    tx = dialog.transactions[0]
    assert tx.source_kind == "credit_card_csv"
    assert tx.raw["TransactionId"] == "TX-123"
    assert "COOP" in tx.description


def test_v4_laedt_mehrere_kontoauszuege_in_ein_review(v4_dialog, tmp_path):
    """Bank- und Kreditkartendatei stehen gemeinsam in einer Pruefliste."""
    bank = tmp_path / "bank.csv"
    karte = tmp_path / "karte.csv"
    _bank_csv(bank)
    _kreditkarten_csv(karte)

    dialog = v4_dialog([], quellen=[])
    dialog._add_paths([str(bank), str(karte)])

    assert [quelle.source_format for quelle in dialog.sources] == [
        "Bank-CSV/PDF",
        "Kreditkarten-CSV",
    ]
    assert len(dialog.transactions) == 2
    assert dialog.table.rowCount() == 2
    erste, zweite = dialog._digest_for_index(0), dialog._digest_for_index(1)
    assert erste != zweite

    # Dieselbe Datei ein zweites Mal aendert nichts.
    dialog._add_paths([str(bank)])
    assert len(dialog.sources) == 2
