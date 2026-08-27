"""Thread-Grenze der Bankimport-Analyse.

Die Analyse soll spaeter in einem Worker laufen. Eine ``sqlite3.Connection``
gehoert aber dem Thread, der sie geoeffnet hat, und die BudgetManager-DB ist
verschluesselt - der Worker koennte also nicht einfach eine zweite Verbindung
aufmachen. Diese Tests halten fest, dass die Analysedaten vorher eingefroren
werden und die Rechnung danach ohne Datenbank auskommt.

Die Beweisfuehrung ist bewusst hart: der Snapshot wird gezogen, die
Verbindung geschlossen, und erst danach gerechnet. Wer wieder eine Abfrage
einbaut, bekommt hier einen ``ProgrammingError`` statt eines gruenen Laufs.
"""

from __future__ import annotations

import dataclasses
import queue
import sqlite3
import threading
from datetime import date
from decimal import Decimal

import pytest

from model.bank_import_ai import AIPrediction, BankImportAI
from model.bank_import_service import BankImportItem, external_id
from model.bank_import_snapshot import (
    BankImportAnalysisSnapshot,
    capture_analysis_snapshot,
)
from model.bank_statement_reader import BankTransaction
from model.tags_model import TagsModel
from model.twint_import_policy import (
    BankImportMarkerStore,
    TwintAwareBankImportService,
)
from model.typ_constants import TYP_EXPENSES, TYP_INCOME
from tests.conftest import (
    V4_DIGEST,
    V4_KATEGORIE,
    V4_KATEGORIE_ZWEI,
    warte_auf_analyse,
)

_DIGEST = V4_DIGEST


def _tx(
    index: int,
    *,
    description: str,
    amount: str,
    counterparty: str = "",
    tag: date | None = None,
) -> BankTransaction:
    return BankTransaction(
        source_kind="csv",
        source_name="konto.csv",
        source_index=index,
        booking_date=tag or date(2026, 3, 17),
        amount=Decimal(amount),
        currency="CHF",
        description=description,
        counterparty=counterparty,
        raw={},
    )


def _befuellte_db(v4_conn: sqlite3.Connection) -> sqlite3.Connection:
    """Legt Lernstoff an: KI-Gedaechtnis, Tag-Regel, Marker, Importzustand."""
    tags = TagsModel(v4_conn)
    tags.create_tag("Lebensmittel")
    tags.create_tag("Geteilte Kosten")
    ai = BankImportAI(v4_conn)
    ai.learn(
        typ=TYP_EXPENSES,
        category=V4_KATEGORIE,
        description="COOP SUPERMARKT WINTERTHUR 123456",
        counterparty="COOP",
        tags=("Lebensmittel", "Geteilte Kosten"),
    )
    ai.learn(
        typ=TYP_EXPENSES,
        category=V4_KATEGORIE_ZWEI,
        description="SBB BILLETT ZUERICH",
        counterparty="SBB",
    )
    ai.learn(
        typ=TYP_INCOME,
        category=V4_KATEGORIE,
        description="LOHN MAERZ",
        counterparty="ARBEITGEBER",
    )
    ai.set_tag_allocation_rule("Lebensmittel", 50, priority=10)

    marker = BankImportMarkerStore(v4_conn)
    marker.mark_classifications(
        [
            (
                _tx(7, description="TWINT Gutschrift", amount="20.00"),
                TYP_EXPENSES,
                V4_KATEGORIE,
            )
        ],
        _DIGEST,
        marker_kind="twint_credit",
    )

    service = TwintAwareBankImportService(v4_conn)
    service.import_items(
        [
            BankImportItem(
                transaction=_tx(3, description="MIGROS ZUERICH", amount="-24.50"),
                typ=TYP_EXPENSES,
                category=V4_KATEGORIE,
                tags=(),
                amount=24.50,
                details="Testbuchung",
            )
        ],
        document_digest=_DIGEST,
    )
    return v4_conn


def _sammle_objekte(wert, gesehen: set[int], treffer: list[object]) -> None:
    if id(wert) in gesehen:
        return
    gesehen.add(id(wert))
    treffer.append(wert)
    if dataclasses.is_dataclass(wert) and not isinstance(wert, type):
        for feld in dataclasses.fields(wert):
            _sammle_objekte(getattr(wert, feld.name), gesehen, treffer)
        return
    if isinstance(wert, dict):
        for schluessel, inhalt in wert.items():
            _sammle_objekte(schluessel, gesehen, treffer)
            _sammle_objekte(inhalt, gesehen, treffer)
        return
    if isinstance(wert, (list, tuple, set, frozenset)):
        for inhalt in wert:
            _sammle_objekte(inhalt, gesehen, treffer)
        return
    try:
        inhalte = dict(wert)
    except (TypeError, ValueError):
        return
    for schluessel, inhalt in inhalte.items():
        _sammle_objekte(schluessel, gesehen, treffer)
        _sammle_objekte(inhalt, gesehen, treffer)


