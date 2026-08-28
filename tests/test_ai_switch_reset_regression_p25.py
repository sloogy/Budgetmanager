"""P2.5 - Regression ueber die Schalter und den Reset der Import-KI.

P2.1 bis P2.4 haben die vier Bausteine einzeln gebaut: die Schalter, den
verschluesselten Lernspeicher, die Gewichtung der Lernquellen und den
Rueckweg fuer nachtraegliche Korrekturen. Diese Datei prueft sie nicht noch
einmal einzeln, sondern als **eine Kette an einer Datenbank, die wie ein
echter Haushalt aussieht**: zwoelf Monate von Hand gebuchte Zeilen, Budgets,
ein Sparziel, dazu ein Bankimport, ein TWINT-Marker und gelerntes Wissen.

Die drei Fragen, die dabei zaehlen, sind Fragen des Anwenders und keine
technischen:

* Wenn ich die KI ausschalte - schweigt sie dann wirklich, und ist mein
  Gelerntes beim Wiedereinschalten noch da?
* Wenn ich das Lernen ausschalte - lernt sie dann auch nicht aus einer
  Korrektur, die ich Wochen spaeter an einer bereits gebuchten Zeile mache?
* Wenn ich zuruecksetze - verliere ich dann *nur* das Gelernte?

Der Reset ist der gefaehrlichste der drei. Er wird darum nicht ueber
Zeilenzahlen geprueft, sondern ueber einen vollstaendigen Abzug der
Datenbank vorher und nachher: Eine Zeile, die der Reset *aendert* statt
loescht, waere ueber eine Zaehlung unsichtbar.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from model.ai_learning_source import (
    SOURCE_IMPORT_CONFIRMED,
    SOURCE_MANUAL,
    SOURCE_MANUAL_BULK,
    SOURCE_TRACKING_CORRECTION,
)
from model.ai_learning_store import learning_stats, reset_learning_data
from model.bank_import_ai import BankImportAI, _fingerprint
from model.bank_import_analysis import AnalysisRequest, LoadedSource, analyse
from model.bank_import_service import BankImportItem
from model.bank_import_snapshot import capture_analysis_snapshot
from model.bank_statement_reader import BankTransaction
from model.migrations import migrate_all
from model.tracking_correction import (
    REASON_LEARNING_DISABLED,
    TrackingCorrectionLearner,
)
from model.tracking_model import TrackingModel
from model.twint_import_policy import (
    TYP_TWINT_AI,
    BankImportMarkerStore,
    TwintAwareBankImportService,
)
from model.typ_constants import TYP_EXPENSES, TYP_INCOME
from tests.conftest import verbindung_merken

DIGEST = "d" * 64

#: Die vier Tabellen des Lernspeichers - hier bewusst ausgeschrieben und
#: nicht aus ``RESET_TABLES`` uebernommen. Ein Test, der seine Erwartung aus
#: dem Prueflingsmodul holt, waechst stillschweigend mit, wenn dort eines
#: Tages eine Tabelle mehr in der Liste steht.
LERNTABELLEN = frozenset(
    {"ai_merchant_memory", "ai_twint_memory", "ai_feedback", "ai_tag_rules"}
)

#: Was die Bank fuer die importierte Zeile geschrieben hat.
BANKTEXT = "MIGROS M BUDGET ZUERICH HB"
GEGENPARTEI = "MIGROS GENOSSENSCHAFT"

#: Eine zweite, der KI unbekannte Zeile - an ihr laesst sich zeigen, dass ein
#: Vorschlag wirklich aus dem Gedaechtnis kommt und nicht geraten ist.
FREMDTEXT = "BAECKEREI SPRUENGLI PARADEPLATZ"

AUSGABE = "Lebensmittel"
AUSGABE_ZWEI = "Restaurant"
EINNAHME = "Lohn"


def _tx(
    index: int,
    *,
    description: str,
    amount: str,
    counterparty: str = "",
    source_name: str = "konto.csv",
    booking_date: date | None = None,
) -> BankTransaction:
    return BankTransaction(
        source_kind="csv",
        source_name=source_name,
        source_index=index,
        booking_date=booking_date or date(2026, 8, 3),
        amount=Decimal(amount),
        currency="CHF",
        description=description,
        counterparty=counterparty,
        raw={},
    )


@dataclass(frozen=True)
class Haushalt:
    """Die vorbereitete Datenbank samt der Kennzahlen, die daran haengen."""

    conn: sqlite3.Connection
    #: Die importierte und damit korrigierbare Buchung.
    importiert_id: int
    #: Die TWINT-Zeile, die markiert, aber nie gebucht wurde.
    twint_tx: BankTransaction


@pytest.fixture
def haushalt() -> Haushalt:
    """Zwoelf Monate echte Finanzdaten plus ein gelernter Bankimport.

    Alles entsteht ueber die produktiven Schreibwege. Eine per ``INSERT``
    nachgebaute Datenbank wuerde spaeter nur beweisen, dass der Reset die
    Attrappe in Ruhe laesst.
    """
    from model.category_model import CategoryModel
    from model.savings_goals_model import SavingsGoalsModel
    from model.tags_model import TagsModel

    conn = verbindung_merken(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_all(conn)

    kategorien = CategoryModel(conn)
    for name in (AUSGABE, AUSGABE_ZWEI):
        kategorien.create(TYP_EXPENSES, name)
    kategorien.create(TYP_INCOME, EINNAHME)
    tags = TagsModel(conn)
    for name in ("Haushalt", "Unterwegs"):
        tags.create_tag(name, action_text="")

    # Zwoelf Monate Handarbeit: genau der Datenbestand, aus dem der Coach ab
    # Phase 3 rechnet - und der einen Reset unbeschadet ueberstehen muss.
    tracking = TrackingModel(conn)
    for monat in range(1, 13):
        tracking.add(date(2026, monat, 25), TYP_INCOME, EINNAHME, 6200.0, "Monatslohn")
        tracking.add(
            date(2026, monat, 4), TYP_EXPENSES, AUSGABE, 420.0 + monat, "Einkauf"
        )
        tracking.add(
            date(2026, monat, 18), TYP_EXPENSES, AUSGABE_ZWEI, 95.0, "Mittagessen"
        )
        conn.execute(
            "INSERT INTO budget(year, month, typ, category, amount) VALUES(?,?,?,?,?)",
            (2026, monat, TYP_EXPENSES, AUSGABE, 500.0),
        )
    SavingsGoalsModel(conn).create("Notgroschen", 12000.0, current_amount=3400.0)

    # Ein echter Bankimport - er legt tracking, bank_import_state samt
    # Originaltext und das Haendlergedaechtnis in einem Zug an.
    dienst = TwintAwareBankImportService(conn)
    ergebnis = dienst.import_items(
        [
            BankImportItem(
                transaction=_tx(
                    0, description=BANKTEXT, amount="-42.50", counterparty=GEGENPARTEI
                ),
                typ=TYP_EXPENSES,
                category=AUSGABE,
                tags=("Haushalt",),
                amount=42.50,
                details=f"{BANKTEXT} | Bankimport: Original 42.50 CHF",
                learn_source=SOURCE_MANUAL,
            )
        ],
        document_digest=DIGEST,
    )
    importiert_id = int(ergebnis.tracking_ids[0])

    # Ein TWINT-Eingang: markiert und kategorisiert, aber nie gebucht.
    twint_tx = _tx(1, description="TWINT Gutschrift von Anna", amount="18.00")
    BankImportMarkerStore(conn).mark_classifications(
        [(twint_tx, TYP_EXPENSES, AUSGABE_ZWEI, SOURCE_MANUAL)], DIGEST
    )

    # Eine Kostenanteil-Regel: Lernmetadaten, die der Reset mitnimmt.
    BankImportAI(conn).set_tag_allocation_rule("Haushalt", 50, priority=5)
    conn.commit()
    return Haushalt(conn=conn, importiert_id=importiert_id, twint_tx=twint_tx)


# ── Werkzeuge: Abzuege statt Zaehlungen ─────────────────────────────────────


def _tabellen(conn: sqlite3.Connection) -> list[str]:
    return sorted(
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if not str(row[0]).startswith("sqlite_")
    )


def _abzug(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Vollstaendiger Inhalt aller Tabellen, zeilenweise vergleichbar."""
    return {
        tabelle: sorted(
            json.dumps(list(zeile), default=str)
            for zeile in conn.execute("SELECT * FROM " + tabelle).fetchall()
        )
        for tabelle in _tabellen(conn)
    }


