from __future__ import annotations

import sys
from pathlib import Path

# Stabilisiert beide Aufrufarten:
#   python -m pytest ...  und  pytest ...
# Einige pytest-Wrapper setzen den Projekt-Root nicht automatisch auf sys.path.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_configure(config):
    """Keep release tests fast without weakening production crypto defaults."""
    import model.crypto as crypto
    import model.user_model as user_model

    test_iterations = 1_000
    crypto.PBKDF2_ITERATIONS = test_iterations
    user_model.PBKDF2_ITERATIONS = test_iterations


def pytest_runtest_teardown(item, nextitem):
    """Finalisiert zyklische Testobjekte pro Test, damit Ressourcenlecks sofort auffallen."""
    import gc

    gc.collect()


# ── Loop 31: Das Bruecken-Register gehoert nie in die echte Nutzerkonfiguration ─
# Ohne diese Weiche schreibt jeder Test, der einen Brueckenordner aufloest, in
# ~/.config/fpm-suite/bridges.json - und traegt tmp-Pfade ein, die es danach
# nicht mehr gibt.
import pytest


@pytest.fixture(autouse=True)
def _bruecken_register_isolieren(tmp_path_factory, monkeypatch):
    ziel = tmp_path_factory.mktemp("bridge-registry") / "bridges.json"
    monkeypatch.setenv("FPM_SUITE_BRIDGE_REGISTRY", str(ziel))
    yield


# ── Testverbindungen gehoeren dem Testlauf, nicht dem Garbage Collector ──────
# Rund zwei Dutzend Testdateien haben eine Hilfsfunktion der Bauart
#
#     def _conn():
#         conn = sqlite3.connect(":memory:")
#         ...
#         return conn
#
# und rufen sie in jedem Test auf, ohne die Verbindung je zu schliessen. Der
# Interpreter raeumte sie irgendwann weg; unter Windows blockiert ein offenes
# Dateihandle auf einer SQLite-Datei aber das Aufraeumen von tmp_path, und
# push-checks.yml faehrt seit v3.0.7 auch windows-latest. Ab Python 3.13 meldet
# sqlite3 solche Verbindungen ausserdem als ResourceWarning "unclosed database" -
# unter dem CI-Pin 3.12 gibt es diese Warnung nicht, weshalb sie nie jemandem
# auffiel.
#
# Statt ~110 Aufrufstellen umzubauen, uebergibt die Hilfsfunktion ihre
# Verbindung an diesen Teardown. Wer eine Verbindung selbst schliesst, merkt
# sie gar nicht erst vor - close() ist idempotent, doppeltes Schliessen waere
# aber trotzdem irrefuehrend.
_OFFENE_TESTVERBINDUNGEN: list = []


def verbindung_merken(verbindung):
    """Uebergibt eine Testverbindung dem Teardown und reicht sie durch."""
    _OFFENE_TESTVERBINDUNGEN.append(verbindung)
    return verbindung


@pytest.fixture(autouse=True)
def _testverbindungen_schliessen():
    """Schliesst am Testende jede ueber ``verbindung_merken`` gemeldete DB."""
    yield
    while _OFFENE_TESTVERBINDUNGEN:
        _OFFENE_TESTVERBINDUNGEN.pop().close()


# ── Bankimport-V4-Testgeruest ────────────────────────────────────────────────
# Mehrere Testdateien fahren den aktiven V4-Dialog offscreen gegen eine echte,
# temporaere SQLite-DB. Bis v3.0.6 waren 58 von 59 Bankimport-Dialogtests reine
# Quelltext-Zusicherungen; genau deshalb blieb der twint_ai-Fehler unbemerkt.
# Das Geruest steht hier, damit es nicht in jeder Datei getrennt driftet.

V4_DIGEST = "a" * 64
V4_DIGEST_ZWEI = "b" * 64
V4_KATEGORIE = "Testkategorie"
V4_KATEGORIE_ZWEI = "Zweitkategorie"


