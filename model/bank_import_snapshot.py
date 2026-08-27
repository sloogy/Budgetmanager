"""Eingefrorene Analysedaten fuer den Bankimport.

Die Bankimport-Analyse liest heute waehrend der Berechnung staendig aus der
Datenbank: existierende Kategorien, erlaubte Tags, das KI-Gedaechtnis, die
TWINT-Marker und die bereits importierten Zeilen. Solange alles im
GUI-Thread lief, war das nur langsam. Sobald die Analyse in einen Worker
wandert, ist es ein Fehler: Eine ``sqlite3.Connection`` gehoert dem Thread,
der sie geoeffnet hat, und die Datenbank des BudgetManagers ist zusaetzlich
verschluesselt - eine zweite Verbindung im Worker haette weder den
Schluessel noch einen konsistenten Blick auf dieselbe Transaktion.

Darum wird alles, was die Analyse braucht, auf dem besitzenden Thread
*einmal* gelesen und in unveraenderliche Python-Strukturen ueberfuehrt.
:class:`BankImportAnalysisSnapshot` ist dieses Buendel. Er beantwortet
dieselben Fragen wie die Modelle, aus denen er stammt, haelt aber weder eine
Verbindung noch ein datenbankgebundenes Objekt.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from model.bank_import_ai import (
    AIKnowledgeSnapshot,
    AIPrediction,
    BankImportAI,
    nocase_key,
)
from model.bank_import_service import external_id
from model.bank_statement_reader import BankTransaction
from model.category_model import CategoryModel
from model.twint_import_policy import ai_fingerprint
from model.typ_constants import TYP_EXPENSES, TYP_INCOME

_CATEGORY_TYPES = (TYP_EXPENSES, TYP_INCOME)


@dataclass(frozen=True)
class MarkerEntry:
    """Ein Eintrag aus ``bank_import_marker_state``.

    ``external_id`` ist dort Primaerschluessel, je Buchungszeile existiert
    also genau ein Marker; die Art steht in ``marker_kind``.
    """

    marker_kind: str
    category_typ: str
    category: str


@dataclass(frozen=True)
class BankImportAnalysisSnapshot:
    """Alle datenbankgebundenen Analysedaten - eingefroren und weitergebbar.

    Die Felder sind bewusst nur lesbar: ``MappingProxyType`` verhindert das
    Eintragen, ``frozenset``/``tuple`` das Aendern. Ein Worker, der aus dem
    Snapshot rechnet, kann den Zustand des GUI-Threads darum nicht
    nachtraeglich verschieben.
    """

    ai: AIKnowledgeSnapshot
    category_tree: Mapping[str, tuple[tuple[str, str], ...]]
    category_tags: Mapping[tuple[str, str], frozenset[str]]
    imported_external_ids: frozenset[str]
    markers: Mapping[str, MarkerEntry]
    twint_memory: Mapping[str, tuple[str, str]]

    # ── Kategorien und Tags ─────────────────────────────────────────────
    def categories_for(self, typ: str) -> frozenset[str]:
        return self.ai.categories_for(typ)

    def category_tree_for(self, typ: str) -> tuple[tuple[str, str], ...]:
        """Anzeige-/Namenspaare fuer die Kategorie-Dropdowns."""
        return self.category_tree.get(typ, ())

    def tags_for_category(self, typ: str, category: str) -> set[str]:
        """Fest an eine Kategorie gebundene Tags."""
        return set(self.category_tags.get((typ, category), frozenset()))

    def allocation_for_tags(self, tags: Sequence[str]) -> tuple[float | None, str]:
        return self.ai.allocation_for_tags(tags)

    def predict(
        self, *, typ: str, description: str, counterparty: str = ""
    ) -> AIPrediction:
        return self.ai.predict(
            typ=typ, description=description, counterparty=counterparty
        )

    # ── Duplikate ───────────────────────────────────────────────────────
    def is_duplicate(self, tx: BankTransaction, document_digest: str) -> bool:
        return external_id(tx, document_digest) in self.imported_external_ids

    def duplicate_indexes(
        self, transactions: Sequence[BankTransaction], document_digest: str
    ) -> set[int]:
        return {
            index
            for index, tx in enumerate(transactions)
            if self.is_duplicate(tx, document_digest)
        }

    # ── TWINT-/KI-Marker ────────────────────────────────────────────────
    def is_marked(
        self,
        tx: BankTransaction,
        document_digest: str,
        *,
        marker_kind: str = "twint_credit",
    ) -> bool:
        entry = self.markers.get(external_id(tx, document_digest))
        return entry is not None and entry.marker_kind == marker_kind

    def marked_indexes(
        self,
        transactions: Sequence[BankTransaction],
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
        entry = self.markers.get(external_id(tx, document_digest))
        if entry is None or entry.marker_kind != marker_kind:
            return "", ""
        return entry.category_typ, entry.category

    def suggest_category(self, tx: BankTransaction) -> tuple[str, str]:
        fingerprint = ai_fingerprint(tx)
        if not fingerprint:
            return "", ""
        return self.twint_memory.get(fingerprint, ("", ""))


def _category_tree(conn: sqlite3.Connection) -> dict[str, tuple[tuple[str, str], ...]]:
    categories = CategoryModel(conn)
    return {typ: tuple(categories.list_names_tree(typ)) for typ in _CATEGORY_TYPES}


def _category_tags(conn: sqlite3.Connection) -> dict[tuple[str, str], frozenset[str]]:
    try:
        rows = conn.execute(
            """
            SELECT c.typ, c.name, t.name
            FROM category_tags ct
            JOIN categories c ON c.id = ct.category_id
            JOIN tags t ON t.id = ct.tag_id
            """
        ).fetchall()
    except sqlite3.OperationalError:
        # Aeltere Datenbestaende kennen category_tags noch nicht; dann gibt es
        # schlicht keine fest gebundenen Tags.
        return {}
    grouped: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        grouped.setdefault((str(row[0]), str(row[1])), set()).add(str(row[2]))
    return {key: frozenset(value) for key, value in grouped.items()}


def _imported_external_ids(conn: sqlite3.Connection) -> frozenset[str]:
    """Nur Zeilen, deren Tracking-Eintrag es noch gibt - wie ``is_duplicate``."""
    try:
        rows = conn.execute(
            """
            SELECT s.external_id
            FROM bank_import_state s
            JOIN tracking t ON t.id = s.tracking_id
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return frozenset()
    return frozenset(str(row[0]) for row in rows)


