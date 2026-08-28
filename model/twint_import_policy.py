"""TWINT-Regel und KI-only Klassifikation für den Bankimport.

Positive TWINT-Buchungen sind im BudgetManager keine Einkommen. Sie können als
Erstattungs-/Zuordnungssignal markiert und einer echten Kategorie zugeordnet
werden, erzeugen aber niemals einen Tracking-Eintrag. Die Kategoriezuordnung
lebt ausschließlich im lokalen KI-Gedächtnis.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import UTC, datetime

from model.ai_learning_source import (
    SOURCE_AI_CONFIRMED,
    SOURCE_MANUAL,
    confirms,
    source_weight,
    strongest_source,
    validate_source,
)
from model.bank_import_service import (
    BankImportItem,
    BankImportService,
    external_id,
)
from model.bank_statement_reader import BankTransaction
from model.database import db_transaction
from model.typ_constants import TYP_EXPENSES, TYP_INCOME

logger = logging.getLogger(__name__)

TYP_TWINT_AI = "TWINT (KI)"

#: Eine zu markierende Zeile: Buchung, Kategorietyp, Kategorie - und optional
#: die Herkunft der Kategorie. Die Dreierform bleibt gueltig, damit die
#: bisherigen Aufrufer unveraendert weiterlaufen.
TwintClassification = (
    tuple[BankTransaction, str, str] | tuple[BankTransaction, str, str, str]
)
_AI_CATEGORY_TYPES = frozenset({TYP_EXPENSES, TYP_INCOME})


def is_twint_credit(tx: BankTransaction) -> bool:
    """True nur für positive TWINT-Eingänge."""
    if tx.amount <= 0:
        return False
    text = f"{tx.counterparty} {tx.description}".casefold()
    return "twint" in text


def ai_fingerprint(tx: BankTransaction) -> str:
    """Schluessel des TWINT-Kategoriegedaechtnisses zu einer Buchungszeile."""
    text = f"{tx.counterparty} {tx.description}".casefold()
    text = re.sub(r"\b\d{5,}\b", " ", text)
    text = re.sub(r"[^a-z0-9äöüß]+", " ", text)
    return " ".join(text.split())


# Der alte private Name bleibt als Alias, damit bestehende Aufrufer und Tests
# unveraendert weiterlaufen.
_ai_fingerprint = ai_fingerprint


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
                source TEXT NOT NULL DEFAULT 'import_confirmed',
                updated_at TEXT NOT NULL
            )
            """
        )
        twint_spalten = {
            str(row[1])
            for row in self.conn.execute(
                "PRAGMA table_info(ai_twint_memory)"
            ).fetchall()
        }
        if "source" not in twint_spalten:
            # Aeltere Datenbank: dieselbe Begruendung wie in
            # ``BankImportAI._add_source_column`` - belegbar ist nur, dass der
            # Vorschlag in der Pruefliste stand und uebernommen wurde.
            self.conn.execute(
                "ALTER TABLE ai_twint_memory "
                "ADD COLUMN source TEXT NOT NULL DEFAULT 'import_confirmed'"
            )
            self.conn.execute(
                "UPDATE ai_twint_memory SET source=?", (SOURCE_AI_CONFIRMED,)
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
        classifications: list[TwintClassification],
        document_digest: str,
        *,
        marker_kind: str = "twint_credit",
        learn: bool = True,
    ) -> int:
        """Markiert Zeilen und lernt die gewählte echte Kategorie ohne Tracking.

        ``learn=False`` schreibt den Marker weiterhin - er gehört zum
        Importzustand und verhindert, dass dieselbe Zeile beim nächsten Lauf
        erneut angeboten wird - füllt aber ``ai_twint_memory`` nicht auf.
        Verallgemeinert wird also nichts mehr, festgehalten schon.

        Ein Eintrag darf ein viertes Feld tragen: die Herkunft der Kategorie
        (siehe :mod:`model.ai_learning_source`). Ohne dieses Feld gilt
        ``manual`` - wer hier eine Kategorie ausdrücklich benennt, tut es von
        Hand. Der Importdialog kennt die echte Herkunft und reicht sie durch.
        Der Marker selbst ist von der Gewichtung nie betroffen: Er hält fest,
        was der Anwender für **diese** Zeile entschieden hat, und wird immer
        geschrieben.
        """
        normalized: list[tuple[BankTransaction, str, str, str]] = []
        for eintrag in classifications:
            tx, category_typ, category = eintrag[0], eintrag[1], eintrag[2]
            source = validate_source(eintrag[3] if len(eintrag) > 3 else SOURCE_MANUAL)
            typ, name = self._validate_category(category_typ, category)
            normalized.append((tx, typ, name, source))

        marked = 0
        now = datetime.now(UTC).isoformat()
        with db_transaction(self.conn):
            for tx, category_typ, category, source in normalized:
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
                fingerprint = _ai_fingerprint(tx) if learn else ""
                if fingerprint:
                    self._remember(
                        fingerprint=fingerprint,
                        category_typ=category_typ,
                        category=category,
                        source=source,
                        now=now,
                    )
                if not existed:
                    marked += 1
        return marked

    def _remember(
        self,
        *,
        fingerprint: str,
        category_typ: str,
        category: str,
        source: str,
        now: str,
    ) -> None:
        """Schreibt das TWINT-Gedaechtnis nach denselben Regeln wie P2.3 sie
        fuer das Haendlergedaechtnis setzt.

        Zwei Fassungen derselben Rangfolge waeren zwei Stellen, an denen sie
        auseinanderlaufen kann; die Regel selbst steht darum in
        :mod:`model.ai_learning_source` und wird hier nur angewandt.
        """
        memory = self.conn.execute(
            "SELECT category_typ, category, confirmations, source "
            "FROM ai_twint_memory WHERE fingerprint=?",
            (fingerprint,),
        ).fetchone()
        if memory is None:
            confirmations, neue_source = 1, source
        else:
            alt_source = str(memory[3] or "")
            alt_confirmations = int(memory[2])
            gleiche_aussage = (
                str(memory[0]) == category_typ
                and str(memory[1]).casefold() == category.casefold()
            )
            if gleiche_aussage:
                neue_source = strongest_source(alt_source, source)
                confirmations = (
                    alt_confirmations + 1 if confirms(source) else alt_confirmations
                )
                if neue_source == alt_source and confirmations == alt_confirmations:
                    return
            elif source_weight(source) < source_weight(alt_source):
                logger.info(
                    "TWINT-Lernsignal verworfen: %s widerspricht gespeichertem %s "
                    "(%s Bestaetigungen)",
                    source,
                    alt_source or "unbekannt",
                    alt_confirmations,
                )
                return
            else:
                confirmations, neue_source = 1, source
        self.conn.execute(
            """
            INSERT INTO ai_twint_memory(
                fingerprint, category_typ, category,
                confirmations, source, updated_at
            ) VALUES(?,?,?,?,?,?)
            ON CONFLICT(fingerprint) DO UPDATE SET
                category_typ=excluded.category_typ,
                category=excluded.category,
                confirmations=excluded.confirmations,
                source=excluded.source,
                updated_at=excluded.updated_at
            """,
            (fingerprint, category_typ, category, confirmations, neue_source, now),
        )

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
