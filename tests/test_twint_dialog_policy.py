"""Fachliche TWINT-Invarianten des aktiven Bankimports (V4).

Bis v3.0.6 pruefte diese Datei den Quelltext von ``bank_import_dialog_v3.py``
per ``read_text()``-Zusicherung. Genau deshalb blieb unbemerkt, dass V4 die
Lernmarker der Vorgaengerversion nicht las: der Quelltext von V3 stimmte
weiterhin, nur lief er nicht mehr. Alle sechs Invarianten stehen jetzt als
Verhaltenstests gegen die ausgefuehrte V4-Klasse. Das Geruest (``v4_*``-
Fixtures) liegt in ``tests/conftest.py``.
"""

from datetime import date

from model.twint_import_policy import TYP_TWINT_AI, BankImportMarkerStore
from model.typ_constants import TYP_EXPENSES, TYP_INCOME
from tests.conftest import V4_DIGEST, V4_KATEGORIE, V4_KATEGORIE_ZWEI


def _kategorie_id(conn, typ: str, name: str) -> int:
    row = conn.execute(
        "SELECT id FROM categories WHERE typ=? AND name=?", (typ, name)
    ).fetchone()
    assert row is not None, f"Kategorie {typ}/{name} fehlt"
    return int(row[0])


def _pflicht_tag(conn, typ: str, kategorie: str, tag_name: str) -> None:
    """Haengt einen fixen Kategorie-Tag an typ/kategorie."""
    from model.tags_model import TagsModel

    tags = TagsModel(conn)
    tag_id = tags.create_tag(tag_name, action_text="")
    if not isinstance(tag_id, int):
        tag_id = int(
            conn.execute("SELECT id FROM tags WHERE name=?", (tag_name,)).fetchone()[0]
        )
    tags.assign_to_category(_kategorie_id(conn, typ, kategorie), int(tag_id))


def test_twint_eingang_ist_ein_reiner_ki_pseudotyp(v4_dialog, v4_tx, v4_helfer):
    """Ein positiver TWINT-Eingang ist immer ``TWINT (KI)`` und bleibt es."""
    dialog = v4_dialog(
        [
            v4_tx(0, description="TWINT Gutschrift Anna", amount="25.00"),
            v4_tx(1, description="Lohn Maerz", amount="4200.00"),
        ]
    )

    assert dialog.states[0].typ == TYP_TWINT_AI
    assert dialog.states[1].typ == TYP_INCOME
    assert dialog.twint_credit_indexes == {0}

    # V4 hat kein Typ-Steuerelement je Zeile; die einzige Umschaltung ist die
    # Massenaktion "nur lernen". Die TWINT-Zeile ist davon ausgenommen.
    v4_helfer.haken_setzen(dialog, 0, True)
    v4_helfer.haken_setzen(dialog, 1, True)
    assert dialog._learn_only_candidates() == [1]

    dialog._toggle_learn_only()
    assert dialog.states[0].typ == TYP_TWINT_AI
    assert dialog.states[1].typ == TYP_TWINT_AI

    dialog._toggle_learn_only()
    assert dialog.states[0].typ == TYP_TWINT_AI
    assert dialog.states[1].typ == TYP_INCOME


def test_twint_zeile_kann_ausgaben_und_einkommenskategorien_waehlen(v4_dialog, v4_tx):
    """Das Lernsignal darf jede echte Kategorie treffen, nicht nur Einkommen."""
    dialog = v4_dialog([v4_tx(0, description="TWINT Gutschrift Anna", amount="25.00")])

    combo = dialog.table.cellWidget(0, dialog.COL_CATEGORY)
    assert combo is not None
    ausgaben = combo.findData(dialog._category_token(TYP_EXPENSES, V4_KATEGORIE))
    einkommen = combo.findData(dialog._category_token(TYP_INCOME, V4_KATEGORIE))
    assert ausgaben >= 0
    assert einkommen >= 0
    assert f"{TYP_EXPENSES} · {V4_KATEGORIE}" == combo.itemText(ausgaben)

    combo.setCurrentIndex(ausgaben)
    assert dialog.states[0].category_typ == TYP_EXPENSES
    assert dialog.states[0].category == V4_KATEGORIE
    # Die Kategorie darf den Pseudotyp nicht kippen.
    assert dialog.states[0].typ == TYP_TWINT_AI


