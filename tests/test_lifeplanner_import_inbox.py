from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from model.category_model import CategoryModel
from model.lifeplanner_import_service import (
    LifePlannerImportError,
    apply_import,
    default_draft,
    load_import_records,
    reject_import,
)
from model.migrations import migrate_all
from utils.money import set_currency


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    migrate_all(conn)
    CategoryModel(conn).create("Ausgaben", "Füller")
    set_currency("CHF")
    return conn


def _payload(amount: float = 123.45, currency: str = "CHF") -> dict:
    return {
        "schema": "budgetmanager.import.v1",
        "operation": "upsert",
        "external_id": "fpm:expense:1",
        "source": "FPM",
        "date": "2026-07-30",
        "amount": amount,
        "currency": currency,
        "category_path": "Hobby/Füller",
        "description": "Asvine V800",
        "counterparty": "Shop",
        "notes": "Test",
        "metadata": {"item_type": "pen"},
    }


def _write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps({"schema": "budgetmanager.import.manifest.v1"})
        + "\n"
        + json.dumps(payload)
        + "\n",
        encoding="utf-8",
    )


def test_review_import_is_idempotent_and_updates_changed_upsert(tmp_path):
    conn = _conn()
    path = tmp_path / "fpm_to_budgetmanager.jsonl"
    _write(path, _payload())

    record = load_import_records(conn, path)[0]
    assert record.status == "pending"
    draft = default_draft(conn, record)
    assert draft.category == "Füller"
    first = apply_import(conn, record, draft)
    assert first.updated is False
    assert load_import_records(conn, path)[0].status == "imported"
    assert conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 1

    _write(path, _payload(amount=130.0))
    changed = load_import_records(conn, path)[0]
    assert changed.status == "changed"
    second = apply_import(conn, changed, default_draft(conn, changed))
    assert second.updated is True
    assert conn.execute("SELECT amount FROM tracking").fetchone()[0] == 130.0
    assert conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 1


def test_rejected_payload_stays_hidden_until_source_changes(tmp_path):
    conn = _conn()
    path = tmp_path / "fpm_to_budgetmanager.jsonl"
    _write(path, _payload())
    record = load_import_records(conn, path)[0]
    reject_import(conn, record)
    assert load_import_records(conn, path)[0].status == "rejected"

    _write(path, _payload(amount=150))
    assert load_import_records(conn, path)[0].status == "changed"


def test_foreign_currency_requires_explicit_confirmation(tmp_path):
    conn = _conn()
    path = tmp_path / "fpm_to_budgetmanager.jsonl"
    _write(path, _payload(currency="EUR"))
    record = load_import_records(conn, path)[0]
    draft = default_draft(conn, record)
    assert draft.currency_confirmed is False
    with pytest.raises(LifePlannerImportError):
        apply_import(conn, record, draft)


def test_rejects_non_finite_amount(tmp_path):
    conn = _conn()
    path = tmp_path / "fpm_to_budgetmanager.jsonl"
    payload = _payload()
    payload["amount"] = "NaN"
    _write(path, payload)
    with pytest.raises(LifePlannerImportError):
        load_import_records(conn, path)


def test_changed_upsert_keeps_previous_user_category(tmp_path):
    from dataclasses import replace

    conn = _conn()
    CategoryModel(conn).create("Ausgaben", "Sammlung")
    path = tmp_path / "fpm_to_budgetmanager.jsonl"
    _write(path, _payload())
    record = load_import_records(conn, path)[0]
    draft = replace(default_draft(conn, record), category="Sammlung")
    apply_import(conn, record, draft)

    _write(path, _payload(amount=199.0))
    changed = load_import_records(conn, path)[0]
    next_draft = default_draft(conn, changed)
    assert next_draft.category == "Sammlung"
    assert next_draft.amount == 199.0
