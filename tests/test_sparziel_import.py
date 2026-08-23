"""Sparzielwuensche aus FPM uebernehmen.

FPM legt seit Loop 53 offene Wuensche im Brueckenordner ab. Bis Loop 54 las
sie niemand - der Nutzer sah dort eine Einstellung, die hier nichts bewirkte.

Review-first wie beim Zahlungsimport: Ein Vorschlag ist kein Sparziel. Erst
eine Bestaetigung legt etwas an.
"""

from __future__ import annotations

import json

import pytest

from model.database import open_db
from model.migrations import migrate_all
from model.savings_goal_import import (
    MANIFEST_SCHEMA,
    MAX_BETRAG,
    SCHEMA,
    WISHES_FILE,
    ablehnen,
    lies_wuensche,
    offene_wuensche,
    uebernehmen,
)
from model.typ_constants import TYP_SAVINGS


def _db(tmp_path):
    pfad = str(tmp_path / "test.db")
    conn = open_db(pfad)
    migrate_all(conn, db_path=pfad, backup_dir=str(tmp_path / "bk"))
    return conn


def _wunsch(**felder) -> dict:
    basis = {
        "schema": SCHEMA,
        "operation": "upsert",
        "external_id": "fpm:wish:1",
        "source": "FPM",
        "name": "Pelikan M800",
        "target_amount": 520.0,
        "currency": "CHF",
        "category": "Wunschliste",
        "item_type": "pen",
        "notes": "Seit Jahren",
    }
    basis.update(felder)
    return basis


def _datei(tmp_path, eintraege: list[dict], *, mit_kopf: bool = True):
    pfad = tmp_path / WISHES_FILE
    zeilen = []
    if mit_kopf:
        zeilen.append(json.dumps({"schema": MANIFEST_SCHEMA, "source": "FPM"}))
    zeilen += [json.dumps(e, ensure_ascii=False) for e in eintraege]
    pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return pfad


# ── Lesen ─────────────────────────────────────────────────────────────────


def test_ein_wunsch_wird_gelesen(tmp_path) -> None:
    (wunsch,) = lies_wuensche(_datei(tmp_path, [_wunsch()]))
    assert wunsch.name == "Pelikan M800"
    assert wunsch.target_amount == pytest.approx(520.0)
    assert wunsch.category == "Wunschliste"


def test_das_manifest_ist_kein_wunsch(tmp_path) -> None:
    assert lies_wuensche(_datei(tmp_path, [])) == []


def test_fremdes_schema_wird_uebergangen(tmp_path) -> None:
    """Im Brueckenordner liegen mehrere Dateien nebeneinander."""
    assert lies_wuensche(_datei(tmp_path, [{"schema": "fpm.import.v1"}])) == []


def test_kaputte_zeile_stoppt_nichts(tmp_path) -> None:
    """Es ist eine Anzeige, kein Import - uebernommen wird erst auf Klick."""
    pfad = tmp_path / WISHES_FILE
    pfad.write_text(
        json.dumps(_wunsch(external_id="a"))
        + "\n{kaputt\n"
        + json.dumps(_wunsch(external_id="b", name="Lamy 2000"))
        + "\n",
        encoding="utf-8",
    )
    assert len(lies_wuensche(pfad)) == 2


@pytest.mark.parametrize(
    "feld,wert",
    [
        ("name", ""),
        ("external_id", ""),
        ("target_amount", 0),
        ("target_amount", -5),
        ("target_amount", MAX_BETRAG * 2),
        ("target_amount", "viel"),
    ],
)
def test_unbrauchbares_wird_uebergangen(tmp_path, feld, wert) -> None:
    """Uebergangen, nicht geraten.

    Ein Ziel ohne Betrag ist keines; ein unsinnig hohes ein Fehler der
    Gegenseite. Beides anzulegen waere schlimmer, als es wegzulassen.
    """
    assert lies_wuensche(_datei(tmp_path, [_wunsch(**{feld: wert})])) == []


# ── Uebernehmen und ablehnen ──────────────────────────────────────────────


def test_uebernehmen_legt_ein_sparziel_an(tmp_path) -> None:
    conn = _db(tmp_path)
    try:
        from model.category_model import CategoryModel
        from model.savings_goals_model import SavingsGoalsModel

        CategoryModel(conn).create(TYP_SAVINGS, "Wunschliste")
        (wunsch,) = lies_wuensche(_datei(tmp_path, [_wunsch()]))
        goal_id = uebernehmen(conn, wunsch)

        ziel = SavingsGoalsModel(conn).get(goal_id)
        assert ziel is not None
        assert ziel.name == "Pelikan M800"
        assert ziel.target_amount == pytest.approx(520.0)
        assert ziel.category == "Wunschliste"
    finally:
        conn.close()


