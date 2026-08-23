"""Atomarer, idempotenter Bankimport für den lokalen PDF/CSV-Reader."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from model.bank_import_ai import BankImportAI
from model.bank_statement_reader import BankTransaction
from model.database import db_transaction
from model.typ_constants import TYP_EXPENSES, TYP_INCOME
from model.undo_redo_model import UndoRedoModel
from utils.money import require_finite_amount

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BankImportItem:
    transaction: BankTransaction
    typ: str
    category: str
    tags: tuple[str, ...]
    amount: float
    details: str


@dataclass(frozen=True)
class BankImportResult:
    imported: int
    skipped_duplicates: int
    tracking_ids: tuple[int, ...]


_REFERENCE_KEYS = frozenset(
    {
        "zkbreferenz",
        "referenznummer",
        "reference",
        "transactionreference",
        "transactionid",
        "endtoendid",
        "endtoendreference",
    }
)


def _norm_key(value: str) -> str:
    value = str(value or "").strip().casefold()
    value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    return re.sub(r"[^a-z0-9]+", "", value)


def source_digest(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bank_reference(tx: BankTransaction) -> str:
    for key, value in tx.raw.items():
        if _norm_key(key) not in _REFERENCE_KEYS:
            continue
        candidate = str(value or "").strip()
        if candidate:
            return candidate
    return ""


def _payload_hash(tx: BankTransaction) -> str:
    payload = {
        "date": tx.booking_date.isoformat(),
        "amount": format(tx.amount, "f"),
        "currency": tx.currency,
        "description": tx.description,
        "counterparty": tx.counterparty,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def external_id(tx: BankTransaction, document_digest: str) -> str:
    """Stabile ID; ohne Bankreferenz bewusst nur datei-idempotent."""
    reference = _bank_reference(tx)
    if reference:
        seed = "|".join(
            (
                "bankref",
                reference,
                tx.booking_date.isoformat(),
                format(tx.amount, "f"),
                tx.currency,
            )
        )
    else:
        seed = "|".join(
            (
                "document",
                document_digest,
                str(tx.source_index),
                _payload_hash(tx),
            )
        )
    return "bankimport:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()


class BankImportService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.ai = BankImportAI(conn)
        self._ensure_state_table()

    def _ensure_state_table(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bank_import_state (
                external_id TEXT PRIMARY KEY,
                tracking_id INTEGER NOT NULL,
                source_digest TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_index INTEGER NOT NULL,
                payload_hash TEXT NOT NULL,
                imported_at TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_bank_import_tracking "
            "ON bank_import_state(tracking_id)"
        )
        self.conn.commit()

    def is_duplicate(self, tx: BankTransaction, document_digest: str) -> bool:
        row = self.conn.execute(
            "SELECT tracking_id FROM bank_import_state WHERE external_id=?",
            (external_id(tx, document_digest),),
        ).fetchone()
        if not row:
            return False
        return bool(
            self.conn.execute(
                "SELECT 1 FROM tracking WHERE id=?",
                (int(row[0]),),
            ).fetchone()
        )

    def duplicate_indexes(
        self,
        transactions: list[BankTransaction],
        document_digest: str,
    ) -> set[int]:
        return {
            index
            for index, tx in enumerate(transactions)
            if self.is_duplicate(tx, document_digest)
        }

    @staticmethod
    def _tracking_has_source(conn: sqlite3.Connection) -> bool:
        rows = conn.execute("PRAGMA table_info(tracking)").fetchall()
        return "source" in {str(row[1]) for row in rows}

    def _category_exists(self, typ: str, category: str) -> bool:
        return bool(
            self.conn.execute(
                "SELECT 1 FROM categories WHERE typ=? AND name=? COLLATE NOCASE",
                (typ, category),
            ).fetchone()
        )

    def _tag_ids(self, tags: tuple[str, ...]) -> list[int]:
        ids: list[int] = []
        for tag in tags:
            row = self.conn.execute(
                "SELECT id FROM tags WHERE name=? COLLATE NOCASE",
                (tag,),
            ).fetchone()
            if not row:
                raise ValueError(f"Tag {tag!r} existiert nicht im BudgetManager.")
            ids.append(int(row[0]))
        return sorted(set(ids))

    def _fixed_tag_ids(self, typ: str, category: str) -> set[int]:
        try:
            rows = self.conn.execute(
                """
                SELECT ct.tag_id
                FROM category_tags ct
                JOIN categories c ON c.id = ct.category_id
                WHERE c.typ=? AND c.name=?
                """,
                (typ, category),
            ).fetchall()
        except sqlite3.OperationalError:
            return set()
        return {int(row[0]) for row in rows}

    def _validate_item(self, item: BankImportItem) -> tuple[float, list[int]]:
        if item.typ not in {TYP_EXPENSES, TYP_INCOME}:
            raise ValueError(f"Nicht unterstützter Bankimport-Typ: {item.typ!r}")
        if not self._category_exists(item.typ, item.category):
            raise ValueError(
                f"Kategorie {item.category!r} existiert nicht für {item.typ!r}."
            )
        amount = float(require_finite_amount(item.amount, field="Bankimport-Betrag"))
        if amount <= 0:
            raise ValueError("Bankimport-Betrag muss größer als 0 sein.")
        return amount, self._tag_ids(item.tags)

    def _insert_tracking(self, item: BankImportItem, amount: float) -> int:
        values = (
            item.transaction.booking_date.isoformat(),
            item.typ,
            item.category,
            amount,
            item.details,
        )
        if self._tracking_has_source(self.conn):
            cur = self.conn.execute(
                """
                INSERT INTO tracking(date, typ, category, amount, details, source)
                VALUES(?,?,?,?,?,?)
                """,
                (*values, "bank_import"),
            )
        else:
            cur = self.conn.execute(
                """
                INSERT INTO tracking(date, typ, category, amount, details)
                VALUES(?,?,?,?,?)
                """,
                values,
            )
        return int(cur.lastrowid)

    def _attach_tags(
        self,
        tracking_id: int,
        typ: str,
        category: str,
        manual_tag_ids: list[int],
    ) -> None:
        tag_ids = set(manual_tag_ids) | self._fixed_tag_ids(typ, category)
        for tag_id in sorted(tag_ids):
            self.conn.execute(
                "INSERT OR IGNORE INTO entry_tags(entry_id, tag_id) VALUES(?,?)",
                (tracking_id, tag_id),
            )

    def _record_state(
        self,
        *,
        ext_id: str,
        tracking_id: int,
        tx: BankTransaction,
        document_digest: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO bank_import_state(
                external_id, tracking_id, source_digest, source_name,
                source_index, payload_hash, imported_at
            ) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(external_id) DO UPDATE SET
                tracking_id=excluded.tracking_id,
                source_digest=excluded.source_digest,
                source_name=excluded.source_name,
                source_index=excluded.source_index,
                payload_hash=excluded.payload_hash,
                imported_at=excluded.imported_at
            """,
            (
                ext_id,
                tracking_id,
                document_digest,
                tx.source_name,
                int(tx.source_index),
                _payload_hash(tx),
                datetime.now(UTC).isoformat(),
            ),
        )

    def _record_undo_group(self, tracking_ids: list[int]) -> None:
        """Best-effort Undo-Gruppe nach erfolgreichem Daten-Commit."""
        if not tracking_ids:
            return
        undo = UndoRedoModel(self.conn)
        group_id = undo.new_group_id()
        try:
            for index, tracking_id in enumerate(tracking_ids):
                row = self.conn.execute(
                    "SELECT * FROM tracking WHERE id=?",
                    (tracking_id,),
                ).fetchone()
                if not row:
                    continue
                new_data = dict(row)
                try:
                    tag_rows = self.conn.execute(
                        "SELECT tag_id FROM entry_tags "
                        "WHERE entry_id=? ORDER BY tag_id",
                        (tracking_id,),
                    ).fetchall()
                    new_data["_tag_ids"] = [int(item[0]) for item in tag_rows]
                except sqlite3.OperationalError:
                    new_data["_tag_ids"] = []
                undo.record_operation(
                    "tracking",
                    "INSERT",
                    None,
                    new_data,
                    group_id=group_id,
                    clear_redo=index == 0,
                )
        except (sqlite3.Error, TypeError, ValueError) as exc:
            logger.warning(
                "Undo-Gruppe für Bankimport konnte nicht erstellt werden: %s",
                exc,
            )
            try:
                self.conn.execute(
                    "DELETE FROM undo_stack WHERE group_id=?",
                    (group_id,),
                )
                self.conn.commit()
            except sqlite3.Error as cleanup_exc:
                logger.warning(
                    "Unvollständige Bankimport-Undo-Gruppe konnte nicht "
                    "bereinigt werden: %s",
                    cleanup_exc,
                )

    def import_items(
        self,
        items: list[BankImportItem],
        *,
        document_digest: str,
    ) -> BankImportResult:
        """Importiert bestätigte Zeilen atomar und lernt im selben Commit."""
        validated: list[tuple[BankImportItem, float, list[int], str]] = []
        skipped = 0
        for item in items:
            amount, tag_ids = self._validate_item(item)
            ext_id = external_id(item.transaction, document_digest)
            if self.is_duplicate(item.transaction, document_digest):
                skipped += 1
                continue
            validated.append((item, amount, tag_ids, ext_id))

        if not validated:
            return BankImportResult(0, skipped, ())

        tracking_ids: list[int] = []
        with db_transaction(self.conn):
            for item, amount, tag_ids, ext_id in validated:
                tracking_id = self._insert_tracking(item, amount)
                self._attach_tags(
                    tracking_id,
                    item.typ,
                    item.category,
                    tag_ids,
                )
                self._record_state(
                    ext_id=ext_id,
                    tracking_id=tracking_id,
                    tx=item.transaction,
                    document_digest=document_digest,
                )
                self.ai.learn(
                    typ=item.typ,
                    category=item.category,
                    description=item.transaction.description,
                    counterparty=item.transaction.counterparty,
                    tags=item.tags,
                    commit=False,
                )
                tracking_ids.append(tracking_id)

        self._record_undo_group(tracking_ids)
        return BankImportResult(
            len(tracking_ids),
            skipped,
            tuple(tracking_ids),
        )
