import sqlite3
from datetime import date
from decimal import Decimal

import pytest

from model.bank_import_service import BankImportItem, BankImportService
from model.bank_statement_reader import BankTransaction
from model.typ_constants import TYP_EXPENSES
from tests.conftest import verbindung_merken


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE categories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            typ TEXT NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(typ, name)
        );
        CREATE TABLE tags(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT NOT NULL DEFAULT '#3498db'
        );
        CREATE TABLE category_tags(
            category_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY(category_id, tag_id)
        );
        CREATE TABLE tracking(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            typ TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            details TEXT,
            source TEXT NOT NULL DEFAULT 'manual'
        );
        CREATE TABLE entry_tags(
            entry_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY(entry_id, tag_id)
        );
        """
    )
    conn.execute(
        "INSERT INTO categories(typ, name) VALUES(?, ?)",
        (TYP_EXPENSES, "Lebensmittel"),
    )
    conn.execute("INSERT INTO tags(name) VALUES('Lebensmittel')")
    conn.commit()
    return verbindung_merken(conn)


def _tx(index: int = 1, reference: str = "ZKB-ABC") -> BankTransaction:
    return BankTransaction(
        source_kind="csv",
        source_name="zkb.csv",
        source_index=index,
        booking_date=date(2026, 8, 23),
        amount=Decimal("-80.00"),
        currency="CHF",
        description="COOP SUPERMARKT WINTERTHUR",
        counterparty="COOP",
        raw={"ZKB-Referenz": reference},
    )


def _item(tx: BankTransaction) -> BankImportItem:
    return BankImportItem(
        transaction=tx,
        typ=TYP_EXPENSES,
        category="Lebensmittel",
        tags=("Lebensmittel",),
        amount=40.0,
        details="COOP | TWINT-Erstattung 40.00 | Eigenanteil 50%",
    )


def test_same_bank_reference_is_not_imported_twice_even_from_new_export():
    conn = _conn()
    service = BankImportService(conn)
    service._record_undo_group = lambda _ids: None

    first = service.import_items([_item(_tx())], document_digest="a" * 64)
    second = service.import_items([_item(_tx())], document_digest="b" * 64)

    assert first.imported == 1
    assert second.imported == 0
    assert second.skipped_duplicates == 1
    assert conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 1
    assert conn.execute("SELECT amount FROM tracking").fetchone()[0] == 40.0


def test_same_exact_document_row_is_deduplicated_without_bank_reference():
    conn = _conn()
    service = BankImportService(conn)
    service._record_undo_group = lambda _ids: None
    tx = _tx(reference="")

    service.import_items([_item(tx)], document_digest="c" * 64)
    result = service.import_items([_item(tx)], document_digest="c" * 64)

    assert result.imported == 0
    assert result.skipped_duplicates == 1
    assert conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 1


def test_different_documents_without_reference_are_not_false_deduplicated():
    conn = _conn()
    service = BankImportService(conn)
    service._record_undo_group = lambda _ids: None
    tx = _tx(reference="")

    service.import_items([_item(tx)], document_digest="d" * 64)
    result = service.import_items([_item(tx)], document_digest="e" * 64)

    assert result.imported == 1
    assert conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 2


def test_batch_rolls_back_tracking_tags_state_and_learning_on_failure(monkeypatch):
    conn = _conn()
    service = BankImportService(conn)
    service._record_undo_group = lambda _ids: None
    tx1 = _tx(index=1, reference="ZKB-1")
    tx2 = BankTransaction(
        source_kind="csv",
        source_name="zkb.csv",
        source_index=2,
        booking_date=date(2026, 8, 24),
        amount=Decimal("-20.00"),
        currency="CHF",
        description="COOP CITY",
        counterparty="COOP",
        raw={"ZKB-Referenz": "ZKB-2"},
    )

    real_learn = service.ai.learn
    calls = 0

    def fail_second(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulierter Lernfehler")
        return real_learn(**kwargs)

    monkeypatch.setattr(service.ai, "learn", fail_second)

    with pytest.raises(RuntimeError, match="simulierter Lernfehler"):
        service.import_items([_item(tx1), _item(tx2)], document_digest="f" * 64)

    assert conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM entry_tags").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM bank_import_state").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM ai_feedback").fetchone()[0] == 0
