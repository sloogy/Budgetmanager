"""TWINT-Regel für den Bankimport.

Positive TWINT-Buchungen sind im BudgetManager keine Einkommen. Sie werden
als Erstattungs-/Zuordnungssignal markiert, können eine Ausgabe netto
reduzieren, erzeugen aber niemals einen Tracking-Eintrag.
"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from model.bank_import_service import (
    BankImportItem,
    BankImportService,
    external_id,
)
from model.bank_statement_reader import BankTransaction
from model.database import db_transaction


def is_twint_credit(tx: BankTransaction) -> bool:
    """True nur für positive TWINT-Eingänge."""
    if tx.amount <= 0:
        return False
    text = f"{tx.counterparty} {tx.description}".casefold()
    return "twint" in text


class TwintAwareBankImportService(BankImportService):
    """Verhindert TWINT-Eingänge als Budgetbuchung auf Service-Ebene."""

    def _validate_item(self, item: BankImportItem) -> tuple[float, list[int]]:
        if is_twint_credit(item.transaction):
            raise ValueError(
                "TWINT-Eingänge werden nur als Erstattungssignal markiert und "
                "nicht als Einkommen/Ausgabe gebucht."
            )
        return super()._validate_item(item)


class BankImportMarkerStore:
    """Persistiert bearbeitete, aber nicht budgetwirksame Bankzeilen."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bank_import_marker_state (
                external_id TEXT PRIMARY KEY,
                marker_kind TEXT NOT NULL,
                source_digest TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_index INTEGER NOT NULL,
                marked_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def is_marked(
        self,
        tx: BankTransaction,
        document_digest: str,
        *,
        marker_kind: str = "twint_credit",
    ) -> bool:
        return bool(
            self.conn.execute(
                "SELECT 1 FROM bank_import_marker_state "
                "WHERE external_id=? AND marker_kind=?",
                (external_id(tx, document_digest), marker_kind),
            ).fetchone()
        )

    def marked_indexes(
        self,
        transactions: list[BankTransaction],
        document_digest: str,
        *,
        marker_kind: str = "twint_credit",
    ) -> set[int]:
        return {
            index
            for index, tx in enumerate(transactions)
            if self.is_marked(tx, document_digest, marker_kind=marker_kind)
        }

    def mark_transactions(
        self,
        transactions: list[BankTransaction],
        document_digest: str,
        *,
        marker_kind: str = "twint_credit",
    ) -> int:
        """Markiert Zeilen idempotent, ohne einen Tracking-Eintrag anzulegen."""
        marked = 0
        with db_transaction(self.conn):
            for tx in transactions:
                ext_id = external_id(tx, document_digest)
                if self.conn.execute(
                    "SELECT 1 FROM bank_import_marker_state "
                    "WHERE external_id=? AND marker_kind=?",
                    (ext_id, marker_kind),
                ).fetchone():
                    continue
                self.conn.execute(
                    """
                    INSERT INTO bank_import_marker_state(
                        external_id, marker_kind, source_digest, source_name,
                        source_index, marked_at
                    ) VALUES(?,?,?,?,?,?)
                    """,
                    (
                        ext_id,
                        marker_kind,
                        document_digest,
                        tx.source_name,
                        int(tx.source_index),
                        datetime.now(UTC).isoformat(),
                    ),
                )
                marked += 1
        return marked
