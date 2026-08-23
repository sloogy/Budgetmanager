"""Der Freigabe-Dialog: was angehakt ist, steht auch so in der Datenbank.

Gegenstueck zu tests/test_bridge_freigabe.py - dort wird geprueft, dass nur
Freigegebenes die Bruecke erreicht, hier, dass der Dialog die Freigabe
richtig anzeigt und richtig speichert. Ein Haekchen, das gesetzt aussieht,
aber nicht ankommt, waere die schlimmste Variante: Der Nutzer glaubt dann,
er habe etwas gesperrt.
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Headless: MUSS vor dem ersten Qt-Import gesetzt sein
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip(
    "PySide6.QtWidgets",
    reason="PySide6 nicht installiert - GUI-Tests uebersprungen",
)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from model.category_model import CategoryModel
from model.migrations import migrate_all
from model.savings_goals_model import SavingsGoalsModel
from model.typ_constants import TYP_EXPENSES, TYP_SAVINGS


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def conn():
    verbindung = sqlite3.connect(":memory:")
    verbindung.row_factory = sqlite3.Row
    migrate_all(verbindung)
    yield verbindung
    verbindung.close()


@pytest.fixture
def dialog(qapp, conn):
    from views.bridge_share_dialog import BridgeShareDialog

    kategorien = CategoryModel(conn)
    kategorien.create(TYP_EXPENSES, "Benzin")
    kategorien.create(TYP_EXPENSES, "Therapie")
    kategorien.create(TYP_SAVINGS, "Wunschliste")
    kategorien.set_bridge_share(TYP_EXPENSES, "Benzin", True)
    SavingsGoalsModel(conn).create(name="Notgroschen", target_amount=5000.0)

    dlg = BridgeShareDialog(conn)
    yield dlg
    dlg.deleteLater()
    qapp.processEvents()


def _eintrag(baum, name: str):
    for i in range(baum.topLevelItemCount()):
        if baum.topLevelItem(i).text(0) == name:
            return baum.topLevelItem(i)
    raise AssertionError(f"{name} steht nicht in der Liste")


def test_der_dialog_zeigt_den_gespeicherten_stand(dialog) -> None:
    """Freigegebenes ist angehakt, der Rest nicht - ohne diese Zuordnung
    entscheidet der Nutzer im Blindflug."""
    assert _eintrag(dialog.baum_ausgaben, "Benzin").checkState(0) == Qt.Checked
    assert _eintrag(dialog.baum_ausgaben, "Therapie").checkState(0) == Qt.Unchecked
    assert _eintrag(dialog.baum_ziele, "Notgroschen").checkState(0) == Qt.Unchecked


def test_ein_haekchen_wird_sofort_gespeichert(dialog, conn) -> None:
    """Kein OK-Knopf: Der Dialog schreibt beim Umschalten. Wer ihn ueber das
    Fensterkreuz schliesst, hat trotzdem gesperrt, was er gesperrt hat."""
    _eintrag(dialog.baum_ausgaben, "Therapie").setCheckState(0, Qt.Checked)

    assert CategoryModel(conn).list_shared_names(TYP_EXPENSES) == [
        "Benzin",
        "Therapie",
    ]


def test_ein_haekchen_laesst_sich_zuruecknehmen(dialog, conn) -> None:
    _eintrag(dialog.baum_ausgaben, "Benzin").setCheckState(0, Qt.Unchecked)

    assert CategoryModel(conn).list_shared_names(TYP_EXPENSES) == []


def test_ein_sparziel_wird_ueber_seine_kennung_gespeichert(dialog, conn) -> None:
    """Kategorien haengen am Namen, Sparziele an der id - eine Verwechslung
    faende der Nutzer erst an der falschen gesperrten Zeile."""
    _eintrag(dialog.baum_ziele, "Notgroschen").setCheckState(0, Qt.Checked)

    ziele = SavingsGoalsModel(conn).list_all()
    assert [z.name for z in ziele if z.bridge_share] == ["Notgroschen"]


def test_alle_abwaehlen_wirkt_nur_im_sichtbaren_reiter(dialog, conn) -> None:
    """Sonst raeumt ein Klick auf der Kategorienliste nebenbei die Sparziele
    mit ab, ohne dass der Nutzer sie sieht."""
    _eintrag(dialog.baum_ziele, "Notgroschen").setCheckState(0, Qt.Checked)
    dialog.tabs.setCurrentWidget(dialog.baum_ausgaben)

    dialog._alle_setzen(False)

    assert CategoryModel(conn).list_shared_names(TYP_EXPENSES) == []
    assert [z.name for z in SavingsGoalsModel(conn).list_all() if z.bridge_share] == [
        "Notgroschen"
    ]


def test_alle_auswaehlen_nimmt_den_ganzen_reiter(dialog, conn) -> None:
    dialog.tabs.setCurrentWidget(dialog.baum_ausgaben)

    dialog._alle_setzen(True)

    assert CategoryModel(conn).list_shared_names(TYP_EXPENSES) == [
        "Benzin",
        "Therapie",
    ]


def test_die_statuszeile_zaehlt_beide_kategorienarten(dialog) -> None:
    """Die Zeile ist die einzige Stelle, an der ohne Blaettern steht, wie viel
    ueberhaupt hinausgeht."""
    zahlen = [int(t) for t in re.findall(r"\d+", dialog.status.text())]

    # 1 von 3 Kategorien (Benzin von Benzin/Therapie/Wunschliste),
    # 0 von 1 Sparzielen.
    assert zahlen == [1, 3, 0, 1]
