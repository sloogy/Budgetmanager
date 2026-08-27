"""Der Analyse-Worker des Bankimports.

Die Analyse rechnet seit P1.1 aus einem eingefrorenen Snapshot statt aus der
Datenbank. Hier wird eingeloest, wofuer das gebaut wurde: Sie laeuft in einem
echten Fremd-Thread, meldet Fortschritt an den Bereich aus P1.2 und liefert
dabei *dasselbe* Ergebnis wie zuvor.

Der Goldwert unten stammt aus einem Lauf der Fassung **vor** dieser
Umstellung - aufgenommen an genau diesem Szenario, mit Duplikat, TWINT-Eingang,
TWINT-Erstattungstreffer, ``twint_ai``-Marker und drei verschiedenen
Vorhersagewegen. Er ist damit die Gegenprobe "alt gegen neu" und nicht eine
zweite Abschrift derselben Rechnung: waere die Fachlogik beim Umzug in den
Worker verrutscht, stuende hier eine andere Zahl.
"""

from __future__ import annotations

import ast
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from model.bank_import_ai import BankImportAI
from model.bank_import_analysis import (
    ALL_PHASES,
    AnalysisCancelled,
    AnalysisRequest,
    ProgressSink,
    analyse,
)
from model.bank_import_service import BankImportItem, source_digest
from model.bank_import_snapshot import capture_analysis_snapshot
from model.bank_statement_reader import load_transactions
from model.credit_card_statement_reader import (
    is_credit_card_csv,
    load_credit_card_csv,
)
from model.tags_model import TagsModel
from model.twint_import_policy import (
    BankImportMarkerStore,
    TwintAwareBankImportService,
)
from model.typ_constants import TYP_EXPENSES
from tests.conftest import V4_KATEGORIE, V4_KATEGORIE_ZWEI, warte_auf_analyse

ROOT = Path(__file__).resolve().parents[1]

BANK_CSV = (
    "Datum;Buchungstext;Whg;Betrag Detail;ZKB-Referenz;Referenznummer;"
    "Belastung CHF;Gutschrift CHF;Valuta;Saldo CHF;Zahlungszweck;Details\n"
    "23.08.2026;Kartenzahlung;CHF;24,50;ZKB-1;REF-1;24,50;;24.08.2026;"
    "1'000,00;COOP SUPERMARKT WINTERTHUR 987654;Filiale Winterthur\n"
    "24.08.2026;Dauerauftrag;CHF;1200,00;ZKB-2;REF-2;1200,00;;25.08.2026;"
    "1'000,00;MIETE MAERZ;Verwaltung Mustermann\n"
    "25.08.2026;Gutschrift;CHF;20,00;ZKB-3;REF-3;;20,00;26.08.2026;"
    "1'000,00;TWINT Gutschrift Anna;\n"
    "26.08.2026;Kartenzahlung;CHF;9,80;ZKB-4;REF-4;9,80;;27.08.2026;"
    "1'000,00;SBB BILLETT ZUERICH 5511;\n"
)

KARTE_CSV = (
    "TransactionId;CardId;Date;ValutaDate;Amount;Currency;;OriginalAmount;"
    "OriginalCurrency;MerchantName;MerchantPlace;MerchantCountry;StateType;"
    "Details;Type;Exchange Rate\n"
    "TX-123;CARD-1;21.08.2026;22.08.2026;-19.85;CHF;;21.30;EUR;"
    "COOP;Winterthur;CH;BOOKED;Mittagessen;PURCHASE;0.9319\n"
    "TX-124;CARD-1;22.08.2026;23.08.2026;55.00;CHF;;55.00;CHF;"
    "TWINT Rueckzahlung Bruno;Winterthur;CH;BOOKED;Rueckzahlung;CREDIT;1.0\n"
)

