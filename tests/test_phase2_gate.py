"""PHASE-2-GATE: was die Unterpunkte P2.1-P2.5 offen gelassen haben.

Die fuenf Unterpunkte haben ihre Bausteine jeweils auf einer frisch
migrierten Datenbank belegt. Das Gate fragt zwei Dinge, die dort
naturgemaess nicht vorkamen:

* Was passiert mit einer Datenbank, die **aelter** ist als P2.4 - also ohne
  die beiden Spalten, an denen der Rueckweg fuer Korrekturen haengt?
* Landet auf einem der KI-Wege irgendwo ein Buchungstext im Log?

Die uebrigen Gate-Punkte - verschluesselte DB, Quick/PIN/Passwort,
Backup/Restore - haben eigene, bereits bestehende Suiten; sie werden im
Gate-Lauf gefahren, nicht hier nachgebaut.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date
from decimal import Decimal

import pytest

from model.ai_learning_source import SOURCE_MANUAL
from model.bank_import_ai import BankImportAI
from model.bank_import_service import BankImportItem
from model.bank_statement_reader import BankTransaction
from model.migrations import migrate_all
from model.tracking_correction import (
    REASON_NO_ORIGINAL_TEXT,
    TrackingCorrectionLearner,
)
from model.tracking_model import TrackingModel
from model.twint_import_policy import TwintAwareBankImportService
from model.typ_constants import TYP_EXPENSES
from tests.conftest import verbindung_merken

DIGEST = "f" * 64
BANKTEXT = "COOP PRONTO ZUERICH WIEDIKON"
GEGENPARTEI = "COOP GENOSSENSCHAFT"
ALT = "Restaurant"
NEU = "Lebensmittel"


def _tx(index: int = 0) -> BankTransaction:
    return BankTransaction(
        source_kind="csv",
        source_name="konto.csv",
        source_index=index,
        booking_date=date(2026, 8, 28),
        amount=Decimal("-19.80"),
        currency="CHF",
        description=BANKTEXT,
        counterparty=GEGENPARTEI,
        raw={},
    )


@pytest.fixture
def alte_datenbank() -> tuple[sqlite3.Connection, int]:
    """Eine Datenbank im Zustand *vor* P2.4.

    ``bank_import_state`` hat die beiden Textspalten noch nicht, und in ihr
    steht bereits eine importierte Buchung - genau die Ausgangslage eines
    Anwenders, der die neue Version aufspielt.
    """
    from model.category_model import CategoryModel

    conn = verbindung_merken(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_all(conn)
    kategorien = CategoryModel(conn)
    for name in (ALT, NEU):
        kategorien.create(TYP_EXPENSES, name)

    # Das alte Schema, von Hand nachgebaut - der heutige Code wuerde die
    # Spalten sofort mitanlegen und die Ausgangslage damit verfehlen.
    conn.execute("DROP TABLE IF EXISTS bank_import_state")
    conn.execute(
        """
        CREATE TABLE bank_import_state (
            external_id TEXT PRIMARY KEY,
            tracking_id INTEGER NOT NULL,
            source_digest TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_index INTEGER NOT NULL,
            payload_hash TEXT NOT NULL,
            imported_at TEXT NOT NULL
        )
        """
    )
    row_id = TrackingModel(conn).add(
        date(2026, 8, 28), TYP_EXPENSES, ALT, 19.80, "Alteintrag", source="bank_import"
    )
    conn.execute(
        "INSERT INTO bank_import_state(external_id, tracking_id, source_digest, "
        "source_name, source_index, payload_hash, imported_at) "
        "VALUES('bankimport:alt',?,?,'konto.csv',0,'x','2026-01-05')",
        (int(row_id), DIGEST),
    )
    conn.commit()
    return conn, int(row_id)


def test_alte_datenbank_bekommt_die_belegspalten_und_behaelt_ihre_zeilen(
    alte_datenbank,
):
    """Nachruesten heisst ergaenzen - die Altzeile bleibt, wie sie war."""
    conn, alt_row_id = alte_datenbank
    spalten_vorher = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(bank_import_state)")
    }
    assert "original_description" not in spalten_vorher

    TwintAwareBankImportService(conn)  # oeffnet und migriert das Zustandsschema

    spalten = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(bank_import_state)")
    }
    assert {"original_description", "original_counterparty"} <= spalten
    zeile = conn.execute(
        "SELECT tracking_id, original_description, original_counterparty "
        "FROM bank_import_state WHERE external_id='bankimport:alt'"
    ).fetchone()
    assert int(zeile[0]) == alt_row_id
    assert (str(zeile[1]), str(zeile[2])) == ("", ""), "leer, nicht geraten"


def test_korrektur_an_einer_altzeile_lernt_nichts(alte_datenbank):
    """Ohne Originaltext wird verzichtet - der Anzeigetext ist kein Ersatz."""
    conn, alt_row_id = alte_datenbank
    TwintAwareBankImportService(conn)
    korrektur = TrackingCorrectionLearner(conn)
    vorher = korrektur.snapshot(alt_row_id)
    TrackingModel(conn).update(
        alt_row_id, date(2026, 8, 28), TYP_EXPENSES, NEU, 19.80, "umgebucht"
    )

    ergebnis = korrektur.relearn(alt_row_id, vorher, learn_enabled=True)

    assert (ergebnis.learned, ergebnis.reason) == (False, REASON_NO_ORIGINAL_TEXT)


def test_nach_der_migration_belegt_der_naechste_import_wieder_den_banktext(
    alte_datenbank,
):
    """Die Nachruestung ist kein Schoenheitsfehler, sondern wirksam.

    Ein Import auf derselben - gerade migrierten - Datenbank schreibt den
    Originaltext, und eine Korrektur daran kommt bei der KI an.
    """
    conn, alt_row_id = alte_datenbank
    dienst = TwintAwareBankImportService(conn)
    ergebnis = dienst.import_items(
        [
            BankImportItem(
                transaction=_tx(),
                typ=TYP_EXPENSES,
                category=ALT,
                tags=(),
                amount=19.80,
                details=f"{BANKTEXT} | Bankimport: Original 19.80 CHF",
                learn_source=SOURCE_MANUAL,
            )
        ],
        document_digest=DIGEST,
    )
    neue_id = int(ergebnis.tracking_ids[0])
    zeile = conn.execute(
        "SELECT original_description, original_counterparty FROM bank_import_state "
        "WHERE tracking_id=?",
        (neue_id,),
    ).fetchone()
    assert (str(zeile[0]), str(zeile[1])) == (BANKTEXT, GEGENPARTEI)

    korrektur = TrackingCorrectionLearner(conn)
    vorher = korrektur.snapshot(neue_id)
    TrackingModel(conn).update(
        neue_id, date(2026, 8, 28), TYP_EXPENSES, NEU, 19.80, "umgebucht"
    )
    assert korrektur.relearn(neue_id, vorher, learn_enabled=True).learned is True
    assert (
        BankImportAI(conn)
        .predict(typ=TYP_EXPENSES, description=BANKTEXT, counterparty=GEGENPARTEI)
        .category
        == NEU
    )


def test_kein_buchungstext_im_log_auf_dem_ganzen_ki_weg(alte_datenbank, caplog):
    """Import, Korrektur und Reset - und kein Wort aus dem Kontoauszug im Log.

    Geprueft wird auf jedem Weg, nicht nur an der einen Stelle, die P2.3
    bereits belegt: Ein spaeter hinzugefuegtes ``logger.debug`` mit dem
    Buchungstext waere sonst ein Klartextleck in der Logdatei - dort, wo die
    verschluesselte Datenbank gerade nicht hilft.
    """
    from model.ai_learning_store import reset_learning_data

    conn, alt_row_id = alte_datenbank
    dienst = TwintAwareBankImportService(conn)
    with caplog.at_level(logging.DEBUG):
        ergebnis = dienst.import_items(
            [
                BankImportItem(
                    transaction=_tx(),
                    typ=TYP_EXPENSES,
                    category=ALT,
                    tags=(),
                    amount=19.80,
                    details=BANKTEXT,
                )
            ],
            document_digest=DIGEST,
        )
        neue_id = int(ergebnis.tracking_ids[0])
        korrektur = TrackingCorrectionLearner(conn)
        vorher = korrektur.snapshot(neue_id)
        TrackingModel(conn).update(
            neue_id, date(2026, 8, 28), TYP_EXPENSES, NEU, 19.80, "umgebucht"
        )
        korrektur.relearn(neue_id, vorher, learn_enabled=True)
        reset_learning_data(conn)

    protokoll = "\n".join(eintrag.getMessage() for eintrag in caplog.records)
    for wort in ("COOP", "PRONTO", "WIEDIKON", "GENOSSENSCHAFT"):
        assert wort not in protokoll.upper(), protokoll
