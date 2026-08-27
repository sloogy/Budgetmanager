"""Reparatur der beiden Befunde aus dem roten PHASE-1-GATE.

**Befund 1** - ``record_operation`` committete seit P1.5 zweimal statt einmal,
und der Bankimport ruft es je Buchung auf. Im verschluesselten Normalmodus
haengt ``EncryptedSession`` an jeden Commit einen Auto-Save der **ganzen**
``.enc``-Datei: 1000 Buchungen ergaben 2004 vollstaendige Schreibvorgaenge und
44 Sekunden gesperrte Oberflaeche. Gemessen mit
``tools/mess_import_blockdauer.py``.

**Befund 2** - ``lifeplanner_import_service.apply_import`` klammert
``tracking.add`` und den Zustands-INSERT mit ``db_transaction``, aber
``tracking.add`` committete ueber sein ``record_operation`` mitten darin. Die
aeussere Klammer war damit vorzeitig geschlossen: Scheiterte danach der
Zustands-INSERT, blieb eine Buchung ohne ``lifeplanner_import_state``-Zeile
stehen - und der Nutzer sah statt der echten Ursache ein
``cannot rollback - no transaction is active``.

Beide Tests messen die Ursache, nicht das Symptom: Der erste zaehlt echte
Auto-Save-Aufrufe an einer echten ``AutosaveConnection``, der zweite laesst den
Zustands-INSERT an einer echten Verbindung scheitern.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from model.bank_import_service import BankImportItem, BankImportService
from model.bank_statement_reader import BankTransaction
from model.category_model import CategoryModel
from model.crypto import AutosaveConnection
from model.migrations import migrate_all
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES
from model.undo_redo_model import UndoRedoModel

KATEGORIE = "Reparaturkategorie"


class _SperrbareVerbindung(sqlite3.Connection):
    """Verbindung, die genau eine Anweisung scheitern laesst.

    Gleiche Bauart wie in ``test_phase1_gate.py``: ``conn.execute`` ist an einer
    echten Verbindung schreibgeschuetzt, deshalb die Unterklasse. Der Fehler
    faellt dort, wo er im Ernstfall faellt - mitten in einer offenen
    Transaktion, hinter bereits geschriebenen Zeilen.
    """

    sperre: str | None = None

    def execute(self, sql, *args, **kwargs):  # type: ignore[override]
        if self.sperre and self.sperre in sql:
            raise sqlite3.OperationalError("Datenbank voll")
        return super().execute(sql, *args, **kwargs)


def _vorbereiten(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_all(conn)
    CategoryModel(conn).create(TYP_EXPENSES, KATEGORIE)
    return conn


@pytest.fixture
def autosave_conn():
    """Echte ``AutosaveConnection`` mit gezaehltem Auto-Save.

    Der Rueckruf ist genau der, den ``EncryptedSession`` registriert und der
    dort die ganze ``.enc``-Datei neu verschluesselt und schreibt. Gezaehlt
    statt geschrieben - die Zahl ist der Kostentreiber, nicht die Kryptografie.
    """
    conn = sqlite3.connect(":memory:", factory=AutosaveConnection)
    _vorbereiten(conn)
    yield conn
    conn.close()


@pytest.fixture
def sperrbare_conn():
    conn = sqlite3.connect(":memory:", factory=_SperrbareVerbindung)
    _vorbereiten(conn)
    yield conn
    conn.close()


def _zaehler_anhaengen(conn: AutosaveConnection) -> list[str]:
    """Haengt den Zaehler an - immer erst, nachdem der Aufbau fertig ist.

    Konstruktoren wie ``UndoRedoModel`` oder ``BankImportService`` legen ihre
    Tabellen an und committen dabei einmal. Das gehoert zum Aufbau, nicht zum
    gemessenen Vorgang.
    """
    speicherungen: list[str] = []
    conn.set_after_commit_callback(speicherungen.append)
    return speicherungen


def _buchungen(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0])


# ── Befund 1: der Auto-Save je Buchung ────────────────────────────


def test_record_operation_committet_genau_einmal(autosave_conn):
    """INSERT und Pruning gehoeren in dieselbe Transaktion.

    Vor der Reparatur committete ``record_operation`` einmal nach dem INSERT
    und ein zweites Mal im ``finally`` nach dem Pruning. Im verschluesselten
    Modus sind das zwei vollstaendige ``.enc``-Schreibvorgaenge fuer einen
    einzigen Undo-Eintrag.
    """
    undo = UndoRedoModel(autosave_conn)
    speicherungen = _zaehler_anhaengen(autosave_conn)

    undo.record_operation("tracking", "INSERT", None, {"id": 1, "amount": 1.0})

    assert len(speicherungen) == 1, (
        "record_operation hat "
        f"{len(speicherungen)} Auto-Saves ausgeloest statt einem"
    )
    assert not autosave_conn.in_transaction, "offene Transaktion nach dem Pruning"


def test_record_operation_committet_nicht_in_einer_fremden_transaktion(
    autosave_conn,
):
    """Wer die Klammer nicht geoeffnet hat, schliesst sie auch nicht.

    Das ist die zweite Haelfte von Befund 2: Ein Commit aus ``record_operation``
    heraus beendete die Transaktion des Aufrufers vorzeitig.
    """
    undo = UndoRedoModel(autosave_conn)
    speicherungen = _zaehler_anhaengen(autosave_conn)

    autosave_conn.execute("BEGIN")
    undo.record_operation("tracking", "INSERT", None, {"id": 1, "amount": 1.0})
    assert autosave_conn.in_transaction, "fremde Transaktion wurde geschlossen"
    assert speicherungen == [], "Auto-Save mitten in einer fremden Transaktion"
    autosave_conn.execute("ROLLBACK")

    verblieben = int(
        autosave_conn.execute(
            "SELECT COUNT(*) FROM undo_stack WHERE table_name='tracking'"
        ).fetchone()[0]
    )
    assert verblieben == 0, "Undo-Eintrag ueberlebte den Rollback des Aufrufers"


def _posten(anzahl: int) -> list[BankImportItem]:
    posten = []
    for index in range(anzahl):
        tx = BankTransaction(
            source_kind="csv",
            source_name="kontoauszug.csv",
            source_index=index,
            booking_date=date(2026, 7, (index % 28) + 1),
            amount=Decimal("-12.50"),
            currency="CHF",
            description=f"Kartenzahlung {index}",
            counterparty="Laden",
        )
        posten.append(
            BankImportItem(
                transaction=tx,
                typ=TYP_EXPENSES,
                category=KATEGORIE,
                tags=(),
                amount=12.5,
                details=tx.description,
            )
        )
    return posten


def test_ein_bankimport_schreibt_die_enc_datei_nicht_je_buchung_neu(autosave_conn):
    """Der Kern von Befund 1, an der Ursache gemessen.

    ``_record_undo_group`` ruft ``record_operation`` je Buchung auf. Ohne
    ``suspend_after_commit_autosave`` wird die ganze verschluesselte Datei je
    Buchung neu geschrieben - vor der Reparatur 2004 Mal fuer 1000 Buchungen,
    44 Sekunden lang bei gesperrter Oberflaeche.

    Die Schranke ist bewusst absolut und nicht relativ: Die Zahl der
    Schreibvorgaenge darf mit der Zahl der Buchungen ueberhaupt nicht wachsen.
    """
    anzahl = 60
    dienst = BankImportService(autosave_conn)
    speicherungen = _zaehler_anhaengen(autosave_conn)

    ergebnis = dienst.import_items(_posten(anzahl), document_digest="c" * 64)

    assert ergebnis.imported == anzahl
    assert len(speicherungen) <= 8, (
        f"{len(speicherungen)} Auto-Saves fuer {anzahl} Buchungen - "
        "die Zahl waechst mit der Importmenge"
    )
    assert not autosave_conn.in_transaction


def test_die_undo_gruppe_des_bankimports_bleibt_trotz_gebuendeltem_speichern(
    autosave_conn,
):
    """Buendeln darf nur das Schreiben sparen, nicht die Buchfuehrung."""
    dienst = BankImportService(autosave_conn)
    ergebnis = dienst.import_items(_posten(5), document_digest="d" * 64)

    assert ergebnis.imported == 5
    gruppen = autosave_conn.execute(
        "SELECT group_id, COUNT(*) AS anzahl FROM undo_stack "
        "WHERE table_name='tracking' GROUP BY group_id"
    ).fetchall()
    assert len(gruppen) == 1, "Bankimport muss genau eine Undo-Gruppe erzeugen"
    assert int(gruppen[0]["anzahl"]) == 5

    undo = UndoRedoModel(autosave_conn)
    assert undo.undo() is True
    assert _buchungen(autosave_conn) == 0


# ── Befund 2: Buchung ohne Zustandszeile ──────────────────────────


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


def test_ein_gescheiterter_zustands_insert_laesst_keine_buchung_zurueck(
    sperrbare_conn, tmp_path
):
    """Befund 2, Datenseite.

    ``apply_import`` klammert Buchung und Zustandszeile gemeinsam. Committete
    ``tracking.add`` mitten darin, war die Klammer beim Zustands-INSERT laengst
    zu: Die Buchung blieb stehen, der LifePlanner hielt den Satz fuer offen und
    bot ihn erneut an - beim naechsten Lauf lag sie doppelt in der Datenbank.
    """
    from model import lifeplanner_import_service as lp
    from utils.money import set_currency

    set_currency("CHF")
    pfad = tmp_path / "fpm_to_budgetmanager.jsonl"
    _lp_datei(pfad)
    satz = lp.load_import_records(sperrbare_conn, pfad)[0]
    entwurf = lp.default_draft(sperrbare_conn, satz)

    sperrbare_conn.sperre = "INSERT INTO lifeplanner_import_state"
    with pytest.raises(sqlite3.OperationalError):
        lp.apply_import(sperrbare_conn, satz, entwurf)
    sperrbare_conn.sperre = None

    assert (
        _buchungen(sperrbare_conn) == 0
    ), "Buchung ohne lifeplanner_import_state-Zeile zurueckgeblieben"
    verblieben = int(
        sperrbare_conn.execute(
            "SELECT COUNT(*) FROM undo_stack WHERE table_name='tracking'"
        ).fetchone()[0]
    )
    assert verblieben == 0, "Undo-Eintrag zu einer Buchung, die es nicht gibt"
    assert not sperrbare_conn.in_transaction


def test_der_gescheiterte_zustands_insert_meldet_seine_eigene_ursache(
    sperrbare_conn, tmp_path
):
    """Befund 2, Meldungsseite.

    Seit P1.5 ersetzte ``db_transaction`` die echte Ausnahme beim gescheiterten
    ``ROLLBACK`` durch ``cannot rollback - no transaction is active``. Der
    Nutzer las damit etwas ueber Transaktionsmechanik statt darueber, was
    schiefging.
    """
    from model import lifeplanner_import_service as lp
    from utils.money import set_currency

    set_currency("CHF")
    pfad = tmp_path / "fpm_to_budgetmanager.jsonl"
    _lp_datei(pfad)
    satz = lp.load_import_records(sperrbare_conn, pfad)[0]
    entwurf = lp.default_draft(sperrbare_conn, satz)

    sperrbare_conn.sperre = "INSERT INTO lifeplanner_import_state"
    with pytest.raises(sqlite3.OperationalError) as fehler:
        lp.apply_import(sperrbare_conn, satz, entwurf)
    sperrbare_conn.sperre = None

    meldung = str(fehler.value)
    assert "Datenbank voll" in meldung, f"echte Ursache verlorengegangen: {meldung}"
    assert "cannot rollback" not in meldung


def test_der_erfolgreiche_lifeplanner_import_bleibt_unveraendert(
    sperrbare_conn, tmp_path
):
    """Gegenprobe zum Erfolgspfad - die Reparatur darf ihn nicht verschieben."""
    from model import lifeplanner_import_service as lp
    from utils.money import set_currency

    set_currency("CHF")
    pfad = tmp_path / "fpm_to_budgetmanager.jsonl"
    _lp_datei(pfad)
    satz = lp.load_import_records(sperrbare_conn, pfad)[0]

    ergebnis = lp.apply_import(
        sperrbare_conn, satz, lp.default_draft(sperrbare_conn, satz)
    )

    assert _buchungen(sperrbare_conn) == 1
    assert not sperrbare_conn.in_transaction
    zustand = sperrbare_conn.execute(
        "SELECT status, tracking_id FROM lifeplanner_import_state WHERE external_id=?",
        ("fpm:expense:1",),
    ).fetchone()
    assert zustand["status"] == "imported"
    assert int(zustand["tracking_id"]) == ergebnis.tracking_id
    assert TrackingModel(sperrbare_conn).count() == 1
