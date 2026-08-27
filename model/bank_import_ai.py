"""Kleine lokale Lern-KI für Bankimporte im BudgetManager.

Sie läuft vollständig auf der bestehenden SQLite-Verbindung, lernt nur aus
bestätigten Buchungen und darf weder Kategorien noch Tags erfinden.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from types import MappingProxyType
from typing import Protocol

from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS

_ALLOWED_TYPES = frozenset({TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS})
_LONG_NUMBER = re.compile(r"\b\d{5,}\b")
_NOISE = re.compile(
    r"\b(?:ref|referenz|zahlung|kartenzahlung|belastung|gutschrift)\b", re.I
)


@dataclass(frozen=True)
class AIPrediction:
    category: str
    tags: tuple[str, ...]
    confidence: float
    method: str
    allocation_percent: float | None = None
    allocation_rule_tag: str = ""


@dataclass(frozen=True)
class MerchantMemoryEntry:
    """Ein bestaetigter Haendlereintrag, bereits gegen die Stammdaten gefiltert."""

    category: str
    tags: tuple[str, ...]
    confirmations: int


@dataclass(frozen=True)
class FeedbackExample:
    """Ein aktives Lernbeispiel; Tags sind bereits auf echte Tags reduziert."""

    fingerprint: str
    category: str
    tags: tuple[str, ...]
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class TagAllocationRule:
    """Eine Kostenanteil-Regel aus ``ai_tag_rules``."""

    tag_name: str
    allocation_percent: float
    priority: int


@dataclass(frozen=True)
class BookingSignal:
    booking_id: str
    booking_date: date
    amount: float
    description: str
    counterparty: str = ""


@dataclass(frozen=True)
class ReimbursementMatch:
    expense_id: str
    credit_id: str
    days_after: int
    reimbursement_amount: float
    reimbursement_percent: float
    personal_share_percent: float
    confidence: float


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).casefold()
    value = _LONG_NUMBER.sub(" ", value)
    value = _NOISE.sub(" ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(token for token in _normalize(text).split() if len(token) >= 2)


def _fingerprint(description: str, counterparty: str = "") -> str:
    return " ".join(dict.fromkeys(_tokens(" ".join((counterparty, description)))))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def nocase_key(value: str) -> str:
    """Bildet SQLites ``COLLATE NOCASE`` nach - es faltet nur ``A``-``Z``.

    Ein Snapshot muss dieselben Treffer liefern wie die SQL-Abfragen, aus denen
    er gefuellt wurde. ``str.casefold`` faltet zu viel (etwa das griechische
    Sigma) und wuerde Tags zusammenziehen, die SQLite getrennt haelt.
    """
    return "".join(
        chr(ord(ch) + 32) if "A" <= ch <= "Z" else ch for ch in str(value or "")
    )


def validate_typ(typ: str) -> str:
    value = str(typ or "").strip()
    if value not in _ALLOWED_TYPES:
        raise ValueError(f"Unbekannter BudgetManager-Typ: {value!r}")
    return value


def validate_tag_names(
    tags: Sequence[str], known_tags: Mapping[str, str]
) -> tuple[str, ...]:
    """Ersetzt Tagnamen durch die Schreibweise der Stammdaten."""
    valid: list[str] = []
    for tag in tags:
        raw = str(tag or "").strip()
        if not raw:
            continue
        canonical = known_tags.get(nocase_key(raw))
        if canonical is None:
            raise ValueError(f"Tag {raw!r} existiert nicht im BudgetManager.")
        if canonical not in valid:
            valid.append(canonical)
    return tuple(valid)


def filter_known_tags(raw_json: str, known_tags: Mapping[str, str]) -> tuple[str, ...]:
    """Liest eine gespeicherte Tagliste und wirft geloeschte Tags weg."""
    try:
        values = tuple(str(value) for value in json.loads(str(raw_json or "[]")))
    except (TypeError, ValueError, json.JSONDecodeError):
        return ()
    return tuple(value for value in values if nocase_key(value) in known_tags)


def decode_tokens(raw_json: str) -> tuple[str, ...]:
    try:
        return tuple(str(value) for value in json.loads(str(raw_json or "[]")))
    except (TypeError, ValueError, json.JSONDecodeError):
        return ()


def resolve_allocation(
    rules: Sequence[TagAllocationRule],
    tags: Sequence[str],
    *,
    known_tags: Mapping[str, str],
) -> tuple[float | None, str]:
    """Bestimmt den Kostenanteil aus den Tag-Regeln - ohne Datenbankzugriff."""
    names = validate_tag_names(tags, known_tags)
    if not names:
        return None, ""
    wanted = {name.casefold() for name in names}
    ordered = sorted(
        rules, key=lambda rule: (-int(rule.priority), nocase_key(rule.tag_name))
    )
    matching = [rule for rule in ordered if str(rule.tag_name).casefold() in wanted]
    if not matching:
        return None, ""
    highest = int(matching[0].priority)
    top = [rule for rule in matching if int(rule.priority) == highest]
    percents = {float(rule.allocation_percent) for rule in top}
    if len(percents) != 1:
        return None, ""
    return float(top[0].allocation_percent), str(top[0].tag_name)


class AIKnowledgeSource(Protocol):
    """Alles, was die Vorhersage braucht - egal ob aus DB oder aus Snapshot."""

    def categories_for(self, typ: str) -> frozenset[str]: ...

    def merchant_entry(
        self, *, fingerprint: str, typ: str
    ) -> MerchantMemoryEntry | None: ...

    def feedback_examples(self, typ: str) -> tuple[FeedbackExample, ...]: ...

    def allocation_for_tags(self, tags: Sequence[str]) -> tuple[float | None, str]: ...


def predict_from_knowledge(
    knowledge: AIKnowledgeSource,
    *,
    typ: str,
    description: str,
    counterparty: str = "",
) -> AIPrediction:
    """Die eine Vorhersagerechnung.

    Sie steht bewusst ausserhalb von :class:`BankImportAI`, damit derselbe
    Code sowohl auf der Datenbank als auch auf einem eingefrorenen Snapshot
    laeuft. Zwei Fassungen derselben Formel wuerden frueher oder spaeter
    auseinanderlaufen, und der Unterschied faellt in einem Importvorschlag
    niemandem auf.
    """
    typ = validate_typ(typ)
    available = knowledge.categories_for(typ)
    if not available:
        return AIPrediction("", (), 0.0, "no_categories")
    fingerprint = _fingerprint(description, counterparty)
    if fingerprint:
        entry = knowledge.merchant_entry(fingerprint=fingerprint, typ=typ)
        if entry is not None and entry.category in available:
            allocation, source_tag = knowledge.allocation_for_tags(entry.tags)
            return AIPrediction(
                entry.category,
                entry.tags,
                min(0.995, 0.90 + 0.015 * int(entry.confirmations)),
                "merchant_memory",
                allocation,
                source_tag,
            )

    examples = [
        example
        for example in knowledge.feedback_examples(typ)
        if example.category in available
    ]
    if not examples:
        return AIPrediction("", (), 0.0, "untrained")

    query = _tokens(" ".join((counterparty, description)))
    query_set = set(query)
    best: tuple[float, FeedbackExample] | None = None
    for example in examples:
        sim = _jaccard(
            query_set or set(fingerprint.split()), set(example.fingerprint.split())
        )
        if best is None or sim > best[0]:
            best = (sim, example)
    if best and best[0] >= 0.72:
        example = best[1]
        allocation, source_tag = knowledge.allocation_for_tags(example.tags)
        return AIPrediction(
            example.category,
            example.tags,
            min(0.89, 0.62 + best[0] * 0.30),
            "similar_merchant",
            allocation,
            source_tag,
        )
    if not query:
        return AIPrediction("", (), 0.0, "no_features")

    category_docs: Counter[str] = Counter()
    category_tokens: dict[str, Counter[str]] = defaultdict(Counter)
    vocabulary: set[str] = set()
    tag_votes: dict[str, Counter[str]] = defaultdict(Counter)
    for example in examples:
        category_docs[example.category] += 1
        category_tokens[example.category].update(example.tokens)
        vocabulary.update(example.tokens)
        for tag in example.tags:
            tag_votes[example.category][tag] += 1
    total_docs = sum(category_docs.values())
    vocab_size = max(1, len(vocabulary))
    scores: dict[str, float] = {}
    for category in category_docs:
        score = math.log(
            (category_docs[category] + 1) / (total_docs + len(category_docs))
        )
        counts = category_tokens[category]
        denominator = sum(counts.values()) + vocab_size
        for token in query:
            score += math.log((counts[token] + 1) / denominator)
        scores[category] = score
    top = max(scores, key=lambda name: scores[name])
    maximum = max(scores.values())
    weights = {cat: math.exp(score - maximum) for cat, score in scores.items()}
    confidence = weights[top] / sum(weights.values())
    if len(scores) == 1:
        confidence = min(confidence, 0.70)
    tags = tuple(tag for tag, _count in tag_votes[top].most_common())
    allocation, source_tag = knowledge.allocation_for_tags(tags)
    return AIPrediction(
        top,
        tags,
        round(float(confidence), 4),
        "naive_bayes",
        allocation,
        source_tag,
    )


@dataclass(frozen=True)
class AIKnowledgeSnapshot:
    """Eingefrorenes KI-Wissen ohne jede Datenbankbindung.

    Der Snapshot wird auf dem besitzenden Thread gezogen; danach rechnet er
    ohne SQLite-Verbindung weiter und darf an einen Worker gereicht werden.
    """

    categories: Mapping[str, frozenset[str]]
    known_tags: Mapping[str, str]
    merchant_memory: Mapping[tuple[str, str], MerchantMemoryEntry]
    feedback: Mapping[str, tuple[FeedbackExample, ...]]
    tag_rules: tuple[TagAllocationRule, ...]

    @classmethod
    def freeze(
        cls,
        *,
        categories: Mapping[str, frozenset[str]],
        known_tags: Mapping[str, str],
        merchant_memory: Mapping[tuple[str, str], MerchantMemoryEntry],
        feedback: Mapping[str, tuple[FeedbackExample, ...]],
        tag_rules: Sequence[TagAllocationRule],
    ) -> AIKnowledgeSnapshot:
        return cls(
            categories=MappingProxyType(dict(categories)),
            known_tags=MappingProxyType(dict(known_tags)),
            merchant_memory=MappingProxyType(dict(merchant_memory)),
            feedback=MappingProxyType(dict(feedback)),
            tag_rules=tuple(tag_rules),
        )

    def categories_for(self, typ: str) -> frozenset[str]:
        return self.categories.get(validate_typ(typ), frozenset())

    def merchant_entry(
        self, *, fingerprint: str, typ: str
    ) -> MerchantMemoryEntry | None:
        return self.merchant_memory.get((fingerprint, typ))

    def feedback_examples(self, typ: str) -> tuple[FeedbackExample, ...]:
        return self.feedback.get(typ, ())

    def allocation_for_tags(self, tags: Sequence[str]) -> tuple[float | None, str]:
        return resolve_allocation(self.tag_rules, tags, known_tags=self.known_tags)

    def predict(
        self, *, typ: str, description: str, counterparty: str = ""
    ) -> AIPrediction:
        return predict_from_knowledge(
            self, typ=typ, description=description, counterparty=counterparty
        )


def _is_twint(signal: BookingSignal) -> bool:
    text = f"{signal.counterparty} {signal.description}".casefold()
    return "twint" in text


def match_twint_reimbursement(
    expense: BookingSignal,
    credits: list[BookingSignal],
    *,
    max_days: int = 4,
) -> ReimbursementMatch | None:
    """Sucht eine plausible zeitnahe TWINT-Erstattung zu einer Ausgabe.

    Der Matcher ändert nichts selbst. Er liefert nur einen reviewbaren Vorschlag.
    """
    if expense.amount >= 0:
        return None
    expense_abs = abs(float(expense.amount))
    if expense_abs <= 0:
        return None

    best: tuple[float, BookingSignal, int] | None = None
    for credit in credits:
        if credit.amount <= 0 or not _is_twint(credit):
            continue
        days = (credit.booking_date - expense.booking_date).days
        if days < 0 or days > max_days:
            continue
        credit_amount = float(credit.amount)
        if credit_amount > expense_abs * 1.02:
            continue
        ratio = min(1.0, credit_amount / expense_abs)
        shape = max(0.0, 1.0 - min(abs(ratio - 0.5), abs(ratio - 1.0)))
        score = 0.62 + 0.22 * (1 - days / max(1, max_days)) + 0.16 * shape
        if best is None or score > best[0]:
            best = (score, credit, days)
    if best is None:
        return None

    score, credit, days = best
    reimbursement = min(expense_abs, float(credit.amount))
    reimbursement_percent = round(reimbursement / expense_abs * 100.0, 2)
    personal = round(max(0.0, 100.0 - reimbursement_percent), 2)
    return ReimbursementMatch(
        expense_id=expense.booking_id,
        credit_id=credit.booking_id,
        days_after=days,
        reimbursement_amount=round(reimbursement, 2),
        reimbursement_percent=reimbursement_percent,
        personal_share_percent=personal,
        confidence=round(min(0.99, score), 4),
    )


class BankImportAI:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS ai_merchant_memory (
                fingerprint TEXT NOT NULL,
                typ TEXT NOT NULL,
                category TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                confirmations INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (fingerprint, typ)
            );
            CREATE TABLE IF NOT EXISTS ai_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint TEXT NOT NULL,
                typ TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                category TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                tokens_json TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ai_tag_rules (
                tag_name TEXT PRIMARY KEY COLLATE NOCASE,
                allocation_percent REAL NOT NULL
                    CHECK(allocation_percent >= 0 AND allocation_percent <= 100),
                priority INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ai_feedback_active
                ON ai_feedback(active, typ, category);
            """
        )
        self.conn.commit()

    def _validate_typ(self, typ: str) -> str:
        return validate_typ(typ)

    def _known_tag_names(self) -> dict[str, str]:
        """Alle echten Tagnamen, nach NOCASE-Schluessel greifbar."""
        names: dict[str, str] = {}
        for row in self.conn.execute("SELECT name FROM tags ORDER BY rowid"):
            names.setdefault(nocase_key(str(row[0])), str(row[0]))
        return names

    def _validate_category(self, typ: str, category: str) -> str:
        typ = self._validate_typ(typ)
        row = self.conn.execute(
            "SELECT name FROM categories "
            "WHERE typ=? AND name=? COLLATE NOCASE LIMIT 1",
            (typ, str(category or "").strip()),
        ).fetchone()
        if not row:
            raise ValueError(
                f"Kategorie {category!r} existiert nicht im BudgetManager-Typ {typ!r}."
            )
        return str(row[0])

    def _validate_tags(self, tags: Sequence[str]) -> tuple[str, ...]:
        return validate_tag_names(tags, self._known_tag_names())

    def set_tag_allocation_rule(
        self, tag_name: str, percent: float, *, priority: int = 0
    ) -> None:
        tag = self._validate_tags((tag_name,))[0]
        percent = float(percent)
        if not 0 <= percent <= 100:
            raise ValueError("Kostenanteil muss zwischen 0 und 100 liegen.")
        self.conn.execute(
            """
            INSERT INTO ai_tag_rules(tag_name, allocation_percent, priority, updated_at)
            VALUES(?,?,?,?)
            ON CONFLICT(tag_name) DO UPDATE SET
              allocation_percent=excluded.allocation_percent,
              priority=excluded.priority,
              updated_at=excluded.updated_at
            """,
            (tag, percent, int(priority), datetime.now(UTC).isoformat()),
        )
        self.conn.commit()

    def _tag_rules(self) -> tuple[TagAllocationRule, ...]:
        return tuple(
            TagAllocationRule(str(row[0]), float(row[1]), int(row[2]))
            for row in self.conn.execute(
                "SELECT tag_name, allocation_percent, priority FROM ai_tag_rules"
            ).fetchall()
        )

    def allocation_for_tags(self, tags: Sequence[str]) -> tuple[float | None, str]:
        return resolve_allocation(
            self._tag_rules(), tags, known_tags=self._known_tag_names()
        )

    def learn(
        self,
        *,
        typ: str,
        category: str,
        description: str,
        counterparty: str = "",
        tags: tuple[str, ...] | list[str] = (),
        commit: bool = True,
    ) -> None:
        """Lernt nur bestätigte Daten; ``commit=False`` dient atomaren Batch-Imports."""
        typ = self._validate_typ(typ)
        category = self._validate_category(typ, category)
        tags = self._validate_tags(tags)
        fingerprint = _fingerprint(description, counterparty)
        if not fingerprint:
            raise ValueError("Buchung enthält keinen lernbaren Text.")
        now = datetime.now(UTC).isoformat()
        row = self.conn.execute(
            "SELECT category, tags_json, confirmations FROM ai_merchant_memory "
            "WHERE fingerprint=? AND typ=?",
            (fingerprint, typ),
        ).fetchone()
        confirmations = 1
        tags_json = json.dumps(tags, ensure_ascii=False)
        if (
            row
            and str(row[0]).casefold() == category.casefold()
            and str(row[1]) == tags_json
        ):
            confirmations = int(row[2]) + 1
        self.conn.execute(
            """
            INSERT INTO ai_merchant_memory(
                fingerprint,typ,category,tags_json,confirmations,updated_at
            ) VALUES(?,?,?,?,?,?)
            ON CONFLICT(fingerprint,typ) DO UPDATE SET
              category=excluded.category,
              tags_json=excluded.tags_json,
              confirmations=excluded.confirmations,
              updated_at=excluded.updated_at
            """,
            (fingerprint, typ, category, tags_json, confirmations, now),
        )
        self.conn.execute(
            "UPDATE ai_feedback SET active=0 "
            "WHERE fingerprint=? AND typ=? AND active=1",
            (fingerprint, typ),
        )
        raw_text = " ".join(part for part in (counterparty, description) if part)
        self.conn.execute(
            """
            INSERT INTO ai_feedback(
                fingerprint,typ,raw_text,category,tags_json,tokens_json,active,created_at
            ) VALUES(?,?,?,?,?,?,1,?)
            """,
            (
                fingerprint,
                typ,
                raw_text,
                category,
                tags_json,
                json.dumps(_tokens(raw_text), ensure_ascii=False),
                now,
            ),
        )
        if commit:
            self.conn.commit()

    def categories_for(self, typ: str) -> frozenset[str]:
        return frozenset(
            str(row[0])
            for row in self.conn.execute(
                "SELECT name FROM categories WHERE typ=?", (validate_typ(typ),)
            ).fetchall()
        )

    def merchant_entry(
        self, *, fingerprint: str, typ: str
    ) -> MerchantMemoryEntry | None:
        row = self.conn.execute(
            "SELECT category,tags_json,confirmations FROM ai_merchant_memory "
            "WHERE fingerprint=? AND typ=?",
            (fingerprint, typ),
        ).fetchone()
        if not row:
            return None
        return MerchantMemoryEntry(
            str(row[0]),
            filter_known_tags(str(row[1]), self._known_tag_names()),
            int(row[2]),
        )

    def feedback_examples(self, typ: str) -> tuple[FeedbackExample, ...]:
        known = self._known_tag_names()
        return tuple(
            FeedbackExample(
                str(row[0]),
                str(row[1]),
                filter_known_tags(str(row[2]), known),
                decode_tokens(str(row[3])),
            )
            for row in self.conn.execute(
                "SELECT fingerprint,category,tags_json,tokens_json "
                "FROM ai_feedback WHERE active=1 AND typ=?",
                (typ,),
            ).fetchall()
        )

    def predict(
        self, *, typ: str, description: str, counterparty: str = ""
    ) -> AIPrediction:
        """Vorhersage direkt auf der Datenbank.

        Die Rechnung selbst steckt in :func:`predict_from_knowledge`; hier
        werden nur die Zeilen nachgeladen, die sie anfordert. Ein Snapshot
        beantwortet dieselben Fragen aus eingefrorenen Daten und kommt darum
        zwangslaeufig auf dasselbe Ergebnis.
        """
        return predict_from_knowledge(
            self, typ=typ, description=description, counterparty=counterparty
        )

    def knowledge_snapshot(self) -> AIKnowledgeSnapshot:
        """Friert das KI-Wissen fuer die Weitergabe an einen Worker ein."""
        known_tags = self._known_tag_names()
        categories: dict[str, frozenset[str]] = {}
        feedback: dict[str, tuple[FeedbackExample, ...]] = {}
        for typ in sorted(_ALLOWED_TYPES):
            categories[typ] = self.categories_for(typ)
            feedback[typ] = self.feedback_examples(typ)
        merchant_memory: dict[tuple[str, str], MerchantMemoryEntry] = {}
        for row in self.conn.execute(
            "SELECT fingerprint,typ,category,tags_json,confirmations "
            "FROM ai_merchant_memory"
        ).fetchall():
            merchant_memory[(str(row[0]), str(row[1]))] = MerchantMemoryEntry(
                str(row[2]), filter_known_tags(str(row[3]), known_tags), int(row[4])
            )
        return AIKnowledgeSnapshot.freeze(
            categories=categories,
            known_tags=known_tags,
            merchant_memory=merchant_memory,
            feedback=feedback,
            tag_rules=self._tag_rules(),
        )
