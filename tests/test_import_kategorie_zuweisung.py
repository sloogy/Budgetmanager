"""Kategorie im Zahlungsimport setzen - wie in der Schnelleingabe.

Der Importdialog hatte fuer die Kategorie eine schlichte Auswahlliste,
waehrend die Schnelleingabe ein Suchfeld ueber einem gefilterten,
gruppierten Dropdown bietet. Bei zweihundert Kategorien ist das der
Unterschied zwischen Tippen und Scrollen - und die richtige Kategorie ist
der Punkt, an dem ein Import brauchbar wird oder nicht.

Dazu kommt die Zuweisung fuer mehrere Vorschlaege auf einmal: Wer zwanzig
Zahlungen derselben Art importiert, soll nicht zwanzigmal denselben Dialog
oeffnen.
"""

from __future__ import annotations

import sqlite3

import pytest

from PySide6.QtWidgets import QApplication

from model.category_model import CategoryModel
from model.migrations import migrate_all
from utils.money import set_currency


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def conn() -> sqlite3.Connection:
    verbindung = sqlite3.connect(":memory:")
    verbindung.row_factory = sqlite3.Row
    verbindung.execute("PRAGMA foreign_keys=ON")
    migrate_all(verbindung)
    modell = CategoryModel(verbindung)
    modell.create("Ausgaben", "Füller")
    modell.create("Ausgaben", "Tinte")
    modell.create("Einkommen", "Lohn")
    set_currency("CHF")
    return verbindung


def test_der_picker_filtert_und_liefert_den_echten_namen(qapp, conn):
    from views.category_search_picker import CategorySearchPicker
    from views.lifeplanner_import_dialog import _kategoriezeilen

    picker = CategorySearchPicker()
    picker.set_rows(_kategoriezeilen(conn, "Ausgaben"))

    picker.search.setText("tin")
    picker._on_search_edited("tin")

    treffer = [
        picker.combo.itemData(i)
        for i in range(picker.combo.count())
        if isinstance(picker.combo.itemData(i), str)
    ]
    assert treffer == ["Tinte"]
    assert picker.selected_category() == "Tinte"


def test_leere_auswahl_meldet_keine_kategorie(qapp, conn):
    """Sonst buchte ein Vorschlag auf die erste Kategorie der Liste."""
    from views.category_search_picker import CategorySearchPicker

    picker = CategorySearchPicker()
    picker.set_rows([])

    assert picker.selected_category() == ""
    assert picker.hat_auswahl() is False


def test_ein_typwechsel_zeigt_die_kategorien_des_neuen_typs(qapp, conn):
    from views.category_search_picker import CategorySearchPicker
    from views.lifeplanner_import_dialog import _kategoriezeilen

    picker = CategorySearchPicker()
    picker.set_rows(_kategoriezeilen(conn, "Ausgaben"))
    assert picker.selected_category() in {"Füller", "Tinte"}

    picker.set_rows(_kategoriezeilen(conn, "Einkommen"))
    namen = {
        picker.combo.itemData(i)
        for i in range(picker.combo.count())
        if isinstance(picker.combo.itemData(i), str)
    }
    assert namen == {"Lohn"}


def test_kategoriezeilen_fallen_auf_die_flache_liste_zurueck(qapp, conn, monkeypatch):
    """Ohne Gruppen soll man waehlen koennen - eine leere Liste waere schlimmer."""
    from views.lifeplanner_import_dialog import _kategoriezeilen

    def _keine_gruppen(self, typ):
        raise AttributeError("kein gruppiertes Dropdown")

    monkeypatch.setattr(
        CategoryModel, "list_for_tracking_dropdown_grouped", _keine_gruppen
    )
    zeilen = _kategoriezeilen(conn, "Ausgaben")

    assert zeilen
    assert all(kind == "item" for kind, _label, _value in zeilen)
    assert {value for _kind, _label, value in zeilen} == {"Füller", "Tinte"}


def _record(external_id: str, status: str = "pending"):
    from datetime import date

    from model.lifeplanner_import_service import ImportRecord

    return ImportRecord(
        external_id=external_id,
        source="FPM",
        booking_date=date(2026, 7, 30),
        amount=12.0,
        currency="CHF",
        category_path="Hobby/Füller",
        description="Füller",
        counterparty="Papeterie",
        notes="",
        metadata={},
        payload_hash="x",
        raw={},
        status=status,
    )


def test_die_zuweisung_laesst_uebernommene_vorschlaege_in_ruhe(qapp, conn):
    """Ihr Entwurf ist Geschichte - die Buchung daraus zoege nicht mit."""
    from datetime import date

    from model.lifeplanner_import_service import ImportDraft
    from views.lifeplanner_import_dialog import _kategorie_auf_entwuerfe_setzen

    def _draft(external_id: str) -> ImportDraft:
        return ImportDraft(
            external_id=external_id,
            booking_date=date(2026, 7, 30),
            typ="Ausgaben",
            category="Füller",
            amount=12.0,
            details="",
            source_currency="CHF",
            currency_confirmed=True,
        )

    records = {
        "offen": _record("offen"),
        "fertig": _record("fertig", status="imported"),
        "abgelehnt": _record("abgelehnt", status="rejected"),
    }
    drafts = {kennung: _draft(kennung) for kennung in records}

    geaendert = _kategorie_auf_entwuerfe_setzen(
        conn=conn,
        drafts=drafts,
        records_by_id=records,
        external_ids=list(records),
        typ="Ausgaben",
        kategorie="Tinte",
    )

    assert geaendert == 1
    assert drafts["offen"].category == "Tinte"
    assert drafts["fertig"].category == "Füller"
    assert drafts["abgelehnt"].category == "Füller"


def test_die_zuweisung_setzt_auch_den_typ(qapp, conn):
    """Sonst landet eine Einkommenskategorie unter Ausgaben."""
    from datetime import date

    from model.lifeplanner_import_service import ImportDraft
    from views.lifeplanner_import_dialog import _kategorie_auf_entwuerfe_setzen

    drafts = {
        "a": ImportDraft(
            external_id="a",
            booking_date=date(2026, 7, 30),
            typ="Ausgaben",
            category="Füller",
            amount=12.0,
            details="",
            source_currency="CHF",
            currency_confirmed=True,
        )
    }
    geaendert = _kategorie_auf_entwuerfe_setzen(
        conn=conn,
        drafts=drafts,
        records_by_id={"a": _record("a")},
        external_ids=["a"],
        typ="Einkommen",
        kategorie="Lohn",
    )

    assert geaendert == 1
    assert drafts["a"].typ == "Einkommen"
    assert drafts["a"].category == "Lohn"
