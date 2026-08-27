"""P2.1 - Zentrale KI-Einstellungen: Schalter, Lernstand und Reset.

Der heikelste Teil ist der Reset. Er darf **genau** den Lernspeicher der
Import-KI leeren und nichts sonst; ein Reset, der zu viel loescht, ist ein
Datenverlust ohne Rueckweg. Die Beweisfuehrung hier legt darum zuerst in
*allen* betroffenen und in *allen* geschuetzten Tabellen echte Daten an,
fotografiert die Datenbank, setzt zurueck und vergleicht das Bild.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from model.ai_learning_store import (
    PROTECTED_TABLES,
    RESET_TABLES,
    learning_stats,
    reset_learning_data,
)
from model.bank_import_ai import BankImportAI, _fingerprint
from model.bank_import_service import BankImportItem
from model.bank_statement_reader import BankTransaction
from model.migrations import migrate_all
from model.twint_import_policy import BankImportMarkerStore, TwintAwareBankImportService
from model.typ_constants import TYP_EXPENSES, TYP_INCOME
from tests.conftest import verbindung_merken

ROOT = Path(__file__).resolve().parents[1]

#: Die vier Tabellen, die ein Reset leeren darf - hier bewusst ausgeschrieben
#: und nicht aus ``RESET_TABLES`` uebernommen. Ein Test, der seine Erwartung
#: aus dem Pruefling holt, waechst stillschweigend mit jedem Versehen mit.
ERLAUBT_ZU_LEEREN = {
    "ai_merchant_memory",
    "ai_twint_memory",
    "ai_feedback",
    "ai_tag_rules",
}

AUSGABE = "Lebensmittel"
EINNAHME = "Lohn"
DIGEST = "c" * 64


def _tx(
    index: int,
    *,
    description: str,
    amount: str,
    counterparty: str = "",
    source_name: str = "konto.csv",
) -> BankTransaction:
    return BankTransaction(
        source_kind="csv",
        source_name=source_name,
        source_index=index,
        booking_date=date(2026, 4, 3),
        amount=Decimal(amount),
        currency="CHF",
        description=description,
        counterparty=counterparty,
        raw={},
    )


@pytest.fixture
def voll_befuellte_db():
    """Eine Datenbank, in der jede beteiligte Tabelle echte Zeilen hat.

    "Echt" heisst hier: ueber die produktiven Schreibwege angelegt, nicht per
    INSERT nachgebaut. Sonst prueft der Test seine eigene Attrappe.
    """
    from model.category_model import CategoryModel
    from model.savings_goals_model import SavingsGoalsModel
    from model.tags_model import TagsModel

    conn = verbindung_merken(sqlite3.connect(":memory:"))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_all(conn)

    kategorien = CategoryModel(conn)
    for typ in (TYP_EXPENSES, TYP_INCOME):
        kategorien.create(typ, AUSGABE if typ == TYP_EXPENSES else EINNAHME)
    tags = TagsModel(conn)
    tags.create_tag("Haushalt", action_text="")

    # Budget, Sparziel und eine Kategorie-Tag-Bindung.
    conn.execute(
        "INSERT INTO budget(year, month, typ, category, amount) VALUES(?,?,?,?,?)",
        (2026, 4, TYP_EXPENSES, AUSGABE, 400.0),
    )
    SavingsGoalsModel(conn).create("Notgroschen", 5000.0, current_amount=250.0)
    kategorie_id = conn.execute(
        "SELECT id FROM categories WHERE typ=? AND name=?", (TYP_EXPENSES, AUSGABE)
    ).fetchone()[0]
    tag_id = conn.execute("SELECT id FROM tags WHERE name=?", ("Haushalt",)).fetchone()[
        0
    ]
    conn.execute(
        "INSERT INTO category_tags(category_id, tag_id) VALUES(?,?)",
        (kategorie_id, tag_id),
    )
    conn.commit()

    # Ein echter Bankimport: schreibt tracking, entry_tags, bank_import_state
    # und in einem Aufwasch das Haendlergedaechtnis samt Lernbeispiel.
    service = TwintAwareBankImportService(conn)
    service.import_items(
        [
            BankImportItem(
                transaction=_tx(0, description="MIGROS ZUERICH", amount="-42.50"),
                typ=TYP_EXPENSES,
                category=AUSGABE,
                tags=("Haushalt",),
                amount=42.50,
                details="MIGROS ZUERICH",
            )
        ],
        document_digest=DIGEST,
    )

    # Ein TWINT-Eingang: schreibt bank_import_marker_state und ai_twint_memory.
    marker = BankImportMarkerStore(conn)
    marker.mark_classifications(
        [(_tx(1, description="TWINT von Anna", amount="12.00"), TYP_EXPENSES, AUSGABE)],
        DIGEST,
    )

    # Lernmetadaten: eine Kostenanteil-Regel.
    BankImportAI(conn).set_tag_allocation_rule("Haushalt", 50, priority=5)
    conn.commit()
    return conn


def _tabellen(conn: sqlite3.Connection) -> list[str]:
    return sorted(
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    )


def _abzug(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Vollstaendiger Inhalt aller Tabellen als vergleichbarer Abzug.

    Nicht nur Zeilenzahlen: Ein Reset, der eine Zeile *aendert*, statt sie zu
    loeschen, waere ueber eine Zaehlung unsichtbar.
    """
    abzug: dict[str, list[str]] = {}
    for tabelle in _tabellen(conn):
        if tabelle.startswith("sqlite_"):
            continue
        zeilen = conn.execute("SELECT * FROM " + tabelle).fetchall()
        abzug[tabelle] = sorted(json.dumps(list(z), default=str) for z in zeilen)
    return abzug