# Aufgenommen aus der synchronen Fassung des V4-Dialogs (Stand 9d88429).
GOLDWERT = {
    "quellen": [
        ("konto.csv", "Bank-CSV/PDF", 4),
        ("karte.csv", "Kreditkarten-CSV", 2),
    ],
    "digest_gruppen": [0, 0, 0, 0, 1, 1],
    "texte": [
        "Kartenzahlung | COOP SUPERMARKT WINTERTHUR 987654 | Filiale Winterthur",
        "Dauerauftrag | MIETE MAERZ | Verwaltung Mustermann",
        "Gutschrift | TWINT Gutschrift Anna",
        "Kartenzahlung | SBB BILLETT ZUERICH 5511",
        "COOP | Winterthur | CH | Mittagessen | PURCHASE",
        "TWINT Rueckzahlung Bruno | Winterthur | CH | Rueckzahlung | CREDIT",
    ],
    "betraege": ["-24.50", "-1200.00", "20.00", "-9.80", "-19.85", "55.00"],
    "duplicate_indexes": [1],
    "twint_credit_indexes": [2, 5],
    "marked_twint_indexes": [],
    "ai_marker_indexes": [5],
    "matched_credit_indexes": [2],
    "matches": {0: ("row:0", "row:2", 2, 20.0, 81.63, 18.37, 0.8606)},
    "states": {
        0: (True, "Ausgaben", "Ausgaben", V4_KATEGORIE, (), 0.845, "similar_merchant"),
        1: (False, "Ausgaben", "", "", (), 0.0, ""),
        2: (True, "TWINT (KI)", "Ausgaben", V4_KATEGORIE, (), 0.9, "twint_match"),
        3: (
            True,
            "Ausgaben",
            "Ausgaben",
            V4_KATEGORIE_ZWEI,
            (),
            0.845,
            "similar_merchant",
        ),
        4: (True, "Ausgaben", "Ausgaben", V4_KATEGORIE, (), 0.9854, "naive_bayes"),
        5: (
            False,
            "TWINT (KI)",
            "Ausgaben",
            V4_KATEGORIE_ZWEI,
            (),
            0.95,
            "twint_memory",
        ),
    },
}


def _befuellte_db(conn: sqlite3.Connection, bank: Path, karte: Path) -> None:
    """Lernstoff, ein bereits importierter Betrag und ein alter Lernmarker."""
    TagsModel(conn).create_tag("Lebensmittel")
    ai = BankImportAI(conn)
    ai.learn(
        typ=TYP_EXPENSES,
        category=V4_KATEGORIE,
        description="COOP SUPERMARKT WINTERTHUR 123456",
        counterparty="COOP",
        tags=("Lebensmittel",),
    )
    ai.learn(
        typ=TYP_EXPENSES,
        category=V4_KATEGORIE_ZWEI,
        description="SBB BILLETT ZUERICH",
        counterparty="SBB",
    )

    zeilen = load_transactions(str(bank), "CHF")
    TwintAwareBankImportService(conn).import_items(
        [
            BankImportItem(
                transaction=zeilen[1],
                typ=TYP_EXPENSES,
                category=V4_KATEGORIE_ZWEI,
                tags=(),
                amount=1200.0,
                details="Miete",
            )
        ],
        document_digest=source_digest(str(bank)),
    )

    karten_zeilen = (
        load_credit_card_csv(str(karte), "CHF")
        if is_credit_card_csv(str(karte))
        else load_transactions(str(karte), "CHF")
    )
    BankImportMarkerStore(conn).mark_classifications(
        [(karten_zeilen[1], TYP_EXPENSES, V4_KATEGORIE_ZWEI)],
        source_digest(str(karte)),
        marker_kind="twint_ai",
    )


@pytest.fixture
def szenario(v4_conn, tmp_path):
    """Zwei Auszugsdateien und eine Datenbank mit Vorgeschichte."""
    bank = tmp_path / "konto.csv"
    karte = tmp_path / "karte.csv"
    bank.write_text(BANK_CSV, encoding="utf-8")
    karte.write_text(KARTE_CSV, encoding="utf-8")
    _befuellte_db(v4_conn, bank, karte)
    return v4_conn, bank, karte


