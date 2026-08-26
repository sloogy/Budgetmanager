import sqlite3
from datetime import date

import pytest

from model.bank_import_ai import (
    BankImportAI,
    BookingSignal,
    match_twint_reimbursement,
)
from model.typ_constants import TYP_EXPENSES, TYP_INCOME
from tests.conftest import verbindung_merken


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE categories(id INTEGER PRIMARY KEY, typ TEXT NOT NULL, name TEXT NOT NULL, UNIQUE(typ,name))"
    )
    conn.execute(
        "CREATE TABLE tags(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, color TEXT NOT NULL DEFAULT '#3498db')"
    )
    conn.executemany(
        "INSERT INTO categories(typ,name) VALUES(?,?)",
        [
            (TYP_EXPENSES, "Lebensmittel"),
            (TYP_EXPENSES, "Restaurant"),
            (TYP_INCOME, "Rückerstattung"),
        ],
    )
    conn.executemany(
        "INSERT INTO tags(name) VALUES(?)",
        [("Lebensmittel",), ("Mittagessen",), ("Geteilte Kosten",)],
    )
    conn.commit()
    return verbindung_merken(conn)


def test_ai_learns_category_and_tags_from_confirmed_booking():
    conn = _conn()
    ai = BankImportAI(conn)
    ai.learn(
        typ=TYP_EXPENSES,
        category="Lebensmittel",
        description="COOP SUPERMARKT WINTERTHUR 123456",
        counterparty="COOP",
        tags=("Lebensmittel", "Geteilte Kosten"),
    )
    prediction = ai.predict(
        typ=TYP_EXPENSES,
        description="COOP SUPERMARKT WINTERTHUR 987654",
        counterparty="COOP",
    )
    assert prediction.category == "Lebensmittel"
    assert set(prediction.tags) == {"Lebensmittel", "Geteilte Kosten"}
    assert prediction.confidence >= 0.9


def test_tag_rule_can_control_personal_cost_share():
    conn = _conn()
    ai = BankImportAI(conn)
    ai.set_tag_allocation_rule("Lebensmittel", 50, priority=10)
    ai.set_tag_allocation_rule("Mittagessen", 100, priority=20)
    assert ai.allocation_for_tags(("Lebensmittel",)) == (50.0, "Lebensmittel")
    assert ai.allocation_for_tags(("Lebensmittel", "Mittagessen")) == (
        100.0,
        "Mittagessen",
    )


def test_equal_priority_conflict_is_not_guessed():
    conn = _conn()
    ai = BankImportAI(conn)
    ai.set_tag_allocation_rule("Lebensmittel", 50, priority=10)
    ai.set_tag_allocation_rule("Mittagessen", 100, priority=10)
    assert ai.allocation_for_tags(("Lebensmittel", "Mittagessen")) == (None, "")


def test_ai_refuses_unknown_category_or_tag():
    conn = _conn()
    ai = BankImportAI(conn)
    with pytest.raises(ValueError, match="existiert nicht"):
        ai.learn(
            typ=TYP_EXPENSES,
            category="Erfunden",
            description="COOP",
        )
    with pytest.raises(ValueError, match="Tag .* existiert nicht"):
        ai.learn(
            typ=TYP_EXPENSES,
            category="Lebensmittel",
            description="COOP",
            tags=("Erfunden",),
        )


def test_twint_refund_derives_personal_share():
    expense = BookingSignal(
        booking_id="expense:1",
        booking_date=date(2026, 8, 20),
        amount=-80.0,
        description="COOP Einkauf",
        counterparty="COOP",
    )
    credit = BookingSignal(
        booking_id="credit:1",
        booking_date=date(2026, 8, 21),
        amount=40.0,
        description="TWINT Zahlung erhalten",
        counterparty="TWINT",
    )
    match = match_twint_reimbursement(expense, [credit])
    assert match is not None
    assert match.reimbursement_percent == 50.0
    assert match.personal_share_percent == 50.0
    assert match.confidence >= 0.8


def test_non_twint_credit_is_not_used_as_refund():
    expense = BookingSignal("expense:1", date(2026, 8, 20), -80.0, "COOP")
    credit = BookingSignal("credit:1", date(2026, 8, 21), 40.0, "Lohn", "Arbeitgeber")
    assert match_twint_reimbursement(expense, [credit]) is None
