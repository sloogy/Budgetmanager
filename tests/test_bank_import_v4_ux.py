from datetime import date
from pathlib import Path

from tests.conftest import warte_auf_analyse

# ---------------------------------------------------------------------------
# Verhaltenstests gegen die echte V4-Klasse (Offscreen-Qt, echte SQLite-DB).
# Bis v3.0.6 standen hier zehn Zusicherungen der Bauart
# ``DATEI.read_text()`` + ``assert "..." in src``; genau deshalb konnte der
# twint_ai-Fehler unbemerkt ausgeliefert werden - der Quelltext enthielt die
# gesuchten Zeichenketten, der Dialog tat trotzdem etwas anderes. Jeder Test
# hier fuehrt den Dialog wirklich aus. Das Geruest steht in tests/conftest.py.
# ---------------------------------------------------------------------------


def test_v4_hauptansicht_hat_sieben_spalten_ohne_typ_und_ki_spalte(v4_dialog, v4_tx):
    """Die Reduktion auf sieben Spalten ist der Kern der V4-Ansicht."""
    from utils.i18n import tr

    dialog = v4_dialog([v4_tx(0, description="Migros", amount="-12.00")])

    assert dialog.table.columnCount() == 7
    beschriftungen = [
        dialog.table.horizontalHeaderItem(spalte).text()
        for spalte in range(dialog.table.columnCount())
    ]
    assert beschriftungen == [
        "✓",
        tr("header.date"),
        tr("bank_import_v4.booking"),
        tr("header.amount"),
        tr("header.category"),
        tr("header.source"),
        tr("bank_import_v4.status"),
    ]
    # Die frueheren Spalten Typ, KI und "effektiv" duerfen nicht zurueckkommen.
    assert not any(
        name.startswith("COL_")
        and name
        not in {
            "COL_USE",
            "COL_DATE",
            "COL_TEXT",
            "COL_AMOUNT",
            "COL_CATEGORY",
            "COL_SOURCE",
            "COL_STATUS",
        }
        for name in vars(type(dialog))
    )
    assert dialog.table.rowCount() == 1


def test_v4_kategorie_bestimmt_den_typ_ohne_eigenes_typ_dropdown(v4_dialog, v4_tx):
    """Statt eines Typ-Dropdowns je Zeile zieht der Typ der Kategorie nach."""
    from model.typ_constants import TYP_EXPENSES, TYP_INCOME
    from tests.conftest import V4_KATEGORIE

    dialog = v4_dialog([v4_tx(0, description="Rueckzahlung", amount="-40.00")])
    assert dialog.states[0].typ == TYP_EXPENSES

    combo = dialog.table.cellWidget(0, dialog.COL_CATEGORY)
    position = combo.findData(dialog._category_token(TYP_INCOME, V4_KATEGORIE))
    assert position >= 0, "Einnahme-Kategorie fehlt im Zeilen-Dropdown"
    combo.setCurrentIndex(position)

    assert dialog.states[0].category == V4_KATEGORIE
    assert dialog.states[0].category_typ == TYP_INCOME
    assert dialog.states[0].typ == TYP_INCOME


def test_v4_pruefungsfilter_trennt_offene_von_fertigen_zeilen(
    v4_dialog, v4_tx, v4_helfer
):
    """Die Filterleiste macht offene Faelle zum Hauptweg."""
    from model.typ_constants import TYP_EXPENSES
    from tests.conftest import V4_KATEGORIE

    dialog = v4_dialog(
        [
            v4_tx(0, description="Alpha", amount="-90.00"),
            v4_tx(1, description="Beta", amount="-10.00"),
        ]
    )
    assert list(dialog.filter_buttons) == [
        "all",
        "review",
        "ready",
        "duplicates",
        "twint",
    ]
    # TWINT-Verrechnung ist eine Entscheidung, keine Vorgabe.
    assert dialog.act_net_twint.isChecked() is False

    v4_helfer.haken_setzen(dialog, 1, False)
    v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE)
    assert dialog._state_kind(0) == "ready"
    assert dialog._state_kind(1) == "review"

    dialog._set_filter("review")
    assert dialog.table.isRowHidden(0)
    assert not dialog.table.isRowHidden(1)

    dialog._set_filter("ready")
    assert not dialog.table.isRowHidden(0)
    assert dialog.table.isRowHidden(1)

    dialog._set_filter("all")
    assert not dialog.table.isRowHidden(0)
    assert not dialog.table.isRowHidden(1)