def _ergebnis_aus_dialog(dialog) -> dict:
    digests = list(dialog._transaction_digests)
    eindeutig = sorted(set(digests), key=digests.index)
    return {
        "quellen": [
            (Path(q.path).name, q.source_format, len(q.transactions))
            for q in dialog.sources
        ],
        "digest_gruppen": [eindeutig.index(d) for d in digests],
        "texte": [tx.description for tx in dialog.transactions],
        "betraege": [str(tx.amount) for tx in dialog.transactions],
        "duplicate_indexes": sorted(dialog.duplicate_indexes),
        "twint_credit_indexes": sorted(dialog.twint_credit_indexes),
        "marked_twint_indexes": sorted(dialog.marked_twint_indexes),
        "ai_marker_indexes": sorted(dialog.ai_marker_indexes),
        "matched_credit_indexes": sorted(dialog.matched_credit_indexes),
        "matches": {
            index: (
                treffer.expense_id,
                treffer.credit_id,
                treffer.days_after,
                treffer.reimbursement_amount,
                treffer.reimbursement_percent,
                treffer.personal_share_percent,
                treffer.confidence,
            )
            for index, treffer in sorted(dialog.matches.items())
        },
        "states": {
            index: (
                zustand.use,
                zustand.typ,
                zustand.category_typ,
                zustand.category,
                tuple(sorted(zustand.manual_tags)),
                round(zustand.confidence, 6),
                zustand.prediction_method,
            )
            for index, zustand in sorted(dialog.states.items())
        },
    }


@pytest.fixture
def analysierter_dialog(v4_app, szenario):
    """V4-Dialog, der beide Dateien durch den Worker analysiert hat."""
    from views.bank_import_dialog_v4 import BankImportDialog

    conn, bank, karte = szenario
    dialog = BankImportDialog(conn)
    dialog.show()
    dialog._add_paths([str(bank), str(karte)])
    warte_auf_analyse(dialog)
    yield dialog
    dialog.close()
    dialog.deleteLater()
    v4_app.processEvents()


# ── Akzeptanz: Analyseergebnis identisch/kompatibel ───────────────────


def test_worker_liefert_dasselbe_ergebnis_wie_die_synchrone_fassung(
    analysierter_dialog,
):
    """Alt gegen neu: der Goldwert stammt aus der Fassung vor dem Worker."""
    assert _ergebnis_aus_dialog(analysierter_dialog) == GOLDWERT


def test_twint_logik_und_duplikaterkennung_bleiben_erhalten(analysierter_dialog):
    """Die zwei Faelle, die beim Umbau am leichtesten kippen, einzeln benannt."""
    dialog = analysierter_dialog
    # Die bereits importierte Miete ist ein Duplikat und nicht angehakt.
    assert 1 in dialog.duplicate_indexes
    assert dialog.states[1].use is False
    # Positive TWINT-Zeilen sind niemals Einkommen.
    assert dialog.twint_credit_indexes == {2, 5}
    assert dialog.states[2].typ == "TWINT (KI)"
    # Der frueher auf "nur lernen" gesetzte Eingang wird nicht erneut gebucht.
    assert dialog.ai_marker_indexes == {5}
    assert dialog.states[5].use is False
    # Die Erstattung uebernimmt die Kategorie der zugehoerigen Ausgabe.
    assert dialog.matches[0].credit_id == "row:2"
    assert dialog.states[2].category == dialog.states[0].category


# ── Akzeptanz: keine SQLite-Connection aus der GUI im Worker ──────────


def test_analyse_rechnet_nach_dem_schliessen_der_verbindung_weiter(szenario):
    """Der Worker haelt nichts, was an der Datenbank haengt.

    Die Gegenprobe steht in ``test_bank_import_analysis_snapshot``: derselbe
    Weg ueber die Verbindung ergibt im Fremd-Thread einen ``ProgrammingError``.
    """
    conn, bank, karte = szenario
    request = AnalysisRequest(
        snapshot=capture_analysis_snapshot(conn),
        new_paths=(str(bank), str(karte)),
    )
    conn.close()

    ergebnis: dict = {}

    def rechnen() -> None:
        ergebnis["wert"] = analyse(request)

    thread = threading.Thread(target=rechnen)
    thread.start()
    thread.join(30)
    assert not thread.is_alive()
    assert len(ergebnis["wert"].transactions) == 6
    assert sorted(ergebnis["wert"].duplicate_indexes) == [1]


