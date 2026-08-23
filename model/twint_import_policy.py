"""TWINT-Regel und KI-only Klassifikation für den Bankimport.

Positive TWINT-Buchungen sind im BudgetManager keine Einkommen. Sie können als
Erstattungs-/Zuordnungssignal markiert und einer echten Kategorie zugeordnet
werden, erzeugen aber niemals einen Tracking-Eintrag. Die Kategoriezuordnung
lebt ausschließlich im lokalen KI-Gedächtnis.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime

from model.bank_import_service import (
    BankImportItem,
    BankImportService,
    external_id,
)
from model.bank_statement_reader import BankTransaction
from model.database import db_transaction
from model.typ_constants import TYP_EXPENSES, TYP_INCOME

TYP_TWINT_AI = "TWINT (KI)"
_AI_CATEGORY_TYPES = frozenset({TYP_EXPENSES, TYP_INCOME})


def is_twint_credit(tx: BankTransaction) -> bool:
    """True nur für positive TWINT-Eingänge."""
    if tx.amount <= 0:
        return False
    text = f"{tx.counterparty} {tx.description}".casefold()
    return "twint" in text


def _ai_fingerprint(tx: BankTransaction) -> str:
    text = f"{tx.counterparty} {tx.description}".casefold()
    text = re.sub(r"\b\d{5,}\b", " ", text)
    text = re.sub(r"[^a-z0-9äöüß]+", " ", text)
    return " ".join(text.split())


class TwintAwareBankImportService(BankImportService):
    """Verhindert TWINT-Eingänge als Budgetbuchung auf Service-Ebene."""

    def _validate_item(self, item: BankImportItem) -> tuple[float, list[int]]:
        if is_twint_credit(item.transaction):
            raise ValueError(
                "TWINT-Eingänge werden nur als KI-/Erstattungssignal markiert "
                "und nicht als Einkommen/Ausgabe gebucht."
            )
        return super()._validate_item(item)


class BankImportMarkerStore:
    """Persistiert nicht budgetwirksame Zeilen und deren KI-Kategorie."""

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
                ai_category_typ TEXT,
                ai_category TEXT,
                marked_at TEXT NOT NULL
            )
            """
        )
        columns = {
            str(row[1])
            for row in self.conn.execute(
                "PRAGMA table_info(bank_import_marker_state)"
            ).fetchall()
        }
        if "ai_category_typ" not in columns:
            self.conn.execute(
                "ALTER TABLE bank_import_marker_state "
                "ADD COLUMN ai_category_typ TEXT"
            )
        if "ai_category" not in columns:
            self.conn.execute(
                "ALTER TABLE bank_import_marker_state ADD COLUMN ai_category TEXT"
            )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_twint_memory (
                fingerprint TEXT PRIMARY KEY,
                category_typ TEXT NOT NULL,
                category TEXT NOT NULL,
                confirmations INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def _validate_category(self, category_typ: str, category: str) -> tuple[str, str]:
        typ = str(category_typ or "").strip()
        name = str(category or "").strip()
        if typ not in _AI_CATEGORY_TYPES:
            raise ValueError("TWINT-KI erlaubt nur Kategorien aus Einkommen/Ausgaben.")
        row = self.conn.execute(
            "SELECT name FROM categories "
            "WHERE typ=? AND name=? COLLATE NOCASE LIMIT 1",
            (typ, name),
        ).fetchone()
        if not row:
            raise ValueError(
                f"Kategorie {name!r} existiert nicht im BudgetManager-Typ {typ!r}."
            )
        return typ, str(row[0])

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

    def classification(
        self,
        tx: BankTransaction,
        document_digest: str,
        *,
        marker_kind: str = "twint_credit",
    ) -> tuple[str, str]:
        row = self.conn.execute(
            "SELECT ai_category_typ, ai_category FROM bank_import_marker_state "
            "WHERE external_id=? AND marker_kind=?",
            (external_id(tx, document_digest), marker_kind),
        ).fetchone()
        if not row:
            return "", ""
        return str(row[0] or ""), str(row[1] or "")

    def suggest_category(self, tx: BankTransaction) -> tuple[str, str]:
        fingerprint = _ai_fingerprint(tx)
        if not fingerprint:
            return "", ""
        row = self.conn.execute(
            "SELECT category_typ, category FROM ai_twint_memory " "WHERE fingerprint=?",
            (fingerprint,),
        ).fetchone()
        if not row:
            return "", ""
        typ, category = str(row[0]), str(row[1])
        exists = self.conn.execute(
            "SELECT 1 FROM categories WHERE typ=? AND name=? COLLATE NOCASE",
            (typ, category),
        ).fetchone()
        return (typ, category) if exists else ("", "")

    def mark_classifications(
        self,
        classifications: list[tuple[BankTransaction, str, str]],
        document_digest: str,
        *,
        marker_kind: str = "twint_credit",
    ) -> int:
        """Markiert Zeilen und lernt die gewählte echte Kategorie ohne Tracking."""
        normalized: list[tuple[BankTransaction, str, str]] = []
        for tx, category_typ, category in classifications:
            typ, name = self._validate_category(category_typ, category)
            normalized.append((tx, typ, name))

        marked = 0
        now = datetime.now(UTC).isoformat()
        with db_transaction(self.conn):
            for tx, category_typ, category in normalized:
                ext_id = external_id(tx, document_digest)
                existed = bool(
                    self.conn.execute(
                        "SELECT 1 FROM bank_import_marker_state "
                        "WHERE external_id=? AND marker_kind=?",
                        (ext_id, marker_kind),
                    ).fetchone()
                )
                self.conn.execute(
                    """
                    INSERT INTO bank_import_marker_state(
                        external_id, marker_kind, source_digest, source_name,
                        source_index, ai_category_typ, ai_category, marked_at
                    ) VALUES(?,?,?,?,?,?,?,?)
                    ON CONFLICT(external_id) DO UPDATE SET
                        marker_kind=excluded.marker_kind,
                        source_digest=excluded.source_digest,
                        source_name=excluded.source_name,
                        source_index=excluded.source_index,
                        ai_category_typ=excluded.ai_category_typ,
                        ai_category=excluded.ai_category,
                        marked_at=excluded.marked_at
                    """,
                    (
                        ext_id,
                        marker_kind,
                        document_digest,
                        tx.source_name,
                        int(tx.source_index),
                        category_typ,
                        category,
                        now,
                    ),
                )
                fingerprint = _ai_fingerprint(tx)
                if fingerprint:
                    memory = self.conn.execute(
                        "SELECT category_typ, category, confirmations "
                        "FROM ai_twint_memory WHERE fingerprint=?",
                        (fingerprint,),
                    ).fetchone()
                    confirmations = 1
                    if (
                        memory
                        and str(memory[0]) == category_typ
                        and str(memory[1]).casefold() == category.casefold()
                    ):
                        confirmations = int(memory[2]) + 1
                    self.conn.execute(
                        """
                        INSERT INTO ai_twint_memory(
                            fingerprint, category_typ, category,
                            confirmations, updated_at
                        ) VALUES(?,?,?,?,?)
                        ON CONFLICT(fingerprint) DO UPDATE SET
                            category_typ=excluded.category_typ,
                            category=excluded.category,
                            confirmations=excluded.confirmations,
                            updated_at=excluded.updated_at
                        """,
                        (fingerprint, category_typ, category, confirmations, now),
                    )
                if not existed:
                    marked += 1
        return marked

    def mark_transactions(
        self,
        transactions: list[BankTransaction],
        document_digest: str,
        *,
        marker_kind: str = "twint_credit",
    ) -> int:
        """Legacy-Markierung ohne Kategorie; für bestehende Aufrufer erhalten."""
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
                        source_index, ai_category_typ, ai_category, marked_at
                    ) VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        ext_id,
                        marker_kind,
                        document_digest,
                        tx.source_name,
                        int(tx.source_index),
                        None,
                        None,
                        datetime.now(UTC).isoformat(),
                    ),
                )
                marked += 1
        return marked
