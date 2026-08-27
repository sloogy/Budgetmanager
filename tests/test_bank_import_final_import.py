"""Der finale Bankimport: Atomaritaet, Abbruch und ehrlicher Fortschritt (P1.5).

Der Import bleibt im Bedien-Thread. Er schreibt in genau die SQLite-Connection,
die dieser Thread besitzt; sie in einen Worker zu reichen verbietet Regel 1.4,
und den Block fuer einen huebscheren Balken aufzuteilen verbietet Regel 1.8.
Ehrlich wird der Fortschritt deshalb anders: unbestimmter Balken waehrend einer
offenen Transaktion, Prozentwert und Abbruch nur zwischen zwei Bloecken.

Der Befund, der diese Datei traegt, war kein Anzeigefehler. ``record_operation``
liess nach dem Pruning des ``undo_stack`` eine implizite Transaktion offen.
``db_transaction`` fand ``conn.in_transaction`` vor und hielt das fuer eine
aeussere Klammer - ab der zweiten Datei lief der Import also voellig ohne
eigenes BEGIN/COMMIT. Ein Fehler mitten in Datei zwei rollte dann *nichts*
zurueck: halbe Datei in ``tracking``, eine Zeile davon sogar ohne Eintrag in
``bank_import_state``, also unsichtbar fuer die Duplikaterkennung. Der naechste
beliebige ``commit()`` der Anwendung schrieb das fest. Getestet wird hier
deshalb nicht die Behauptung, sondern der Zustand nach einem Fehler mitten im
Import.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from model.bank_import_service import BankImportItem, BankImportService, external_id
from model.bank_statement_reader import BankTransaction
from model.category_model import CategoryModel
from model.migrations import migrate_all
from model.typ_constants import TYP_EXPENSES
from model.undo_redo_model import UndoRedoModel
from tests.conftest import V4_DIGEST, V4_DIGEST_ZWEI, V4_KATEGORIE

# ── Hilfen ────────────────────────────────────────────────────────


def _zustandszeilen(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute("SELECT external_id FROM bank_import_state").fetchall()
    }


def _verwaiste_buchungen(conn: sqlite3.Connection) -> list[int]:
    """Tracking-Zeilen aus einem Bankimport ohne Eintrag in ``bank_import_state``.

    Genau die sind das Gift: Sie stehen im Budget, aber die Duplikaterkennung
    kennt sie nicht - ein zweiter Lauf derselben Datei buchte sie erneut.
    """
    rows = conn.execute(
        """
        SELECT t.id FROM tracking t
        LEFT JOIN bank_import_state s ON s.tracking_id = t.id
        WHERE t.source = 'bank_import' AND s.external_id IS NULL
        """
    ).fetchall()
    return [int(row[0]) for row in rows]


def _buchungszahl(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0])


def _fehler_ab_dem_nten_datensatz(dialog, n: int) -> None:
    """Laesst den Import ab dem ``n``-ten geschriebenen Datensatz scheitern.

    ``_record_state`` sitzt mitten in der offenen Transaktion, hinter dem
    ``INSERT`` in ``tracking`` und vor dem Ende des Blocks. Ein Fehler an dieser
    Stelle ist der Ernstfall: die Zeile steht schon, der Block ist es nicht.
    """
    echt = dialog.service._record_state
    zaehler = {"n": 0}

    def kaputt(**kwargs):
        zaehler["n"] += 1
        if zaehler["n"] >= n:
            raise sqlite3.OperationalError("Datenbank voll")
        return echt(**kwargs)

    dialog.service._record_state = kaputt


@pytest.fixture
def zwei_dateien(v4_app, v4_dialog, v4_tx, v4_helfer, v4_import_bestaetigen):
    """Dialog mit zwei Quellen: eine Zeile in Datei A, zwei in Datei B."""

    def _factory():
        v4_import_bestaetigen()
        dialog = v4_dialog(
            [],
            quellen=[
                (
                    V4_DIGEST,
                    "a.csv",
                    [v4_tx(0, description="Alpha Laden", amount="-10.00")],
                ),
                (
                    V4_DIGEST_ZWEI,
                    "b.csv",
                    [
                        v4_tx(
                            0,
                            description="Beta Laden",
                            amount="-20.00",
                            booking_date=date(2026, 4, 1),
                            source_name="b.csv",
                        ),
                        v4_tx(
                            1,
                            description="Gamma Laden",
                            amount="-30.00",
                            booking_date=date(2026, 4, 2),
                            source_name="b.csv",
                        ),
                    ],
                ),
            ],
        )
        v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE)
        # Gezeigt, weil ``isVisible()`` sonst auch fuer einen eingeblendeten
        # Knopf False meldet - dieselbe Vorbereitung wie in P1.4.
        dialog.show()
        v4_app.processEvents()
        return dialog

    return _factory


# ── Atomaritaet und Rollback ──────────────────────────────────────


def test_fehler_mitten_im_import_rollt_die_ganze_datei_zurueck(zwei_dateien, v4_conn):
    """Haken 1 und 2: Import atomar, Rollback bei Fehler.

    Datei A ist ein eigener Block und bleibt. Datei B scheitert bei ihrer
    zweiten Zeile - dann darf von Datei B *keine* Zeile stehen, auch nicht die
    erste, die vor dem Fehler schon geschrieben war.
    """
    dialog = zwei_dateien()
    _fehler_ab_dem_nten_datensatz(dialog, 3)  # Zeile 1 von A, dann 2 von B

    dialog.import_selected()

    assert _buchungszahl(v4_conn) == 1, "Datei B wurde nicht zurueckgerollt"
    gespeichert = _zustandszeilen(v4_conn)
    assert len(gespeichert) == 1
    assert external_id(dialog.transactions[0], V4_DIGEST) in gespeichert
    assert not v4_conn.in_transaction, "offene Transaktion nach dem Fehler"


def test_ein_spaeterer_commit_schreibt_keine_halbe_datei_fest(zwei_dateien, v4_conn):
    """Haken 2: der Rollback haelt auch dem naechsten fremden Commit stand.

    Der alte Weg hinterliess die halbe Datei in einer fremden, nie geschlossenen
    Transaktion. Sichtbar wurde das erst, wenn irgendein anderer Schreibweg der
    Anwendung committete - im verschluesselten Modus schreibt jeder Commit
    ausserdem sofort die .enc-Datei. Danach war die halbe Datei dauerhaft da.
    """
    dialog = zwei_dateien()
    _fehler_ab_dem_nten_datensatz(dialog, 3)
    dialog.import_selected()

    v4_conn.commit()

    assert _buchungszahl(v4_conn) == 1
    assert len(_zustandszeilen(v4_conn)) == 1


def test_nach_dem_fehler_bleibt_keine_buchung_ohne_importzustand(zwei_dateien, v4_conn):
    """Haken 3 und 4: ``bank_import_state`` und ``tracking`` bleiben deckungsgleich."""
    dialog = zwei_dateien()
    _fehler_ab_dem_nten_datensatz(dialog, 3)
    dialog.import_selected()

    assert _verwaiste_buchungen(v4_conn) == []


def test_der_zweite_lauf_holt_genau_die_gescheiterte_datei_nach(
    zwei_dateien, v4_conn, v4_helfer
):
    """Haken 3 und 4, die Probe aufs Exempel.

    Nach dem Rollback muss der Wiederholungslauf Datei B genau einmal buchen und
    Datei A als Duplikat ueberspringen. Eine verwaiste Tracking-Zeile haette
    genau hier eine Doppelbuchung erzeugt.
    """
    dialog = zwei_dateien()
    _fehler_ab_dem_nten_datensatz(dialog, 3)
    dialog.import_selected()

    zweiter = zwei_dateien()
    zweiter.import_selected()

    assert _buchungszahl(v4_conn) == 3
    assert len(_zustandszeilen(v4_conn)) == 3
    assert _verwaiste_buchungen(v4_conn) == []


def test_undo_nach_einem_fehlerhaften_import_laesst_die_datenbank_sauber(
    zwei_dateien, v4_conn
):
    """Haken 5: Undo/Redo konsistent.

    Der abgeschlossene Block bekommt seine eigene Undo-Gruppe; der
    zurueckgerollte bekommt keine. Ein Undo raeumt deshalb genau Datei A weg -
    und der Import derselben Datei ist danach wieder moeglich, weil
    ``is_duplicate`` die Tracking-Zeile mitprueft und nicht nur den Zustand.
    """
    dialog = zwei_dateien()
    _fehler_ab_dem_nten_datensatz(dialog, 3)
    dialog.import_selected()

    undo = UndoRedoModel(v4_conn)
    assert undo.undo() is True
    assert _buchungszahl(v4_conn) == 0
    assert _verwaiste_buchungen(v4_conn) == []
    assert not v4_conn.in_transaction

    assert undo.redo() is True
    assert _buchungszahl(v4_conn) == 1
    assert _verwaiste_buchungen(v4_conn) == []


def test_jede_datei_bekommt_ihre_eigene_undo_gruppe(zwei_dateien, v4_conn):
    """Haken 5: Ein Undo nimmt eine Datei zurueck, nicht den halben Import."""
    dialog = zwei_dateien()
    dialog.import_selected()

    assert _buchungszahl(v4_conn) == 3
    undo = UndoRedoModel(v4_conn)
    assert undo.undo() is True
    assert _buchungszahl(v4_conn) == 1, "Undo nahm mehr als die letzte Datei zurueck"
    assert undo.undo() is True
    assert _buchungszahl(v4_conn) == 0


# ── Ehrlicher Fortschritt ─────────────────────────────────────────


def _fortschritt_mitschreiben(dialog) -> list[tuple]:
    """Protokolliert Prozentwerte und den Balkenzustand *innerhalb* der Bloecke.

    Der Eintrag ``block`` entsteht in dem Moment, in dem die Transaktion
    geschrieben wird. Genau dort darf keine Prozentzahl stehen.
    """
    protokoll: list[tuple] = []

    echt_prozent = dialog.progress_area.set_percent

    def gemerkt(percent):
        protokoll.append(("percent", percent))
        echt_prozent(percent)

    dialog.progress_area.set_percent = gemerkt

    echt_import = dialog.service.import_items

    def beobachtet(items, *, document_digest):
        bereich = dialog.progress_area
        protokoll.append(
            (
                "block",
                bereich.bar.minimum(),
                bereich.bar.maximum(),
                bereich.status_text(),
                bereich.btn_cancel.isVisible() and bereich.btn_cancel.isEnabled(),
            )
        )
        return echt_import(items, document_digest=document_digest)

    dialog.service.import_items = beobachtet
    return protokoll


def test_waehrend_eines_blocks_laeuft_der_balken_unbestimmt(zwei_dateien):
    """Haken 6: Fortschritt ehrlich.

    Waehrend einer offenen Transaktion gibt es keine seriose Restmenge. Der
    Balken laeuft unbestimmt (``range(0, 0)``), und die Zeile sagt, was
    tatsaechlich passiert - keine erfundene Zahl (Regel 1.7).
    """
    from utils.i18n import tr

    dialog = zwei_dateien()
    protokoll = _fortschritt_mitschreiben(dialog)

    dialog.import_selected()

    bloecke = [eintrag for eintrag in protokoll if eintrag[0] == "block"]
    assert len(bloecke) == 2, "erwartet: ein Block je Datei"
    for _, minimum, maximum, text, abbrechbar in bloecke:
        assert (minimum, maximum) == (0, 0), "Balken war waehrend des Blocks bestimmt"
        assert tr("import_progress.phase_commit") in text
        assert "%" not in text, f"erfundene Prozentzahl im Block: {text!r}"
        assert abbrechbar, "Abbrechen war waehrend des Blocks nicht bedienbar"


def test_zwischen_den_bloecken_steigt_der_prozentwert_bis_hundert(zwei_dateien):
    """Haken 6: Zwischen sicheren Bloecken wird der Stand fortgeschrieben."""
    dialog = zwei_dateien()
    protokoll = _fortschritt_mitschreiben(dialog)

    dialog.import_selected()

    werte = [eintrag[1] for eintrag in protokoll if eintrag[0] == "percent"]
    assert werte, "der finale Import meldete ueberhaupt keinen Fortschritt"
    assert werte[0] == 0
    assert werte[-1] == 100
    assert werte == sorted(werte), f"Fortschritt sprang zurueck: {werte}"
    # Nach Buchungszahl gewichtet: Datei A hat eine von drei Zeilen.
    assert 33 in werte


def test_der_fortschrittsbereich_verschwindet_auch_nach_einem_fehler(zwei_dateien):
    """Haken 6: Kein stehengebliebener Balken - auch nicht im Fehlerfall."""
    dialog = zwei_dateien()
    _fehler_ab_dem_nten_datensatz(dialog, 3)

    dialog.import_selected()

    assert not dialog.progress_area.is_active()
    assert not dialog.progress_area.isVisible()
    assert not dialog.import_running()


def test_waehrend_des_imports_ist_die_pruefliste_gesperrt(zwei_dateien):
    """Haken 6: Was gerade geschrieben wird, laesst sich nicht nebenher aendern.

    Der Import pumpt zwischen den Bloecken die Ereignisschleife, damit der
    Abbrechen-Knopf ankommt. Damit kaeme aber auch jeder andere Klick an. Die
    Pruefliste und die Importknoepfe ruhen deshalb solange; nur Abbrechen bleibt.
    """
    dialog = zwei_dateien()
    beobachtet: list[tuple[bool, bool]] = []
    echt = dialog.service.import_items

    def merken(items, *, document_digest):
        beobachtet.append((dialog.table.isEnabled(), dialog.btn_import.isEnabled()))
        return echt(items, document_digest=document_digest)

    dialog.service.import_items = merken
    dialog.import_selected()

    assert beobachtet, "kein Block gelaufen"
    assert all(not tabelle and not knopf for tabelle, knopf in beobachtet)
    # Danach ist wieder alles frei.
    assert dialog.table.isEnabled()


# ── Abbruch nur an sicheren Punkten ───────────────────────────────


def test_abbruch_mitten_im_block_laesst_den_block_zu_ende_laufen(zwei_dateien, v4_conn):
    """Haken 7: Cancel nur an sicheren Punkten.

    Der Klick faellt in die offene Transaktion von Datei A. Er darf sie nicht
    zerreissen: Datei A wird fertig geschrieben und committet, Datei B beginnt
    gar nicht erst.
    """
    dialog = zwei_dateien()
    echt = dialog.service.import_items
    gelaufen: list[str] = []

    def mit_klick(items, *, document_digest):
        gelaufen.append(document_digest)
        # Der echte Knopf, der echte Signalweg - kein direkt gesetztes Flag.
        dialog.progress_area.btn_cancel.click()
        return echt(items, document_digest=document_digest)

    dialog.service.import_items = mit_klick
    dialog.import_selected()

    assert gelaufen == [V4_DIGEST], "Datei B lief trotz Abbruch an"
    assert _buchungszahl(v4_conn) == 1, "Datei A wurde nicht fertig geschrieben"
    assert len(_zustandszeilen(v4_conn)) == 1
    assert _verwaiste_buchungen(v4_conn) == []
    assert not v4_conn.in_transaction


def test_nach_einem_abbruch_holt_der_naechste_lauf_den_rest_nach(zwei_dateien, v4_conn):
    """Haken 7: Der Abbruch markiert nichts faelschlich als erledigt."""
    dialog = zwei_dateien()
    echt = dialog.service.import_items

    def mit_klick(items, *, document_digest):
        dialog.progress_area.btn_cancel.click()
        return echt(items, document_digest=document_digest)

    dialog.service.import_items = mit_klick
    dialog.import_selected()
    assert dialog.result() == 0, "abgebrochener Import schloss den Dialog als Erfolg"

    zweiter = zwei_dateien()
    zweiter.import_selected()

    assert _buchungszahl(v4_conn) == 3
    assert _verwaiste_buchungen(v4_conn) == []


def test_das_fensterkreuz_reisst_keinen_laufenden_block_auf(zwei_dateien, v4_conn):
    """Haken 7: Auch Escape und Fensterkreuz warten auf die Blockgrenze.

    ``done()`` erreicht der Dialog waehrend des Imports nur ueber die gepumpte
    Ereignisschleife. Wuerde er dort schliessen, raeumte Qt den Dialog samt
    Service mitten in einer offenen Transaktion ab.
    """
    dialog = zwei_dateien()
    echt = dialog.service.import_items
    gelaufen: list[str] = []

    def mit_schliessen(items, *, document_digest):
        gelaufen.append(document_digest)
        dialog.reject()  # laeuft ueber done()
        return echt(items, document_digest=document_digest)

    dialog.service.import_items = mit_schliessen
    dialog.import_selected()

    assert gelaufen == [V4_DIGEST]
    assert _buchungszahl(v4_conn) == 1
    assert not v4_conn.in_transaction
    assert not dialog.import_running()


def test_ein_zweiter_importklick_waehrend_des_laufs_prallt_ab(zwei_dateien, v4_conn):
    """Haken 1: Das Pumpen der Ereignisschleife darf nichts doppelt schreiben."""
    dialog = zwei_dateien()
    echt = dialog.service.import_items

    def mit_zweitklick(items, *, document_digest):
        dialog.import_selected()
        return echt(items, document_digest=document_digest)

    dialog.service.import_items = mit_zweitklick
    dialog.import_selected()

    assert _buchungszahl(v4_conn) == 3
    assert len(_zustandszeilen(v4_conn)) == 3


# ── DB-/File-Locks (Ursache statt Windows-Augenschein) ────────────


def _dateideskriptoren() -> set[str]:
    """Die offenen Deskriptoren des Prozesses - wie schon in P1.4."""
    verzeichnis = Path("/proc/self/fd")
    if not verzeichnis.exists():  # pragma: no cover - nur auf Linux vorhanden
        pytest.skip("/proc/self/fd nicht verfuegbar")
    offen = set()
    for eintrag in verzeichnis.iterdir():
        try:
            offen.add(os.readlink(str(eintrag)))
        except OSError:
            continue
    return offen


@pytest.fixture
def datei_datenbank(tmp_path):
    """Echte Datei-DB statt ``:memory:`` - nur so gibt es ueberhaupt Sperren."""
    pfad = tmp_path / "budget.db"
    conn = sqlite3.connect(str(pfad))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_all(conn)
    CategoryModel(conn).create(TYP_EXPENSES, V4_KATEGORIE)
    yield pfad, conn
    conn.close()


def _posten(index: int, quelle: str) -> BankImportItem:
    tx = BankTransaction(
        source_kind="csv",
        source_name=quelle,
        source_index=index,
        booking_date=date(2026, 3, 17),
        amount=Decimal("-10.00"),
        currency="CHF",
        description=f"Kauf {quelle} {index}",
        counterparty="",
        raw={},
    )
    return BankImportItem(tx, TYP_EXPENSES, V4_KATEGORIE, (), 10.0, "Detail")


def test_nach_jedem_block_haelt_niemand_mehr_eine_schreibsperre(datei_datenbank):
    """Haken 8, Ursache statt Augenschein: keine offene Transaktion.

    Eine offene SQLite-Schreibtransaktion haelt eine RESERVED-Sperre auf der
    Datei. Unter Windows blockiert genau das Backup, Restore und jedes
    Verschieben der .db - und zwar unbemerkt, weil lokal alles weiterlaeuft.
    Geprueft wird deshalb der Zustand, der die Sperre erzeugt, und zusaetzlich,
    ob eine zweite Verbindung sofort schreiben darf.
    """
    pfad, conn = datei_datenbank
    service = BankImportService(conn)

    for lauf, digest in enumerate((V4_DIGEST, V4_DIGEST_ZWEI), start=1):
        service.import_items([_posten(0, f"{lauf}.csv")], document_digest=digest)
        assert not conn.in_transaction, f"Block {lauf} liess eine Transaktion offen"

        fremd = sqlite3.connect(str(pfad), timeout=0.5)
        try:
            fremd.execute("CREATE TABLE IF NOT EXISTS sperrprobe(id INTEGER)")
            fremd.execute("INSERT INTO sperrprobe(id) VALUES(1)")
            fremd.commit()
        finally:
            fremd.close()


def test_auch_ein_fehlgeschlagener_block_gibt_die_sperre_frei(datei_datenbank):
    """Haken 8: Der Rollback loest die Sperre - sonst haengt der naechste Zugriff."""
    pfad, conn = datei_datenbank
    service = BankImportService(conn)
    service.import_items([_posten(0, "a.csv")], document_digest=V4_DIGEST)

    echt = service._record_state
    zaehler = {"n": 0}

    def kaputt(**kwargs):
        zaehler["n"] += 1
        if zaehler["n"] >= 2:
            raise sqlite3.OperationalError("Datenbank voll")
        return echt(**kwargs)

    service._record_state = kaputt
    with pytest.raises(sqlite3.OperationalError):
        service.import_items(
            [_posten(0, "b.csv"), _posten(1, "b.csv")],
            document_digest=V4_DIGEST_ZWEI,
        )

    assert not conn.in_transaction
    fremd = sqlite3.connect(str(pfad), timeout=0.5)
    try:
        fremd.execute("CREATE TABLE IF NOT EXISTS sperrprobe(id INTEGER)")
        fremd.commit()
    finally:
        fremd.close()


def test_der_import_laesst_keine_zusaetzlichen_deskriptoren_zurueck(zwei_dateien):
    """Haken 8: Der Schreibweg oeffnet keine Datei, die er nicht wieder schliesst."""
    dialog = zwei_dateien()
    vorher = _dateideskriptoren()

    dialog.import_selected()

    neu = _dateideskriptoren() - vorher
    assert not neu, f"nach dem Import zusaetzlich offen: {sorted(neu)}"