def test_der_auftrag_traegt_keine_datenbankobjekte(szenario):
    """Was in den Worker geht, ist reine Python-Datenstruktur."""
    from views.bank_import_analysis_worker import BankImportAnalysisWorker

    conn, bank, _karte = szenario
    request = AnalysisRequest(
        snapshot=capture_analysis_snapshot(conn), new_paths=(str(bank),)
    )
    worker = BankImportAnalysisWorker(request)

    verboten = (sqlite3.Connection, sqlite3.Cursor, BankImportAI)
    for feld in vars(worker).values():
        assert not isinstance(feld, verboten)
    for feld in vars(request.snapshot).values():
        assert not isinstance(feld, verboten)
    assert not hasattr(request.snapshot, "conn")


# ── Akzeptanz: keine direkten Widget-Zugriffe aus dem Worker ──────────


def _importierte_module(pfad: Path) -> set[str]:
    baum = ast.parse(pfad.read_text(encoding="utf-8"), filename=str(pfad))
    namen: set[str] = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            namen.update(teil.name for teil in knoten.names)
        elif isinstance(knoten, ast.ImportFrom) and knoten.module:
            namen.add(knoten.module)
    return namen


@pytest.mark.parametrize(
    "modul",
    ["model/bank_import_analysis.py", "views/bank_import_analysis_worker.py"],
)
def test_worker_und_rechnung_kennen_keine_widgets(modul):
    """Kommunikation nur ueber Signale - kein Widget, kein Dialog, keine DB."""
    namen = _importierte_module(ROOT / modul)
    assert not any(name.startswith("PySide6.QtWidgets") for name in namen)
    assert not any(name.startswith("PySide6.QtGui") for name in namen)
    assert "sqlite3" not in namen
    assert not any(
        name.startswith("views.") and name != "views.bank_import_analysis_worker"
        for name in namen
    )


def test_worker_meldet_ausschliesslich_ueber_signale(v4_app, szenario):
    """Der Worker kennt weder den Dialog noch den Fortschrittsbereich."""
    from PySide6.QtCore import SignalInstance

    from views.bank_import_analysis_worker import BankImportAnalysisWorker

    conn, bank, _karte = szenario
    worker = BankImportAnalysisWorker(
        AnalysisRequest(
            snapshot=capture_analysis_snapshot(conn), new_paths=(str(bank),)
        )
    )
    for name in (
        "status_changed",
        "progress_changed",
        "item_progress",
        "finished",
        "failed",
        "cancelled",
    ):
        assert isinstance(getattr(worker, name), SignalInstance), name


# ── Akzeptanz: UI bleibt bedienbar ────────────────────────────────────