def _markers(conn: sqlite3.Connection) -> dict[str, MarkerEntry]:
    try:
        rows = conn.execute(
            "SELECT external_id, marker_kind, ai_category_typ, ai_category "
            "FROM bank_import_marker_state"
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    return {
        str(row[0]): MarkerEntry(str(row[1]), str(row[2] or ""), str(row[3] or ""))
        for row in rows
    }


def _twint_memory(
    conn: sqlite3.Connection, categories: Mapping[str, frozenset[str]]
) -> dict[str, tuple[str, str]]:
    """TWINT-Gedaechtnis, bereits gegen die echten Kategorien gefiltert.

    ``BankImportMarkerStore.suggest_category`` prueft die Existenz erst beim
    Lesen. Hier geschieht das einmal beim Einfrieren, damit der Worker keinen
    Kategorienamen mehr nachschlagen muss.
    """
    try:
        rows = conn.execute(
            "SELECT fingerprint, category_typ, category FROM ai_twint_memory"
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    known = {
        typ: {nocase_key(name) for name in names} for typ, names in categories.items()
    }
    memory: dict[str, tuple[str, str]] = {}
    for row in rows:
        typ, category = str(row[1]), str(row[2])
        if nocase_key(category) in known.get(typ, set()):
            memory[str(row[0])] = (typ, category)
    return memory


def capture_analysis_snapshot(
    conn: sqlite3.Connection,
    *,
    ai_model: BankImportAI | None = None,
) -> BankImportAnalysisSnapshot:
    """Zieht den Snapshot auf dem Thread, dem die Verbindung gehoert.

    Diese Funktion ist der einzige Ort, an dem die Analyse noch Datenbank
    beruehrt. Alles danach rechnet aus dem Rueckgabewert.

    ``ai_model`` reicht eine bereits vorhandene :class:`BankImportAI` durch;
    sonst wird eine erzeugt - was die KI-Tabellen anlegt, falls sie fehlen.
    """
    ai = (ai_model or BankImportAI(conn)).knowledge_snapshot()
    return BankImportAnalysisSnapshot(
        ai=ai,
        category_tree=MappingProxyType(_category_tree(conn)),
        category_tags=MappingProxyType(_category_tags(conn)),
        imported_external_ids=_imported_external_ids(conn),
        markers=MappingProxyType(_markers(conn)),
        twint_memory=MappingProxyType(_twint_memory(conn, ai.categories)),
    )


__all__ = [
    "BankImportAnalysisSnapshot",
    "MarkerEntry",
    "capture_analysis_snapshot",
]