# ── Der Reset: was er leert und was er anfassen darf ────────────────────────


def test_reset_leert_genau_die_drei_ki_bereiche(voll_befuellte_db):
    """KI-Memory, KI-Feedback und KI-Lernmetadaten sind danach leer."""
    conn = voll_befuellte_db
    vorher = learning_stats(conn)
    assert vorher.merchant_patterns == 1
    assert vorher.twint_patterns == 1
    assert vorher.feedback_examples == 1
    assert vorher.tag_rules == 1
    assert not vorher.is_empty

    geloescht = reset_learning_data(conn)

    assert geloescht == vorher, "Der Reset meldet, was er wirklich geloescht hat"
    for tabelle in RESET_TABLES:
        zahl = conn.execute("SELECT COUNT(*) FROM " + tabelle).fetchone()[0]
        assert zahl == 0, f"{tabelle} ist nach dem Reset nicht leer"
    assert learning_stats(conn).is_empty


def test_reset_laesst_jede_andere_tabelle_bitgenau_stehen(voll_befuellte_db):
    """Alles ausserhalb des Lernspeichers bleibt Zeile fuer Zeile identisch."""
    conn = voll_befuellte_db
    vorher = _abzug(conn)
    reset_learning_data(conn)
    nachher = _abzug(conn)

    assert set(vorher) == set(nachher), "Der Reset hat Tabellen angelegt oder entfernt"
    veraendert = {name for name in vorher if vorher[name] != nachher[name]}
    assert veraendert == ERLAUBT_ZU_LEEREN, (
        "Nur der Lernspeicher darf sich aendern - veraendert wurde: "
        f"{sorted(veraendert)}"
    )


def test_die_geschuetzten_tabellen_sind_im_test_wirklich_gefuellt(voll_befuellte_db):
    """Gegenprobe zum Test darueber: leere Tabellen beweisen nichts.

    Ohne diese Zusicherung koennte der Vergleich oben gruen bleiben, weil in
    Tracking, Budget und Co. schlicht nichts drinsteht.
    """
    conn = voll_befuellte_db
    for tabelle in PROTECTED_TABLES:
        zahl = conn.execute("SELECT COUNT(*) FROM " + tabelle).fetchone()[0]
        assert zahl > 0, f"{tabelle} ist leer - der Reset-Beweis waere wertlos"


def test_reset_erhaelt_die_duplikaterkennung(voll_befuellte_db):
    """Nach dem Reset gilt eine bereits importierte Zeile weiter als Duplikat.

    Das ist die gefaehrlichste Verwechslung: ``bank_import_state`` sieht wie
    KI-Daten aus, ist aber die Duplikaterkennung. Wer sie mitloescht, bereitet
    Doppelbuchungen vor.
    """
    conn = voll_befuellte_db
    service = TwintAwareBankImportService(conn)
    tx = _tx(0, description="MIGROS ZUERICH", amount="-42.50")
    assert service.is_duplicate(tx, DIGEST)

    reset_learning_data(conn)

    assert service.is_duplicate(tx, DIGEST)
    ergebnis = service.import_items(
        [
            BankImportItem(
                transaction=tx,
                typ=TYP_EXPENSES,
                category=AUSGABE,
                tags=(),
                amount=42.50,
                details="MIGROS ZUERICH",
            )
        ],
        document_digest=DIGEST,
    )
    assert ergebnis.imported == 0
    assert ergebnis.skipped_duplicates == 1
    assert conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 1