def test_oberflaeche_laeuft_weiter_waehrend_der_worker_rechnet(
    v4_app, szenario, monkeypatch
):
    """Waehrend der Rechnung verarbeitet der GUI-Thread weiter Ereignisse.

    Die Probe ist bewusst hart: Der Worker haelt mitten in der Analyse an und
    laesst erst weiter, nachdem der GUI-Thread nachweislich gearbeitet hat.
    Liefe die Rechnung noch im GUI-Thread, kaeme dieser Test nie ueber die
    Sperre hinaus - er liefe in seinen Timeout.
    """
    import views.bank_import_analysis_worker as worker_modul
    from views.bank_import_dialog_v4 import BankImportDialog

    conn, bank, karte = szenario
    angehalten = threading.Event()
    weiter = threading.Event()
    echtes_analyse = worker_modul.analyse

    def gebremst(request, sink=None):
        sink = sink or ProgressSink()
        sink.phase("read")
        angehalten.set()
        assert weiter.wait(30), "GUI-Thread hat den Worker nie freigegeben"
        return echtes_analyse(request, sink)

    monkeypatch.setattr(worker_modul, "analyse", gebremst)

    dialog = BankImportDialog(conn)
    dialog.show()
    dialog._add_paths([str(bank), str(karte)])

    # Der Aufruf ist zurueckgekehrt, obwohl die Analyse noch laeuft.
    assert dialog.analysis_running()
    assert angehalten.wait(30), "Worker ist nie angelaufen"

    # Der GUI-Thread arbeitet: Ereignisse laufen durch, der Balken steht.
    ende = time.monotonic() + 30
    while not dialog.progress_area.is_active() and time.monotonic() < ende:
        v4_app.processEvents()
        time.sleep(0.001)
    assert dialog.progress_area.is_active()
    assert dialog.progress_area.status_text()
    # Bedienbar heisst auch: Eingaben kommen an, waehrend der Worker rechnet.
    dialog.search_input.setText("COOP")
    v4_app.processEvents()
    assert dialog.search_input.text() == "COOP"

    weiter.set()
    warte_auf_analyse(dialog)
    assert len(dialog.transactions) == 6
    assert not dialog.progress_area.is_active()
    dialog.close()
    dialog.deleteLater()
    v4_app.processEvents()


def test_fortschritt_erreicht_den_bereich_aus_p1_2(v4_app, szenario):
    """Der Bereich wird angetrieben: Taetigkeit, Prozent und Stueckzahlen."""
    from views.bank_import_dialog_v4 import BankImportDialog

    conn, bank, karte = szenario
    dialog = BankImportDialog(conn)
    dialog.show()

    gesehen: list[tuple[str, int]] = []
    dialog.progress_area.bar.valueChanged.connect(
        lambda wert: gesehen.append((dialog.progress_area.status_text(), wert))
    )
    dialog._add_paths([str(bank), str(karte)])
    warte_auf_analyse(dialog)

    assert gesehen, "Der Fortschrittsbereich hat nie einen Wert bekommen"
    assert all(0 <= wert <= 100 for _text, wert in gesehen)
    # Jede Meldung nennt eine Taetigkeit - eine nackte Zahl gibt es nicht.
    assert all(text for text, _wert in gesehen)
    # Nach dem Ende ist der Bereich wieder verschwunden.
    assert not dialog.progress_area.isVisible()
    dialog.close()
    dialog.deleteLater()
    v4_app.processEvents()


def test_alle_phasen_haben_einen_uebersetzten_namen():
    """Kein Schritt meldet sich mit einem leeren oder rohen Bezeichner."""
    from views.bank_import_analysis_worker import phase_label

    for sprache in ("de", "en", "fr"):
        from utils.i18n import get_language, set_language

        vorher = get_language()
        try:
            set_language(sprache)
            for phase in ALL_PHASES:
                text = phase_label(phase)
                assert text, f"{sprache}/{phase} ohne Text"
                assert text != phase
        finally:
            set_language(vorher)


# ── Akzeptanz: Fehler werden in die UI zurueckgefuehrt ────────────────


def test_ein_fehler_im_worker_landet_als_meldung_im_dialog(
    v4_app, szenario, monkeypatch
):
    """Eine kaputte Datei bricht nicht still ab, sondern meldet sich."""
    import views.bank_import_dialog_v4 as v4
    from views.bank_import_dialog_v4 import BankImportDialog

    conn, bank, _karte = szenario
    meldungen: list[tuple[str, str]] = []
    monkeypatch.setattr(
        v4, "show_warning", lambda _eltern, titel, text: meldungen.append((titel, text))
    )

    import views.bank_import_analysis_worker as worker_modul

    def kaputt(_request, _sink=None):
        raise ValueError("Auszug unleserlich")

    monkeypatch.setattr(worker_modul, "analyse", kaputt)

    dialog = BankImportDialog(conn)
    dialog.show()
    dialog._add_paths([str(bank)])
    warte_auf_analyse(dialog)

    assert meldungen, "Der Fehler ist nirgends aufgetaucht"
    assert "Auszug unleserlich" in meldungen[-1][1]
    # Kein stehengebliebener Balken und kein gesperrtes Fenster.
    assert not dialog.progress_area.is_active()
    assert dialog.btn_add_files.isEnabled()
    dialog.close()
    dialog.deleteLater()
    v4_app.processEvents()