def _lernabzug(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Nur der Lernspeicher - fuer die Frage, ob wirklich nichts dazukam."""
    return {name: abzug for name, abzug in _abzug(conn).items() if name in LERNTABELLEN}


def _coach_zahlen(conn: sqlite3.Connection) -> dict[str, object]:
    """Die Groessen, aus denen der Finanz-Coach ab Phase 3 rechnet.

    Bewusst als Auswertung und nicht als Tabellenabzug: Der Reset koennte
    theoretisch eine Zeile unveraendert lassen und trotzdem etwas
    verschieben, das erst in der Summe sichtbar wird.
    """
    ausgaben = conn.execute(
        "SELECT strftime('%Y-%m', date) AS monat, category, ROUND(SUM(amount), 2) "
        "FROM tracking WHERE typ=? GROUP BY monat, category ORDER BY monat, category",
        (TYP_EXPENSES,),
    ).fetchall()
    einnahmen = conn.execute(
        "SELECT strftime('%Y-%m', date) AS monat, ROUND(SUM(amount), 2) "
        "FROM tracking WHERE typ=? GROUP BY monat ORDER BY monat",
        (TYP_INCOME,),
    ).fetchall()
    return {
        "ausgaben_je_monat": [tuple(row) for row in ausgaben],
        "einnahmen_je_monat": [tuple(row) for row in einnahmen],
        "budgets": [
            tuple(row)
            for row in conn.execute(
                "SELECT year, month, typ, category, amount FROM budget "
                "ORDER BY year, month, category"
            )
        ],
        "sparziele": [
            tuple(row)
            for row in conn.execute(
                "SELECT name, target_amount, current_amount FROM savings_goals "
                "ORDER BY name"
            )
        ],
        "zeilen": conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0],
        "tagbindungen": conn.execute("SELECT COUNT(*) FROM entry_tags").fetchone()[0],
    }


def _pruefliste(conn: sqlite3.Connection, zeilen, *, ai_enabled: bool):
    """Die echte Analyse - dieselbe Rechnung, die der Worker ausfuehrt."""
    quelle = LoadedSource("konto.csv", DIGEST, "Bank-CSV/PDF", list(zeilen), set())
    request = AnalysisRequest(
        snapshot=capture_analysis_snapshot(conn),
        sources=(quelle,),
        ai_enabled=ai_enabled,
    )
    return analyse(request).states


def _neue_zeilen() -> list[BankTransaction]:
    """Zwei noch nicht gebuchte Zeilen: bekannter Haendler, fremder Haendler."""
    return [
        _tx(5, description=BANKTEXT, amount="-31.20", counterparty=GEGENPARTEI),
        _tx(6, description=FREMDTEXT, amount="-8.40"),
    ]


# ── 1/2: Der KI-Schalter ────────────────────────────────────────────────────


def test_ki_aus_sagt_nichts_voraus_und_ki_ein_wieder_genau_dasselbe(haushalt):
    """Aus heisst still, Ein heisst: derselbe Vorschlag wie vorher.

    Beide Richtungen in einem Test, weil genau der Vergleich die Aussage
    traegt - "keine Kategorie" allein bewiese nur, dass die KI nichts weiss.
    """
    conn = haushalt.conn
    zeilen = _neue_zeilen()

    vorher = _pruefliste(conn, zeilen, ai_enabled=True)
    assert vorher[0].category == AUSGABE
    assert vorher[0].prediction_method == "merchant_memory"
    assert vorher[0].confidence > 0.0

    aus = _pruefliste(conn, zeilen, ai_enabled=False)
    assert aus[0].category == ""
    assert aus[0].category_typ == ""
    assert aus[0].prediction_method == ""
    assert aus[0].confidence == 0.0
    # Die Zeile verschwindet nicht - sie ist nur ein offener Fall.
    assert aus[0].use is True
    assert aus[0].typ == TYP_EXPENSES

    nachher = _pruefliste(conn, zeilen, ai_enabled=True)
    assert nachher[0] == vorher[0], "Wiedereinschalten muss den alten Stand liefern"


def test_der_bekannte_haendler_wiegt_schwerer_als_der_fremde(haushalt):
    """Gegenprobe: Der Vorschlag oben kommt aus dem Gedaechtnis, nicht vom Typ.

    Der fremde Buchungstext bekommt sehr wohl eine Vermutung - die KI
    verallgemeinert ueber die Wortstatistik, und dafuer ist sie da. Sie sagt
    es aber anders: eine schwaechere Methode und eine sichtbar geringere
    Zuversicht. Ohne diesen Unterschied haette der Test oben auch dann gruen
    bleiben koennen, wenn die KI jeder Ausgabe dieselbe Kategorie anhaengt.
    """
    zustaende = _pruefliste(haushalt.conn, _neue_zeilen(), ai_enabled=True)

    assert zustaende[0].prediction_method == "merchant_memory"
    assert zustaende[1].prediction_method != "merchant_memory"
    assert zustaende[1].confidence < zustaende[0].confidence

    # Und mit abgeschalteter KI schweigt auch die Vermutung.
    aus = _pruefliste(haushalt.conn, _neue_zeilen(), ai_enabled=False)
    assert [zustand.category for zustand in aus.values()] == ["", ""]


# ── 3: Lernen AUS - auf allen drei Wegen ────────────────────────────────────


def test_lernen_aus_schreibt_beim_import_nichts_neues(haushalt):
    conn = haushalt.conn
    vorher = _lernabzug(conn)

    ergebnis = TwintAwareBankImportService(conn).import_items(
        [
            BankImportItem(
                transaction=_tx(7, description=FREMDTEXT, amount="-8.40"),
                typ=TYP_EXPENSES,
                category=AUSGABE_ZWEI,
                tags=(),
                amount=8.40,
                details=FREMDTEXT,
            )
        ],
        document_digest=DIGEST,
        learn=False,
    )

    assert ergebnis.imported == 1, "Gebucht wird trotzdem"
    assert _lernabzug(conn) == vorher, "Der Lernspeicher darf sich nicht bewegen"


def test_lernen_aus_haelt_die_twint_zeile_fest_ohne_zu_verallgemeinern(haushalt):
    conn = haushalt.conn
    vorher = _lernabzug(conn)
    tx = _tx(8, description="TWINT Gutschrift von Beat", amount="9.00")

    BankImportMarkerStore(conn).mark_classifications(
        [(tx, TYP_EXPENSES, AUSGABE)], DIGEST, learn=False
    )

    assert BankImportMarkerStore(conn).is_marked(
        tx, DIGEST
    ), "Der Marker gehoert zum Importzustand, nicht zum Lernen"
    assert _lernabzug(conn) == vorher


def test_lernen_aus_lernt_auch_keine_nachtraegliche_korrektur(haushalt):
    """Die Ergaenzung aus P2.4: Der Schalter gilt auch Wochen nach dem Import.

    Ohne diesen Nachweis waere "Lernen AUS" eine halbe Zusage - der Import
    schwiege, der Rueckweg aus der Buchungsliste schriebe weiter.
    """
    conn = haushalt.conn
    vorher = _lernabzug(conn)
    korrektur = TrackingCorrectionLearner(conn)
    stand = korrektur.snapshot(haushalt.importiert_id)
    TrackingModel(conn).update(
        haushalt.importiert_id,
        date(2026, 8, 3),
        TYP_EXPENSES,
        AUSGABE_ZWEI,
        42.50,
        "umgebucht",
    )

    ergebnis = korrektur.relearn(haushalt.importiert_id, stand, learn_enabled=False)

    assert (ergebnis.learned, ergebnis.reason) == (False, REASON_LEARNING_DISABLED)
    assert _lernabzug(conn) == vorher
    # Die Buchung selbst ist trotzdem umgebucht - der Schalter betrifft das
    # Lernen, nicht die Buchhaltung.
    assert (
        conn.execute(
            "SELECT category FROM tracking WHERE id=?", (haushalt.importiert_id,)
        ).fetchone()[0]
        == AUSGABE_ZWEI
    )


def test_gegenprobe_mit_eingeschaltetem_lernen_kommt_die_korrektur_an(haushalt):
    """Sonst bewiese der Test darueber nur, dass dieser Weg nie etwas tut."""
    conn = haushalt.conn
    korrektur = TrackingCorrectionLearner(conn)
    stand = korrektur.snapshot(haushalt.importiert_id)
    TrackingModel(conn).update(
        haushalt.importiert_id,
        date(2026, 8, 3),
        TYP_EXPENSES,
        AUSGABE_ZWEI,
        42.50,
        "umgebucht",
    )

    assert (
        korrektur.relearn(haushalt.importiert_id, stand, learn_enabled=True).learned
        is True
    )

    eintrag = conn.execute(
        "SELECT category, source FROM ai_merchant_memory WHERE fingerprint=? AND typ=?",
        (_fingerprint(BANKTEXT, GEGENPARTEI), TYP_EXPENSES),
    ).fetchone()
    assert (str(eintrag[0]), str(eintrag[1])) == (
        AUSGABE_ZWEI,
        SOURCE_TRACKING_CORRECTION,
    )


# ── 4/5: Ausschalten ist kein Vergessen ─────────────────────────────────────


def test_ein_ganzer_durchlauf_mit_abgeschalteter_ki_laesst_das_wissen_stehen(haushalt):
    """Analysieren, buchen, markieren - und danach ist der Bestand derselbe."""
    conn = haushalt.conn
    vorher = _lernabzug(conn)
    bestand = learning_stats(conn)
    assert not bestand.is_empty

    _pruefliste(conn, _neue_zeilen(), ai_enabled=False)
    TwintAwareBankImportService(conn).import_items(
        [
            BankImportItem(
                transaction=_tx(9, description=FREMDTEXT, amount="-8.40"),
                typ=TYP_EXPENSES,
                category=AUSGABE_ZWEI,
                tags=(),
                amount=8.40,
                details=FREMDTEXT,
            )
        ],
        document_digest=DIGEST,
        learn=False,
    )

    assert _lernabzug(conn) == vorher
    assert learning_stats(conn) == bestand


def test_reaktivieren_greift_auf_das_alte_wissen_zurueck(haushalt):
    """Nach dem Wiedereinschalten sagt die KI voraus, ohne neu zu lernen."""
    conn = haushalt.conn
    _pruefliste(conn, _neue_zeilen(), ai_enabled=False)

    vorhersage = BankImportAI(conn).predict(
        typ=TYP_EXPENSES, description=BANKTEXT, counterparty=GEGENPARTEI
    )

    assert vorhersage.category == AUSGABE
    assert vorhersage.method == "merchant_memory"
    zustaende = _pruefliste(conn, _neue_zeilen(), ai_enabled=True)
    assert zustaende[0].category == AUSGABE


# ── 6: Der Reset macht die KI ahnungslos ────────────────────────────────────


def test_reset_hinterlaesst_eine_untrainierte_ki(haushalt):
    conn = haushalt.conn
    assert not learning_stats(conn).is_empty

    geloescht = reset_learning_data(conn)

    assert geloescht.learned_patterns == 2, "Haendler- und TWINT-Muster"
    assert learning_stats(conn).is_empty
    vorhersage = BankImportAI(conn).predict(
        typ=TYP_EXPENSES, description=BANKTEXT, counterparty=GEGENPARTEI
    )
    assert (vorhersage.category, vorhersage.confidence) == ("", 0.0)
    assert vorhersage.method == "untrained"
    # Und in der Pruefliste bleibt die Zeile offen, obwohl die KI an ist.
    zustaende = _pruefliste(conn, _neue_zeilen(), ai_enabled=True)
    assert zustaende[0].category == ""
    assert zustaende[0].prediction_method == "untrained"


# ── 7/8: Was der Reset nicht anfassen darf ──────────────────────────────────


def test_reset_laesst_jede_zeile_ausserhalb_des_lernspeichers_stehen(haushalt):
    conn = haushalt.conn
    vorher = _abzug(conn)

    reset_learning_data(conn)

    nachher = _abzug(conn)
    assert set(vorher) == set(nachher), "Der Reset legt keine Tabellen an oder weg"
    veraendert = {name for name in vorher if vorher[name] != nachher[name]}
    assert veraendert == set(LERNTABELLEN), (
        "Ausserhalb des Lernspeichers veraendert: "
        f"{sorted(veraendert - LERNTABELLEN)}"
    )


def test_reset_laesst_die_coach_grundlage_unveraendert(haushalt):
    """Zwoelf Monate Auswertung ergeben davor und danach dieselben Zahlen."""
    conn = haushalt.conn
    vorher = _coach_zahlen(conn)
    assert vorher["zeilen"] == 37, "36 manuelle Zeilen plus die importierte"
    assert len(vorher["ausgaben_je_monat"]) == 24, "zwoelf Monate mal zwei Kategorien"
    assert len(vorher["einnahmen_je_monat"]) == 12

    reset_learning_data(conn)

    assert _coach_zahlen(conn) == vorher


def test_reset_laesst_den_originaltext_des_imports_unberuehrt(haushalt):
    """Die Ergaenzung aus P2.4: ``bank_import_state`` ist Beleg, nicht Wissen.

    Sie ist zugleich die Duplikaterkennung; wer sie mitloescht, bereitet
    Doppelbuchungen vor. Der Banktext ueberlebt den Reset deshalb - die KI
    bleibt trotzdem ahnungslos, weil sie aus dieser Tabelle nichts vorhersagt.
    """
    conn = haushalt.conn
    spalte = "SELECT original_description, original_counterparty, external_id "
    vorher = conn.execute(
        spalte + "FROM bank_import_state WHERE tracking_id=?",
        (haushalt.importiert_id,),
    ).fetchone()
    assert (str(vorher[0]), str(vorher[1])) == (BANKTEXT, GEGENPARTEI)

    reset_learning_data(conn)

    nachher = conn.execute(
        spalte + "FROM bank_import_state WHERE tracking_id=?",
        (haushalt.importiert_id,),
    ).fetchone()
    assert tuple(nachher) == tuple(vorher)
    # Die Duplikaterkennung arbeitet weiter.
    assert TwintAwareBankImportService(conn).is_duplicate(
        _tx(0, description=BANKTEXT, amount="-42.50", counterparty=GEGENPARTEI),
        DIGEST,
    )


def test_nach_dem_reset_macht_die_naechste_korrektur_wieder_wissen(haushalt):
    """Der erhaltene Originaltext ist kein totes Gewicht.

    Er ist der Grund, warum die KI nach einem Reset nicht bei null anfangen
    muss, sobald der Anwender das naechste Mal etwas richtigstellt.
    """
    conn = haushalt.conn
    reset_learning_data(conn)
    assert learning_stats(conn).is_empty

    korrektur = TrackingCorrectionLearner(conn)
    stand = korrektur.snapshot(haushalt.importiert_id)
    TrackingModel(conn).update(
        haushalt.importiert_id,
        date(2026, 8, 3),
        TYP_EXPENSES,
        AUSGABE_ZWEI,
        42.50,
        "umgebucht",
    )

    assert (
        korrektur.relearn(haushalt.importiert_id, stand, learn_enabled=True).learned
        is True
    )
    assert (
        BankImportAI(conn)
        .predict(typ=TYP_EXPENSES, description=BANKTEXT, counterparty=GEGENPARTEI)
        .category
        == AUSGABE_ZWEI
    )


# ── 9: TWINT haengt nicht an der KI ─────────────────────────────────────────


def test_twint_regel_gilt_ohne_ki_und_nach_dem_reset(haushalt):
    """Ein positiver TWINT-Eingang wird nie zum Einkommen - egal wie die
    Schalter stehen. Die Regel ist Buchhaltung, keine Vorhersage."""
    conn = haushalt.conn
    reset_learning_data(conn)
    dienst = TwintAwareBankImportService(conn)

    with pytest.raises(ValueError, match="TWINT"):
        dienst.import_items(
            [
                BankImportItem(
                    transaction=haushalt.twint_tx,
                    typ=TYP_INCOME,
                    category=EINNAHME,
                    tags=(),
                    amount=18.00,
                    details="TWINT",
                )
            ],
            document_digest=DIGEST,
        )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM tracking WHERE typ=? AND amount=18.0", (TYP_INCOME,)
        ).fetchone()[0]
        == 0
    )


def test_der_twint_marker_ueberlebt_reset_und_abgeschaltete_ki(haushalt):
    """Der Marker haelt fest, was fuer *diese* Zeile entschieden wurde.

    Anders als das TWINT-Gedaechtnis verallgemeinert er nicht - er darf
    deshalb weder vom Reset geleert noch vom KI-Schalter verschwiegen werden,
    sonst boete der naechste Import dieselbe Zeile erneut an.
    """
    conn = haushalt.conn
    speicher = BankImportMarkerStore(conn)
    assert speicher.classification(haushalt.twint_tx, DIGEST) == (
        TYP_EXPENSES,
        AUSGABE_ZWEI,
    )

    reset_learning_data(conn)

    assert speicher.is_marked(haushalt.twint_tx, DIGEST)
    assert speicher.classification(haushalt.twint_tx, DIGEST) == (
        TYP_EXPENSES,
        AUSGABE_ZWEI,
    )
    zustaende = _pruefliste(conn, [haushalt.twint_tx], ai_enabled=False)
    assert zustaende[0].typ == TYP_TWINT_AI
    assert zustaende[0].category == AUSGABE_ZWEI
    assert zustaende[0].use is False, "Bereits markiert - nicht erneut anbieten"


# ── 10: Der Import von Hand braucht die KI nicht ────────────────────────────


def test_import_von_hand_funktioniert_ohne_ki_und_ohne_wissen(haushalt):
    """Reset, KI aus - und der Anwender bucht seinen Auszug trotzdem fertig."""
    conn = haushalt.conn
    reset_learning_data(conn)
    zeilen = _neue_zeilen()

    zustaende = _pruefliste(conn, zeilen, ai_enabled=False)
    assert [zustand.category for zustand in zustaende.values()] == ["", ""]

    # Der Anwender setzt die Kategorien selbst; genau das wird gebucht.
    vorher = conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0]
    ergebnis = TwintAwareBankImportService(conn).import_items(
        [
            BankImportItem(
                transaction=zeilen[0],
                typ=TYP_EXPENSES,
                category=AUSGABE,
                tags=("Haushalt",),
                amount=31.20,
                details=BANKTEXT,
            ),
            BankImportItem(
                transaction=zeilen[1],
                typ=TYP_EXPENSES,
                category=AUSGABE_ZWEI,
                tags=(),
                amount=8.40,
                details=FREMDTEXT,
            ),
        ],
        document_digest=DIGEST,
        learn=False,
    )

    assert (ergebnis.imported, ergebnis.skipped_duplicates) == (2, 0)
    assert conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == vorher + 2
    gebucht = conn.execute(
        "SELECT typ, category, amount FROM tracking WHERE id=?",
        (int(ergebnis.tracking_ids[0]),),
    ).fetchone()
    assert (str(gebucht[0]), str(gebucht[1]), float(gebucht[2])) == (
        TYP_EXPENSES,
        AUSGABE,
        31.20,
    )
    # Ohne Lernen bleibt die KI ahnungslos - der Import haengt nicht daran.
    assert learning_stats(conn).is_empty
    # Und die frisch gebuchten Zeilen gelten ab jetzt als Duplikat - das
    # haengt am Importzustand, nicht an der KI.
    dienst = TwintAwareBankImportService(conn)
    assert all(dienst.is_duplicate(zeile, DIGEST) for zeile in zeilen)
    schnappschuss = capture_analysis_snapshot(conn)
    assert all(schnappschuss.is_duplicate(zeile, DIGEST) for zeile in zeilen)


def test_der_gebuchte_bestand_bleibt_beim_import_ohne_lernen_vollstaendig(haushalt):
    """Buchhaltung und Lernspeicher sind zwei Dinge - hier beide zugleich."""
    conn = haushalt.conn
    vorher = _coach_zahlen(conn)
    reset_learning_data(conn)

    TwintAwareBankImportService(conn).import_items(
        [
            BankImportItem(
                transaction=_tx(11, description=FREMDTEXT, amount="-8.40"),
                typ=TYP_EXPENSES,
                category=AUSGABE_ZWEI,
                tags=(),
                amount=8.40,
                details=FREMDTEXT,
            )
        ],
        document_digest=DIGEST,
        learn=False,
    )

    nachher = _coach_zahlen(conn)
    assert nachher["zeilen"] == int(vorher["zeilen"]) + 1
    assert nachher["budgets"] == vorher["budgets"]
    assert nachher["sparziele"] == vorher["sparziele"]
    assert nachher["einnahmen_je_monat"] == vorher["einnahmen_je_monat"]


# ── Derselbe Zyklus, aber ueber die echten Bedienelemente ───────────────────
#
# Bis hierher lief alles am Rechenweg. Was fehlt, ist die Verbindung von der
# Einstellungsdatei zum Schalter und vom Schalter zum Import: Ein umbenannter
# Einstellungsschluessel oder ein nicht durchgereichtes ``learn`` waere in den
# Tests oben unsichtbar geblieben.


@pytest.fixture
def dialog_mit_wissen(v4_app, v4_conn, tmp_path):
    """V4-Dialog mit echten Einstellungen und einem gelernten Haendler."""
    from settings import Settings
    from tests.conftest import V4_DIGEST, V4_KATEGORIE, warte_auf_analyse
    from views.bank_import_dialog_v4 import BankImportDialog, LoadedSource

    # Ausgangslage: ein Haendler, den ein frueherer Import bestaetigt hat.
    # Bewusst die schwaechste Quelle - so kann die Handarbeit im Test unten
    # ueberhaupt etwas ueberschreiben (die Rangfolge ist P2.3).
    BankImportAI(v4_conn).learn(
        typ=TYP_EXPENSES,
        category=V4_KATEGORIE,
        description=BANKTEXT,
        counterparty=GEGENPARTEI,
        source=SOURCE_IMPORT_CONFIRMED,
    )
    v4_conn.commit()
    settings = Settings(str(tmp_path / "settings.json"))
    erzeugte = []

    def _factory():
        dialog = BankImportDialog(v4_conn, settings=settings)
        dialog.sources = [
            LoadedSource(
                "konto.csv",
                V4_DIGEST,
                "Bank-CSV/PDF",
                [
                    _tx(
                        0,
                        description=BANKTEXT,
                        amount="-42.50",
                        counterparty=GEGENPARTEI,
                    )
                ],
                set(),
            )
        ]
        dialog._rebuild_from_sources()
        warte_auf_analyse(dialog)
        erzeugte.append(dialog)
        return dialog, settings

    yield _factory
    for dialog in erzeugte:
        # ``reject()`` haelt den Analyse-Worker an; ohne das raeumt Qt den
        # Dialog ab, waehrend der Thread noch rechnet.
        dialog.reject()
        dialog.deleteLater()
    v4_app.processEvents()


def test_der_schalter_im_dialog_faehrt_den_ganzen_zyklus(dialog_mit_wissen, v4_conn):
    """Ein - aus - ein, gemessen an der Pruefliste und am Lernbestand."""
    from tests.conftest import V4_KATEGORIE, warte_auf_analyse

    dialog, settings = dialog_mit_wissen()
    bestand = learning_stats(v4_conn)
    assert dialog.states[0].category == V4_KATEGORIE
    assert dialog.states[0].prediction_method == "merchant_memory"

    dialog.act_ai_enabled.setChecked(False)
    warte_auf_analyse(dialog)

    assert settings.bank_import_ai_enabled is False, "Der Schalter wird gespeichert"
    assert dialog.states[0].category == ""
    assert dialog.states[0].confidence == 0.0
    assert learning_stats(v4_conn) == bestand, "Ausschalten loescht nichts"

    dialog.act_ai_enabled.setChecked(True)
    warte_auf_analyse(dialog)

    assert dialog.states[0].category == V4_KATEGORIE
    assert dialog.states[0].prediction_method == "merchant_memory"


def _widersprechen(dialog, v4_helfer) -> None:
    """Setzt die Kategorie der Zeile von Hand auf eine andere.

    Ohne diesen Widerspruch liefe die Zeile als blosse Eigenbestaetigung durch
    den Import - der Lernspeicher saehe danach genauso aus wie vorher, und ein
    Test auf "nichts dazugelernt" waere auch dann gruen, wenn der Schalter
    ueberhaupt nicht durchgereicht wird.
    """
    from tests.conftest import V4_KATEGORIE_ZWEI

    v4_helfer.haken_setzen(dialog, 0, True)
    v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE_ZWEI)
    assert dialog.states[0].prediction_method == "manual_bulk"


def test_der_lernschalter_des_dialogs_erreicht_den_echten_import(
    dialog_mit_wissen, v4_conn, v4_helfer, v4_import_bestaetigen
):
    """Gebucht wird, gelernt nicht - und zwar auf dem Weg durch den Dialog."""
    from tests.conftest import warte_auf_analyse

    v4_import_bestaetigen()
    dialog, _settings = dialog_mit_wissen()
    dialog.act_ai_learning.setChecked(False)
    warte_auf_analyse(dialog)
    _widersprechen(dialog, v4_helfer)
    vorher = _lernabzug(v4_conn)
    assert dialog.ai_learning_enabled() is False

    dialog.import_selected()

    assert v4_conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 1
    assert _lernabzug(v4_conn) == vorher, "Der Import hat trotz Schalter gelernt"


def test_gegenprobe_mit_lernen_schreibt_derselbe_weg_sehr_wohl(
    dialog_mit_wissen, v4_conn, v4_helfer, v4_import_bestaetigen
):
    """Sonst bewiese der Test darueber nur, dass dieser Import nie lernt."""
    from tests.conftest import V4_KATEGORIE_ZWEI

    v4_import_bestaetigen()
    dialog, _settings = dialog_mit_wissen()
    assert dialog.ai_learning_enabled() is True
    _widersprechen(dialog, v4_helfer)

    dialog.import_selected()

    eintrag = v4_conn.execute(
        "SELECT category, source FROM ai_merchant_memory WHERE fingerprint=?",
        (_fingerprint(BANKTEXT, GEGENPARTEI),),
    ).fetchone()
    assert str(eintrag[0]) == V4_KATEGORIE_ZWEI
    assert str(eintrag[1]) == SOURCE_MANUAL_BULK


def test_alle_drei_lernwege_lesen_denselben_einstellungsschluessel():
    """Ein Schalter, drei Stellen - und keine eigene Schreibweise.

    Der Importdialog, die Schnelleingabe und die Tagvergabe der Buchungsliste
    fragen dieselbe Einstellung ab. Benennt sie jemand an einer Stelle um,
    liefe der Rest stumm mit der Vorgabe *an* weiter - genau die Art Fehler,
    die niemandem auffaellt.
    """
    from pathlib import Path

    wurzel = Path(__file__).resolve().parents[1]
    for pfad in (
        "views/bank_import_dialog_v4.py",
        "views/quick_add_dialog.py",
        "views/tabs/tracking_tab.py",
    ):
        quelle = (wurzel / pfad).read_text(encoding="utf-8")
        assert "bank_import_ai_learning_enabled" in quelle, pfad