def test_snapshot_enthaelt_weder_verbindung_noch_db_gebundene_ki(v4_conn):
    """Nichts im Snapshot darf noch an der Datenbank haengen."""
    snapshot = capture_analysis_snapshot(_befuellte_db(v4_conn))

    treffer: list[object] = []
    _sammle_objekte(snapshot, set(), treffer)
    verboten = (
        sqlite3.Connection,
        sqlite3.Cursor,
        BankImportAI,
        TagsModel,
        BankImportMarkerStore,
        TwintAwareBankImportService,
    )
    gefunden = [obj for obj in treffer if isinstance(obj, verboten)]
    assert not gefunden, f"DB-gebundene Objekte im Snapshot: {gefunden}"
    assert not any(
        hasattr(obj, "conn") for obj in treffer if not isinstance(obj, type)
    ), "Ein Snapshot-Bestandteil traegt noch ein conn-Attribut"


def test_snapshot_ist_nur_lesbar(v4_conn):
    """Der Worker darf den eingefrorenen Stand nicht verschieben koennen."""
    snapshot = capture_analysis_snapshot(_befuellte_db(v4_conn))

    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.ai = None
    with pytest.raises(TypeError):
        snapshot.markers["x"] = None
    with pytest.raises(TypeError):
        snapshot.ai.merchant_memory[("x", TYP_EXPENSES)] = None
    with pytest.raises(TypeError):
        snapshot.category_tree[TYP_EXPENSES] = ()
    assert isinstance(snapshot.imported_external_ids, frozenset)
    assert isinstance(snapshot.ai.tag_rules, tuple)
    # Eine ausgehaendigte Tagmenge ist eine Kopie: wer sie aendert, aendert
    # den Snapshot nicht mit.
    kopie = snapshot.tags_for_category(TYP_EXPENSES, V4_KATEGORIE)
    kopie.add("Fremdes Tag")
    assert "Fremdes Tag" not in snapshot.tags_for_category(TYP_EXPENSES, V4_KATEGORIE)


@pytest.mark.parametrize(
    ("typ", "beschreibung", "gegenpartei"),
    [
        (TYP_EXPENSES, "COOP SUPERMARKT WINTERTHUR 987654", "COOP"),
        (TYP_EXPENSES, "COOP SUPERMARKT", "COOP"),
        (TYP_EXPENSES, "SBB BILLETT BERN", "SBB"),
        (TYP_EXPENSES, "Voellig unbekannter Text", "Fremd"),
        (TYP_EXPENSES, "", ""),
        (TYP_INCOME, "LOHN APRIL", "ARBEITGEBER"),
    ],
)
def test_snapshot_sagt_dasselbe_voraus_wie_die_datenbank_ki(
    v4_conn, typ, beschreibung, gegenpartei
):
    """Bestehende Prediction-Ergebnisse bleiben Zeichen fuer Zeichen gleich."""
    conn = _befuellte_db(v4_conn)
    ai = BankImportAI(conn)
    snapshot = capture_analysis_snapshot(conn)

    aus_db = ai.predict(typ=typ, description=beschreibung, counterparty=gegenpartei)
    aus_snapshot = snapshot.predict(
        typ=typ, description=beschreibung, counterparty=gegenpartei
    )
    assert isinstance(aus_snapshot, AIPrediction)
    assert aus_snapshot == aus_db


def test_snapshot_liefert_dieselben_duplikate_marker_und_tagregeln(v4_conn):
    conn = _befuellte_db(v4_conn)
    ai = BankImportAI(conn)
    marker = BankImportMarkerStore(conn)
    service = TwintAwareBankImportService(conn)
    snapshot = capture_analysis_snapshot(conn)

    zeilen = [
        _tx(3, description="MIGROS ZUERICH", amount="-24.50"),
        _tx(7, description="TWINT Gutschrift", amount="20.00"),
        _tx(9, description="Neue Zeile", amount="-5.00"),
    ]
    assert snapshot.duplicate_indexes(zeilen, _DIGEST) == service.duplicate_indexes(
        zeilen, _DIGEST
    )
    assert snapshot.duplicate_indexes(zeilen, _DIGEST) == {0}
    assert snapshot.marked_indexes(
        zeilen, _DIGEST, marker_kind="twint_credit"
    ) == marker.marked_indexes(zeilen, _DIGEST, marker_kind="twint_credit")
    assert snapshot.classification(
        zeilen[1], _DIGEST, marker_kind="twint_credit"
    ) == marker.classification(zeilen[1], _DIGEST, marker_kind="twint_credit")
    assert snapshot.suggest_category(zeilen[1]) == marker.suggest_category(zeilen[1])
    assert snapshot.allocation_for_tags(("Lebensmittel",)) == ai.allocation_for_tags(
        ("Lebensmittel",)
    )
    # Unbekannte Tags muessen weiterhin ValueError ausloesen; der Dialog faengt
    # genau diesen Fall ab, wenn ein Tag zwischenzeitlich geloescht wurde.
    with pytest.raises(ValueError):
        snapshot.allocation_for_tags(("Gibt es nicht",))


