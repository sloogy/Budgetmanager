"""PHASE-1-GATE: die Nachbarn des Bankimports nach der Transaktionsverschaerfung.

P1.5 hat ``db_transaction`` geaendert: Ein verschachtelter Block laeuft nicht
mehr wirkungslos mit, sondern wird per SAVEPOINT geklammert. Das ist strenger,
nicht laxer - und ``db_transaction`` ist die gemeinsame Klammer von
``tracking_model``, ``category_model``, ``lifeplanner_import_service`` und
``twint_import_policy``. Die Uebergabe an dieses Gate lautete deshalb
ausdruecklich: Undo/Redo und den LifePlanner-Import mitpruefen, und zwar an
echten Fehlerfaellen statt am Erfolgspfad.

Genau das steht hier. Die Bankimport-eigenen Belege bleiben in
``test_bank_import_final_import.py``; diese Datei prueft, was *ausserhalb* des
Bankimports an derselben Klammer haengt.
"""

from __future__ import annotations

import ast
import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from model.category_model import CategoryModel
from model.database import db_transaction
from model.migrations import migrate_all
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES
from model.undo_redo_model import UndoRedoModel

WURZEL = Path(__file__).resolve().parents[1]
KATEGORIE = "Gatekategorie"


class _SperrbareVerbindung(sqlite3.Connection):
    """Verbindung, die genau eine Anweisung scheitern laesst.

    ``conn.execute`` ist an einer echten ``sqlite3.Connection`` schreibgeschuetzt
    und laesst sich nicht monkeypatchen - deshalb die Unterklasse. Der Fehler
    faellt damit dort, wo er im Ernstfall faellt: mitten in einer offenen
    Transaktion, hinter bereits geschriebenen Zeilen.
    """

    sperre: str | None = None

    def execute(self, sql, *args, **kwargs):  # type: ignore[override]
        if self.sperre and self.sperre in sql:
            raise sqlite3.OperationalError("Datenbank voll")
        return super().execute(sql, *args, **kwargs)


@pytest.fixture
def gate_conn():
    conn = sqlite3.connect(":memory:", factory=_SperrbareVerbindung)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_all(conn)
    CategoryModel(conn).create(TYP_EXPENSES, KATEGORIE)
    yield conn
    conn.close()


def _buchungen(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0])


# ── Die Klammer selbst ────────────────────────────────────────────


def test_ein_verschachtelter_block_rollt_seinen_eigenen_teil_zurueck(gate_conn):
    """Der Kern der P1.5-Aenderung: verschachtelt heisst nicht wirkungslos.

    Vor P1.5 lief der innere Block ohne jede Klammer mit - ein Fehler darin
    liess seine Zeilen stehen. Jetzt haelt ein SAVEPOINT sie fest, ohne die
    aeussere Klammer vorzeitig zu schliessen.
    """
    gate_conn.execute("CREATE TABLE probe(x)")
    with db_transaction(gate_conn):
        gate_conn.execute("INSERT INTO probe VALUES(1)")
        with pytest.raises(ValueError), db_transaction(gate_conn):
            gate_conn.execute("INSERT INTO probe VALUES(2)")
            raise ValueError("innerer Block scheitert")
        assert gate_conn.in_transaction, "die aeussere Klammer wurde mitgerissen"
        gate_conn.execute("INSERT INTO probe VALUES(3)")

    werte = [row[0] for row in gate_conn.execute("SELECT x FROM probe ORDER BY x")]
    assert werte == [1, 3]
    assert not gate_conn.in_transaction


def test_ein_erfolgreicher_verschachtelter_block_committet_nicht_vorzeitig(gate_conn):
    """Der SAVEPOINT darf die aeussere Transaktion nicht beenden.

    Sonst haette der Bankimport nach jedem inneren Block eine neue, fremde
    Transaktion - und die Datei waere wieder nur halb geschuetzt.
    """
    gate_conn.execute("CREATE TABLE probe(x)")
    with pytest.raises(RuntimeError), db_transaction(gate_conn):
        with db_transaction(gate_conn):
            gate_conn.execute("INSERT INTO probe VALUES(1)")
        assert gate_conn.in_transaction
        raise RuntimeError("aeusserer Block scheitert")

    assert _spaltenwerte(gate_conn) == []


def _spaltenwerte(conn: sqlite3.Connection) -> list[int]:
    return [int(row[0]) for row in conn.execute("SELECT x FROM probe ORDER BY x")]


