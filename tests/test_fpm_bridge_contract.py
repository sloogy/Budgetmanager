"""Der Kontrakt zwischen BudgetManager und FPM.

Warum es diesen Test zusaetzlich zu ``test_lifeplanner_import_inbox`` gibt:
Dort erzeugt BudgetManager seine Testdaten selbst. Dadurch blieb lange
unbemerkt, dass die hier geschriebenen Sparziele als ``fpm.savings-goal.v1``
herausgehen, waehrend FPM nur ``fpm.savings_goal.v1`` las - beide Seiten fuer
sich gruen, die Spiegelung kam trotzdem nie an.

Hier steht darum eine **Probe aus der Gegenseite**, wortgetreu uebernommen aus
``FPM/logic/budget_export_service.py``, und die Gegenprobe: was BudgetManager
schreibt, muss FPM auch annehmen. Aendert FPM sein Format, muss diese Datei
mitgeaendert werden - genau das ist der Zweck.

Das Gegenstueck heisst FPM/tests/test_budgetmanager_bridge_contract.py.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from model.category_model import CategoryModel
from model.lifeplanner_import_service import (
    export_savings_goals,
    load_import_records,
)
from model.migrations import migrate_all
from tests.conftest import verbindung_merken
from utils.money import set_currency

# Aus FPM/logic/budget_export_service.py, SAVINGS_GOAL_SCHEMAS. FPM nimmt beide
# Schreibweisen an; kanonisch bleibt die Bindestrich-Form, die hier entsteht.
FPM_SAVINGS_GOAL_SCHEMAS = {"fpm.savings-goal.v1", "fpm.savings_goal.v1"}

# Aus FPM/logic/budget_export_service.py, load_budgetmanager_expense_proposals.
FPM_EXPENSE_SCHEMAS = {"fpm.import.v1", "fpm.expense.v1"}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    migrate_all(conn)
    CategoryModel(conn).create("Ausgaben", "Füller")
    set_currency("CHF")
    return verbindung_merken(conn)


# ── FPM schreibt, BudgetManager liest ───────────────────────────────────────

# Wortgetreu das, was expense_to_budgetmanager_record() in FPM erzeugt.
FPM_AUSGABE = {
    "schema": "budgetmanager.import.v1",
    "operation": "upsert",
    "external_id": "fpm:expense:5",
    "source": "FPM",
    "date": "2026-07-04",
    "amount": 320.0,
    "currency": "CHF",
    "category_path": "Hobby/Füller",
    "description": "Pilot Custom 823",
    "counterparty": "Fontoplumo",
    "notes": "",
    "metadata": {
        "item_type": "pen",
        "amount": 320.0,
        "shipping": 0.0,
        "customs": 0.0,
        "order_number": "",
        "payment_method": "",
        "pen_id": None,
        "ink_id": None,
        "nib_id": None,
        "paper_id": None,
    },
}
FPM_MANIFEST = {
    "schema": "budgetmanager.import.manifest.v1",
    "source": "FPM",
    "created_at": "2026-08-21T10:00:00+00:00",
    "mode": "reviewable_bridge_import",
}


def test_eine_echte_fpm_zeile_wird_angenommen(tmp_path: Path):
    pfad = tmp_path / "fpm_to_budgetmanager.jsonl"
    pfad.write_text(
        json.dumps(FPM_MANIFEST, ensure_ascii=False)
        + "\n"
        + json.dumps(FPM_AUSGABE, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    records = load_import_records(_conn(), pfad)
    assert len(records) == 1
    assert records[0].external_id == "fpm:expense:5"
    assert records[0].amount == 320.0
    assert records[0].category_path == "Hobby/Füller"
    assert records[0].description == "Pilot Custom 823"


def test_die_von_fpm_gebauten_externen_ids_werden_angenommen(tmp_path: Path):
    """FPM baut die ID ohne Datenbank-ID aus dem Label - frueher roh, samt
    Leerzeichen. Das brachte nicht diese Zeile, sondern den ganzen Lauf zu Fall."""
    ids = [
        "fpm:expense:5",
        "fpm:expense:2026-07-04:Pilot-Custom-823-1a2b3c4d",
        "fpm:expense:2026-07-04:9f8e7d6c",
    ]
    pfad = tmp_path / "fpm_to_budgetmanager.jsonl"
    pfad.write_text(
        "\n".join(
            json.dumps(dict(FPM_AUSGABE, external_id=i), ensure_ascii=False)
            for i in ids
        )
        + "\n",
        encoding="utf-8",
    )

    records = load_import_records(_conn(), pfad)
    assert [r.external_id for r in records] == ids


def test_das_manifest_zaehlt_nicht_als_buchung(tmp_path: Path):
    pfad = tmp_path / "fpm_to_budgetmanager.jsonl"
    pfad.write_text(json.dumps(FPM_MANIFEST) + "\n", encoding="utf-8")
    assert load_import_records(_conn(), pfad) == []


# ── BudgetManager schreibt, FPM liest ───────────────────────────────────────


def _sparziel_anlegen(conn: sqlite3.Connection) -> None:
    spalten = {row["name"] for row in conn.execute("PRAGMA table_info(savings_goals)")}
    werte = {
        "name": "Pilot Custom 823",
        "target_amount": 300.0,
        "current_amount": 120.0,
        "deadline": "2026-09-01",
        "category": "Füller",
        "notes": "",
        "status": "sparend",
        "created_date": "2026-01-01",
        # Seit v19 exportiert der BudgetManager nur Freigegebenes. Diese
        # Tests pruefen das Dateiformat, nicht die Freigabe - also wird sie
        # hier gesetzt, damit ueberhaupt eine Zeile entsteht.
        "bridge_share": 1,
    }
    vorhanden = {k: v for k, v in werte.items() if k in spalten}
    conn.execute(
        f"INSERT INTO savings_goals ({', '.join(vorhanden)}) "  # nosec B608
        f"VALUES ({', '.join('?' * len(vorhanden))})",
        tuple(vorhanden.values()),
    )
    conn.commit()


def _zeilen(pfad: Path) -> list[dict]:
    return [
        json.loads(z)
        for z in pfad.read_text(encoding="utf-8").splitlines()
        if z.strip()
    ]


@pytest.fixture()
def sparziel_datei(tmp_path: Path) -> Path:
    conn = _conn()
    _sparziel_anlegen(conn)
    pfad = tmp_path / "budgetmanager_savings_goals.jsonl"
    export_savings_goals(conn, pfad)
    return pfad


def test_das_sparziel_schema_ist_eines_das_fpm_kennt(sparziel_datei: Path):
    """Der Fehler, der diesen Test veranlasst hat."""
    ziele = [z for z in _zeilen(sparziel_datei) if "manifest" not in z["schema"]]
    assert ziele, "Es wurde kein Sparziel geschrieben"
    for ziel in ziele:
        assert ziel["schema"] in FPM_SAVINGS_GOAL_SCHEMAS, ziel["schema"]


def test_das_sparziel_traegt_die_felder_die_fpm_liest(sparziel_datei: Path):
    ziel = next(z for z in _zeilen(sparziel_datei) if "manifest" not in z["schema"])
    for feld in (
        "external_id",
        "source",
        "item_type",
        "label",
        "goal_name",
        "status",
        "target_amount",
        "current_amount",
        "remaining_amount",
        "progress_percent",
        "currency",
        "deadline",
        "category",
        "notes",
    ):
        assert feld in ziel, feld


def test_fpm_blendet_das_sparziel_nicht_als_unsichtbar_aus(sparziel_datei: Path):
    """FPM filtert auf ``visible is False``. Fehlt das Feld, bleibt das Ziel
    sichtbar - stuende hier versehentlich False, verschwaende es lautlos."""
    ziel = next(z for z in _zeilen(sparziel_datei) if "manifest" not in z["schema"])
    assert ziel.get("visible") is not False


def test_die_externe_id_des_sparziels_ist_stabil(sparziel_datei: Path):
    ziel = next(z for z in _zeilen(sparziel_datei) if "manifest" not in z["schema"])
    assert ziel["external_id"].startswith("budgetmanager:savings-goal:")


def _ausgabe_anlegen(conn: sqlite3.Connection) -> None:
    from model.typ_constants import TYP_EXPENSES

    conn.execute(
        "INSERT INTO tracking (date, typ, category, amount, details) VALUES (?,?,?,?,?)",
        ("2026-07-04", TYP_EXPENSES, "Füller", 320.0, "Pilot Custom 823"),
    )
    conn.commit()


@pytest.fixture()
def ausgabe_datei(tmp_path: Path) -> Path:
    from model.lifeplanner_import_service import export_fpm_expense_proposals

    conn = _conn()
    _ausgabe_anlegen(conn)
    pfad = tmp_path / "budgetmanager_to_fpm.jsonl"
    export_fpm_expense_proposals(conn, pfad)
    return pfad


def test_der_ausgabevorschlag_traegt_ein_schema_das_fpm_kennt(ausgabe_datei: Path):
    vorschlaege = [z for z in _zeilen(ausgabe_datei) if "manifest" not in z["schema"]]
    assert vorschlaege, "Es wurde kein Vorschlag geschrieben"
    for vorschlag in vorschlaege:
        assert vorschlag["schema"] in FPM_EXPENSE_SCHEMAS, vorschlag["schema"]


def test_der_ausgabevorschlag_traegt_die_felder_die_fpm_liest(ausgabe_datei: Path):
    """FPM verwirft eine Zeile ohne externe ID oder mit Betrag 0 stillschweigend."""
    vorschlag = next(z for z in _zeilen(ausgabe_datei) if "manifest" not in z["schema"])
    assert vorschlag["external_id"]
    assert float(vorschlag["amount"]) > 0
    # FPM liest "category" oder "category_path" - eines davon muss da sein.
    assert vorschlag.get("category") or vorschlag.get("category_path")
    assert vorschlag["date"]


# ── Der Zustand der Bruecke ist sichtbar ────────────────────────────────────


def test_der_zustand_nennt_alle_drei_dateien(tmp_path, monkeypatch):
    """Ohne diese Anzeige ist nicht zu erkennen, ob der Austausch stattfindet -
    und vor allem nicht, welcher Ordner gerade gilt. Gegenstueck zu FPM."""
    from model.lifeplanner_import_service import bridge_zustand

    monkeypatch.setenv("LIFEPLANNER_BRIDGE_DIR", str(tmp_path))
    ordner, befunde = bridge_zustand()

    assert ordner == tmp_path
    assert len(befunde) == 3
    assert all(not b.vorhanden for b in befunde)


def test_der_zustand_zaehlt_die_eintraege(tmp_path, monkeypatch):
    from model.lifeplanner_import_service import bridge_zustand

    monkeypatch.setenv("LIFEPLANNER_BRIDGE_DIR", str(tmp_path))
    (tmp_path / "fpm_to_budgetmanager.jsonl").write_text(
        json.dumps(FPM_MANIFEST) + "\n" + json.dumps(FPM_AUSGABE) + "\n",
        encoding="utf-8",
    )

    _, befunde = bridge_zustand()
    nach_name = {b.name: b for b in befunde}

    assert nach_name["FPM → BudgetManager"].eintraege == 1
    # Die anderen gibt es noch nicht - das ist etwas anderes als leer.
    assert not nach_name["Sparziele → FPM"].vorhanden


def test_eine_kaputte_zeile_sprengt_die_anzeige_nicht(tmp_path, monkeypatch):
    from model.lifeplanner_import_service import bridge_zustand

    monkeypatch.setenv("LIFEPLANNER_BRIDGE_DIR", str(tmp_path))
    (tmp_path / "fpm_to_budgetmanager.jsonl").write_text(
        "kein json\n" + json.dumps(FPM_AUSGABE) + "\n", encoding="utf-8"
    )

    _, befunde = bridge_zustand()
    nach_name = {b.name: b for b in befunde}
    assert nach_name["FPM → BudgetManager"].eintraege == 1
