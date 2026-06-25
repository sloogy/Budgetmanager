"""Regressionstests für v2.1.0.

Deckt die zwei Hardening-Fixes ab:
  1. Legacy-Entschlackung im RecurringTransactionsModel: die produktiv nicht
     angebundene Per-Eintrag-Terminvorschau (`get_pending_bookings`,
     `_is_already_booked`, `update_last_booking_date`) ist entfernt; die von
     Tests genutzten Datums-Helfer bleiben funktionsfähig; der frühere
     deutschsprachige Dubletten-Marker taucht im Modell-Code nicht mehr auf.
  2. Portabilität: der Crash-Log-Fallback in main.py nutzt
     `tempfile.gettempdir()` statt eines hartkodierten `/tmp`-Pfads, der unter
     Windows nicht existiert.

Läuft ohne Qt/PySide6.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.migrations import migrate_all  # noqa: E402
from model.recurring_transactions_model import (  # noqa: E402
    RecurringTransactionsModel,
    RecurringTransaction,
)


@pytest.fixture
def migrated_conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    migrate_all(c)
    yield c
    c.close()


def _make_trans(day: int) -> RecurringTransaction:
    return RecurringTransaction(
        id=1, typ="Ausgaben", category="Miete", amount=100.0, details="",
        day_of_month=day, is_active=True, start_date=date(2026, 2, 1),
        end_date=None, created_date=None, last_booking_date=None,
    )


# ── Fix 1: Legacy-Entschlackung ──────────────────────────────────


def test_dead_scheduling_methods_are_removed():
    """Die produktiv toten Scheduling-Methoden sind nicht mehr vorhanden."""
    for name in ("get_pending_bookings", "_is_already_booked", "update_last_booking_date"):
        assert not hasattr(RecurringTransactionsModel, name), (
            f"{name} sollte in v2.1.0 entfernt sein"
        )


def test_kept_crud_and_helpers_still_present():
    """Die dokumentierte Kompat-CRUD + getestete Helfer bleiben erhalten."""
    for name in (
        "create_recurring_transaction",
        "get_all_recurring_transactions",
        "update_recurring_transaction",
        "delete_recurring_transaction",
        "toggle_active",
        "_calculate_booking_date",
        "_is_valid_booking_date",
        "_row_to_transaction",
    ):
        assert hasattr(RecurringTransactionsModel, name), f"{name} darf nicht fehlen"


def test_kept_date_helpers_still_compute_correctly(migrated_conn):
    """Die verbliebenen Datums-Helfer verhalten sich unverändert."""
    m = RecurringTransactionsModel(migrated_conn)
    # Monatsende-Overflow
    assert m._calculate_booking_date(_make_trans(31), date(2026, 2, 1)) == date(2026, 2, 28)
    assert m._calculate_booking_date(_make_trans(31), date(2028, 2, 1)) == date(2028, 2, 29)
    assert m._calculate_booking_date(_make_trans(31), date(2026, 4, 1)) == date(2026, 4, 30)
    # Gültigkeitsfenster
    t = _make_trans(15)
    assert m._is_valid_booking_date(t, date(2026, 3, 15)) is True
    assert m._is_valid_booking_date(t, date(2026, 1, 15)) is False  # vor start_date


def test_crud_roundtrip_still_works(migrated_conn):
    """Die generische Tabellen-CRUD funktioniert weiterhin end-to-end."""
    m = RecurringTransactionsModel(migrated_conn)
    m.create_recurring_transaction(
        typ="Ausgaben", category="Strom", amount=80.0, details="",
        day_of_month=5, start_date=date(2026, 1, 1),
    )
    rows = m.get_all_recurring_transactions()
    assert len(rows) == 1 and rows[0].category == "Strom"


def test_no_german_marker_filter_in_model_source():
    """Der frühere deutschsprachige Dubletten-Marker wird im Modell nicht
    mehr als Filter/SQL-Literal verwendet (nur Erwähnung im Doku-Kommentar)."""
    src = (ROOT / "model" / "recurring_transactions_model.py").read_text(encoding="utf-8")
    for line in src.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue  # Kommentarzeile (Doku) ist erlaubt
        assert "Wiederkehrend (ID:" not in line, (
            "Sprachabhängiger Marker darf nicht mehr als Code-Literal vorkommen"
        )


# ── Fix 2: Portabler Crash-Log-Pfad ──────────────────────────────


def test_main_crash_log_fallback_is_portable():
    """main.py darf keinen hartkodierten /tmp-Pfad mehr enthalten und muss den
    OS-Temp-Pfad verwenden (Windows-Kompatibilität)."""
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert '"/tmp/' not in src, "Hartkodierter /tmp-Pfad darf nicht mehr vorkommen"
    assert "tempfile.gettempdir()" in src, (
        "Crash-Log-Fallback muss tempfile.gettempdir() nutzen"
    )