def test_kein_commit_steht_lexikalisch_in_einem_db_transaction_block():
    """Ein ``commit()`` im Block zerstoert seit P1.5 den SAVEPOINT.

    Vorher war so ein Aufruf nur unsauber; seit P1.5 laesst er den Block ohne
    seinen SAVEPOINT zurueck, und ``RELEASE``/``ROLLBACK TO`` scheitert mit
    ``no such savepoint`` - wobei die eigentliche Ausnahme verlorengeht. Der
    Baum ist heute frei davon; dieser Test haelt ihn so.
    """
    treffer: list[str] = []
    dateien = (
        sorted(WURZEL.glob("model/*.py"))
        + sorted(WURZEL.glob("views/**/*.py"))
        + sorted(WURZEL.glob("utils/*.py"))
    )
    for pfad in dateien:
        baum = ast.parse(pfad.read_text(encoding="utf-8"), filename=str(pfad))
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.With):
                continue
            if not any(_ist_db_transaction(eintrag) for eintrag in knoten.items):
                continue
            for innen in ast.walk(knoten):
                if (
                    isinstance(innen, ast.Call)
                    and isinstance(innen.func, ast.Attribute)
                    and innen.func.attr in {"commit", "rollback"}
                ):
                    treffer.append(
                        f"{pfad.relative_to(WURZEL)}:{innen.lineno} "
                        f"{innen.func.attr}()"
                    )
    assert (
        treffer == []
    ), "commit()/rollback() innerhalb von db_transaction: " + ", ".join(treffer)


def _ist_db_transaction(eintrag: ast.withitem) -> bool:
    ausdruck = eintrag.context_expr
    if not isinstance(ausdruck, ast.Call):
        return False
    name = getattr(ausdruck.func, "id", None) or getattr(ausdruck.func, "attr", None)
    return name == "db_transaction"


# ── Undo/Redo an echten Fehlerfaellen ─────────────────────────────


def test_ein_fehler_im_tracking_insert_laesst_weder_zeile_noch_undo_eintrag(gate_conn):
    """Haken "keine Regression in Undo/Redo", Fehlerpfad.

    Scheitert das Anlegen mitten in der Transaktion, darf danach weder eine
    Tracking-Zeile noch ein Undo-Eintrag stehen - sonst nimmt ein spaeteres
    Undo etwas zurueck, das es nie gab.
    """
    tracking = TrackingModel(gate_conn)
    vorher = _undo_zeilen(gate_conn)  # die Kategorie der Fixture zaehlt schon mit
    gate_conn.sperre = "INSERT INTO tracking"
    with pytest.raises(sqlite3.OperationalError):
        tracking.add(date(2026, 5, 1), TYP_EXPENSES, KATEGORIE, 10.0, "Fehlerfall")
    gate_conn.sperre = None

    assert _buchungen(gate_conn) == 0
    assert _undo_zeilen(gate_conn) == vorher, "Undo-Eintrag ohne Buchung"
    assert not gate_conn.in_transaction, "offene Transaktion nach dem Fehler"


