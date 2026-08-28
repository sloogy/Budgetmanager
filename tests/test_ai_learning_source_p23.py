"""P2.3 - Lernquelle und Gewichtung der Import-KI.

Der Fehler, den diese Datei ausschliesst, ist kein Absturz und keine falsche
Zahl auf dem Bildschirm. Er ist eine Rueckkopplung::

    KI raet falsch -> Nutzer korrigiert nicht -> Import
    -> KI behandelt eigenen Rat als starke Wahrheit -> wird immer sicherer falsch

Nachgewiesen wird darum nicht nur, *dass* eine Herkunft gespeichert wird,
sondern dass sie einen Unterschied macht: dass Handarbeit eine Vermutung
ueberschreibt, dass die Gegenrichtung verweigert wird, und dass die KI von
ihrem eigenen Echo nicht sicherer wird.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date
from decimal import Decimal

import pytest

from model.ai_learning_source import (
    SOURCE_AI_CONFIRMED,
    SOURCE_IMPORT_CONFIRMED,
    SOURCE_MANUAL,
    SOURCE_MANUAL_BULK,
    SOURCE_TRACKING_CORRECTION,
    source_from_prediction_method,
    source_weight,
    validate_source,
)
from model.bank_import_ai import BankImportAI, _fingerprint
from model.bank_import_service import BankImportItem
from model.bank_statement_reader import BankTransaction
from model.twint_import_policy import (
    BankImportMarkerStore,
    TwintAwareBankImportService,
    ai_fingerprint,
)
from model.typ_constants import TYP_EXPENSES, TYP_INCOME
from tests.conftest import verbindung_merken

#: Die Rangfolge aus der Aufgabenstellung, hier ausgeschrieben statt aus dem
#: Pruefling geholt. Ein Test, der seine Erwartung beim Geprueften abholt,
#: waechst mit jedem Versehen stillschweigend mit.
RANGFOLGE = (
    "tracking_correction",
    "manual",
    "manual_bulk",
    "ai_confirmed",
    "import_confirmed",
)

DIGEST = "d" * 64


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE categories(id INTEGER PRIMARY KEY, typ TEXT NOT NULL, "
        "name TEXT NOT NULL, UNIQUE(typ,name))"
    )
    conn.execute(
        "CREATE TABLE tags(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, "
        "color TEXT NOT NULL DEFAULT '#3498db')"
    )
    conn.executemany(
        "INSERT INTO categories(typ,name) VALUES(?,?)",
        [
            (TYP_EXPENSES, "Lebensmittel"),
            (TYP_EXPENSES, "Restaurant"),
            (TYP_INCOME, "Rückerstattung"),
        ],
    )
    conn.executemany(
        "INSERT INTO tags(name) VALUES(?)", [("Haushalt",), ("Geteilte Kosten",)]
    )
    conn.commit()
    return verbindung_merken(conn)


def _lerne(ai: BankImportAI, kategorie: str, quelle: str, *, text: str = "MIGROS ZH"):
    return ai.learn(
        typ=TYP_EXPENSES,
        category=kategorie,
        description=text,
        counterparty="MIGROS",
        source=quelle,
    )


def _stand(conn: sqlite3.Connection, text: str = "MIGROS ZH") -> tuple[str, int, str]:
    row = conn.execute(
        "SELECT category, confirmations, source FROM ai_merchant_memory "
        "WHERE fingerprint=? AND typ=?",
        (_fingerprint(text, "MIGROS"), TYP_EXPENSES),
    ).fetchone()
    return str(row[0]), int(row[1]), str(row[2])


# ── Die Rangfolge selbst ────────────────────────────────────────────────────


def test_rangfolge_entspricht_der_aufgabenstellung():
    gewichte = [source_weight(name) for name in RANGFOLGE]
    assert gewichte == sorted(gewichte, reverse=True)
    assert len(set(gewichte)) == len(RANGFOLGE), "keine zwei Quellen gleich schwer"
    # Eine unbekannte Herkunft - alte Zeile, neuere Programmversion - wiegt
    # weniger als jede bekannte und darf darum nichts ueberschreiben.
    assert source_weight("ausgedacht") == 0
    assert source_weight("") == 0


def test_schreibweg_nimmt_keine_erfundene_herkunft_an():
    assert validate_source(SOURCE_MANUAL) == SOURCE_MANUAL
    with pytest.raises(ValueError, match="Unbekannte Lernquelle"):
        validate_source("halbmanuell")
    conn = _conn()
    with pytest.raises(ValueError, match="Unbekannte Lernquelle"):
        _lerne(BankImportAI(conn), "Lebensmittel", "halbmanuell")


def test_prueflistenvermerk_wird_zur_lernquelle():
    assert source_from_prediction_method("manual") == SOURCE_MANUAL
    assert source_from_prediction_method("manual_bulk") == SOURCE_MANUAL_BULK
    # Verallgemeinerungen auf einen noch unbekannten Fingerprint sind eine
    # Aussage - stehen lassen zaehlt als schwache Bestaetigung.
    assert source_from_prediction_method("naive_bayes") == SOURCE_AI_CONFIRMED
    assert source_from_prediction_method("similar_merchant") == SOURCE_AI_CONFIRMED
    # Das Gedaechtnis gibt zurueck, was schon drinsteht. Das ist die
    # Eigenbestaetigung - und genau der Fall aus der Aufgabenstellung.
    assert source_from_prediction_method("merchant_memory") == SOURCE_IMPORT_CONFIRMED
    assert source_from_prediction_method("twint_memory") == SOURCE_IMPORT_CONFIRMED
    assert source_from_prediction_method("twint_match") == SOURCE_IMPORT_CONFIRMED
    # Im Zweifel das schwaechste Gewicht.
    assert source_from_prediction_method("") == SOURCE_IMPORT_CONFIRMED
    assert source_from_prediction_method("untrained") == SOURCE_IMPORT_CONFIRMED
    assert source_from_prediction_method("aus_version_4") == SOURCE_IMPORT_CONFIRMED


# ── Herkunft gespeichert ────────────────────────────────────────────────────


def test_herkunft_steht_am_haendlereintrag_und_am_lernbeispiel():
    conn = _conn()
    _lerne(BankImportAI(conn), "Lebensmittel", SOURCE_MANUAL_BULK)
    assert _stand(conn) == ("Lebensmittel", 1, SOURCE_MANUAL_BULK)
    quellen = [
        str(row[0])
        for row in conn.execute("SELECT source FROM ai_feedback WHERE active=1")
    ]
    assert quellen == [SOURCE_MANUAL_BULK]


def test_herkunft_steht_auch_am_twint_gedaechtnis():
    conn = _conn()
    marker = BankImportMarkerStore(conn)
    tx = _tx(0, description="TWINT von Anna", amount="12.00")
    marker.mark_classifications(
        [(tx, TYP_EXPENSES, "Lebensmittel", SOURCE_MANUAL)], DIGEST
    )
    row = conn.execute(
        "SELECT confirmations, source FROM ai_twint_memory WHERE fingerprint=?",
        (ai_fingerprint(tx),),
    ).fetchone()
    assert (int(row[0]), str(row[1])) == (1, SOURCE_MANUAL)


# ── Starke Signale schlagen schwache ────────────────────────────────────────


def test_handarbeit_ueberschreibt_eine_schwache_annahme():
    conn = _conn()
    ai = BankImportAI(conn)
    _lerne(ai, "Restaurant", SOURCE_IMPORT_CONFIRMED)
    assert _stand(conn) == ("Restaurant", 1, SOURCE_IMPORT_CONFIRMED)

    ergebnis = _lerne(ai, "Lebensmittel", SOURCE_MANUAL)

    assert ergebnis.stored is True
    assert ergebnis.superseded is False
    # Der Zaehler beginnt von vorn: Die alten Bestaetigungen galten einer
    # anderen Kategorie und belegen die neue nicht.
    assert _stand(conn) == ("Lebensmittel", 1, SOURCE_MANUAL)
    assert (
        ai.predict(
            typ=TYP_EXPENSES, description="MIGROS ZH", counterparty="MIGROS"
        ).category
        == "Lebensmittel"
    )


def test_schwaches_signal_schiebt_handarbeit_nicht_beiseite():
    conn = _conn()
    ai = BankImportAI(conn)
    _lerne(ai, "Lebensmittel", SOURCE_MANUAL)

    ergebnis = _lerne(ai, "Restaurant", SOURCE_IMPORT_CONFIRMED)

    assert ergebnis.stored is False
    assert ergebnis.superseded is True
    assert _stand(conn) == ("Lebensmittel", 1, SOURCE_MANUAL)
    # Auch der Umweg ueber die Lernbeispiele bleibt zu: Ein verworfenes
    # Signal darf sich nicht ueber die Wortstatistik doch noch durchsetzen.
    kategorien = {
        str(row[0]) for row in conn.execute("SELECT category FROM ai_feedback")
    }
    assert kategorien == {"Lebensmittel"}


def test_die_korrektur_schlaegt_alles():
    conn = _conn()
    ai = BankImportAI(conn)
    _lerne(ai, "Lebensmittel", SOURCE_MANUAL)
    ergebnis = _lerne(ai, "Restaurant", SOURCE_TRACKING_CORRECTION)
    assert ergebnis.stored is True
    assert _stand(conn) == ("Restaurant", 1, SOURCE_TRACKING_CORRECTION)


def test_gleich_starkes_signal_darf_die_meinung_aendern():
    conn = _conn()
    ai = BankImportAI(conn)
    _lerne(ai, "Lebensmittel", SOURCE_MANUAL)
    ergebnis = _lerne(ai, "Restaurant", SOURCE_MANUAL)
    assert ergebnis.stored is True
    assert _stand(conn) == ("Restaurant", 1, SOURCE_MANUAL)


def test_verworfenes_signal_nennt_keine_buchungstexte(caplog):
    """P2.2-Erbe: Auch der neue Log-Eintrag bleibt frei von Nutzdaten."""
    conn = _conn()
    ai = BankImportAI(conn)
    _lerne(ai, "Lebensmittel", SOURCE_MANUAL, text="MIGROS ZUERICH OERLIKON")
    with caplog.at_level(logging.INFO, logger="model.bank_import_ai"):
        _lerne(
            ai, "Restaurant", SOURCE_IMPORT_CONFIRMED, text="MIGROS ZUERICH OERLIKON"
        )
    text = "\n".join(caplog.messages)
    assert "verworfen" in text
    for verraeterisch in ("MIGROS", "OERLIKON", "Restaurant", "Lebensmittel"):
        assert verraeterisch not in text


# ── Die Eigenbestaetigung verstaerkt sich nicht ─────────────────────────────


def test_eigenbestaetigung_erhoeht_weder_zaehler_noch_zuversicht():
    conn = _conn()
    ai = BankImportAI(conn)
    _lerne(ai, "Restaurant", SOURCE_IMPORT_CONFIRMED)
    erste = ai.predict(
        typ=TYP_EXPENSES, description="MIGROS ZH 123456", counterparty="MIGROS"
    )
    for _ in range(20):
        ergebnis = _lerne(ai, "Restaurant", SOURCE_IMPORT_CONFIRMED)
        assert ergebnis.stored is False
    spaeter = ai.predict(
        typ=TYP_EXPENSES, description="MIGROS ZH 123456", counterparty="MIGROS"
    )

    # Ohne diese Zeile bewiese der Test nichts: Nur der Weg ueber das
    # Haendlergedaechtnis kennt Zaehler und Herkunftsdeckel ueberhaupt.
    assert erste.method == spaeter.method == "merchant_memory"
    assert _stand(conn) == ("Restaurant", 1, SOURCE_IMPORT_CONFIRMED)
    assert spaeter.confidence == erste.confidence
    assert spaeter.confidence <= 0.90
    # Und es entsteht auch kein Wust an Lernbeispielen, der spaeter als
    # Belegmasse durchginge.
    assert conn.execute("SELECT COUNT(*) FROM ai_feedback").fetchone()[0] == 1


def test_gegenprobe_echte_bestaetigungen_machen_die_ki_sicherer():
    conn = _conn()
    ai = BankImportAI(conn)
    _lerne(ai, "Restaurant", SOURCE_MANUAL)
    erste = ai.predict(
        typ=TYP_EXPENSES, description="MIGROS ZH 123456", counterparty="MIGROS"
    )
    for _ in range(20):
        _lerne(ai, "Restaurant", SOURCE_MANUAL)
    spaeter = ai.predict(
        typ=TYP_EXPENSES, description="MIGROS ZH 123456", counterparty="MIGROS"
    )
    assert erste.method == spaeter.method == "merchant_memory"
    assert _stand(conn) == ("Restaurant", 21, SOURCE_MANUAL)
    assert spaeter.confidence > erste.confidence


def test_eine_handarbeit_hebt_den_deckel_dauerhaft():
    """Die Herkunft am Eintrag ist die staerkste, die ihn je getragen hat."""
    conn = _conn()
    ai = BankImportAI(conn)
    _lerne(ai, "Restaurant", SOURCE_MANUAL)
    _lerne(ai, "Restaurant", SOURCE_IMPORT_CONFIRMED)
    kategorie, zaehler, quelle = _stand(conn)
    assert (kategorie, zaehler, quelle) == ("Restaurant", 1, SOURCE_MANUAL)


def test_eigenbestaetigung_verallgemeinert_nicht_auf_fremde_haendler():
    conn = _conn()
    ai = BankImportAI(conn)
    # Ein einmal geratener und nur durchgewinkter Eintrag.
    ai.learn(
        typ=TYP_EXPENSES,
        category="Restaurant",
        description="KIOSK BAHNHOF WINTERTHUR",
        source=SOURCE_IMPORT_CONFIRMED,
    )
    # Der exakte Fingerprint findet ihn weiterhin - dafuer ist er da.
    assert (
        ai.predict(typ=TYP_EXPENSES, description="KIOSK BAHNHOF WINTERTHUR").method
        == "merchant_memory"
    )
    # Auf einen fremden Text darf er nicht ausstrahlen: Er belegt nichts.
    assert ai.feedback_examples(TYP_EXPENSES) == ()
    fremd = ai.predict(typ=TYP_EXPENSES, description="KIOSK BAHNHOF ZUERICH")
    assert fremd.category == ""
    assert fremd.method == "untrained"


def test_gegenprobe_bestaetigte_ki_vorhersage_verallgemeinert_sehr_wohl():
    conn = _conn()
    ai = BankImportAI(conn)
    ai.learn(
        typ=TYP_EXPENSES,
        category="Restaurant",
        description="KIOSK BAHNHOF WINTERTHUR",
        source=SOURCE_AI_CONFIRMED,
    )
    fremd = ai.predict(typ=TYP_EXPENSES, description="KIOSK BAHNHOF ZUERICH")
    assert fremd.category == "Restaurant"


# ── Der Weg durch den echten Import ─────────────────────────────────────────


def _tx(
    index: int, *, description: str, amount: str, counterparty: str = ""
) -> BankTransaction:
    return BankTransaction(
        source_kind="csv",
        source_name="konto.csv",
        source_index=index,
        booking_date=date(2026, 8, 28),
        amount=Decimal(amount),
        currency="CHF",
        description=description,
        counterparty=counterparty,
        raw={},
    )


def _import_db() -> sqlite3.Connection:
    from model.category_model import CategoryModel
    from model.migrations import migrate_all
    from model.tags_model import TagsModel

    conn = verbindung_merken(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_all(conn)
    kategorien = CategoryModel(conn)
    kategorien.create(TYP_EXPENSES, "Lebensmittel")
    kategorien.create(TYP_EXPENSES, "Restaurant")
    TagsModel(conn).create_tag("Haushalt", action_text="")
    conn.commit()
    return conn


def _item(index: int, kategorie: str, quelle: str) -> BankImportItem:
    return BankImportItem(
        transaction=_tx(index, description="MIGROS ZUERICH", amount="-42.50"),
        typ=TYP_EXPENSES,
        category=kategorie,
        tags=(),
        amount=42.50,
        details="MIGROS ZUERICH",
        learn_source=quelle,
    )


def test_durchgewinkter_import_macht_die_ki_nicht_sicherer():
    """Der Ablauf aus der Aufgabenstellung, einmal komplett nachgestellt."""
    conn = _import_db()
    dienst = TwintAwareBankImportService(conn)
    # Runde 1: Die KI hat nichts, der Anwender setzt von Hand.
    dienst.import_items([_item(0, "Restaurant", SOURCE_MANUAL)], document_digest=DIGEST)
    fingerprint = _fingerprint("MIGROS ZUERICH", "")
    stand = conn.execute(
        "SELECT confirmations, source FROM ai_merchant_memory WHERE fingerprint=?",
        (fingerprint,),
    ).fetchone()
    assert (int(stand[0]), str(stand[1])) == (1, SOURCE_MANUAL)

    # Runden 2..6: Die KI schlaegt ihr eigenes Wissen vor, niemand widerspricht.
    for lauf in range(1, 6):
        dienst.import_items(
            [_item(lauf, "Restaurant", SOURCE_IMPORT_CONFIRMED)],
            document_digest=DIGEST,
        )
    stand = conn.execute(
        "SELECT confirmations, source FROM ai_merchant_memory WHERE fingerprint=?",
        (fingerprint,),
    ).fetchone()
    assert (int(stand[0]), str(stand[1])) == (1, SOURCE_MANUAL)
    # Alle fuenf Buchungen sind trotzdem gebucht - die Gewichtung betrifft nur
    # den Lernspeicher, nie das Buchen.
    assert conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 6


def test_import_bucht_auch_wenn_das_lernsignal_verworfen_wird():
    conn = _import_db()
    dienst = TwintAwareBankImportService(conn)
    dienst.import_items([_item(0, "Restaurant", SOURCE_MANUAL)], document_digest=DIGEST)
    ergebnis = dienst.import_items(
        [_item(1, "Lebensmittel", SOURCE_IMPORT_CONFIRMED)], document_digest=DIGEST
    )
    assert ergebnis.imported == 1
    kategorien = [
        str(row[0]) for row in conn.execute("SELECT category FROM tracking ORDER BY id")
    ]
    assert kategorien == ["Restaurant", "Lebensmittel"]
    # Gelernt wurde die schwaechere Aussage nicht.
    stand = conn.execute(
        "SELECT category, source FROM ai_merchant_memory WHERE fingerprint=?",
        (_fingerprint("MIGROS ZUERICH", ""),),
    ).fetchone()
    assert (str(stand[0]), str(stand[1])) == ("Restaurant", SOURCE_MANUAL)


# ── TWINT folgt derselben Rangfolge ─────────────────────────────────────────


def test_twint_gedaechtnis_wiegt_genauso():
    conn = _conn()
    marker = BankImportMarkerStore(conn)
    tx = _tx(0, description="TWINT von Anna", amount="12.00")

    marker.mark_classifications(
        [(tx, TYP_EXPENSES, "Lebensmittel", SOURCE_MANUAL)], DIGEST
    )
    for _ in range(5):
        marker.mark_classifications(
            [(tx, TYP_EXPENSES, "Restaurant", SOURCE_IMPORT_CONFIRMED)], DIGEST
        )
    row = conn.execute(
        "SELECT category, confirmations, source FROM ai_twint_memory WHERE fingerprint=?",
        (ai_fingerprint(tx),),
    ).fetchone()
    assert (str(row[0]), int(row[1]), str(row[2])) == (
        "Lebensmittel",
        1,
        SOURCE_MANUAL,
    )
    # Der Marker gehoert zum Importzustand und wird immer geschrieben.
    assert marker.classification(tx, DIGEST) == (TYP_EXPENSES, "Restaurant")


def test_twint_eigenbestaetigung_zaehlt_nicht_hoch():
    conn = _conn()
    marker = BankImportMarkerStore(conn)
    tx = _tx(0, description="TWINT von Anna", amount="12.00")
    for _ in range(4):
        marker.mark_classifications(
            [(tx, TYP_EXPENSES, "Lebensmittel", SOURCE_IMPORT_CONFIRMED)], DIGEST
        )
    row = conn.execute(
        "SELECT confirmations, source FROM ai_twint_memory WHERE fingerprint=?",
        (ai_fingerprint(tx),),
    ).fetchone()
    assert (int(row[0]), str(row[1])) == (1, SOURCE_IMPORT_CONFIRMED)


# ── Bestehende Aufrufer und bestehende Datenbanken ──────────────────────────


def test_api_bleibt_fuer_bisherige_aufrufer_unveraendert():
    conn = _conn()
    ai = BankImportAI(conn)
    # learn() ohne Herkunft: gilt als Handarbeit, zaehlt also weiterhin hoch.
    for _ in range(3):
        ai.learn(
            typ=TYP_EXPENSES,
            category="Lebensmittel",
            description="MIGROS ZH",
            counterparty="MIGROS",
        )
    assert _stand(conn) == ("Lebensmittel", 3, SOURCE_MANUAL)
    # BankImportItem ohne learn_source: dieselbe Annahme.
    assert (
        BankImportItem(
            transaction=_tx(0, description="MIGROS", amount="-1.00"),
            typ=TYP_EXPENSES,
            category="Lebensmittel",
            tags=(),
            amount=1.0,
            details="",
        ).learn_source
        == SOURCE_MANUAL
    )
    # mark_classifications mit den bisherigen Dreier-Tupeln.
    marker = BankImportMarkerStore(conn)
    tx = _tx(1, description="TWINT von Bea", amount="9.00")
    assert (
        marker.mark_classifications([(tx, TYP_EXPENSES, "Lebensmittel")], DIGEST) == 1
    )
    row = conn.execute(
        "SELECT source FROM ai_twint_memory WHERE fingerprint=?", (ai_fingerprint(tx),)
    ).fetchone()
    assert str(row[0]) == SOURCE_MANUAL


def test_alte_datenbank_bekommt_die_herkunftsspalte_nachgeruestet():
    """Bestand bleibt erhalten und wird als belegbar eingestuft - nicht mehr."""
    conn = _conn()
    conn.executescript(
        """
        CREATE TABLE ai_merchant_memory (
            fingerprint TEXT NOT NULL,
            typ TEXT NOT NULL,
            category TEXT NOT NULL,
            tags_json TEXT NOT NULL DEFAULT '[]',
            confirmations INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (fingerprint, typ)
        );
        CREATE TABLE ai_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint TEXT NOT NULL,
            typ TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            category TEXT NOT NULL,
            tags_json TEXT NOT NULL DEFAULT '[]',
            tokens_json TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
            created_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO ai_merchant_memory("
        "fingerprint,typ,category,tags_json,confirmations,updated_at) "
        "VALUES('migros zh','" + TYP_EXPENSES + "','Lebensmittel','[]',7,'2026-01-01')"
    )
    conn.execute(
        "INSERT INTO ai_feedback("
        "fingerprint,typ,raw_text,category,tags_json,tokens_json,active,created_at) "
        "VALUES('migros zh','"
        + TYP_EXPENSES
        + "','MIGROS ZH','Lebensmittel','[]','[\"migros\",\"zh\"]',1,'2026-01-01')"
    )
    conn.commit()

    BankImportAI(conn)

    stand = conn.execute(
        "SELECT confirmations, source FROM ai_merchant_memory"
    ).fetchone()
    assert (int(stand[0]), str(stand[1])) == (7, SOURCE_AI_CONFIRMED)
    assert (
        str(conn.execute("SELECT source FROM ai_feedback").fetchone()[0])
        == SOURCE_AI_CONFIRMED
    )
    # Ein zweiter Aufbau darf die Einstufung nicht noch einmal ueberschreiben.
    BankImportAI(conn).learn(
        typ=TYP_EXPENSES,
        category="Lebensmittel",
        description="MIGROS ZH",
        source=SOURCE_MANUAL,
    )
    stand = conn.execute(
        "SELECT confirmations, source FROM ai_merchant_memory"
    ).fetchone()
    assert (int(stand[0]), str(stand[1])) == (8, SOURCE_MANUAL)