def test_twint_ki_hat_null_budgetwirkung_und_erzeugt_nie_eine_buchung(
    v4_dialog, v4_tx, v4_helfer
):
    dialog = v4_dialog([v4_tx(0, description="TWINT Gutschrift Anna", amount="25.00")])
    v4_helfer.haken_setzen(dialog, 0, True)
    v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE)

    assert dialog._effective_amount(0) == (0.0, "twint_ai")
    assert dialog._build_item(0) is None


def test_twint_lernen_verlangt_eine_echte_kategorie(
    v4_conn, v4_dialog, v4_tx, v4_helfer, monkeypatch
):
    """Ohne Kategorie darf der Import weder buchen noch lernen."""
    import views.bank_import_dialog_v4 as v4

    warnungen: list[str] = []
    monkeypatch.setattr(
        v4, "show_warning", lambda _parent, _title, text: warnungen.append(str(text))
    )
    monkeypatch.setattr(v4, "show_info", lambda *args, **kwargs: None)

    def _keine_rueckfrage(*args, **kwargs):  # pragma: no cover - darf nie laufen
        raise AssertionError("Import haette vor der Rueckfrage abbrechen muessen")

    monkeypatch.setattr(v4.QMessageBox, "question", staticmethod(_keine_rueckfrage))

    tx = v4_tx(0, description="TWINT Gutschrift Anna", amount="25.00")
    dialog = v4_dialog([tx])
    v4_helfer.haken_setzen(dialog, 0, True)
    assert not dialog.states[0].category

    dialog.import_selected()

    assert warnungen, "Fehlende Kategorie muss gemeldet werden"
    store = BankImportMarkerStore(v4_conn)
    assert not store.is_marked(tx, V4_DIGEST, marker_kind="twint_credit")
    assert not store.is_marked(tx, V4_DIGEST, marker_kind="twint_ai")
    assert v4_conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 0


def test_bereits_markierter_twint_eingang_wird_nicht_erneut_verrechnet(
    v4_conn, v4_dialog, v4_tx
):
    """Ein gelernter TWINT-Eingang darf keine zweite Ausgabe mehr kuerzen."""
    ausgabe = v4_tx(
        0,
        description="Restaurant Bern",
        amount="-80.00",
        booking_date=date(2026, 3, 17),
    )
    eingang = v4_tx(
        1,
        description="TWINT Gutschrift Anna",
        amount="40.00",
        booking_date=date(2026, 3, 18),
    )

    ohne_marker = v4_dialog([ausgabe, eingang])
    assert 0 in ohne_marker.matches
    assert ohne_marker.matched_credit_indexes == {1}

    BankImportMarkerStore(v4_conn).mark_classifications(
        [(eingang, TYP_EXPENSES, V4_KATEGORIE)], V4_DIGEST, marker_kind="twint_credit"
    )

    mit_marker = v4_dialog([ausgabe, eingang])
    assert mit_marker.marked_twint_indexes == {1}
    assert mit_marker.matches == {}
    assert mit_marker.matched_credit_indexes == set()


def test_tags_stammen_aus_der_kategorie_und_landen_in_der_buchung(
    v4_conn, v4_dialog, v4_tx, v4_helfer
):
    """Kategorie-Tags werden abgeleitet, nicht in der Zeile gepflegt."""
    _pflicht_tag(v4_conn, TYP_EXPENSES, V4_KATEGORIE, "Haushalt")
    _pflicht_tag(v4_conn, TYP_EXPENSES, V4_KATEGORIE_ZWEI, "Freizeit")

    dialog = v4_dialog([v4_tx(0, description="Migros Zuerich", amount="-45.20")])
    assert dialog._category_tags(0) == set()

    v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE)
    assert dialog._category_tags(0) == {"Haushalt"}
    assert dialog._all_tags(0) == ("Haushalt",)
    assert dialog.states[0].manual_tags == set()

    item = dialog._build_item(0)
    assert item is not None
    assert item.tags == ("Haushalt",)

    v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE_ZWEI)
    assert dialog._all_tags(0) == ("Freizeit",)
