import sqlite3
from datetime import date
from decimal import Decimal

import pytest

from model.bank_import_service import BankImportItem
from model.bank_statement_reader import BankTransaction
from model.twint_import_policy import (
    BankImportMarkerStore,
    TYP_TWINT_AI,
    TwintAwareBankImportService,
    is_twint_credit,
)
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS


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
    conn.executemany(
        "INSERT INTO categories(typ, name) VALUES(?, ?)",
        (
            (TYP_INCOME, "Sonstige Einnahmen"),
            (TYP_EXPENSES, "Lebensmittel"),
            (TYP_SAVINGS, "Notgroschen"),
        ),
    )
    conn.commit()
    return conn


def _twint_credit(description: str = "TWINT Zahlung erhalten | Geteilte Kosten") -> BankTransaction:
    return BankTransaction(
        source_kind="csv",
        source_name="zkb.csv",
        source_index=7,
        booking_date=date(2026, 8, 23),
        amount=Decimal("40.00"),
        currency="CHF",
        description=description,
        counterparty="TWINT",
        raw={"ZKB-Referenz": "TWINT-REF-1"},
    )


def _normal_income() -> BankTransaction:
    return BankTransaction(
        source_kind="csv",
        source_name="zkb.csv",
        source_index=8,
        booking_date=date(2026, 8, 23),
        amount=Decimal("500.00"),
        currency="CHF",
        description="Rückvergütung Arbeitgeber",
        counterparty="Arbeitgeber",
        raw={"ZKB-Referenz": "INCOME-REF-1"},
    )


def _income_item(tx: BankTransaction) -> BankImportItem:
    return BankImportItem(
        transaction=tx,
        typ=TYP_INCOME,
        category="Sonstige Einnahmen",
        tags=(),
        amount=float(tx.amount),
        details=tx.description,
    )


def test_twint_pseudo_type_is_not_a_real_budget_type():
    assert TYP_TWINT_AI == "TWINT (KI)"
    assert TYP_TWINT_AI not in {TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS}


def test_positive_twint_is_detected_but_normal_income_is_not():
    assert is_twint_credit(_twint_credit()) is True
    assert is_twint_credit(_normal_income()) is False


def test_service_refuses_to_book_twint_credit_as_income():
    conn = _conn()
    service = TwintAwareBankImportService(conn)
    service._record_undo_group = lambda _ids: None

    with pytest.raises(ValueError, match="KI-/Erstattungssignal"):
        service.import_items(
            [_income_item(_twint_credit())],
            document_digest="a" * 64,
        )

    assert conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM ai_feedback").fetchone()[0] == 0


def test_twint_ai_can_learn_expense_category_without_tracking():
    conn = _conn()
    store = BankImportMarkerStore(conn)
    tx = _twint_credit()

    learned = store.mark_classifications(
        [(tx, TYP_EXPENSES, "Lebensmittel")],
        "b" * 64,
    )

    assert learned == 1
    assert store.classification(tx, "b" * 64) == (TYP_EXPENSES, "Lebensmittel")
    assert store.suggest_category(tx) == (TYP_EXPENSES, "Lebensmittel")
    assert conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 0
    memory = conn.execute(
        "SELECT category_typ, category, confirmations FROM ai_twint_memory"
    ).fetchone()
    assert tuple(memory) == (TYP_EXPENSES, "Lebensmittel", 1)


def test_twint_ai_can_learn_income_category_without_tracking():
    conn = _conn()
    store = BankImportMarkerStore(conn)
    tx = _twint_credit("TWINT Zahlung erhalten | Rückerstattung Lohnspesen")

    store.mark_classifications(
        [(tx, TYP_INCOME, "Sonstige Einnahmen")],
        "c" * 64,
    )

    assert store.classification(tx, "c" * 64) == (
        TYP_INCOME,
        "Sonstige Einnahmen",
    )
    assert conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 0


def test_twint_ai_rejects_savings_and_unknown_categories():
    conn = _conn()
    store = BankImportMarkerStore(conn)
    tx = _twint_credit()

    with pytest.raises(ValueError, match="nur Kategorien aus Einkommen/Ausgaben"):
        store.mark_classifications(
            [(tx, TYP_SAVINGS, "Notgroschen")],
            "d" * 64,
        )
    with pytest.raises(ValueError, match="existiert nicht"):
        store.mark_classifications(
            [(tx, TYP_EXPENSES, "Nicht vorhanden")],
            "d" * 64,
        )
    assert conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 0


def test_same_twint_fingerprint_reuses_learned_category():
    conn = _conn()
    store = BankImportMarkerStore(conn)
    first = _twint_credit("TWINT Zahlung erhalten | Geteilte Kosten")
    second = BankTransaction(
        source_kind="csv",
        source_name="neu.csv",
        source_index=2,
        booking_date=date(2026, 8, 24),
        amount=Decimal("35.00"),
        currency="CHF",
        description="TWINT Zahlung erhalten | Geteilte Kosten",
        counterparty="TWINT",
        raw={"ZKB-Referenz": "TWINT-REF-2"},
    )

    store.mark_classifications(
        [(first, TYP_EXPENSES, "Lebensmittel")],
        "e" * 64,
    )

    assert store.suggest_category(second) == (TYP_EXPENSES, "Lebensmittel")


def test_legacy_marking_stays_idempotent_without_tracking_entry():
    conn = _conn()
    store = BankImportMarkerStore(conn)
    tx = _twint_credit()

    first = store.mark_transactions([tx], "f" * 64)
    second = store.mark_transactions([tx], "g" * 64)

    assert first == 1
    assert second == 0
    assert store.is_marked(tx, "g" * 64) is True
    assert conn.execute("SELECT COUNT(*) FROM bank_import_marker_state").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 0


def test_normal_positive_credit_can_still_be_imported_as_income():
    conn = _conn()
    service = TwintAwareBankImportService(conn)
    service._record_undo_group = lambda _ids: None

    result = service.import_items(
        [_income_item(_normal_income())],
        document_digest="h" * 64,
    )

    assert result.imported == 1
    row = conn.execute("SELECT typ, amount FROM tracking").fetchone()
    assert row[0] == TYP_INCOME
    assert row[1] == 500.0
