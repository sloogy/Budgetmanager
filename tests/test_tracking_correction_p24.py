"""P2.4 - Nachtraegliche Korrekturen zurueckgeben.

Der Nutzen ist offensichtlich, die Gefahr nicht: Ein Ruecklernweg, der zu
grosszuegig ausloest, macht aus jeder Betragskorrektur ein Lernsignal
hoechsten Gewichts - und aus dem zusammengesetzten Anzeigetext der
Buchungsdetails den Lernstoff der KI. Diese Datei prueft darum beide
Richtungen: dass die echte Korrektur ankommt, und dass alles andere
draussen bleibt.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from model.ai_learning_source import (
    SOURCE_IMPORT_CONFIRMED,
    SOURCE_MANUAL,
    SOURCE_TRACKING_CORRECTION,
)
from model.bank_import_ai import BankImportAI, _fingerprint
from model.bank_import_service import BankImportItem
from model.bank_statement_reader import BankTransaction
from model.migrations import migrate_all
from model.tracking_correction import (
    REASON_AMBIGUOUS_ORIGIN,
    REASON_LEARNING_DISABLED,
    REASON_NO_ENTRY,
    REASON_NO_ORIGINAL_TEXT,
    REASON_NOT_IMPORTED,
    REASON_UNCHANGED,
    TrackingCorrectionLearner,
)
from model.tracking_model import TrackingModel
from model.twint_import_policy import TwintAwareBankImportService
from model.typ_constants import TYP_EXPENSES, TYP_INCOME
from tests.conftest import verbindung_merken

DIGEST = "e" * 64

#: Was die Bank geschrieben hat.
BANKTEXT = "KIOSK BAHNHOF WINTERTHUR"
GEGENPARTEI = "SBB KIOSK AG"


def _tx(index: int = 0) -> BankTransaction:
    return BankTransaction(
        source_kind="csv",
        source_name="konto.csv",
        source_index=index,
        booking_date=date(2026, 8, 28),
        amount=Decimal("-12.50"),
        currency="CHF",
        description=BANKTEXT,
        counterparty=GEGENPARTEI,
        raw={},
    )


@pytest.fixture
def db() -> sqlite3.Connection:
    from model.category_model import CategoryModel
    from model.tags_model import TagsModel

    conn = verbindung_merken(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_all(conn)
    kategorien = CategoryModel(conn)
    for name in ("Restaurant", "Lebensmittel"):
        kategorien.create(TYP_EXPENSES, name)
    kategorien.create(TYP_INCOME, "Rückerstattung")
    tags = TagsModel(conn)
    for name in ("Unterwegs", "Haushalt"):
        tags.create_tag(name, action_text="")
    conn.commit()
    return conn


def _importiere(conn: sqlite3.Connection, kategorie: str = "Restaurant") -> int:
    """Ein echter Import - der einzige Weg, auf dem ein Beleg entsteht."""
    dienst = TwintAwareBankImportService(conn)
    ergebnis = dienst.import_items(
        [
            BankImportItem(
                transaction=_tx(),
                typ=TYP_EXPENSES,
                category=kategorie,
                tags=(),
                amount=12.50,
                # Genau der zusammengesetzte Anzeigetext, den P2.4 nicht
                # lernen darf.
                details="KIOSK | Bankimport: Original 12.50 CHF; Tag-Regel -",
                learn_source=SOURCE_IMPORT_CONFIRMED,
            )
        ],
        document_digest=DIGEST,
    )
    return int(ergebnis.tracking_ids[0])


def _umbuchen(conn: sqlite3.Connection, row_id: int, kategorie: str) -> None:
    TrackingModel(conn).update(
        row_id, date(2026, 8, 28), TYP_EXPENSES, kategorie, -12.50, "unveraendert"
    )


def _merchant(conn: sqlite3.Connection) -> tuple[str, str] | None:
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_merchant_memory'"
    ).fetchone():
        # Ohne Import hat die KI ihre Tabellen nie angelegt - auch das ist eine
        # gueltige Antwort auf "was weiss die KI ueber diesen Haendler".
        return None
    row = conn.execute(
        "SELECT category, source FROM ai_merchant_memory WHERE fingerprint=? AND typ=?",
        (_fingerprint(BANKTEXT, GEGENPARTEI), TYP_EXPENSES),
    ).fetchone()
    return (str(row[0]), str(row[1])) if row else None


# ── Der Hauptfall ───────────────────────────────────────────────────────────


def test_umgebuchte_importbuchung_wird_zurueckgelernt(db):
    row_id = _importiere(db, "Restaurant")
    assert _merchant(db) == ("Restaurant", SOURCE_IMPORT_CONFIRMED)

    korrektur = TrackingCorrectionLearner(db)
    vorher = korrektur.snapshot(row_id)
    _umbuchen(db, row_id, "Lebensmittel")
    ergebnis = korrektur.relearn(row_id, vorher, learn_enabled=True)

    assert ergebnis.learned is True
    assert ergebnis.reason == ""
    assert _merchant(db) == ("Lebensmittel", SOURCE_TRACKING_CORRECTION)
    # Und die KI sagt es beim naechsten Mal auch so vorher.
    vorhersage = BankImportAI(db).predict(
        typ=TYP_EXPENSES, description=BANKTEXT, counterparty=GEGENPARTEI
    )
    assert vorhersage.category == "Lebensmittel"


def test_korrektur_schlaegt_auch_eine_von_hand_gesetzte_kategorie(db):
    """Die staerkste Quelle muss die zweitstaerkste ueberschreiben koennen."""
    row_id = _importiere(db, "Restaurant")
    BankImportAI(db).learn(
        typ=TYP_EXPENSES,
        category="Restaurant",
        description=BANKTEXT,
        counterparty=GEGENPARTEI,
        source=SOURCE_MANUAL,
    )
    assert _merchant(db) == ("Restaurant", SOURCE_MANUAL)

    korrektur = TrackingCorrectionLearner(db)
    vorher = korrektur.snapshot(row_id)
    _umbuchen(db, row_id, "Lebensmittel")
    assert korrektur.relearn(row_id, vorher, learn_enabled=True).learned is True
    assert _merchant(db) == ("Lebensmittel", SOURCE_TRACKING_CORRECTION)


def test_gelernt_wird_der_banktext_nicht_der_anzeigetext(db):
    row_id = _importiere(db, "Restaurant")
    korrektur = TrackingCorrectionLearner(db)
    vorher = korrektur.snapshot(row_id)
    _umbuchen(db, row_id, "Lebensmittel")
    korrektur.relearn(row_id, vorher, learn_enabled=True)

    beispiele = [
        str(row[0])
        for row in db.execute("SELECT raw_text FROM ai_feedback WHERE active=1")
    ]
    assert beispiele == [f"{GEGENPARTEI} {BANKTEXT}"]
    for anzeigewort in ("Bankimport", "Tag-Regel", "Original 12.50"):
        assert all(anzeigewort not in text for text in beispiele)


def test_geaenderte_tags_zaehlen_ebenfalls_als_korrektur(db):
    from model.tags_model import TagsModel

    row_id = _importiere(db, "Restaurant")
    korrektur = TrackingCorrectionLearner(db)
    vorher = korrektur.snapshot(row_id)
    tag_id = db.execute("SELECT id FROM tags WHERE name=?", ("Unterwegs",)).fetchone()[
        0
    ]
    TagsModel(db).set_entry_tags(row_id, [int(tag_id)])
    ergebnis = korrektur.relearn(row_id, vorher, learn_enabled=True)

    assert ergebnis.learned is True
    row = db.execute(
        "SELECT tags_json, source FROM ai_merchant_memory WHERE fingerprint=?",
        (_fingerprint(BANKTEXT, GEGENPARTEI),),
    ).fetchone()
    assert '"Unterwegs"' in str(row[0])
    assert str(row[1]) == SOURCE_TRACKING_CORRECTION


# ── Und alles, was draussen bleiben muss ────────────────────────────────────


def test_abgeschaltetes_lernen_lernt_auch_keine_korrektur(db):
    row_id = _importiere(db, "Restaurant")
    korrektur = TrackingCorrectionLearner(db)
    vorher = korrektur.snapshot(row_id)
    _umbuchen(db, row_id, "Lebensmittel")

    ergebnis = korrektur.relearn(row_id, vorher, learn_enabled=False)

    assert (ergebnis.learned, ergebnis.reason) == (False, REASON_LEARNING_DISABLED)
    assert _merchant(db) == ("Restaurant", SOURCE_IMPORT_CONFIRMED)


def test_reine_betragskorrektur_ist_kein_widerspruch(db):
    """Sonst stiege eine unveraenderte Zuordnung stumm auf das hoechste
    Gewicht - ohne dass jemand sie bestaetigt haette."""
    row_id = _importiere(db, "Restaurant")
    korrektur = TrackingCorrectionLearner(db)
    vorher = korrektur.snapshot(row_id)
    TrackingModel(db).update(
        row_id,
        date(2026, 8, 28),
        TYP_EXPENSES,
        "Restaurant",
        -13.90,
        "Betrag berichtigt",
    )

    ergebnis = korrektur.relearn(row_id, vorher, learn_enabled=True)

    assert (ergebnis.learned, ergebnis.reason) == (False, REASON_UNCHANGED)
    assert _merchant(db) == ("Restaurant", SOURCE_IMPORT_CONFIRMED)


def test_von_hand_erfasste_buchung_wird_nicht_zurueckgelernt(db):
    """Ohne Bankimport gibt es keinen Originaltext - und nichts zu lernen."""
    row_id = TrackingModel(db).add(
        date(2026, 8, 28), TYP_EXPENSES, "Restaurant", -20.0, "Mittagessen"
    )
    korrektur = TrackingCorrectionLearner(db)
    vorher = korrektur.snapshot(int(row_id))
    _umbuchen(db, int(row_id), "Lebensmittel")

    ergebnis = korrektur.relearn(int(row_id), vorher, learn_enabled=True)

    assert (ergebnis.learned, ergebnis.reason) == (False, REASON_NOT_IMPORTED)
    assert _merchant(db) is None


def test_datenbank_ohne_gespeicherten_originaltext_lernt_nichts(db):
    """Bestandsdatenbanken aus der Zeit vor P2.4: verzichten statt raten."""
    row_id = _importiere(db, "Restaurant")
    db.execute(
        "UPDATE bank_import_state SET original_description='', "
        "original_counterparty='' WHERE tracking_id=?",
        (row_id,),
    )
    db.commit()
    korrektur = TrackingCorrectionLearner(db)
    vorher = korrektur.snapshot(row_id)
    _umbuchen(db, row_id, "Lebensmittel")

    ergebnis = korrektur.relearn(row_id, vorher, learn_enabled=True)

    assert (ergebnis.learned, ergebnis.reason) == (False, REASON_NO_ORIGINAL_TEXT)
    assert _merchant(db) == ("Restaurant", SOURCE_IMPORT_CONFIRMED)


def test_mehrdeutige_herkunft_wird_abgelehnt(db):
    row_id = _importiere(db, "Restaurant")
    db.execute(
        "INSERT INTO bank_import_state(external_id, tracking_id, source_digest, "
        "source_name, source_index, payload_hash, original_description, "
        "original_counterparty, imported_at) "
        "VALUES('bankimport:zweitbeleg',?,?,'anderes.csv',9,'x','ANDERER TEXT','',"
        "'2026-08-28')",
        (row_id, DIGEST),
    )
    db.commit()
    korrektur = TrackingCorrectionLearner(db)
    vorher = korrektur.snapshot(row_id)
    _umbuchen(db, row_id, "Lebensmittel")

    ergebnis = korrektur.relearn(row_id, vorher, learn_enabled=True)

    assert (ergebnis.learned, ergebnis.reason) == (False, REASON_AMBIGUOUS_ORIGIN)
    assert _merchant(db) == ("Restaurant", SOURCE_IMPORT_CONFIRMED)


def test_geloeschte_buchung_laesst_den_lernspeicher_in_ruhe(db):
    row_id = _importiere(db, "Restaurant")
    korrektur = TrackingCorrectionLearner(db)
    vorher = korrektur.snapshot(row_id)
    TrackingModel(db).delete(row_id)

    ergebnis = korrektur.relearn(row_id, vorher, learn_enabled=True)

    assert (ergebnis.learned, ergebnis.reason) == (False, REASON_NO_ENTRY)


def test_kategorie_umbenennen_ist_kein_nutzerfeedback(db):
    """Ein internes Massenupdate laeuft nicht ueber diesen Weg - und darf es
    auch nicht, sonst lernte die KI aus jeder Umbenennung."""
    from model.category_model import CategoryModel

    _importiere(db, "Restaurant")
    kategorien = CategoryModel(db)
    cat_id = db.execute(
        "SELECT id FROM categories WHERE typ=? AND name=?", (TYP_EXPENSES, "Restaurant")
    ).fetchone()[0]
    kategorien.rename_and_cascade(
        int(cat_id), typ=TYP_EXPENSES, old_name="Restaurant", new_name="Beiz"
    )

    assert _merchant(db) == ("Restaurant", SOURCE_IMPORT_CONFIRMED)
    quellen = {
        str(row[0]) for row in db.execute("SELECT source FROM ai_merchant_memory")
    }
    assert SOURCE_TRACKING_CORRECTION not in quellen


def test_importherkunft_ist_nachweisbar(db):
    row_id = _importiere(db, "Restaurant")
    herkunft = TrackingCorrectionLearner(db).import_origin(row_id)
    assert herkunft is not None
    assert herkunft.description == BANKTEXT
    assert herkunft.counterparty == GEGENPARTEI
    assert herkunft.external_id.startswith("bankimport:")
    assert TrackingCorrectionLearner(db).import_origin(999999) is None


# ── Die Verdrahtung in der Oberflaeche ──────────────────────────────────────
#
# Die beiden Dialoge brauchen Qt und lassen sich hier nicht bauen; geprueft
# wird darum am Quelltext - aber nicht nur auf Vorkommen. Entscheidend ist die
# *Reihenfolge*: Der Stand davor muss vor dem Schreiben stehen, das
# Zuruecklernen nach dem Setzen der Tags. Beides falschherum waere ein Test,
# der gruen bleibt, waehrend die KI den Tagstand von gestern lernt.

ROOT = Path(__file__).resolve().parents[1]


def _reihenfolge(quelle: str, *marker: str) -> list[int]:
    stellen = [quelle.find(teil) for teil in marker]
    assert all(stelle >= 0 for stelle in stellen), dict(zip(marker, stellen))
    return stellen


def test_schnelleingabe_lernt_in_der_richtigen_reihenfolge():
    quelle = (ROOT / "views/quick_add_dialog.py").read_text(encoding="utf-8")
    stellen = _reihenfolge(
        quelle,
        "korrektur = TrackingCorrectionLearner(self.conn)",
        "vorher = korrektur.snapshot(int(self._edit_row_id))",
        "self.tracking.update(",
        "self.tags_model.set_entry_tags(int(self._edit_row_id), list(tag_ids))",
        "korrektur.relearn(",
    )
    assert stellen == sorted(stellen)
    assert "learn_enabled=self._ai_learning_enabled()" in quelle
    assert "bank_import_ai_learning_enabled" in quelle


def test_tagdialog_der_buchungsliste_lernt_in_der_richtigen_reihenfolge():
    quelle = (ROOT / "views/tabs/tracking_tab.py").read_text(encoding="utf-8")
    stellen = _reihenfolge(
        quelle,
        "korrektur = TrackingCorrectionLearner(self.conn)",
        "vorher = korrektur.snapshot(int(entry_id))",
        "self.tags_model.set_entry_tags(entry_id, new_ids)",
        "korrektur.relearn(",
    )
    assert stellen == sorted(stellen)
    assert "learn_enabled=self._ai_learning_enabled()" in quelle


def test_automatische_wege_ruehren_den_lernspeicher_nicht_an():
    """Die drei bekannten internen Schreibwege duerfen nicht zurueckzulernen."""
    for pfad in (
        "model/lifeplanner_import_service.py",
        "model/category_model.py",
        "model/undo_redo_model.py",
    ):
        quelle = (ROOT / pfad).read_text(encoding="utf-8")
        assert "TrackingCorrectionLearner" not in quelle, pfad