def test_analyse_rechnet_nach_dem_schliessen_der_verbindung_weiter(v4_conn):
    """Der haerteste Beleg: ohne Verbindung darf nichts mehr fehlen."""
    conn = _befuellte_db(v4_conn)
    snapshot = capture_analysis_snapshot(conn)
    zeilen = [
        _tx(3, description="MIGROS ZUERICH", amount="-24.50"),
        _tx(7, description="TWINT Gutschrift", amount="20.00"),
        _tx(
            9,
            description="COOP SUPERMARKT WINTERTHUR 5",
            amount="-11.00",
            counterparty="COOP",
        ),
    ]
    conn.close()

    assert snapshot.duplicate_indexes(zeilen, _DIGEST) == {0}
    assert snapshot.marked_indexes(zeilen, _DIGEST, marker_kind="twint_credit") == {1}
    assert snapshot.classification(zeilen[1], _DIGEST) == (TYP_EXPENSES, V4_KATEGORIE)
    assert snapshot.suggest_category(zeilen[1]) == (TYP_EXPENSES, V4_KATEGORIE)
    vorhersage = snapshot.predict(
        typ=TYP_EXPENSES, description=zeilen[2].description, counterparty="COOP"
    )
    assert vorhersage.category == V4_KATEGORIE
    assert vorhersage.method == "merchant_memory"
    assert vorhersage.allocation_percent == 50.0
    assert snapshot.tags_for_category(TYP_EXPENSES, V4_KATEGORIE) == set()
    assert [name for _anzeige, name in snapshot.category_tree_for(TYP_EXPENSES)] == [
        V4_KATEGORIE,
        V4_KATEGORIE_ZWEI,
    ]


def test_analyse_laeuft_in_fremdem_thread_ohne_die_gui_verbindung(v4_conn):
    """Ein echter Fremd-Thread rechnet aus dem Snapshot - ohne SQLite."""
    conn = _befuellte_db(v4_conn)
    snapshot = capture_analysis_snapshot(conn)
    zeilen = [
        _tx(3, description="MIGROS ZUERICH", amount="-24.50"),
        _tx(
            9,
            description="COOP SUPERMARKT WINTERTHUR 5",
            amount="-11.00",
            counterparty="COOP",
        ),
    ]

    ergebnisse: queue.Queue = queue.Queue()

    def _arbeiten() -> None:
        try:
            ergebnisse.put(
                (
                    "ok",
                    (
                        snapshot.duplicate_indexes(zeilen, _DIGEST),
                        snapshot.predict(
                            typ=TYP_EXPENSES,
                            description=zeilen[1].description,
                            counterparty="COOP",
                        ),
                    ),
                )
            )
        except Exception as exc:
            # Der Test will jeden Fehler des Fremd-Threads sehen, nicht nur
            # den erwarteten - sonst bliebe er stumm gruen.
            ergebnisse.put(("fehler", exc))

    worker = threading.Thread(target=_arbeiten, name="bankimport-analyse")
    worker.start()
    worker.join(timeout=15)
    assert not worker.is_alive(), "Analyse-Thread haengt"

    zustand, wert = ergebnisse.get_nowait()
    assert zustand == "ok", f"Analyse im Fremd-Thread scheiterte: {wert}"
    duplikate, vorhersage = wert
    assert duplikate == {0}
    assert vorhersage == snapshot.predict(
        typ=TYP_EXPENSES, description=zeilen[1].description, counterparty="COOP"
    )
    # Gegenprobe: dieselbe Rechnung ueber die Verbindung waere im Fremd-Thread
    # ein Fehler. Ohne diesen Nachweis koennte der Test auch dann gruen sein,
    # wenn SQLite den Zugriff gar nicht bemaengelt.
    fehler: queue.Queue = queue.Queue()

    def _mit_verbindung() -> None:
        try:
            BankImportAI(conn).predict(
                typ=TYP_EXPENSES, description="MIGROS", counterparty=""
            )
            fehler.put(None)
        except sqlite3.ProgrammingError as exc:
            fehler.put(exc)

    zweiter = threading.Thread(target=_mit_verbindung, name="bankimport-db")
    zweiter.start()
    zweiter.join(timeout=15)
    assert isinstance(fehler.get_nowait(), sqlite3.ProgrammingError)


