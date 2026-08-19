from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from model.lifeplanner_import_service import (
    export_fpm_expense_proposals,
    export_savings_goals,
    sync_default_outboxes,
)
from model.migrations import migrate_all
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate_all(conn)
    return conn


def test_bidirectional_outboxes_remain_available(tmp_path: Path) -> None:
    conn = _db()
    TrackingModel(conn).add("2026-08-02", TYP_EXPENSES, "Füller", 19.90, "Tinte")
    expenses = export_fpm_expense_proposals(conn, tmp_path / "fpm.jsonl")
    savings = export_savings_goals(conn, tmp_path / "savings.jsonl")
    assert expenses.count == 1
    assert expenses.path.is_file()
    assert savings.path.is_file()
    records = [
        json.loads(line)
        for line in expenses.path.read_text(encoding="utf-8").splitlines()
    ]
    assert records[0]["schema"] == "fpm.import.manifest.v1"
    assert records[1]["schema"] == "fpm.import.v1"


def test_default_outbox_sync_writes_both_files(monkeypatch, tmp_path: Path) -> None:
    conn = _db()
    monkeypatch.setenv("LIFEPLANNER_BRIDGE_DIR", str(tmp_path))
    expenses, savings = sync_default_outboxes(conn)
    assert expenses.path.parent == tmp_path.resolve()
    assert savings.path.parent == tmp_path.resolve()
    assert expenses.path.exists() and savings.path.exists()
