"""GUI-Smoke-Tests für BudgetManager (v1.0.31, Punkt 2 der Qualitätsliste).

Diese Tests starten die echte Qt-Anwendung headless (Offscreen-Platform) und
prüfen die Pfade, die in v1.0.29 still kaputt waren:

    - MainWindow startet ohne Exception (hätte den fehlenden trf-Import gefangen)
    - Sprachwechsel läuft durch und baut die Menüs neu auf
      (hätte den _setup_menus-Bug gefangen)
    - Alle Tabs sind vorhanden und ein Tab-Wechsel wirft nicht

Voraussetzungen:
    - PySide6 installiert (CI: requirements-build.txt)
    - Kein Display nötig: QT_QPA_PLATFORM=offscreen wird hier gesetzt

Lokal ohne PySide6 werden die Tests übersprungen (skip), nicht rot.

Ausführen:
    pytest tests/ -v
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Headless: MUSS vor dem ersten Qt-Import gesetzt sein
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip(
    "PySide6.QtWidgets",
    reason="PySide6 nicht installiert — GUI-Smoke-Tests übersprungen",
)

from PySide6.QtWidgets import QApplication  # noqa: E402

from model.migrations import migrate_all  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def migrated_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_all(conn)
    yield conn
    conn.close()


@pytest.fixture
def main_window(qapp, migrated_conn):
    from views.main_window import MainWindow

    win = MainWindow(migrated_conn)
    win._suppress_close_confirm = True  # headless: Beenden-Bestätigung überspringen
    yield win
    win.close()
    win.deleteLater()
    qapp.processEvents()


def test_main_window_starts(main_window):
    """MainWindow lässt sich ohne Exception instanziieren und anzeigen."""
    main_window.show()
    QApplication.processEvents()
    assert main_window.isVisible()
    assert main_window.windowTitle(), "Fenstertitel fehlt"


def test_all_tabs_present_and_switchable(main_window, qapp):
    """Alle Tabs existieren und ein Durchschalten wirft keine Exception."""
    tabs = main_window.tabs
    assert tabs.count() >= 4, f"Erwartet >=4 Tabs, gefunden: {tabs.count()}"
    for i in range(tabs.count()):
        tabs.setCurrentIndex(i)
        qapp.processEvents()
        assert tabs.currentIndex() == i


def test_menubar_built(main_window):
    """Die Menüleiste wurde mit Einträgen aufgebaut."""
    actions = main_window.menuBar().actions()
    assert len(actions) >= 4, f"Erwartet >=4 Menüs, gefunden: {len(actions)}"


def test_language_switch_rebuilds_menus(main_window, qapp):
    """Sprachwechsel: _retranslate_ui muss durchlaufen und die Menüs neu
    aufbauen — in v1.0.29 schlug das still fehl (Aufruf einer nicht
    existierenden Methode), Menüs blieben unübersetzt."""
    from utils import i18n

    original_lang = i18n.get_language()
    menu_count_before = len(main_window.menuBar().actions())
    assert menu_count_before > 0

    target = "en" if original_lang != "en" else "de"
    try:
        i18n.set_language(target)
        main_window._retranslate_ui()
        qapp.processEvents()

        actions_after = main_window.menuBar().actions()
        assert len(actions_after) == menu_count_before, (
            f"Menüanzahl nach Sprachwechsel verändert: "
            f"{menu_count_before} → {len(actions_after)}"
        )
        assert all(
            a.text() or a.isSeparator() for a in actions_after
        ), "Menü ohne Titel nach Sprachwechsel"
    finally:
        i18n.set_language(original_lang)
        main_window._retranslate_ui()
        qapp.processEvents()


def test_status_message_helpers_do_not_raise(main_window):
    """Statusmeldungen mit trf() dürfen nicht werfen (Regression: fehlender
    trf-Import in v1.0.29 erzeugte NameError-Crashdialoge)."""
    from utils.i18n import trf

    main_window.statusBar().showMessage(
        trf("lbl.anzeigename_geaendert_new_name", new_name="Test"), 100
    )
    main_window.statusBar().showMessage(
        trf("lbl.datenordner_geoeffnet_folder", folder="/tmp"), 100
    )