def test_v4_versehentlich_geladene_datei_laesst_sich_wieder_entfernen(
    v4_dialog, tmp_path
):
    """Das Quellenmenue nimmt eine falsch gewaehlte Datei wieder heraus."""
    bank = tmp_path / "bank.csv"
    karte = tmp_path / "karte.csv"
    _bank_csv(bank)
    _kreditkarten_csv(karte)

    dialog = v4_dialog([], quellen=[])
    dialog._add_paths([str(bank), str(karte)])
    warte_auf_analyse(dialog)
    assert len(dialog.sources) == 2
    assert dialog.table.rowCount() == 2

    eintraege = dialog.btn_sources.menu().actions()
    entfernen = [
        aktion
        for aktion in eintraege
        if aktion.text().startswith("✕") and not aktion.isSeparator()
    ]
    assert len(entfernen) == 2
    entfernen[1].trigger()
    warte_auf_analyse(dialog)

    assert [Path(quelle.path).name for quelle in dialog.sources] == ["bank.csv"]
    assert len(dialog.transactions) == 1
    assert dialog.table.rowCount() == 1

    verbleibend = [
        aktion
        for aktion in dialog.btn_sources.menu().actions()
        if aktion.text().startswith("✕")
    ]
    assert len(verbleibend) == 1
    verbleibend[0].trigger()

    assert dialog.sources == []
    assert dialog.transactions == []
    assert dialog.table.rowCount() == 0
    assert dialog.btn_sources.isVisible() is False


def test_v4_twint_treffer_uebernimmt_die_kategorie_der_ausgabe(
    v4_conn, v4_dialog, v4_tx, v4_helfer, v4_import_bestaetigen
):
    """Eine erkannte TWINT-Erstattung wird kein zweiter Pflichtschritt."""
    from model.typ_constants import TYP_EXPENSES
    from tests.conftest import V4_DIGEST, V4_DIGEST_ZWEI, V4_KATEGORIE

    # Erst lernt die KI den Haendler aus einem regulaeren Import.
    lernlauf = v4_dialog([v4_tx(0, description="Restaurant Sonne", amount="-80.00")])
    v4_helfer.kategorie_setzen(lernlauf, TYP_EXPENSES, V4_KATEGORIE)
    v4_import_bestaetigen()
    lernlauf.import_selected()

    ausgabe = v4_tx(
        0,
        description="Restaurant Sonne",
        amount="-60.00",
        booking_date=date(2026, 5, 4),
        source_name="mai.csv",
    )
    erstattung = v4_tx(
        1,
        description="TWINT Gutschrift Anna",
        amount="30.00",
        booking_date=date(2026, 5, 5),
        source_name="mai.csv",
    )
    dialog = v4_dialog([], quellen=[(V4_DIGEST_ZWEI, "mai.csv", [ausgabe, erstattung])])

    assert V4_DIGEST != V4_DIGEST_ZWEI
    assert dialog.states[0].category == V4_KATEGORIE
    assert 0 in dialog.matches, "TWINT-Erstattung wurde nicht erkannt"

    gutschrift = dialog.states[1]
    assert gutschrift.category == V4_KATEGORIE
    assert gutschrift.category_typ == dialog.states[0].category_typ
    assert gutschrift.prediction_method == "twint_match"
    assert gutschrift.use is True


def test_v4_tag_dialog_haelt_gemischte_zeilen_im_dritten_zustand(
    v4_conn, v4_dialog, v4_tx, monkeypatch
):
    """Ein teilweise gesetztes Haekchen heisst "gemischt lassen", nicht "weg"."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDialog

    import views.bank_import_dialog_v4 as v4
    from model.tags_model import TagsModel

    TagsModel(v4_conn).create_tag("Ferien", action_text="")

    dialog = v4_dialog(
        [
            v4_tx(0, description="Alpha", amount="-10.00"),
            v4_tx(1, description="Beta", amount="-20.00"),
        ]
    )
    dialog.states[0].manual_tags = {"Ferien"}
    dialog.states[1].manual_tags = set()
    assert dialog._checked_indexes() == [0, 1]

    geoeffnet: list[object] = []
    entscheidung: dict[str, object] = {"wert": None}

    class _Sonde(v4.TagSelectionDialog):
        """Bedient den echten Dialog, statt ihn zu ersetzen."""

        def exec(self):
            geoeffnet.append(self)
            if entscheidung["wert"] is not None:
                for row in range(self.list.count()):
                    self.list.item(row).setCheckState(entscheidung["wert"])
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(v4, "TagSelectionDialog", _Sonde)

    # 1. Unveraendert bestaetigen: Der gemischte Zustand bleibt gemischt.
    dialog._edit_tags_for_checked()
    assert geoeffnet[0].tag_states()["Ferien"] == Qt.CheckState.PartiallyChecked
    assert dialog.states[0].manual_tags == {"Ferien"}
    assert dialog.states[1].manual_tags == set()

    # 2. Auf gesetzt schalten: Der Tag gilt danach fuer beide Zeilen.
    entscheidung["wert"] = Qt.CheckState.Checked
    dialog._edit_tags_for_checked()
    assert geoeffnet[1].tag_states()["Ferien"] == Qt.CheckState.Checked
    assert dialog.states[0].manual_tags == {"Ferien"}
    assert dialog.states[1].manual_tags == {"Ferien"}

    # 3. Auf leer schalten: Der Tag verschwindet aus beiden Zeilen.
    entscheidung["wert"] = Qt.CheckState.Unchecked
    dialog._edit_tags_for_checked()
    assert dialog.states[0].manual_tags == set()
    assert dialog.states[1].manual_tags == set()


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
    warte_auf_analyse(dialog)

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
    warte_auf_analyse(dialog)

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
    warte_auf_analyse(dialog)
    assert len(dialog.sources) == 2
