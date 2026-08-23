"""Nur Freigegebenes verlaesst den BudgetManager.

Bis v2.4.1 spiegelte die Bruecke alles: jede Kategorie, jedes Sparziel. Wer
40 Kategorien fuehrt, schickte 40 Namen an ein Programm, das drei davon
braucht - und Kategorienamen sind keine neutralen Etiketten. Seit v19
entscheidet ein Haekchen je Eintrag.

Gegenstueck in FPM: tests/test_sparziel_wuensche.py, dort dieselbe Frage fuer
die andere Richtung.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from model.category_model import CategoryModel
from model.lifeplanner_import_service import (
    export_categories,
    export_savings_goals,
)
from model.migrations import _cols, _migrate_v18_to_v19, migrate_all
from model.savings_goals_model import SavingsGoalsModel
from model.typ_constants import TYP_EXPENSES, TYP_SAVINGS


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    pfad = tmp_path / "budgetmanager.db"
    verbindung = sqlite3.connect(pfad)
    verbindung.row_factory = sqlite3.Row
    migrate_all(verbindung, str(pfad))
    return verbindung


def _namen(pfad: Path) -> set[str]:
    return {
        json.loads(zeile)["name"]
        for zeile in pfad.read_text(encoding="utf-8").splitlines()
        if zeile.strip() and "manifest" not in zeile
    }


def _labels(pfad: Path) -> set[str]:
    return {
        json.loads(zeile)["label"]
        for zeile in pfad.read_text(encoding="utf-8").splitlines()
        if zeile.strip() and "manifest" not in zeile
    }


# ── Kategorien ──────────────────────────────────────────────────────────────


def test_neue_kategorien_gehen_nicht_von_allein_hinaus(conn, tmp_path) -> None:
    """Die Vorgabe ist aus. Eine Freigabe ist eine Entscheidung."""
    kategorien = CategoryModel(conn)
    kategorien.create(TYP_EXPENSES, "Anwalt")
    ergebnis = export_categories(conn, tmp_path / "kat.jsonl")
    assert ergebnis.count == 0
    assert _namen(ergebnis.path) == set()


def test_freigegebene_kategorien_gehen_mit(conn, tmp_path) -> None:
    kategorien = CategoryModel(conn)
    kategorien.create(TYP_EXPENSES, "Hobby")
    kategorien.create(TYP_EXPENSES, "Anwalt")
    kategorien.set_bridge_share(TYP_EXPENSES, "Hobby", True)
    ergebnis = export_categories(conn, tmp_path / "kat.jsonl")
    assert _namen(ergebnis.path) == {"Hobby"}


def test_die_freigabe_laesst_sich_zuruecknehmen(conn, tmp_path) -> None:
    """Zuruecknehmen muss beim naechsten Schreiben wirken.

    Die Datei ist ein vollstaendiger Stand, kein Nachtrag - stuende der Name
    danach noch drin, waere die Ruecknahme wirkungslos.
    """
    kategorien = CategoryModel(conn)
    kategorien.create(TYP_EXPENSES, "Hobby")
    kategorien.set_bridge_share(TYP_EXPENSES, "Hobby", True)
    export_categories(conn, tmp_path / "kat.jsonl")

    kategorien.set_bridge_share(TYP_EXPENSES, "Hobby", False)
    ergebnis = export_categories(conn, tmp_path / "kat.jsonl")
    assert _namen(ergebnis.path) == set()


def test_sparkategorien_werden_getrennt_freigegeben(conn, tmp_path) -> None:
    """Ausgaben und Ersparnisse sind im Dialog zwei Reiter - und hier zwei
    Entscheidungen. Ein Haken beim einen setzt den anderen nicht."""
    kategorien = CategoryModel(conn)
    kategorien.create(TYP_EXPENSES, "Hobby")
    kategorien.create(TYP_SAVINGS, "Ruecklage")
    kategorien.set_bridge_share(TYP_SAVINGS, "Ruecklage", True)
    ergebnis = export_categories(conn, tmp_path / "kat.jsonl")
    assert _namen(ergebnis.path) == {"Ruecklage"}


# ── Sparziele ───────────────────────────────────────────────────────────────


def test_neue_sparziele_gehen_nicht_von_allein_hinaus(conn, tmp_path) -> None:
    SavingsGoalsModel(conn).create(name="Notgroschen", target_amount=5000.0)
    ergebnis = export_savings_goals(conn, tmp_path / "ziele.jsonl")
    assert ergebnis.count == 0


def test_freigegebene_sparziele_gehen_mit(conn, tmp_path) -> None:
    ziele = SavingsGoalsModel(conn)
    ziel_id = ziele.create(name="Montblanc 149", target_amount=1200.0)
    ziele.create(name="Notgroschen", target_amount=5000.0)
    ziele.set_bridge_share(ziel_id, True)
    ergebnis = export_savings_goals(conn, tmp_path / "ziele.jsonl")
    assert _labels(ergebnis.path) == {"Montblanc 149"}


def test_das_sparziel_traegt_visible(conn, tmp_path) -> None:
    """FPM filtert seit jeher auf ``visible`` - der BudgetManager schrieb das
    Feld nie. Ohne es wirft die Gegenseite nichts weg."""
    ziele = SavingsGoalsModel(conn)
    ziele.set_bridge_share(ziele.create(name="Ferien", target_amount=3000.0), True)
    ergebnis = export_savings_goals(conn, tmp_path / "ziele.jsonl")
    zeilen = [
        json.loads(z)
        for z in ergebnis.path.read_text(encoding="utf-8").splitlines()
        if z.strip() and "manifest" not in z
    ]
    assert all(z["visible"] is True for z in zeilen)


def test_die_freigabe_ueberlebt_das_neuladen(conn) -> None:
    ziele = SavingsGoalsModel(conn)
    ziel_id = ziele.create(name="Ferien", target_amount=3000.0)
    ziele.set_bridge_share(ziel_id, True)
    geladen = {z.name: z.bridge_share for z in SavingsGoalsModel(conn).list_all()}
    assert geladen == {"Ferien": True}


# ── Umstieg ─────────────────────────────────────────────────────────────────


def test_bestehende_eintraege_bleiben_beim_update_freigegeben(conn) -> None:
    """Bestandsschutz statt Datensparsamkeit bei der Umstellung.

    Sonst waere FPMs Kategorien-Zuordnung nach dem Update schlagartig leer
    und der Nutzer suchte den Fehler dort, wo keiner ist.
    """
    kategorien = CategoryModel(conn)
    kategorien.create(TYP_EXPENSES, "Benzin")
    SavingsGoalsModel(conn).create(name="Ferien", target_amount=3000.0)

    # Zustand einer Datenbank vor v19 herstellen
    conn.execute("ALTER TABLE categories DROP COLUMN bridge_share")
    conn.execute("ALTER TABLE savings_goals DROP COLUMN bridge_share")
    conn.commit()
    assert "bridge_share" not in _cols(conn, "categories")

    _migrate_v18_to_v19(conn)

    assert kategorien.list_shared_names(TYP_EXPENSES) == ["Benzin"]
    assert all(z.bridge_share for z in SavingsGoalsModel(conn).list_all())


def test_nach_dem_update_angelegtes_ist_wieder_aus(conn) -> None:
    """Der Bestandsschutz gilt einmalig, nicht als neue Vorgabe."""
    kategorien = CategoryModel(conn)
    kategorien.create(TYP_EXPENSES, "Benzin")
    conn.execute("ALTER TABLE categories DROP COLUMN bridge_share")
    conn.commit()
    _migrate_v18_to_v19(conn)

    kategorien.create(TYP_EXPENSES, "Therapie")
    assert kategorien.list_shared_names(TYP_EXPENSES) == ["Benzin"]


def test_eine_datenbank_ohne_die_spalte_verhaelt_sich_wie_frueher(conn) -> None:
    """Downgrade-Schutz: Ohne Spalte wird gespiegelt wie vor v19.

    Andernfalls raeumte ein Rueckschritt die Bruecke wortlos leer, und in FPM
    verschwaende die Zuordnung ohne erkennbaren Grund.
    """
    kategorien = CategoryModel(conn)
    kategorien.create(TYP_EXPENSES, "Benzin")
    conn.execute("ALTER TABLE categories DROP COLUMN bridge_share")
    conn.commit()
    assert kategorien.list_shared_names(TYP_EXPENSES) == ["Benzin"]


# ── Wunschimport ────────────────────────────────────────────────────────────


def test_ein_uebernommener_wunsch_wird_zurueckgespiegelt(conn, tmp_path) -> None:
    """Ausnahme von der Vorgabe.

    Wer in FPM einen Wunsch stellt und ihn hier bestaetigt, will den
    Fortschritt dort sehen - sonst waere die Bestaetigung umsonst gewesen.
    """
    from model.savings_goal_import import SparzielWunsch, uebernehmen

    wunsch = SparzielWunsch(
        external_id="fpm:wish:1",
        source="FPM",
        name="Pelikan M800",
        target_amount=520.0,
        currency="CHF",
        category="",
    )
    goal_id = uebernehmen(conn, wunsch)
    ziel = SavingsGoalsModel(conn).get(goal_id)
    assert ziel is not None
    assert ziel.bridge_share is True