@pytest.fixture(scope="session")
def v4_app():
    """QApplication fuer die Offscreen-Dialogtests."""
    pytest.importorskip("PySide6")
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    yield QApplication.instance() or QApplication([])


@pytest.fixture
def v4_conn():
    """Frisch migrierte DB mit zwei Kategorien je Budgettyp."""
    import sqlite3

    from model.category_model import CategoryModel
    from model.migrations import migrate_all
    from model.typ_constants import TYP_EXPENSES, TYP_INCOME

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate_all(connection)
    categories = CategoryModel(connection)
    for typ in (TYP_EXPENSES, TYP_INCOME):
        categories.create(typ, V4_KATEGORIE)
        categories.create(typ, V4_KATEGORIE_ZWEI)
    yield connection
    connection.close()


@pytest.fixture
def v4_tx():
    """Fabrik fuer Buchungszeilen ohne Datei- oder Leseumweg."""
    from datetime import date
    from decimal import Decimal

    from model.bank_statement_reader import BankTransaction

    def _factory(
        index: int,
        *,
        description: str,
        amount: str,
        counterparty: str = "",
        booking_date=None,
        source_name: str = "konto.csv",
    ) -> BankTransaction:
        return BankTransaction(
            source_kind="csv",
            source_name=source_name,
            source_index=index,
            booking_date=booking_date or date(2026, 3, 17),
            amount=Decimal(amount),
            currency="CHF",
            description=description,
            counterparty=counterparty,
            raw={},
        )

    return _factory


@pytest.fixture
def v4_dialog(v4_app, v4_conn):
    """Fabrik fuer einen bereits mit Quellen befuellten V4-Dialog."""
    from views.bank_import_dialog_v4 import BankImportDialog, LoadedSource

    erzeugte = []

    def _factory(transactions, *, digest: str = V4_DIGEST, quellen=None):
        dialog = BankImportDialog(v4_conn)
        if quellen is None:
            quellen = [(digest, "konto.csv", list(transactions))]
        dialog.sources = [
            LoadedSource(name, quell_digest, "Bank-CSV/PDF", list(zeilen), set())
            for quell_digest, name, zeilen in quellen
        ]
        dialog._rebuild_from_sources()
        erzeugte.append(dialog)
        return dialog

    yield _factory
    for dialog in erzeugte:
        dialog.deleteLater()
    v4_app.processEvents()


@pytest.fixture
def v4_import_bestaetigen(monkeypatch):
    """Beantwortet die Import-Rueckfrage mit Ja und stellt Meldungen still."""

    def _aktivieren() -> None:
        from PySide6.QtWidgets import QMessageBox

        import views.bank_import_dialog_v4 as v4

        monkeypatch.setattr(
            QMessageBox,
            "question",
            staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes),
        )
        monkeypatch.setattr(v4, "show_info", lambda *args, **kwargs: None)
        monkeypatch.setattr(v4, "show_warning", lambda *args, **kwargs: None)

    return _aktivieren


def v4_kategorie_setzen(dialog, typ: str, name: str) -> None:
    """Setzt die Kategorie ueber das echte Massen-Dropdown des Dialogs."""
    token = dialog._category_token(typ, name)
    position = dialog.cmb_bulk_category.findData(token)
    assert position >= 0, f"Kategorie {typ}/{name} fehlt im Massen-Dropdown"
    dialog.cmb_bulk_category.setCurrentIndex(position)
    dialog._bulk_set_category()


def v4_haken_setzen(dialog, row: int, checked: bool = True) -> None:
    """Klickt das Haekchen der Zeile so, wie es die Oberflaeche tut."""
    from PySide6.QtCore import Qt

    item = dialog.table.item(row, dialog.COL_USE)
    item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)


@pytest.fixture
def v4_helfer():
    """Reicht die Bedienhelfer als Fixture durch, statt conftest zu importieren."""

    class _Helfer:
        kategorie_setzen = staticmethod(v4_kategorie_setzen)
        haken_setzen = staticmethod(v4_haken_setzen)

    return _Helfer