def test_dialog_analyse_kommt_ohne_die_db_modelle_aus(v4_dialog, v4_tx, monkeypatch):
    """Der V4-Dialog darf waehrend der Analyse keine Modelle mehr befragen."""
    dialog = v4_dialog(
        [
            v4_tx(0, description="MIGROS ZUERICH", amount="-24.50"),
            v4_tx(1, description="TWINT Gutschrift", amount="20.00"),
        ]
    )

    def _verboten(*args, **kwargs):
        raise AssertionError("Analyse hat wieder ein DB-gebundenes Modell befragt")

    for objekt, name in (
        (dialog.ai, "predict"),
        (dialog.ai, "allocation_for_tags"),
        (dialog.service, "duplicate_indexes"),
        (dialog.marker_store, "marked_indexes"),
        (dialog.marker_store, "classification"),
        (dialog.marker_store, "suggest_category"),
        (dialog.tags, "get_tag_ids_for_category_name"),
    ):
        monkeypatch.setattr(objekt, name, _verboten)

    dialog._rebuild_from_sources()

    warte_auf_analyse(dialog)

    assert len(dialog.states) == 2
    assert dialog._effective_amount(0)[0] == pytest.approx(24.50)
    assert dialog._all_tags(0) == ()
    assert isinstance(dialog.snapshot, BankImportAnalysisSnapshot)


def test_dialog_zieht_den_snapshot_vor_jeder_analyse_neu(v4_dialog, v4_tx):
    """Neu Gelerntes muss im naechsten Snapshot ankommen.

    Ein einmal gezogener Snapshot waere sonst genau die Sorte Zwischenspeicher,
    die nach dem ersten Import veraltet ist und alte Vorschlaege wiederholt.
    """
    dialog = v4_dialog([v4_tx(0, description="COOP", amount="-9.00")])
    assert dialog.snapshot.predict(typ=TYP_EXPENSES, description="COOP").category == ""

    BankImportAI(dialog.conn).learn(
        typ=TYP_EXPENSES,
        category=V4_KATEGORIE,
        description="COOP",
        counterparty="",
    )
    dialog._rebuild_from_sources()
    warte_auf_analyse(dialog)

    frisch = dialog.snapshot.predict(typ=TYP_EXPENSES, description="COOP")
    assert frisch.category == V4_KATEGORIE
    assert frisch.method == "merchant_memory"


def test_externe_import_ids_stehen_im_snapshot(v4_conn):
    """Die Duplikatinformation liegt als reine Menge von IDs vor."""
    conn = _befuellte_db(v4_conn)
    snapshot = capture_analysis_snapshot(conn)
    bekannte = external_id(
        _tx(3, description="MIGROS ZUERICH", amount="-24.50"), _DIGEST
    )

    assert bekannte in snapshot.imported_external_ids
    assert isinstance(snapshot.imported_external_ids, frozenset)


def test_neu_angelegtes_tag_landet_sofort_im_snapshot(
    v4_dialog, v4_tx, v4_helfer, monkeypatch
):
    """Ein im Tag-Dialog neu erstelltes Tag muss sofort im Snapshot stehen.

    Der Snapshot ist ein eingefrorener Stand - genau deshalb muss er dort neu
    gezogen werden, wo die Oberflaeche selbst Stammdaten anlegt. Sonst haelt
    die Analyse das gerade erzeugte Tag fuer unbekannt, verwirft still den
    Kostenanteil und rechnet mit dem vollen Betrag.
    """
    import views.bank_import_dialog_v4 as v4

    dialog = v4_dialog([v4_tx(0, description="MIGROS ZUERICH", amount="-24.50")])
    v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE)
    v4_helfer.haken_setzen(dialog, 0, True)

    class _TagDialogAttrappe:
        """Verhaelt sich wie der echte Tag-Dialog samt Tag-Neuanlage."""

        def __init__(self, tags, **_kwargs):
            self._tags = tags

        def exec(self):
            from PySide6.QtWidgets import QDialog

            self._tags.create_tag("Frisch erstellt")
            return QDialog.DialogCode.Accepted

        def tag_states(self):
            from PySide6.QtCore import Qt

            return {"Frisch erstellt": Qt.CheckState.Checked}

    monkeypatch.setattr(v4, "TagSelectionDialog", _TagDialogAttrappe)
    dialog._edit_tags_for_checked()

    assert dialog.states[0].manual_tags == {"Frisch erstellt"}
    # Der Snapshot kennt das Tag; ohne Nachziehen fiele hier ein ValueError an
    # und der Kostenanteil verschwaende lautlos.
    assert dialog.snapshot.allocation_for_tags(("Frisch erstellt",)) == (None, "")
    assert dialog._effective_amount(0)[0] == pytest.approx(24.50)
    posten = dialog._build_item(0)
    assert posten is not None
    assert posten.tags == ("Frisch erstellt",)