def test_reset_macht_die_ki_wieder_ahnungslos(voll_befuellte_db):
    """Vor dem Reset sagt die KI etwas voraus, danach nichts mehr."""
    conn = voll_befuellte_db
    ai = BankImportAI(conn)
    vorher = ai.predict(typ=TYP_EXPENSES, description="MIGROS ZUERICH")
    assert vorher.category == AUSGABE

    reset_learning_data(conn)

    nachher = ai.predict(typ=TYP_EXPENSES, description="MIGROS ZUERICH")
    assert nachher.category == ""
    assert nachher.confidence == 0.0


def test_reset_auf_frischer_datenbank_ohne_ki_tabellen():
    """Wer nie importiert hat, darf am Reset nicht scheitern."""
    conn = verbindung_merken(sqlite3.connect(":memory:"))
    migrate_all(conn)
    assert "ai_merchant_memory" not in _tabellen(conn)

    assert learning_stats(conn).is_empty
    assert reset_learning_data(conn).is_empty


class _StolpernBeiTagRegeln:
    """Reicht alles an die echte Verbindung weiter - bis auf eine Anweisung.

    ``sqlite3.Connection`` laesst sich nicht monkeypatchen (die Attribute
    liegen im C-Typ), deshalb dieser duenne Vorbau. Er faellt bewusst beim
    *letzten* der vier DELETEs um: Die drei davor sind dann bereits
    ausgefuehrt, und nur eine echte Transaktionsklammer holt sie zurueck.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @property
    def in_transaction(self) -> bool:
        return self._conn.in_transaction

    def execute(self, sql, *args, **kwargs):
        if "DELETE FROM ai_tag_rules" in str(sql):
            raise sqlite3.OperationalError("kuenstlicher Fehler")
        return self._conn.execute(sql, *args, **kwargs)


def test_reset_bleibt_bei_einem_fehler_folgenlos(voll_befuellte_db):
    """Die Transaktionsklammer haelt: entweder ganz oder gar nicht."""
    conn = voll_befuellte_db
    vorher = _abzug(conn)

    with pytest.raises(sqlite3.OperationalError):
        reset_learning_data(_StolpernBeiTagRegeln(conn))

    assert _abzug(conn) == vorher, "Ein gescheiterter Reset darf nichts hinterlassen"


def test_reset_tabellen_und_schutzliste_ueberschneiden_sich_nicht():
    """Waechter gegen ein spaeteres Versehen in der Liste selbst."""
    assert not set(RESET_TABLES) & set(PROTECTED_TABLES)
    assert set(RESET_TABLES) == ERLAUBT_ZU_LEEREN


# ── Die drei Einstellungen ──────────────────────────────────────────────────


def test_die_drei_ki_einstellungen_haben_vorgaben(tmp_path):
    from settings import Settings

    settings = Settings(str(tmp_path / "settings.json"))
    assert settings.get("bank_import_ai_enabled") is True
    assert settings.get("bank_import_ai_learning_enabled") is True
    assert settings.get("finance_insights_enabled") is True
    assert settings.bank_import_ai_enabled is True
    assert settings.bank_import_ai_learning_enabled is True
    assert settings.finance_insights_enabled is True


def test_die_ki_einstellungen_ueberleben_einen_neustart(tmp_path):
    from settings import Settings

    pfad = str(tmp_path / "settings.json")
    settings = Settings(pfad)
    settings.bank_import_ai_enabled = False
    settings.bank_import_ai_learning_enabled = False
    settings.finance_insights_enabled = False

    frisch = Settings(pfad)
    assert frisch.bank_import_ai_enabled is False
    assert frisch.bank_import_ai_learning_enabled is False
    assert frisch.finance_insights_enabled is False


# ── Wirkung der Schalter ────────────────────────────────────────────────────


def test_import_ohne_lernen_bucht_aber_lernt_nicht(voll_befuellte_db):
    conn = voll_befuellte_db
    service = TwintAwareBankImportService(conn)
    vorher = learning_stats(conn)

    ergebnis = service.import_items(
        [
            BankImportItem(
                transaction=_tx(9, description="COOP BERN", amount="-11.00"),
                typ=TYP_EXPENSES,
                category=AUSGABE,
                tags=(),
                amount=11.00,
                details="COOP BERN",
            )
        ],
        document_digest=DIGEST,
        learn=False,
    )

    assert ergebnis.imported == 1
    nachher = learning_stats(conn)
    assert nachher.merchant_patterns == vorher.merchant_patterns
    assert nachher.feedback_examples == vorher.feedback_examples
    # Praeziser als eine Vorhersage: Fuer diesen Haendler gibt es schlicht
    # keinen Gedaechtniseintrag. (Die Vorhersage selbst raet weiterhin - sie
    # kennt nur eine Ausgabenkategorie und trifft damit zwangslaeufig.)
    fingerprint = _fingerprint("COOP BERN", "")
    assert (
        BankImportAI(conn).merchant_entry(fingerprint=fingerprint, typ=TYP_EXPENSES)
        is None
    )


def test_lernen_aus_laesst_bestehendes_wissen_unberuehrt(voll_befuellte_db):
    """Ausschalten ist kein Reset - das bisherige Wissen bleibt abrufbar."""
    conn = voll_befuellte_db
    service = TwintAwareBankImportService(conn)
    service.import_items(
        [
            BankImportItem(
                transaction=_tx(9, description="COOP BERN", amount="-11.00"),
                typ=TYP_EXPENSES,
                category=AUSGABE,
                tags=(),
                amount=11.00,
                details="COOP BERN",
            )
        ],
        document_digest=DIGEST,
        learn=False,
    )
    assert (
        BankImportAI(conn)
        .predict(typ=TYP_EXPENSES, description="MIGROS ZUERICH")
        .category
        == AUSGABE
    )


def test_marker_ohne_lernen_haelt_die_zeile_fest_ohne_zu_verallgemeinern(
    voll_befuellte_db,
):
    conn = voll_befuellte_db
    marker = BankImportMarkerStore(conn)
    vorher = learning_stats(conn).twint_patterns
    tx = _tx(7, description="TWINT von Beat", amount="9.00")

    marker.mark_classifications([(tx, TYP_EXPENSES, AUSGABE)], DIGEST, learn=False)

    assert marker.is_marked(tx, DIGEST), "Der Importzustand gehoert nicht zum Lernen"
    assert learning_stats(conn).twint_patterns == vorher


# ── Der Bereich "Lokale Import-KI" in den Einstellungen ─────────────────────


@pytest.fixture
def einstellungen_dialog(v4_app, tmp_path, voll_befuellte_db):
    """Echter Einstellungsdialog gegen die befuellte Datenbank."""
    from settings import Settings
    from settings_dialog import SettingsDialog

    settings = Settings(str(tmp_path / "settings.json"))

    def _factory(*, security_mode: str = "password", encrypted: bool = True):
        dialog = SettingsDialog(
            settings,
            None,
            app_version="test",
            encrypted_mode=encrypted,
            conn=voll_befuellte_db,
            security_mode=security_mode,
        )
        return dialog

    erzeugte = []

    def _merken(**kwargs):
        dialog = _factory(**kwargs)
        erzeugte.append(dialog)
        return dialog

    yield _merken
    for dialog in erzeugte:
        dialog.deleteLater()
    v4_app.processEvents()


def test_einstellungen_zeigen_alle_sechs_geforderten_punkte(einstellungen_dialog):
    """Die sechs Punkte aus P2.1 sind da - jeder einzeln nachgewiesen."""
    from utils.i18n import tr

    dialog = einstellungen_dialog()

    # 1 KI-Kategorisierung verwenden, 2 Aus meinen Korrekturen lernen
    assert dialog.cb_bank_import_ai.text() == tr("ai_settings.use_ai")
    assert dialog.cb_bank_import_ai_learning.text() == tr(
        "ai_settings.learn_from_corrections"
    )
    # 3 KI-Lerndaten zuruecksetzen ...
    assert dialog.btn_ai_reset.text() == tr("ai_settings.reset_button")
    assert dialog.btn_ai_reset.text().endswith("…")
    # 4 Anzahl gelernter Muster - hier zwei (Haendler + TWINT)
    assert "2" in dialog.lbl_ai_patterns.text()
    # 5 Verschluesselungs-/Sicherheitsstatus
    assert dialog.lbl_ai_security.text() == tr("ai_settings.security_secret")
    # 6 lokaler Datenschutz-Hinweis
    assert dialog.lbl_ai_privacy.text() == tr("ai_settings.privacy_note")

    # Und der Bereich ist ueber die Navigation erreichbar.
    eintraege = [dialog.lw_nav.item(i).text() for i in range(dialog.lw_nav.count())]
    assert tr("ai_settings.group") in eintraege
    assert dialog.lw_nav.count() == dialog.sw_pages.count()


def test_sicherheitsstatus_beschoenigt_den_schnellzugang_nicht(einstellungen_dialog):
    """Regel 1.6: Im Quick-Modus darf kein Schutzversprechen stehen."""
    from utils.i18n import tr

    quick = einstellungen_dialog(security_mode="quick")
    text = quick.lbl_ai_security.text()
    assert text == tr("ai_settings.security_quick")
    assert "lesbar" in text
    assert text != tr("ai_settings.security_secret")

    offen = einstellungen_dialog(security_mode="", encrypted=False)
    assert offen.lbl_ai_security.text() == tr("ai_settings.security_plain")


def test_einstellungen_geben_die_beiden_schalter_zurueck(einstellungen_dialog):
    dialog = einstellungen_dialog()
    assert dialog.cb_bank_import_ai.isChecked() is True
    assert dialog.cb_bank_import_ai_learning.isChecked() is True

    dialog.cb_bank_import_ai.setChecked(False)
    dialog.cb_bank_import_ai_learning.setChecked(False)
    werte = dialog.get_settings()
    assert werte["bank_import_ai_enabled"] is False
    assert werte["bank_import_ai_learning_enabled"] is False


def test_reset_knopf_loescht_nur_die_ki_daten(
    einstellungen_dialog, voll_befuellte_db, monkeypatch
):
    """Der echte Knopf, die echte Rueckfrage, die echte Datenbank."""
    from PySide6.QtWidgets import QMessageBox

    import settings_dialog as sd

    dialog = einstellungen_dialog()
    vorher = _abzug(voll_befuellte_db)
    assert dialog.btn_ai_reset.isEnabled()

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *args, **kwargs: QMessageBox.Yes),
    )
    monkeypatch.setattr(sd, "show_info", lambda *args, **kwargs: None)
    dialog.btn_ai_reset.click()

    nachher = _abzug(voll_befuellte_db)
    veraendert = {name for name in vorher if vorher[name] != nachher[name]}
    assert veraendert == ERLAUBT_ZU_LEEREN
    assert "0" in dialog.lbl_ai_patterns.text()
    assert not dialog.btn_ai_reset.isEnabled()


def test_reset_knopf_gehorcht_einem_nein(
    einstellungen_dialog, voll_befuellte_db, monkeypatch
):
    from PySide6.QtWidgets import QMessageBox

    dialog = einstellungen_dialog()
    vorher = _abzug(voll_befuellte_db)
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *args, **kwargs: QMessageBox.No)
    )
    dialog.btn_ai_reset.click()
    assert _abzug(voll_befuellte_db) == vorher


# ── Schnellzugriff im Importdialog ──────────────────────────────────────────


def test_importdialog_hat_nur_ein_und_aus_und_lernen(v4_app, v4_conn):
    """Zwei Schalter ja - ein Reset ausdruecklich nicht."""
    from utils.i18n import tr
    from views.bank_import_dialog_v4 import BankImportDialog

    dialog = BankImportDialog(v4_conn)
    try:
        beschriftungen = [
            aktion.text() for aktion in dialog.btn_options.menu().actions()
        ]
        assert tr("ai_settings.use_ai") in beschriftungen
        assert tr("ai_settings.learn_from_corrections") in beschriftungen
        assert tr("ai_settings.reset_button") not in beschriftungen
        assert dialog.act_ai_enabled.isCheckable()
        assert dialog.act_ai_learning.isCheckable()
        # Kein Knopf, kein Menuepunkt, kein Aufruf: Der Reset ist im
        # Importdialog nirgends erreichbar.
        quelle = Path("views/bank_import_dialog_v4.py").read_text(encoding="utf-8")
        assert "reset_learning_data" not in quelle
        assert "ai_settings.reset_button" not in quelle
    finally:
        dialog.reject()
        dialog.deleteLater()
        v4_app.processEvents()


def test_schnellzugriff_schreibt_in_die_einstellungen(v4_app, v4_conn, tmp_path):
    from settings import Settings
    from views.bank_import_dialog_v4 import BankImportDialog

    settings = Settings(str(tmp_path / "settings.json"))
    dialog = BankImportDialog(v4_conn, settings=settings)
    try:
        dialog.act_ai_enabled.setChecked(False)
        dialog.act_ai_learning.setChecked(False)
        assert settings.bank_import_ai_enabled is False
        assert settings.bank_import_ai_learning_enabled is False
        assert dialog.ai_enabled() is False
        assert dialog.ai_learning_enabled() is False
    finally:
        dialog.reject()
        dialog.deleteLater()
        v4_app.processEvents()


def test_ohne_eltern_schreibt_der_dialog_keine_echten_einstellungen(v4_app, v4_conn):
    """Ein Testlauf darf die Schalter des Anwenders nicht umlegen."""
    from views.bank_import_dialog_v4 import BankImportDialog, _KISchalterOhneDatei

    dialog = BankImportDialog(v4_conn)
    try:
        assert isinstance(dialog.settings, _KISchalterOhneDatei)
        assert dialog.ai_enabled() is True
    finally:
        dialog.reject()
        dialog.deleteLater()
        v4_app.processEvents()


# ── Wirkung des Schalters auf die Pruefliste ────────────────────────────────


@pytest.fixture
def gelernter_dialog(v4_app, v4_conn, tmp_path):
    """V4-Dialog mit einer bereits gelernten Buchung und echten Einstellungen."""
    from model.category_model import CategoryModel
    from settings import Settings
    from tests.conftest import V4_KATEGORIE, warte_auf_analyse
    from views.bank_import_dialog_v4 import BankImportDialog, LoadedSource

    CategoryModel(v4_conn)
    BankImportAI(v4_conn).learn(
        typ=TYP_EXPENSES,
        category=V4_KATEGORIE,
        description="MIGROS ZUERICH",
    )
    settings = Settings(str(tmp_path / "settings.json"))
    erzeugte = []

    def _factory():
        dialog = BankImportDialog(v4_conn, settings=settings)
        dialog.sources = [
            LoadedSource(
                "konto.csv",
                DIGEST,
                "Bank-CSV/PDF",
                [_tx(0, description="MIGROS ZUERICH", amount="-42.50")],
                set(),
            )
        ]
        dialog._rebuild_from_sources()
        warte_auf_analyse(dialog)
        erzeugte.append(dialog)
        return dialog, settings

    yield _factory
    for dialog in erzeugte:
        # reject() geht ueber done() und haelt den Analyse-Worker an. Ohne das
        # raeumt Qt den Dialog ab, waehrend der Thread noch rechnet - genau der
        # Fehler, den P1.3 mit _PARKED_THREADS abgefangen hat. In einem
        # Sammellauf blockiert das spaetere Threadtests.
        dialog.reject()
        dialog.deleteLater()
    v4_app.processEvents()


def test_ki_aus_liefert_keine_vorhersage_mehr(gelernter_dialog):
    """Der Schalter wirkt sofort auf die Pruefliste - und wieder zurueck."""
    from tests.conftest import V4_KATEGORIE, warte_auf_analyse

    dialog, _settings = gelernter_dialog()
    assert dialog.states[0].category == V4_KATEGORIE
    assert dialog.states[0].prediction_method == "merchant_memory"

    dialog.act_ai_enabled.setChecked(False)
    warte_auf_analyse(dialog)
    assert dialog.states[0].category == ""
    assert dialog.states[0].prediction_method == ""
    assert dialog.states[0].confidence == 0.0

    dialog.act_ai_enabled.setChecked(True)
    warte_auf_analyse(dialog)
    assert dialog.states[0].category == V4_KATEGORIE


def test_ki_aus_laesst_das_gelernte_wissen_stehen(gelernter_dialog, v4_conn):
    """Ausschalten ist kein Reset: Der Bestand bleibt vollstaendig."""
    from tests.conftest import warte_auf_analyse

    dialog, _settings = gelernter_dialog()
    vorher = learning_stats(v4_conn)

    dialog.act_ai_enabled.setChecked(False)
    warte_auf_analyse(dialog)

    assert learning_stats(v4_conn) == vorher
    assert not vorher.is_empty


def test_der_schalter_wirft_handarbeit_nicht_weg(gelernter_dialog, v4_helfer):
    """Von Hand gesetzte Kategorien ueberleben das Umlegen des Schalters."""
    from tests.conftest import V4_KATEGORIE_ZWEI, warte_auf_analyse

    dialog, _settings = gelernter_dialog()
    v4_helfer.haken_setzen(dialog, 0, True)
    v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE_ZWEI)
    assert dialog.states[0].prediction_method == "manual_bulk"

    dialog.act_ai_enabled.setChecked(False)
    warte_auf_analyse(dialog)

    assert dialog.states[0].category == V4_KATEGORIE_ZWEI
    assert dialog.states[0].prediction_method == "manual_bulk"
