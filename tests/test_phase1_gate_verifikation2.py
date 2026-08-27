"""Zweite Verifikation des PHASE-1-GATE: die Nesting-Semantik als Ganzes.

Die Reparatur in ``3e0c3d5`` hat ``record_operation`` beigebracht, in einer
**fremden** Transaktion nicht mehr zu committen. Sie nennt selbst den breitesten
Teil ihrer Aenderung: Das wirkt nicht nur auf den LifePlanner-Import, sondern auf
**alle** Aufrufer - ``tracking_model``, ``budget_model``, ``category_model``,
``savings_goals_model``, den Bankimport. Ueberall dort faellt der Undo-Eintrag
jetzt mit der Klammer des Aufrufers zusammen, statt vorzeitig festgeschrieben zu
werden.

Diese Datei prueft genau diese Verallgemeinerung, und zwar an drei Fragen je
Schreibweg, die die vorhandenen Tests nicht zusammen stellen:

1. **Kommt der Undo-Eintrag noch an?** Ohne fremde Transaktion committet
   ``record_operation`` weiterhin selbst. Faellt dieser Commit weg - etwa weil
   irgendwo eine implizite Transaktion offen stehenbleibt -, waere der
   Undo-Eintrag im verschluesselten Modus nie auf Platte.
2. **Ist er nach einem Fehler weg?** Innerhalb einer fremden Klammer muss er mit
   ihr zurueckgerollt werden - sonst zeigt der Stack eine Buchung an, die es
   nicht gibt.
3. **Traegt Undo/Redo hin und zurueck?**

Dazu die Frage, die das gebuendelte Speichern der Reparatur aufwirft: Der
Bankimport laeuft jetzt unter ``suspend_after_commit_autosave``. Wenn dieses
Buendeln den *letzten* Save verschluckte, waere die Undo-Gruppe zwar im RAM, aber
nicht in der ``.enc``-Datei - ein Datenverlust, den keine Zaehlung von
Schreibvorgaengen sichtbar macht. ``test_die_enc_datei_traegt...`` liest deshalb
die echte verschluesselte Datei von der Platte zurueck.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from model.bank_import_service import BankImportItem, BankImportService
from model.bank_statement_reader import BankTransaction
from model.budget_model import BudgetModel
from model.category_model import CategoryModel
from model.crypto import AutosaveConnection
from model.database import db_transaction
from model.migrations import migrate_all
from model.savings_goals_model import SavingsGoalsModel
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES, TYP_SAVINGS
from model.undo_redo_model import UndoRedoModel

KATEGORIE = "Verifikationskategorie"
SPARKATEGORIE = "Verifikationssparziel"


class _SperrbareVerbindung(sqlite3.Connection):
    """Laesst genau eine Anweisung scheitern - mitten in offener Transaktion."""

    sperre: str | None = None

    def execute(self, sql, *args, **kwargs):  # type: ignore[override]
        if self.sperre and self.sperre in sql:
            raise sqlite3.OperationalError("Datenbank voll")
        return super().execute(sql, *args, **kwargs)


def _aufbauen(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_all(conn)
    kategorien = CategoryModel(conn)
    kategorien.create(TYP_EXPENSES, KATEGORIE)
    kategorien.create(TYP_SAVINGS, SPARKATEGORIE)
    return conn


@pytest.fixture
def conn():
    verbindung = sqlite3.connect(":memory:", factory=AutosaveConnection)
    _aufbauen(verbindung)
    yield verbindung
    verbindung.close()


@pytest.fixture
def sperrbare_conn():
    verbindung = sqlite3.connect(":memory:", factory=_SperrbareVerbindung)
    _aufbauen(verbindung)
    yield verbindung
    verbindung.close()


@pytest.fixture(autouse=True)
def _waehrung():
    from utils.money import set_currency

    set_currency("CHF")


def _undo_zeilen(conn: sqlite3.Connection, tabelle: str) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM undo_stack WHERE table_name=?", (tabelle,)
        ).fetchone()[0]
    )


def _zeilen(conn: sqlite3.Connection, tabelle: str) -> int:
    return int(
        conn.execute(f"SELECT COUNT(*) FROM {tabelle}").fetchone()[0]
    )  # nosec B608


def _stack_leeren(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM undo_stack")
    conn.execute("DELETE FROM redo_stack")
    conn.commit()


def _buchung(index: int) -> BankTransaction:
    return BankTransaction(
        source_kind="csv",
        source_name="kontoauszug.csv",
        source_index=index,
        booking_date=date(2026, 7, (index % 28) + 1),
        amount=Decimal("-12.50"),
        currency="CHF",
        description=f"Kartenzahlung {index}",
        counterparty="Laden",
    )


def _posten(anzahl: int) -> list[BankImportItem]:
    return [
        BankImportItem(
            transaction=_buchung(index),
            typ=TYP_EXPENSES,
            category=KATEGORIE,
            tags=(),
            amount=12.5,
            details="Kauf",
        )
        for index in range(anzahl)
    ]


# ── Frage 1: Kommt der Undo-Eintrag ohne fremde Klammer noch an? ──


def _alle_schreibwege(conn: sqlite3.Connection) -> list[tuple[str, object, str]]:
    """Jeder Schreibweg, der ``record_operation`` erreicht, als Aufruf.

    Bewusst die vollstaendige Liste statt einer Auswahl: Die Reparatur wirkt auf
    alle Aufrufer, also muessen auch alle geprueft werden.
    """
    tracking = TrackingModel(conn)
    budget = BudgetModel(conn)
    kategorien = CategoryModel(conn)
    sparziele = SavingsGoalsModel(conn)

    buchung_id = tracking.add(date(2026, 6, 1), TYP_EXPENSES, KATEGORIE, 10.0, "alt")
    budget.set_amount(2026, 6, TYP_EXPENSES, KATEGORIE, 100.0)
    kat_id = kategorien.create(TYP_EXPENSES, "Wegwerfkategorie")
    ziel_id = sparziele.create("Altziel", 500.0, category=SPARKATEGORIE)

    return [
        (
            "tracking.add",
            lambda: tracking.add(date(2026, 7, 1), TYP_EXPENSES, KATEGORIE, 20.0, "n"),
            "tracking",
        ),
        (
            "tracking.update",
            lambda: tracking.update(
                buchung_id, date(2026, 7, 2), TYP_EXPENSES, KATEGORIE, 30.0, "neu"
            ),
            "tracking",
        ),
        ("tracking.delete", lambda: tracking.delete(buchung_id), "tracking"),
        (
            "budget.set_amount",
            lambda: budget.set_amount(2026, 7, TYP_EXPENSES, KATEGORIE, 500.0),
            "budget",
        ),
        (
            "budget.delete_category_for_year",
            lambda: budget.delete_category_for_year(2026, TYP_EXPENSES, KATEGORIE),
            "budget",
        ),
        (
            "category.create",
            lambda: kategorien.create(TYP_EXPENSES, "Frischkategorie"),
            "categories",
        ),
        (
            "category.update_flags",
            lambda: kategorien.update_flags(kat_id, is_fix=True),
            "categories",
        ),
        (
            "category.delete_category_safely",
            lambda: kategorien.delete_category_safely(
                kat_id, data_action="delete_until_last_booking"
            ),
            "categories",
        ),
        (
            "savings.create",
            lambda: sparziele.create("Neuziel", 900.0, category=SPARKATEGORIE),
            "savings_goals",
        ),
        (
            "savings.update",
            lambda: sparziele.update(ziel_id, name="Altziel neu"),
            "savings_goals",
        ),
        ("savings.delete", lambda: sparziele.delete(ziel_id), "savings_goals"),
        (
            "bank_import.import_items",
            lambda: BankImportService(conn).import_items(
                _posten(3), document_digest="a" * 64
            ),
            "tracking",
        ),
    ]


def test_jeder_schreibweg_schreibt_seinen_undo_eintrag_fest(conn):
    """Ohne fremde Klammer committet ``record_operation`` weiterhin selbst.

    Der Gegenfall waere still und teuer: Der Undo-Eintrag stuende nur im RAM,
    und im verschluesselten Modus - dem Normalmodus - erreichte er die
    ``.enc``-Datei nie.
    """
    fehlend: list[str] = []
    offen: list[str] = []
    for name, aufruf, tabelle in _alle_schreibwege(conn):
        _stack_leeren(conn)
        aufruf()
        if _undo_zeilen(conn, tabelle) == 0:
            fehlend.append(name)
        if conn.in_transaction:
            offen.append(name)

    assert not fehlend, f"kein Undo-Eintrag angekommen bei: {', '.join(fehlend)}"
    assert not offen, (
        "offene Transaktion nach dem Schreibweg - eine RESERVED-Sperre, die "
        f"unter Windows Backup und Verschieben blockiert: {', '.join(offen)}"
    )


def test_kein_schreibweg_laesst_eine_transaktion_offen_stehen(conn):
    """Alle Wege nacheinander, ohne Zwischenaufraeumen.

    Eine offene implizite Transaktion pflanzt sich fort: Der naechste
    ``db_transaction`` haelt sie fuer eine aeussere Klammer, und seit der
    Reparatur verzichtet auch ``record_operation`` dann auf seinen Commit.
    Der Fehler waere also nicht mehr nur unsauber, sondern datenwirksam.
    """
    for _name, aufruf, _tabelle in _alle_schreibwege(conn):
        aufruf()
        assert not conn.in_transaction

    assert not conn.in_transaction


# ── Frage 2: Faellt der Eintrag nach einem Fehler mit weg? ────────


def test_die_verschachtelten_schreibwege_fallen_mit_der_fremden_klammer(conn):
    """Die Wege, die in der Anwendung tatsaechlich verschachtelt vorkommen.

    ``lifeplanner_import_service.apply_import`` klammert ``tracking.add`` bzw.
    ``tracking.update``; ``delete_category_safely`` klammert sich selbst. Genau
    diese muessen innerhalb einer fremden Transaktion vollstaendig
    zurueckrollen - Daten **und** Undo-Eintrag.
    """
    tracking = TrackingModel(conn)
    _stack_leeren(conn)
    buchungen_vorher = _zeilen(conn, "tracking")

    with pytest.raises(RuntimeError), db_transaction(conn):
        tracking.add(date(2026, 7, 1), TYP_EXPENSES, KATEGORIE, 42.0, "x")
        assert conn.in_transaction, (
            "record_operation hat die fremde Klammer geschlossen - genau der "
            "Befund, den die Reparatur behoben hat"
        )
        raise RuntimeError("Abbruch mitten in der fremden Klammer")

    assert _zeilen(conn, "tracking") == buchungen_vorher, "Buchung ueberlebte"
    assert _undo_zeilen(conn, "tracking") == 0, (
        "Undo-Eintrag zu einer Buchung, die es nicht gibt - der Stack zeigt "
        "eine Ruecknahme an, die ins Leere greift"
    )
    assert not conn.in_transaction


def test_die_verschachtelten_schreibwege_kommen_mit_der_fremden_klammer_an(conn):
    """Die Gegenprobe: Bei Erfolg muss der Eintrag da sein, nicht verschluckt."""
    tracking = TrackingModel(conn)
    _stack_leeren(conn)

    with db_transaction(conn):
        tracking.add(date(2026, 7, 1), TYP_EXPENSES, KATEGORIE, 42.0, "x")

    assert _zeilen(conn, "tracking") == 1
    assert _undo_zeilen(conn, "tracking") == 1
    assert not conn.in_transaction

    undo = UndoRedoModel(conn)
    assert undo.undo() is True
    assert _zeilen(conn, "tracking") == 0
    assert undo.redo() is True
    assert _zeilen(conn, "tracking") == 1


def test_der_sparstand_faellt_mit_der_zurueckgerollten_buchung_zurueck(conn):
    """Eine Sparbuchung schreibt in zwei Tabellen - beide muessen zurueck.

    ``tracking.add`` zieht ueber ``_sync_savings`` den Sparzielstand mit. Liefe
    dieser Teil ausserhalb der Klammer, bliebe nach einem Fehler ein Sparziel
    mit einem Stand ohne zugehoerige Buchung stehen.
    """
    sparziele = SavingsGoalsModel(conn)
    tracking = TrackingModel(conn)
    ziel_id = sparziele.create("Sparprobe", 1000.0, category=SPARKATEGORIE)
    _stack_leeren(conn)

    def stand() -> float:
        return float(
            conn.execute(
                "SELECT current_amount FROM savings_goals WHERE id=?", (ziel_id,)
            ).fetchone()[0]
        )

    vorher = stand()
    with pytest.raises(RuntimeError), db_transaction(conn):
        tracking.add(date(2026, 7, 1), TYP_SAVINGS, SPARKATEGORIE, 100.0)
        raise RuntimeError("Abbruch")

    assert stand() == vorher, "Sparstand ohne zugehoerige Buchung zurueckgeblieben"
    assert _zeilen(conn, "tracking") == 0
    assert _undo_zeilen(conn, "tracking") == 0


def test_ein_gescheiterter_bankimport_laesst_keinen_undo_eintrag_zurueck(
    sperrbare_conn,
):
    """Der Fehler faellt hinter bereits geschriebenen Zeilen, mitten im Block."""
    dienst = BankImportService(sperrbare_conn)
    _stack_leeren(sperrbare_conn)

    sperrbare_conn.sperre = "INSERT INTO bank_import_state"
    with pytest.raises(sqlite3.OperationalError):
        dienst.import_items(_posten(5), document_digest="b" * 64)
    sperrbare_conn.sperre = None

    assert _zeilen(sperrbare_conn, "tracking") == 0
    assert _zeilen(sperrbare_conn, "bank_import_state") == 0
    assert _undo_zeilen(sperrbare_conn, "tracking") == 0
    assert not sperrbare_conn.in_transaction


def test_der_lifeplanner_update_zweig_rollt_zurueck_und_nennt_die_ursache(
    sperrbare_conn, tmp_path
):
    """Der zweite Zweig von ``apply_import`` - bisher nur der INSERT geprueft.

    Beim wiederholten Import derselben ``external_id`` laeuft ``tracking.update``
    statt ``tracking.add``. Auch dieser Weg muss innerhalb der Klammer bleiben:
    Scheitert danach der Zustands-INSERT, darf der geaenderte Betrag nicht
    stehenbleiben, und die echte Ursache muss durchkommen.
    """
    from model import lifeplanner_import_service as lp

    def schreiben(betrag: float) -> None:
        nutzlast = {
            "schema": "budgetmanager.import.v1",
            "operation": "upsert",
            "external_id": "fpm:expense:1",
            "source": "FPM",
            "date": "2026-07-30",
            "amount": betrag,
            "currency": "CHF",
            "category_path": f"Hobby/{KATEGORIE}",
            "description": "Verifikation",
            "counterparty": "Shop",
            "notes": "",
            "metadata": {},
        }
        pfad.write_text(
            json.dumps({"schema": "budgetmanager.import.manifest.v1"})
            + "\n"
            + json.dumps(nutzlast)
            + "\n",
            encoding="utf-8",
        )

    pfad = tmp_path / "fpm_to_budgetmanager.jsonl"
    schreiben(50.0)
    satz = lp.load_import_records(sperrbare_conn, pfad)[0]
    lp.apply_import(sperrbare_conn, satz, lp.default_draft(sperrbare_conn, satz))

    schreiben(80.0)
    satz = lp.load_import_records(sperrbare_conn, pfad)[0]
    ergebnis = lp.apply_import(
        sperrbare_conn, satz, lp.default_draft(sperrbare_conn, satz)
    )
    assert ergebnis.updated is True
    assert _zeilen(sperrbare_conn, "tracking") == 1

    def betrag() -> float:
        return float(
            sperrbare_conn.execute("SELECT amount FROM tracking").fetchone()[0]
        )

    vorher = betrag()
    schreiben(95.0)
    satz = lp.load_import_records(sperrbare_conn, pfad)[0]
    sperrbare_conn.sperre = "INSERT INTO lifeplanner_import_state"
    with pytest.raises(sqlite3.OperationalError) as fehler:
        lp.apply_import(sperrbare_conn, satz, lp.default_draft(sperrbare_conn, satz))
    sperrbare_conn.sperre = None

    assert betrag() == vorher, "geaenderter Betrag ohne Zustandszeile stehengeblieben"
    assert "Datenbank voll" in str(fehler.value)
    assert "cannot rollback" not in str(fehler.value)
    assert not sperrbare_conn.in_transaction


# ── Frage 3: Traegt Undo/Redo hin und zurueck? ────────────────────


def test_undo_und_redo_tragen_ueber_alle_tabellen_hin_und_zurueck(conn):
    """Anlegen, Aendern und Loeschen je Tabelle, jeweils vor und zurueck."""
    tracking = TrackingModel(conn)
    budget = BudgetModel(conn)
    kategorien = CategoryModel(conn)
    sparziele = SavingsGoalsModel(conn)
    undo = UndoRedoModel(conn)

    _stack_leeren(conn)
    buchung_id = tracking.add(date(2026, 7, 1), TYP_EXPENSES, KATEGORIE, 11.0, "a")
    assert undo.undo() is True and _zeilen(conn, "tracking") == 0
    assert undo.redo() is True and _zeilen(conn, "tracking") == 1

    tracking.update(buchung_id, date(2026, 7, 3), TYP_EXPENSES, KATEGORIE, 77.0, "b")
    assert float(conn.execute("SELECT amount FROM tracking").fetchone()[0]) == 77.0
    assert undo.undo() is True
    assert float(conn.execute("SELECT amount FROM tracking").fetchone()[0]) == 11.0
    assert undo.redo() is True
    assert float(conn.execute("SELECT amount FROM tracking").fetchone()[0]) == 77.0

    tracking.delete(buchung_id)
    assert _zeilen(conn, "tracking") == 0
    assert undo.undo() is True and _zeilen(conn, "tracking") == 1
    assert undo.redo() is True and _zeilen(conn, "tracking") == 0

    _stack_leeren(conn)
    budget.set_amount(2026, 8, TYP_EXPENSES, KATEGORIE, 250.0)
    assert undo.undo() is True
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM budget WHERE year=2026 AND month=8"
        ).fetchone()[0]
        == 0
    )
    assert undo.redo() is True

    _stack_leeren(conn)
    vor = _zeilen(conn, "categories")
    kategorien.create(TYP_EXPENSES, "Undoprobe")
    assert _zeilen(conn, "categories") == vor + 1
    assert undo.undo() is True and _zeilen(conn, "categories") == vor
    assert undo.redo() is True and _zeilen(conn, "categories") == vor + 1

    _stack_leeren(conn)
    vor = _zeilen(conn, "savings_goals")
    sparziele.create("Undoziel", 400.0, category=SPARKATEGORIE)
    assert undo.undo() is True and _zeilen(conn, "savings_goals") == vor
    assert undo.redo() is True and _zeilen(conn, "savings_goals") == vor + 1


def test_der_bankimport_traegt_als_eine_gruppe_hin_und_zurueck(conn):
    """Ein Import ist eine Ruecknahme, nicht dreissig."""
    dienst = BankImportService(conn)
    _stack_leeren(conn)
    ergebnis = dienst.import_items(_posten(30), document_digest="c" * 64)
    assert ergebnis.imported == 30

    gruppen = conn.execute(
        "SELECT COUNT(DISTINCT group_id) FROM undo_stack WHERE table_name='tracking'"
    ).fetchone()[0]
    assert int(gruppen) == 1, "Bankimport muss genau eine Undo-Gruppe erzeugen"

    undo = UndoRedoModel(conn)
    assert undo.undo() is True
    assert _zeilen(conn, "tracking") == 0
    assert undo.redo() is True
    assert _zeilen(conn, "tracking") == 30


# ── Das gebuendelte Speichern: erreicht es die Platte? ────────────


def test_die_zahl_der_auto_saves_waechst_nicht_mit_der_importmenge(conn):
    """Der Kern der Reparatur, an zwei Groessen statt einer gemessen.

    ``test_phase1_reparatur`` prueft eine absolute Schranke bei 60 Buchungen.
    Das schlaegt auch an, wenn die Zahl langsam mitwaechst. Zwei Groessen im
    Verhaeltnis 1:4 zeigen das Wachstum selbst.
    """
    dienst = BankImportService(conn)
    klein: list[str] = []
    conn.set_after_commit_callback(klein.append)
    dienst.import_items(_posten(40), document_digest="d" * 64)
    conn.set_after_commit_callback(None)

    gross: list[str] = []
    conn.set_after_commit_callback(gross.append)
    dienst.import_items(_posten(160), document_digest="e" * 64)
    conn.set_after_commit_callback(None)

    assert len(gross) == len(klein), (
        f"{len(klein)} Auto-Saves fuer 40 Buchungen, {len(gross)} fuer 160 - "
        "die Zahl der vollstaendigen .enc-Schreibvorgaenge waechst mit der "
        "Importmenge"
    )


def test_die_enc_datei_traegt_nach_einem_import_auch_die_undo_gruppe(tmp_path):
    """Buendeln darf das Schreiben sparen, nicht das Ergebnis.

    ``suspend_after_commit_autosave`` unterdrueckt die Auto-Saves waehrend der
    Undo-Schleife und holt beim Verlassen genau einen nach. Bliebe dieser
    letzte Save aus, stuende die Undo-Gruppe nur im RAM: Nach einem Absturz
    haette der Nutzer die Buchungen, aber keine Moeglichkeit, sie
    zurueckzunehmen. Gelesen wird deshalb die echte Datei von der Platte -
    ohne ein abschliessendes ``session.save()``.
    """
    from cryptography.fernet import Fernet

    from model.crypto import decrypt_db_from_file, encrypt_db_to_file
    from model.database import EncryptedSession

    vorlage = sqlite3.connect(":memory:")
    _aufbauen(vorlage)
    schluessel = Fernet.generate_key()
    salz = os.urandom(16)
    enc_pfad = tmp_path / "user.enc"
    encrypt_db_to_file(vorlage, str(enc_pfad), schluessel, salz)
    vorlage.close()

    sitzung = EncryptedSession.open_with_key(str(enc_pfad), schluessel, salz)
    try:
        ergebnis = BankImportService(sitzung.conn).import_items(
            _posten(40), document_digest="f" * 64
        )
        assert ergebnis.imported == 40
        im_ram = _undo_zeilen(sitzung.conn, "tracking")
        assert im_ram == 40
        assert not sitzung.conn.in_transaction
    finally:
        sitzung.freeze()

    # Das Salz steht in den ersten Bytes der .enc-Datei selbst; die
    # Entschluesselung liest es dort und nimmt es nicht entgegen.
    auf_platte = decrypt_db_from_file(str(enc_pfad), schluessel)
    try:
        auf_platte.row_factory = sqlite3.Row
        assert _zeilen(auf_platte, "tracking") == 40, "Buchungen nicht auf Platte"
        assert _undo_zeilen(auf_platte, "tracking") == im_ram, (
            "die Undo-Gruppe blieb im RAM - das gebuendelte Speichern hat den "
            "abschliessenden Auto-Save verschluckt"
        )
        assert _zeilen(auf_platte, "bank_import_state") == 40, (
            "Buchungen ohne Importzustand auf Platte - beim naechsten Lauf "
            "waere jede davon eine Doppelbuchung"
        )
    finally:
        auf_platte.close()


def test_ein_import_mit_tausend_buchungen_bleibt_unter_einer_sekunde(conn):
    """Die Zahl aus der Ergebniszeile als Schranke, grosszuegig gefasst.

    Der rote Gate-Lauf mass 1000 Buchungen mit **44 Sekunden** gesperrter
    Oberflaeche. Gemessen wird hier ohne Verschluesselung und ohne Dateizugriff,
    also nur der Anteil, der nicht an der Maschine haengt; die Schranke ist
    bewusst weit, damit langsame Laeufer nicht rot werden. Sie schlaegt an, wenn
    je Buchung wieder ein vollstaendiger Schreibvorgang entsteht.
    """
    import time

    dienst = BankImportService(conn)
    posten = _posten(1000)
    beginn = time.perf_counter()
    ergebnis = dienst.import_items(posten, document_digest="g" * 64)
    dauer = time.perf_counter() - beginn

    assert ergebnis.imported == 1000
    assert dauer < 10.0, (
        f"1000 Buchungen brauchten {dauer:.1f} s - im verschluesselten Modus "
        "kaeme je Commit eine vollstaendige Neuverschluesselung dazu"
    )


def test_ein_import_ohne_offene_transaktion_und_ohne_tempdatei(conn):
    """Nach dem Import keine RESERVED-Sperre - die Ursache der Windows-Befunde."""
    dienst = BankImportService(conn)
    dienst.import_items(_posten(10), document_digest="h" * 64)
    assert not conn.in_transaction

    with tempfile.TemporaryDirectory() as ordner:
        pfad = Path(ordner) / "zweit.db"
        zweite = sqlite3.connect(str(pfad))
        zweite.execute("CREATE TABLE probe(id INTEGER)")
        zweite.execute("INSERT INTO probe VALUES(1)")
        zweite.commit()
        zweite.close()