def test_eine_unlesbare_datei_wird_gemeldet_und_die_uebrigen_geladen(
    v4_app, szenario, monkeypatch
):
    """Der Sammelfehler je Datei bleibt erhalten - jetzt aus dem Worker."""
    import views.bank_import_dialog_v4 as v4
    from views.bank_import_dialog_v4 import BankImportDialog

    conn, bank, karte = szenario
    kaputt = karte.parent / "kaputt.csv"
    kaputt.write_text("nur eine Zeile ohne Kopf\n", encoding="utf-8")
    meldungen: list[tuple[str, str]] = []
    monkeypatch.setattr(
        v4, "show_warning", lambda _eltern, titel, text: meldungen.append((titel, text))
    )

    dialog = BankImportDialog(conn)
    dialog.show()
    dialog._add_paths([str(bank), str(kaputt)])
    warte_auf_analyse(dialog)

    assert len(dialog.sources) == 1
    assert meldungen and "kaputt.csv" in meldungen[-1][1]
    assert len(dialog.transactions) == 4
    dialog.close()
    dialog.deleteLater()
    v4_app.processEvents()


# ── Akzeptanz: der Worker wird sauber beendet ─────────────────────────


def test_schliessen_beendet_den_laufenden_worker_bevor_qt_ihn_abraeumt(
    v4_app, szenario, monkeypatch
):
    """Die Falle aus dem LifePlanner: ein zerstoerter, laufender QThread.

    "QThread: Destroyed while thread is still running" beendet den Prozess
    hart - nach dem Schliessen, wenn niemand mehr hinsieht. Deshalb muss der
    Thread nachweislich *vor* der Zerstoerung des Dialogs geendet haben.
    """
    import views.bank_import_analysis_worker as worker_modul
    from views.bank_import_dialog_v4 import BankImportDialog

    conn, bank, karte = szenario
    angelaufen = threading.Event()
    echtes_analyse = worker_modul.analyse

    def langsam(request, sink=None):
        sink = sink or ProgressSink()
        angelaufen.set()
        # Kooperativ: haengt, bis der Abbruch kommt, aber nie laenger.
        ende = time.monotonic() + 30
        while time.monotonic() < ende:
            if sink.cancelled():
                raise AnalysisCancelled()
            time.sleep(0.002)
        return echtes_analyse(request, sink)

    monkeypatch.setattr(worker_modul, "analyse", langsam)

    dialog = BankImportDialog(conn)
    dialog.show()
    dialog._add_paths([str(bank), str(karte)])
    assert angelaufen.wait(30), "Worker ist nie angelaufen"
    thread = dialog._analysis_thread
    assert thread is not None and thread.isRunning()

    dialog.close()

    assert not thread.isRunning(), "Der Thread lief beim Schliessen noch"
    assert not dialog.analysis_running()
    dialog.deleteLater()
    v4_app.processEvents()