def _undo_zeilen(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM undo_stack").fetchone()[0])


def test_undo_und_redo_tragen_ueber_anlegen_aendern_loeschen(gate_conn):
    """Haken "keine Regression in Undo/Redo", Erfolgspfad ueber alle drei Wege.

    Alle drei Schreibwege von ``TrackingModel`` gehen durch ``db_transaction``
    und schreiben ihren Undo-Eintrag danach. Geprueft wird die ganze Kette
    rueckwaerts und wieder vorwaerts, nicht nur ein einzelner Schritt.
    """
    tracking = TrackingModel(gate_conn)
    rid = tracking.add(date(2026, 5, 1), TYP_EXPENSES, KATEGORIE, 10.0, "Anlage")
    tracking.update(rid, date(2026, 5, 2), TYP_EXPENSES, KATEGORIE, 25.0, "Aenderung")
    tracking.delete(rid)
    assert _buchungen(gate_conn) == 0

    undo = UndoRedoModel(gate_conn)
    assert undo.undo() is True  # DELETE zurueck
    assert _buchungen(gate_conn) == 1
    assert _betrag(gate_conn) == pytest.approx(25.0)
    assert undo.undo() is True  # UPDATE zurueck
    assert _betrag(gate_conn) == pytest.approx(10.0)
    assert undo.undo() is True  # INSERT zurueck
    assert _buchungen(gate_conn) == 0

    assert undo.redo() is True
    assert _betrag(gate_conn) == pytest.approx(10.0)
    assert undo.redo() is True
    assert _betrag(gate_conn) == pytest.approx(25.0)
    assert undo.redo() is True
    assert _buchungen(gate_conn) == 0
    assert not gate_conn.in_transaction


def _betrag(conn: sqlite3.Connection) -> float:
    return float(conn.execute("SELECT amount FROM tracking").fetchone()[0])


def test_nach_einem_gescheiterten_schreibweg_bleibt_undo_weiter_benutzbar(gate_conn):
    """Ein Fehler darf den Undo-Stack nicht vergiften.

    Genau das war der P1.5-Befund in seiner allgemeinen Form: ein Schreibweg,
    der nach dem ``record_operation`` noch etwas anderes tut, liess eine offene
    Transaktion zurueck. Hier wird geprueft, dass ein Fehler dazwischen den
    naechsten Undo-Schritt nicht beschaedigt.
    """
    tracking = TrackingModel(gate_conn)
    rid = tracking.add(date(2026, 5, 1), TYP_EXPENSES, KATEGORIE, 10.0, "Erste")

    gate_conn.sperre = "INSERT INTO tracking"
    with pytest.raises(sqlite3.OperationalError):
        tracking.add(date(2026, 5, 3), TYP_EXPENSES, KATEGORIE, 99.0, "Scheitert")
    gate_conn.sperre = None

    assert _buchungen(gate_conn) == 1
    undo = UndoRedoModel(gate_conn)
    assert undo.undo() is True
    assert _buchungen(gate_conn) == 0
    assert undo.redo() is True
    assert int(gate_conn.execute("SELECT id FROM tracking").fetchone()[0]) == rid
    assert not gate_conn.in_transaction


# ── LifePlanner-Import an derselben Klammer ───────────────────────


def _lp_datei(pfad: Path, betrag: float = 123.45) -> None:
    nutzlast = {
        "schema": "budgetmanager.import.v1",
        "operation": "upsert",
        "external_id": "fpm:expense:1",
        "source": "FPM",
        "date": "2026-07-30",
        "amount": betrag,
        "currency": "CHF",
        "category_path": f"Hobby/{KATEGORIE}",
        "description": "Asvine V800",
        "counterparty": "Shop",
        "notes": "Test",
        "metadata": {},
    }
    pfad.write_text(
        json.dumps({"schema": "budgetmanager.import.manifest.v1"})
        + "\n"
        + json.dumps(nutzlast)
        + "\n",
        encoding="utf-8",
    )


def test_lifeplanner_import_laesst_keine_offene_transaktion_zurueck(
    gate_conn, tmp_path
):
    """Haken "Windows-spezifische Pfade", Ursache statt Augenschein.

    ``apply_import`` klammert seinen Schreibblock mit ``db_transaction`` und
    ruft darin ``TrackingModel`` auf - also verschachtelt. Bliebe danach eine
    Transaktion offen, hielte SQLite eine RESERVED-Sperre auf der Datei; unter
    Windows blockiert genau das Backup, Restore und jedes Verschieben der .db.
    """
    from model import lifeplanner_import_service as lp
    from utils.money import set_currency

    set_currency("CHF")
    pfad = tmp_path / "fpm_to_budgetmanager.jsonl"
    _lp_datei(pfad)

    satz = lp.load_import_records(gate_conn, pfad)[0]
    lp.apply_import(gate_conn, satz, lp.default_draft(gate_conn, satz))

    assert not gate_conn.in_transaction, "offene Transaktion nach apply_import"
    assert _buchungen(gate_conn) == 1
    zustand = gate_conn.execute(
        "SELECT status FROM lifeplanner_import_state WHERE external_id=?",
        ("fpm:expense:1",),
    ).fetchone()
    assert zustand["status"] == "imported"


def test_lifeplanner_import_bleibt_nach_der_verschaerfung_ruecknehmbar(
    gate_conn, tmp_path
):
    """Haken "keine Regression in Undo/Redo" fuer den zweiten Importweg.

    Der LifePlanner-Import schreibt ueber ``TrackingModel`` und erzeugt damit
    einen Undo-Eintrag. Seit P1.5 laeuft dieser Schreibweg verschachtelt unter
    einem SAVEPOINT - die Ruecknahme muss trotzdem greifen.
    """
    from model import lifeplanner_import_service as lp
    from utils.money import set_currency

    set_currency("CHF")
    pfad = tmp_path / "fpm_to_budgetmanager.jsonl"
    _lp_datei(pfad)

    satz = lp.load_import_records(gate_conn, pfad)[0]
    lp.apply_import(gate_conn, satz, lp.default_draft(gate_conn, satz))
    assert _buchungen(gate_conn) == 1

    undo = UndoRedoModel(gate_conn)
    assert undo.undo() is True
    assert _buchungen(gate_conn) == 0
    assert undo.redo() is True
    assert _buchungen(gate_conn) == 1
    assert not gate_conn.in_transaction


def test_der_zweite_lifeplanner_import_bucht_nicht_doppelt(gate_conn, tmp_path):
    """Haken "keine Regression in Duplikaten" fuer den LifePlanner-Weg."""
    from model import lifeplanner_import_service as lp
    from utils.money import set_currency

    set_currency("CHF")
    pfad = tmp_path / "fpm_to_budgetmanager.jsonl"
    _lp_datei(pfad)

    satz = lp.load_import_records(gate_conn, pfad)[0]
    lp.apply_import(gate_conn, satz, lp.default_draft(gate_conn, satz))
    erneut = lp.load_import_records(gate_conn, pfad)[0]
    assert erneut.status == "imported"
    lp.apply_import(gate_conn, erneut, lp.default_draft(gate_conn, erneut))

    assert _buchungen(gate_conn) == 1
    zeilen = int(
        gate_conn.execute("SELECT COUNT(*) FROM lifeplanner_import_state").fetchone()[0]
    )
    assert zeilen == 1
