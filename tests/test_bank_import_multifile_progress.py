"""Multi-Datei-Fortschritt und Abbruch der Bankimport-Analyse (P1.4).

Zwei Dinge werden hier eingeloest, die bis P1.3 offen blieben.

**Ein Balken statt sieben.** Die Rechnung meldet Fortschritt je Phase und je
Datei. Wer das ungefiltert anzeigt, laesst den Balken an jeder Phasen- und
Dateigrenze auf null zurueckfallen - bei fuenf Dateien und sieben Phasen
fuenfunddreissig Mal. ``WeightedProgress`` legt daraus einen Gesamtfortschritt
zusammen, gewichtet nach Buchungszahl. Geprueft wird das nicht per Augenschein,
sondern an der mitgeschriebenen Folge aller gemeldeten Prozentwerte.

**Der Abbrechen-Knopf.** Er war in P1.3 bewusst unsichtbar, weil ihn nichts
bediente. Hier wird er verdrahtet - samt der Frage, die dabei wirklich weh tut:
ob nach einem Abbruch noch ein Dateihandle offen steht. Unter Windows liesse
sich die Datei danach weder loeschen noch verschieben. Behauptet wird das
nicht; der Test liest die offenen Dateideskriptoren des Prozesses.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pytest

from model.bank_import_analysis import (
    ALL_PHASES,
    GLOBAL_PHASES,
    PHASE_CATEGORIZE,
    PHASE_PARSE,
    PHASE_READ,
    AnalysisCancelled,
    AnalysisRequest,
    ProgressSink,
    analyse,
)
from model.bank_import_snapshot import capture_analysis_snapshot
from tests.conftest import warte_auf_analyse

ROOT = Path(__file__).resolve().parents[1]

KOPFZEILE = (
    "Datum;Buchungstext;Whg;Betrag Detail;ZKB-Referenz;Referenznummer;"
    "Belastung CHF;Gutschrift CHF;Valuta;Saldo CHF;Zahlungszweck;Details\n"
)


def schreibe_auszug(pfad: Path, zeilen: int, *, praefix: str = "A") -> Path:
    """Legt einen Bank-CSV-Auszug mit genau ``zeilen`` Buchungen an."""
    inhalt = [KOPFZEILE]
    for nummer in range(1, zeilen + 1):
        tag = (nummer % 28) + 1
        inhalt.append(
            f"{tag:02d}.03.2026;Kartenzahlung;CHF;12,50;ZKB-{praefix}{nummer};"
            f"REF-{praefix}{nummer};12,50;;{tag:02d}.03.2026;1'000,00;"
            f"{praefix}-HAENDLER {nummer};Filiale\n"
        )
    pfad.write_text("".join(inhalt), encoding="utf-8")
    return pfad


class Mitschrift(ProgressSink):
    """Schreibt jede Fortschrittsmeldung mit, in der Reihenfolge des Eingangs."""

    def __init__(self) -> None:
        self.phasen: list[str] = []
        self.prozente: list[int] = []
        self.dateien: list[tuple[int, int]] = []
        self.posten: list[tuple[int, int]] = []
        #: Prozentwert im Moment jeder Phasenmeldung - fuer Grenzenfragen.
        self.an_der_grenze: list[tuple[str, int]] = []

    def phase(self, phase: str) -> None:
        self.phasen.append(phase)
        self.an_der_grenze.append((phase, self.prozente[-1] if self.prozente else 0))

    def file(self, current: int, total: int) -> None:
        self.dateien.append((current, total))

    def items(self, current: int, total: int) -> None:
        self.posten.append((current, total))

    def percent(self, value: int | None) -> None:
        if value is not None:
            self.prozente.append(int(value))


def _lauf(conn, pfade: list[Path]) -> Mitschrift:
    """Faehrt eine vollstaendige Analyse und liefert die Mitschrift."""
    mitschrift = Mitschrift()
    analyse(
        AnalysisRequest(
            snapshot=capture_analysis_snapshot(conn),
            new_paths=tuple(str(pfad) for pfad in pfade),
        ),
        mitschrift,
    )
    return mitschrift


# ── Multi-Datei: globaler Fortschritt ────────────────────────────────


def test_der_fortschritt_faellt_ueber_alle_dateien_und_phasen_nie_zurueck(
    v4_conn, tmp_path
):
    """Monotonie, gemessen statt betrachtet.

    Die Folge aller gemeldeten Prozentwerte darf an keiner Stelle kleiner
    werden - weder an einer Phasengrenze noch beim Wechsel auf die naechste
    Datei. Eine Sichtpruefung wuerde genau den Ruecksprung uebersehen, der nur
    fuer einen Lidschlag sichtbar ist.
    """
    pfade = [
        schreibe_auszug(tmp_path / "eins.csv", 40, praefix="A"),
        schreibe_auszug(tmp_path / "zwei.csv", 120, praefix="B"),
        schreibe_auszug(tmp_path / "drei.csv", 8, praefix="C"),
    ]
    mitschrift = _lauf(v4_conn, pfade)

    assert mitschrift.prozente, "Es wurde ueberhaupt kein Fortschritt gemeldet"
    assert mitschrift.prozente == sorted(mitschrift.prozente)
    assert mitschrift.prozente[-1] == 100
    assert min(mitschrift.prozente) >= 0 and max(mitschrift.prozente) <= 100
    # Nicht nur zwei Stuetzstellen: der Balken laeuft wirklich durch.
    assert len(set(mitschrift.prozente)) > 10


def test_die_zweite_datei_faengt_nicht_wieder_bei_null_an(v4_conn, tmp_path):
    """Der Kern der Vorgabe: kein Nullpunkt je Datei.

    Beim Wechsel auf die naechste Datei beginnt wieder die Phase "Datei
    lesen". Frueher setzte genau das den Balken zurueck. Jetzt ist der Wert an
    jeder dieser Grenzen groesser als beim vorigen Dateibeginn.
    """
    pfade = [
        schreibe_auszug(tmp_path / f"datei{nummer}.csv", 30, praefix=f"D{nummer}")
        for nummer in range(1, 4)
    ]
    mitschrift = _lauf(v4_conn, pfade)

    dateigrenzen = [
        prozent for phase, prozent in mitschrift.an_der_grenze if phase == PHASE_READ
    ]
    assert len(dateigrenzen) == 3
    assert dateigrenzen[0] == 0
    assert dateigrenzen[1] > 0, "Datei 2 begann wieder bei null"
    assert dateigrenzen[2] > dateigrenzen[1], "Datei 3 begann nicht spaeter als 2"


def test_die_gewichtung_folgt_der_buchungszahl_und_nicht_der_dateizahl(
    v4_conn, tmp_path
):
    """Zwei Dateien, gleiche Anzahl - aber sehr verschiedene Groesse.

    Wuerde nach Dateien gezaehlt, stuende der Balken nach der ersten Datei in
    beiden Faellen bei derselben Zahl. Gewichtet nach Buchungen liegt die
    Grenze einmal weit vorne und einmal ganz hinten - genau daran haengt der
    Haken "moeglichst nach Anzahl Buchungen gewichtet".
    """
    klein_zuerst = _lauf(
        v4_conn,
        [
            schreibe_auszug(tmp_path / "klein.csv", 4, praefix="K"),
            schreibe_auszug(tmp_path / "gross.csv", 400, praefix="G"),
        ],
    )
    gross_zuerst = _lauf(
        v4_conn,
        [
            schreibe_auszug(tmp_path / "gross2.csv", 400, praefix="H"),
            schreibe_auszug(tmp_path / "klein2.csv", 4, praefix="L"),
        ],
    )

    def zweite_dateigrenze(mitschrift: Mitschrift) -> int:
        grenzen = [
            prozent
            for phase, prozent in mitschrift.an_der_grenze
            if phase == PHASE_READ
        ]
        assert len(grenzen) == 2
        return grenzen[1]

    nach_klein = zweite_dateigrenze(klein_zuerst)
    nach_gross = zweite_dateigrenze(gross_zuerst)

    assert nach_klein < 5, f"Die winzige Datei belegte {nach_klein} % des Balkens"
    assert nach_gross > 20, f"Die grosse Datei belegte nur {nach_gross} % des Balkens"
    assert nach_gross > nach_klein * 4


def test_die_datei_nummer_steigt_und_bleibt_im_rahmen(v4_conn, tmp_path):
    """ "Datei 3 von 5" ist eine Aussage ueber die Wirklichkeit.

    Sie wird auch in den Phasen gemeldet, die ueber alle Buchungen laufen -
    dort benennt sie die Quelle der gerade bearbeiteten Buchung. Rueckwaerts
    darf sie dabei nie laufen.
    """
    pfade = [
        schreibe_auszug(tmp_path / "a.csv", 20, praefix="A"),
        schreibe_auszug(tmp_path / "b.csv", 20, praefix="B"),
        schreibe_auszug(tmp_path / "c.csv", 20, praefix="C"),
    ]
    mitschrift = _lauf(v4_conn, pfade)

    assert mitschrift.dateien, "Die Dateiposition wurde nie gemeldet"
    nummern = [nummer for nummer, _gesamt in mitschrift.dateien]
    assert all(1 <= nummer <= gesamt for nummer, gesamt in mitschrift.dateien)
    assert max(nummern) == 3
    # Beim Lesen laeuft die Reihe einmal durch, danach je Durchgang ueber
    # alle Buchungen erneut. Innerhalb eines Durchgangs steigt sie streng.
    durchgaenge: list[list[int]] = [[]]
    for nummer in nummern:
        if durchgaenge[-1] and nummer <= durchgaenge[-1][-1]:
            durchgaenge.append([])
        durchgaenge[-1].append(nummer)
    assert durchgaenge[0] == [
        1,
        2,
        3,
    ], "Die Dateien wurden nicht der Reihe nach gelesen"
    assert len(durchgaenge) > 1, "Nach dem Lesen wurde keine Datei mehr benannt"
    for durchgang in durchgaenge:
        assert durchgang == sorted(durchgang)
        assert len(durchgang) == len(set(durchgang))


def test_alle_sieben_phasen_der_vorgabe_melden_sich(v4_conn, tmp_path):
    """Die Vorgabe nennt sieben Phasen; sieben werden auch gemeldet."""
    pfade = [
        schreibe_auszug(tmp_path / "x.csv", 12, praefix="X"),
        schreibe_auszug(tmp_path / "y.csv", 12, praefix="Y"),
    ]
    mitschrift = _lauf(v4_conn, pfade)

    assert len(ALL_PHASES) == 7
    assert set(mitschrift.phasen) == set(ALL_PHASES)
    # Die Phasen ueber alle Buchungen kommen genau einmal, die je Datei zweimal.
    for phase in GLOBAL_PHASES:
        assert mitschrift.phasen.count(phase) == 1, phase


# ── Multi-Datei: die Statuszeile aus der Vorgabe ─────────────────────


def test_die_statuszeile_hat_genau_die_form_aus_der_vorgabe(v4_app):
    """``Datei 3 von 5 · KI-Kategorisierung · 684 / 1242 · 55 %``"""
    from views.import_progress_area import ImportProgressArea

    bereich = ImportProgressArea()
    bereich.start("KI-Kategorisierung")
    bereich.set_file_progress(3, 5)
    bereich.set_item_counts(684, 1242)
    bereich.set_percent(55)

    assert bereich.status_text() == (
        "Datei 3 von 5 · KI-Kategorisierung · 684 / 1242 · 55 %"
    )
    bereich.deleteLater()


def test_die_stueckzahl_ueberschreibt_den_gesamtfortschritt_nicht(v4_app):
    """Beide Zahlen stehen nebeneinander und meinen Verschiedenes.

    ``684 / 1242`` ist die laufende Phase, ``55 %`` der ganze Lauf. Wuerde die
    Stueckzahl den Prozentwert weiterhin selbst ausrechnen, stuende hier 55
    statt der Phasenzahl - und der Balken zeigte wieder Phasenfortschritt.
    """
    from views.import_progress_area import ImportProgressArea

    bereich = ImportProgressArea()
    bereich.start("Duplikate prüfen")
    bereich.set_percent(31)
    bereich.set_item_counts(900, 1000)

    assert bereich.bar.value() == 31
    assert bereich.status_text().endswith("900 / 1000 · 31 %")
    bereich.deleteLater()


def test_bei_einer_einzigen_quelle_steht_keine_dateizeile(v4_app):
    """ "Datei 1 von 1" ist keine Information, sondern Zeilenlaenge."""
    from views.import_progress_area import ImportProgressArea

    bereich = ImportProgressArea()
    bereich.start("Datei lesen")
    bereich.set_file_progress(1, 1)
    bereich.set_percent(10)

    assert bereich.status_text() == "Datei lesen · 10 %"
    bereich.deleteLater()


@pytest.mark.parametrize("sprache", ["de", "en", "fr"])
def test_die_neuen_texte_stehen_in_allen_drei_sprachen(sprache):
    """Phasennamen und Dateizeile sind uebersetzbarer Text mit Platzhaltern."""
    import json

    werte = json.loads(
        (ROOT / "locales" / f"{sprache}.json").read_text(encoding="utf-8")
    )
    block = werte["import_progress"]
    for schluessel in (
        "phase_read",
        "phase_parse",
        "phase_duplicates",
        "phase_twint",
        "phase_categorize",
        "phase_tags",
        "phase_review",
        "file_position",
        "status_prefix",
    ):
        assert block.get(schluessel), f"{sprache}: {schluessel} fehlt"
    assert "{current}" in block["file_position"]
    assert "{total}" in block["file_position"]
    assert "{prefix}" in block["status_prefix"]
    assert "{status}" in block["status_prefix"]


# ── Abbruch: kooperativ, ohne terminate() ────────────────────────────


def test_der_abbruch_greift_auch_mitten_in_einer_phase(v4_conn, tmp_path):
    """Regelmaessige Pruefpunkte, nicht nur an den Phasengrenzen.

    Der Sink sagt erst mitten in der Kategorisierung "abbrechen". Traefe die
    Rechnung ihre Pruefpunkte nur an den Phasengrenzen, liefe sie die
    restlichen Zeilen trotzdem zu Ende.
    """
    pfad = schreibe_auszug(tmp_path / "gross.csv", 500, praefix="Z")

    class SpaeterAbbruch(ProgressSink):
        def __init__(self) -> None:
            self.phase_jetzt = ""
            self.gesehen = 0
            self.abbruch = False

        def phase(self, phase: str) -> None:
            self.phase_jetzt = phase

        def items(self, current: int, total: int) -> None:
            if self.phase_jetzt == PHASE_CATEGORIZE:
                self.gesehen = current

        def cancelled(self) -> bool:
            if self.phase_jetzt == PHASE_CATEGORIZE and self.gesehen >= 100:
                self.abbruch = True
            return self.abbruch

    sink = SpaeterAbbruch()
    with pytest.raises(AnalysisCancelled):
        analyse(
            AnalysisRequest(
                snapshot=capture_analysis_snapshot(v4_conn),
                new_paths=(str(pfad),),
            ),
            sink,
        )
    # Abgebrochen wurde frueh genug, dass der Rest nicht mehr lief.
    assert 100 <= sink.gesehen < 500


def test_nirgends_wird_ein_thread_abgeschossen():
    """``QThread.terminate()`` liesse halboffene Dateihandles zurueck.

    Geprueft am Syntaxbaum und nicht am Text: In den Erklaerungen daneben
    steht das Wort genau deshalb, weil es dort nicht aufgerufen wird.
    """
    import ast

    for modul in (
        "views/bank_import_analysis_worker.py",
        "views/bank_import_dialog_v4.py",
        "model/bank_import_analysis.py",
    ):
        pfad = ROOT / modul
        baum = ast.parse(pfad.read_text(encoding="utf-8"), filename=str(pfad))
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.Attribute):
                assert knoten.attr != "terminate", modul
                assert knoten.attr != "requestInterruption", modul


# ── Abbruch im laufenden Dialog ──────────────────────────────────────


@pytest.fixture
def gebremster_worker(monkeypatch):
    """Haelt die echte Analyse an einer waehlbaren Phase an.

    Bewusst kein Ersatz fuer ``analyse``: Die echte Rechnung laeuft, nur der
    Sink haelt sie an einer Phasengrenze fest. Damit prueft der Test den
    wirklichen Abbruchweg und nicht eine Attrappe.
    """

    import views.bank_import_analysis_worker as worker_modul

    echte = worker_modul.analyse
    steuerung: dict[str, object] = {}

    def einrichten(phase: str):
        angehalten = threading.Event()
        weiter = threading.Event()

        def gebremst(request, sink=None):
            basis = sink or ProgressSink()

            class Bremse(ProgressSink):
                def phase(self, name: str) -> None:
                    basis.phase(name)
                    if name == phase and not angehalten.is_set():
                        angehalten.set()
                        assert weiter.wait(30), "Der Test gab den Worker nie frei"

                def file(self, current: int, total: int) -> None:
                    basis.file(current, total)

                def items(self, current: int, total: int) -> None:
                    basis.items(current, total)

                def percent(self, value: int | None) -> None:
                    basis.percent(value)

                def cancelled(self) -> bool:
                    return basis.cancelled()

            return echte(request, Bremse())

        monkeypatch.setattr(worker_modul, "analyse", gebremst)
        steuerung["angehalten"] = angehalten
        steuerung["weiter"] = weiter
        return angehalten, weiter

    einrichten.steuerung = steuerung  # type: ignore[attr-defined]
    return einrichten


def _dialog_mit(conn, v4_app):
    from views.bank_import_dialog_v4 import BankImportDialog

    dialog = BankImportDialog(conn)
    dialog.show()
    v4_app.processEvents()
    return dialog


def test_der_abbrechen_knopf_ist_sichtbar_und_beendet_den_lauf(
    v4_app, v4_conn, tmp_path, gebremster_worker
):
    """Der Knopf aus P1.2 haengt jetzt am Abbruchweg aus P1.3.

    In P1.3 startete der Dialog den Bereich mit ``cancellable=False``: Ein
    sichtbarer Knopf ohne Wirkung waere schlimmer als keiner. Hier wird er
    sichtbar - und er wirkt.
    """
    angehalten, weiter = gebremster_worker(PHASE_CATEGORIZE)
    pfade = [
        str(schreibe_auszug(tmp_path / "eins.csv", 60, praefix="A")),
        str(schreibe_auszug(tmp_path / "zwei.csv", 60, praefix="B")),
    ]

    dialog = _dialog_mit(v4_conn, v4_app)
    dialog._add_paths(pfade)
    assert angehalten.wait(30), "Der Worker ist nie bis zur Bremse gekommen"

    ende = time.monotonic() + 30
    while not dialog.progress_area.is_active() and time.monotonic() < ende:
        v4_app.processEvents()
        time.sleep(0.001)
    assert dialog.progress_area.btn_cancel.isVisible()
    assert dialog.progress_area.btn_cancel.isEnabled()

    dialog.progress_area.btn_cancel.click()
    v4_app.processEvents()
    weiter.set()
    warte_auf_analyse(dialog)

    # Kein Ergebnis uebernommen, kein stehengebliebener Balken, kein
    # gesperrtes Fenster.
    assert dialog.sources == []
    assert dialog.transactions == []
    assert not dialog.progress_area.is_active()
    assert not dialog.progress_area.isVisible()
    assert dialog.btn_add_files.isEnabled()

    dialog.close()
    dialog.deleteLater()
    v4_app.processEvents()


def test_nach_dem_abbruch_laeuft_eine_neue_analyse_durch(
    v4_app, v4_conn, tmp_path, gebremster_worker
):
    """Ein Abbruch ist kein Endzustand - der naechste Versuch muss tragen."""
    angehalten, weiter = gebremster_worker(PHASE_CATEGORIZE)
    pfade = [
        str(schreibe_auszug(tmp_path / "eins.csv", 30, praefix="A")),
        str(schreibe_auszug(tmp_path / "zwei.csv", 30, praefix="B")),
    ]

    dialog = _dialog_mit(v4_conn, v4_app)
    dialog._add_paths(pfade)
    assert angehalten.wait(30)
    dialog.request_analysis_cancel()
    weiter.set()
    warte_auf_analyse(dialog)
    assert dialog.sources == []

    # Zweiter Anlauf, diesmal ohne Bremse: dieselben Dateien, volles Ergebnis.
    import views.bank_import_analysis_worker as worker_modul
    from model.bank_import_analysis import analyse as echte_analyse

    worker_modul.analyse = echte_analyse
    dialog._add_paths(pfade)
    warte_auf_analyse(dialog)

    assert len(dialog.sources) == 2
    assert len(dialog.transactions) == 60
    assert dialog.progress_area.isVisible() is False
    assert dialog.btn_add_files.isEnabled()

    dialog.close()
    dialog.deleteLater()
    v4_app.processEvents()


# ── Abbruch: keine offenen Dateihandles ──────────────────────────────

_FD_VERZEICHNIS = Path("/proc/self/fd")
ohne_proc = pytest.mark.skipif(
    not _FD_VERZEICHNIS.is_dir(),
    reason="Offene Dateideskriptoren sind nur ueber /proc pruefbar",
)


def offene_dateien() -> set[str]:
    """Alle Pfade, auf die dieser Prozess gerade einen Deskriptor haelt.

    Das ist die Linux-Entsprechung des Windows-Dateihandles. Auf Linux
    blockiert ein offener Deskriptor das Loeschen nicht - deshalb waere ein
    ``unlink()``-Test hier ohne Aussage, und deshalb wird stattdessen direkt
    nachgesehen.
    """
    offen: set[str] = set()
    for eintrag in _FD_VERZEICHNIS.iterdir():
        try:
            offen.add(os.readlink(str(eintrag)))
        except OSError:
            continue
    return offen


def minimales_pdf(pfad: Path) -> Path:
    """Ein echtes, gueltiges PDF - der einzige Leseweg mit eigenem Datenstrom."""
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with pfad.open("wb") as datei:
        writer.write(datei)
    return pfad


@ohne_proc
def test_nach_einem_abbruch_bleibt_kein_dateideskriptor_offen(v4_conn, tmp_path):
    """Der schwierigste Haken: nach Cancel unter Windows loesch-/verschiebbar.

    Alle Lesewege holen die Datei in einem ``with``-Block bzw. ueber
    ``read_bytes()`` und geben sie sofort wieder frei; der PDF-Leser wird im
    ``finally`` geschlossen. Geprueft wird das an den offenen Deskriptoren des
    Prozesses - vor dem Lauf, nach dem Abbruch und nach dem Fehlerfall.
    """
    csv_pfad = schreibe_auszug(tmp_path / "konto.csv", 200, praefix="C")
    pdf_pfad = minimales_pdf(tmp_path / "auszug.pdf")
    pfade = (str(csv_pfad), str(pdf_pfad))
    vorher = offene_dateien()

    class NachDemLesen(ProgressSink):
        """Bricht ab, sobald die erste Datei gelesen und erkannt ist."""

        def __init__(self) -> None:
            self.gelesen = False

        def phase(self, phase: str) -> None:
            if phase == PHASE_PARSE:
                self.gelesen = True

        def cancelled(self) -> bool:
            return self.gelesen

    request = AnalysisRequest(
        snapshot=capture_analysis_snapshot(v4_conn), new_paths=pfade
    )
    with pytest.raises(AnalysisCancelled):
        analyse(request, NachDemLesen())

    nachher = offene_dateien()
    for pfad in pfade:
        assert pfad not in nachher, f"Nach dem Abbruch noch offen: {pfad}"
    assert nachher - vorher == set() or not (nachher - vorher) & set(pfade)

    # Und der vollstaendige Lauf, inklusive des scheiternden PDF-Wegs.
    ergebnis = analyse(
        AnalysisRequest(snapshot=capture_analysis_snapshot(v4_conn), new_paths=pfade)
    )
    assert ergebnis.errors, "Das leere PDF haette gemeldet werden muessen"
    for pfad in pfade:
        assert pfad not in offene_dateien(), f"Nach dem Lauf noch offen: {pfad}"


def test_die_quelldateien_lassen_sich_nach_dem_abbruch_bewegen(v4_conn, tmp_path):
    """Die Windows-Frage, so weit sie sich auf Linux stellen laesst.

    Loeschen und Umbenennen gelingen auf Linux auch bei offenem Deskriptor -
    dieser Teil ist deshalb nur die Zusicherung, dass die Anwendung die Datei
    nicht anderweitig festhaelt (Sperre, Kopie, verzoegertes Schreiben). Die
    Aussage mit Gewicht steht im Test darueber.
    """
    csv_pfad = schreibe_auszug(tmp_path / "beweglich.csv", 120, praefix="M")
    pdf_pfad = minimales_pdf(tmp_path / "beweglich.pdf")

    class SofortNachDemLesen(ProgressSink):
        def __init__(self) -> None:
            self.gelesen = False

        def phase(self, phase: str) -> None:
            if phase == PHASE_PARSE:
                self.gelesen = True

        def cancelled(self) -> bool:
            return self.gelesen

    with pytest.raises(AnalysisCancelled):
        analyse(
            AnalysisRequest(
                snapshot=capture_analysis_snapshot(v4_conn),
                new_paths=(str(csv_pfad), str(pdf_pfad)),
            ),
            SofortNachDemLesen(),
        )

    verschoben = csv_pfad.with_name("woanders.csv")
    csv_pfad.rename(verschoben)
    assert verschoben.is_file()
    verschoben.unlink()
    pdf_pfad.unlink()
    assert not verschoben.exists() and not pdf_pfad.exists()