def test_ein_haengender_thread_wird_geparkt_statt_zerstoert(
    v4_app, szenario, monkeypatch
):
    """Wenn das Warten nicht reicht, bleibt der Thread am Leben.

    Ein Worker, der den Abbruch nicht rechtzeitig sieht, darf trotzdem nicht
    mit dem Dialog abgeraeumt werden. Er wandert dann in eine Liste, die ihn
    haelt, bis er von selbst endet.
    """
    import views.bank_import_analysis_worker as worker_modul
    import views.bank_import_dialog_v4 as v4
    from views.bank_import_dialog_v4 import BankImportDialog

    conn, bank, _karte = szenario
    angelaufen = threading.Event()
    freigeben = threading.Event()

    def stur(_request, _sink=None):
        angelaufen.set()
        assert freigeben.wait(30), "Der Test hat den Worker nie freigegeben"
        raise AnalysisCancelled()

    monkeypatch.setattr(worker_modul, "analyse", stur)
    monkeypatch.setattr(v4, "_ANALYSIS_STOP_WAIT_MS", 50)

    dialog = BankImportDialog(conn)
    dialog.show()
    dialog._add_paths([str(bank)])
    assert angelaufen.wait(30), "Worker ist nie angelaufen"
    thread = dialog._analysis_thread

    dialog.close()
    assert thread in v4._PARKED_THREADS
    assert thread.isRunning()

    freigeben.set()
    ende = time.monotonic() + 30
    while thread in v4._PARKED_THREADS and time.monotonic() < ende:
        v4_app.processEvents()
        time.sleep(0.002)
    assert thread not in v4._PARKED_THREADS, "Der geparkte Thread wurde nie entlassen"
    dialog.deleteLater()
    v4_app.processEvents()


def test_kein_zweiter_lauf_solange_der_erste_arbeitet(v4_app, szenario, monkeypatch):
    """Zwei gleichzeitige Analysen haetten zwei Meinungen zur Pruefliste."""
    import views.bank_import_analysis_worker as worker_modul
    from views.bank_import_dialog_v4 import BankImportDialog

    conn, bank, karte = szenario
    angelaufen = threading.Event()
    weiter = threading.Event()
    echtes_analyse = worker_modul.analyse
    laeufe = []

    def gebremst(request, sink=None):
        laeufe.append(request)
        angelaufen.set()
        assert weiter.wait(30)
        return echtes_analyse(request, sink or ProgressSink())

    monkeypatch.setattr(worker_modul, "analyse", gebremst)

    dialog = BankImportDialog(conn)
    dialog.show()
    dialog._add_paths([str(bank)])
    assert angelaufen.wait(30)

    dialog._add_paths([str(karte)])
    assert not dialog.btn_add_files.isEnabled()

    weiter.set()
    warte_auf_analyse(dialog)
    assert len(laeufe) == 1
    assert len(dialog.sources) == 1
    dialog.close()
    dialog.deleteLater()
    v4_app.processEvents()


# ── Abbruchhaken fuer P1.4 ────────────────────────────────────────────


def test_die_rechnung_prueft_den_abbruch_an_ihren_schleifengrenzen(szenario):
    """``request_cancel`` wirkt kooperativ - ohne ``terminate()``.

    Der Vollausbau (Knopf, Mehrdateifortschritt, Windows-Dateihandles) ist
    P1.4; belegt ist hier nur, dass der Haken traegt.
    """
    conn, bank, karte = szenario
    request = AnalysisRequest(
        snapshot=capture_analysis_snapshot(conn),
        new_paths=(str(bank), str(karte)),
    )

    class _SofortAbbrechen(ProgressSink):
        def cancelled(self) -> bool:
            return True

    with pytest.raises(AnalysisCancelled):
        analyse(request, _SofortAbbrechen())


def test_worker_meldet_abbruch_statt_ergebnis(v4_app, szenario):
    """Ein abgebrochener Lauf liefert ``cancelled()`` und kein Ergebnis."""
    from views.bank_import_analysis_worker import BankImportAnalysisWorker

    conn, bank, _karte = szenario
    worker = BankImportAnalysisWorker(
        AnalysisRequest(
            snapshot=capture_analysis_snapshot(conn), new_paths=(str(bank),)
        )
    )
    gemeldet: list[str] = []
    worker.finished.connect(lambda _ergebnis: gemeldet.append("finished"))
    worker.failed.connect(lambda _text: gemeldet.append("failed"))
    worker.cancelled.connect(lambda: gemeldet.append("cancelled"))

    worker.request_cancel()
    worker.run()
    v4_app.processEvents()

    assert gemeldet == ["cancelled"]