def test_eine_unbekannte_kategorie_wird_nicht_angelegt(tmp_path) -> None:
    """Ein fremdes Programm soll den Kategorienbaum nicht verändern.

    Das Ziel entsteht trotzdem - ohne Kategorie, und der Nutzer ordnet es
    hier zu. Alles andere hiesse, dass FPM hier Kategorien anlegen kann.
    """
    conn = _db(tmp_path)
    try:
        from model.category_model import CategoryModel
        from model.savings_goals_model import SavingsGoalsModel

        vorher = set(CategoryModel(conn).list_names(TYP_SAVINGS))
        (wunsch,) = lies_wuensche(
            _datei(tmp_path, [_wunsch(category="Gibt es hier nicht")])
        )
        goal_id = uebernehmen(conn, wunsch)

        assert set(CategoryModel(conn).list_names(TYP_SAVINGS)) == vorher
        assert SavingsGoalsModel(conn).get(goal_id).category in (None, "")
    finally:
        conn.close()


def test_uebernommenes_taucht_nicht_wieder_auf(tmp_path) -> None:
    """Der Absender weiss nicht, was hier passiert ist - er schickt weiter."""
    conn = _db(tmp_path)
    try:
        pfad = _datei(tmp_path, [_wunsch()])
        (wunsch,) = offene_wuensche(conn, pfad)
        uebernehmen(conn, wunsch)
        assert offene_wuensche(conn, pfad) == []
    finally:
        conn.close()


def test_abgelehntes_taucht_nicht_wieder_auf(tmp_path) -> None:
    conn = _db(tmp_path)
    try:
        pfad = _datei(tmp_path, [_wunsch()])
        (wunsch,) = offene_wuensche(conn, pfad)
        ablehnen(conn, wunsch)
        assert offene_wuensche(conn, pfad) == []
    finally:
        conn.close()


def test_ablehnen_legt_nichts_an(tmp_path) -> None:
    conn = _db(tmp_path)
    try:
        from model.savings_goals_model import SavingsGoalsModel

        vorher = len(SavingsGoalsModel(conn).list_all())
        (wunsch,) = lies_wuensche(_datei(tmp_path, [_wunsch()]))
        ablehnen(conn, wunsch)
        assert len(SavingsGoalsModel(conn).list_all()) == vorher
    finally:
        conn.close()


def test_ohne_datei_gibt_es_nichts_zu_tun(tmp_path) -> None:
    """Wer FPM nicht nutzt, soll keine Meldung sehen."""
    conn = _db(tmp_path)
    try:
        assert offene_wuensche(conn, tmp_path / "gibtsnicht.jsonl") == []
    finally:
        conn.close()


# ── Kontrakt gegen FPM ────────────────────────────────────────────────────


def test_das_schema_stimmt_mit_der_senderseite_ueberein() -> None:
    """Die Namen sind der Vertrag; die Senderseite liegt in einem anderen
    Repository und schreibt genau diese."""
    assert SCHEMA == "budgetmanager.savings_goal_request.v1"
    assert MANIFEST_SCHEMA == "budgetmanager.savings_goal_request.manifest.v1"
    assert WISHES_FILE == "fpm_savings_wishes.jsonl"


def test_der_tabellenname_steht_ueberall_gleich() -> None:
    """Die Abfragen schreiben den Namen aus, die Konstante nennt ihn.

    SQL aus einem f-String zu bauen ist auch dann eine schlechte
    Gewohnheit, wenn der eingesetzte Wert eine Konstante ist - die
    Release-Prüfung ``d1_sql_surface`` beanstandet es zu Recht. Dann muss
    aber jemand dafür sorgen, dass die beiden nicht auseinanderlaufen.
    """
    from pathlib import Path

    from model.savings_goal_import import STATE_TABLE

    quelle = Path(__file__).resolve().parents[1] / "model" / "savings_goal_import.py"
    text = quelle.read_text(encoding="utf-8")

    # Jede SQL-Zeile, die eine Tabelle nennt, muss genau diese nennen.
    for schluessel in ("CREATE TABLE IF NOT EXISTS", "INSERT OR REPLACE INTO", "FROM"):
        for zeile in text.splitlines():
            if schluessel in zeile and "savings_goal" in zeile:
                assert STATE_TABLE in zeile, f"anderer Tabellenname: {zeile.strip()}"
