"""Der BudgetManager veroeffentlicht seinen Kategorienkatalog.

Ohne ihn muss ein anderes Modul raten, wie die Kategorien des Nutzers
heissen. FPM schickte darum bis Loop 49 feste Namen ("Hobby/Fueller"), die es
hier meist gar nicht gibt - der Import legte sie an oder jede Zahlung musste
von Hand zugeordnet werden.

Uebertragen werden nur Name und Typ: Der Katalog sagt, *wohin* etwas gebucht
werden kann, nicht was dort steht.
"""

from __future__ import annotations

import json

from model.category_model import CategoryModel
from model.database import open_db
from model.lifeplanner_import_service import (
    CATEGORIES_OUTBOX_FILE,
    export_categories,
)
from model.migrations import migrate_all
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS


def _db(tmp_path):
    pfad = str(tmp_path / "test.db")
    conn = open_db(pfad)
    migrate_all(conn, db_path=pfad, backup_dir=str(tmp_path / "bk"))
    return conn


def _lies(pfad) -> tuple[dict, list[dict]]:
    zeilen = [
        json.loads(z)
        for z in pfad.read_text(encoding="utf-8").splitlines()
        if z.strip()
    ]
    return zeilen[0], zeilen[1:]


def test_katalog_traegt_ausgaben_und_ersparnisse(tmp_path) -> None:
    conn = _db(tmp_path)
    try:
        kategorien = CategoryModel(conn)
        kategorien.create(TYP_EXPENSES, "Freizeit")
        kategorien.create(TYP_SAVINGS, "Wunschliste")
        kategorien.set_bridge_share(TYP_EXPENSES, "Freizeit", True)
        kategorien.set_bridge_share(TYP_SAVINGS, "Wunschliste", True)
        ergebnis = export_categories(conn, tmp_path / CATEGORIES_OUTBOX_FILE)
    finally:
        conn.close()

    kopf, eintraege = _lies(ergebnis.path)
    assert kopf["schema"] == "budgetmanager.categories.manifest.v1"
    namen = {(e["typ"], e["name"]) for e in eintraege}
    assert (TYP_EXPENSES, "Freizeit") in namen
    assert (TYP_SAVINGS, "Wunschliste") in namen


def test_einkommen_bleibt_aussen_vor(tmp_path) -> None:
    """Ein anderes Modul meldet Ausgaben und Ersparnisse, keine Einnahmen."""
    conn = _db(tmp_path)
    try:
        CategoryModel(conn).create(TYP_INCOME, "Lohn")
        ergebnis = export_categories(conn, tmp_path / CATEGORIES_OUTBOX_FILE)
    finally:
        conn.close()

    _, eintraege = _lies(ergebnis.path)
    assert all(e["typ"] != TYP_INCOME for e in eintraege)
    assert all(e["name"] != "Lohn" for e in eintraege)


def test_katalog_traegt_keine_betraege(tmp_path) -> None:
    """Wohin gebucht werden kann - nicht, was dort steht.

    Die Datei liegt im Brueckenordner und ist fuer jedes Modul lesbar.
    """
    conn = _db(tmp_path)
    try:
        CategoryModel(conn).create(TYP_EXPENSES, "Miete")
        CategoryModel(conn).set_bridge_share(TYP_EXPENSES, "Miete", True)
        ergebnis = export_categories(conn, tmp_path / CATEGORIES_OUTBOX_FILE)
    finally:
        conn.close()

    # Geprueft wird die Menge der Felder, nicht der Text: "budget" steckt
    # im Schemanamen selbst und ist dort in Ordnung. Was zaehlt, ist, dass
    # neben Name und Typ nichts steht.
    _, eintraege = _lies(ergebnis.path)
    for eintrag in eintraege:
        assert set(eintrag) == {"schema", "typ", "name"}


def test_zeilenformat_passt_zu_fpm(tmp_path) -> None:
    """Die Feldnamen sind der Vertrag - die Leseseite liegt in einem
    anderen Repository und prueft auf genau diese."""
    conn = _db(tmp_path)
    try:
        CategoryModel(conn).create(TYP_EXPENSES, "Freizeit")
        CategoryModel(conn).set_bridge_share(TYP_EXPENSES, "Freizeit", True)
        ergebnis = export_categories(conn, tmp_path / CATEGORIES_OUTBOX_FILE)
    finally:
        conn.close()

    _, eintraege = _lies(ergebnis.path)
    (eintrag,) = eintraege
    assert set(eintrag) == {"schema", "typ", "name"}
    assert eintrag["schema"] == "budgetmanager.category.v1"


def test_der_dateiname_ist_der_vereinbarte() -> None:
    assert CATEGORIES_OUTBOX_FILE == "budgetmanager_categories.jsonl"


def test_leere_datenbank_erzeugt_einen_leeren_katalog(tmp_path) -> None:
    """Nicht gar keine Datei: Sonst waere nicht zu unterscheiden, ob der
    BudgetManager nie lief oder keine Kategorien hat."""
    conn = _db(tmp_path)
    try:
        for typ in (TYP_EXPENSES, TYP_SAVINGS):
            for kategorie in CategoryModel(conn).list(typ):
                CategoryModel(conn).delete(int(kategorie.id))
        ergebnis = export_categories(conn, tmp_path / CATEGORIES_OUTBOX_FILE)
    finally:
        conn.close()

    assert ergebnis.path.is_file()
    kopf, _ = _lies(ergebnis.path)
    assert kopf["schema"] == "budgetmanager.categories.manifest.v1"
