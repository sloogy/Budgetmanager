"""Nachtraegliche Korrekturen an importierten Buchungen zurueckgeben (P2.4).

Wenn der Anwender eine importierte Buchung von ``Restaurant`` auf
``Lebensmittel`` umstellt, ist das das ehrlichste Signal, das die Import-KI
bekommen kann: Jemand ist zurueckgegangen und hat eine Entscheidung
ausdruecklich zurueckgenommen. Es traegt darum die staerkste Lernquelle,
``tracking_correction`` (siehe :mod:`model.ai_learning_source`).

**Vier Dinge muessen belegt sein, sonst wird nichts gelernt.**

1. *Die Buchung stammt wirklich aus einem Bankimport.* Nachgewiesen wird das
   ueber genau eine Zeile in ``bank_import_state`` zu dieser ``tracking_id``
   und - wo die Spalte existiert - ueber ``tracking.source``. Zwei Zeilen
   heissen: nicht eindeutig, also nichts lernen.

2. *Der Originaltext ist verfuegbar.* Gelernt wird, was die Bank geschrieben
   hat, nicht der Text, den der Import daraus fuer die Buchungsdetails
   zusammengesetzt hat. In ``tracking.details`` steht unter anderem
   ``| Bankimport: Original 42.50 CHF; Tag-Regel Haushalt 50.00%`` - wer daraus
   lernte, brachte der KI die eigene Anzeigesprache bei. Datenbanken aus der
   Zeit vor P2.4 haben die beiden Spalten leer; dort wird nicht gelernt,
   sondern verzichtet.

3. *Es hat sich etwas geaendert, das die KI ueberhaupt vorhersagt.* Typ,
   Kategorie oder Tags. Wer nur den Betrag korrigiert, hat der KI nicht
   widersprochen - ein Lernvorgang wuerde die vorhandene Zuordnung stumm auf
   ``tracking_correction`` hochstufen, ohne dass jemand sie bestaetigt haette.

4. *Es ist eine Person gewesen.* Automatische interne Aenderungen - der
   LifePlanner-Abgleich, das Umbenennen einer Kategorie, ein Undo - laufen
   nicht ueber diesen Weg. Er wird ausschliesslich von den beiden Stellen
   gerufen, an denen ein Mensch eine Buchung bearbeitet.

Gelernt wird ausserdem nur bei eingeschaltetem Lernen; der Schalter kommt
vom Aufrufer, damit dieses Modul keine Einstellungsdatei kennen muss.

**Was der Originaltext fuer P2.1 und P2.2 bedeutet.** Er liegt in
``bank_import_state`` - derselben verschluesselten Benutzer-Datenbank wie
alles andere, also unter denselben Bedingungen wie ``ai_feedback.raw_text``
(einschliesslich des in P2.2 benannten Vorbehalts beim Schnellzugang, dessen
Sicherung den Schluessel mitnimmt). ``bank_import_state`` steht in
``PROTECTED_TABLES``: Ein KI-Reset leert sie **nicht**, denn sie ist die
Duplikaterkennung des Imports - wer sie mitloescht, bereitet Doppelbuchungen
vor. Der Banktext ueberlebt einen Reset damit; die KI bleibt trotzdem
``untrained``, weil sie aus dieser Tabelle nichts vorhersagt. Erst die
naechste Korrektur macht daraus wieder Wissen.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field

from model.ai_learning_source import SOURCE_TRACKING_CORRECTION
from model.bank_import_ai import BankImportAI, LearnOutcome

logger = logging.getLogger(__name__)

#: Das Lernen ist abgeschaltet - P2.1-Schalter, hier nur durchgereicht.
REASON_LEARNING_DISABLED = "learning_disabled"
#: Die Buchung gibt es nicht (mehr).
REASON_NO_ENTRY = "no_entry"
#: Keine Bankimport-Herkunft nachweisbar.
REASON_NOT_IMPORTED = "not_imported"
#: Mehr als eine Importzeile zeigt auf diese Buchung - nicht eindeutig.
REASON_AMBIGUOUS_ORIGIN = "ambiguous_origin"
#: Importiert, aber ohne gespeicherten Originaltext (Datenbank vor P2.4).
REASON_NO_ORIGINAL_TEXT = "no_original_text"
#: Nichts geaendert, was die KI vorhersagt.
REASON_UNCHANGED = "unchanged"
#: Die neue Kategorie gibt es im Ziel-Typ nicht (mehr).
REASON_UNKNOWN_CATEGORY = "unknown_category"


@dataclass(frozen=True)
class TrackingSnapshot:
    """Der Stand einer Buchung, soweit die KI ihn vorhersagt."""

    typ: str
    category: str
    tags: frozenset[str] = field(default_factory=frozenset)

    def predicts_same_as(self, other: TrackingSnapshot) -> bool:
        return (
            self.typ == other.typ
            and self.category.casefold() == other.category.casefold()
            and self.tags == other.tags
        )


@dataclass(frozen=True)
class ImportOrigin:
    """Der belegte Ursprung einer importierten Buchung."""

    external_id: str
    description: str
    counterparty: str


@dataclass(frozen=True)
class CorrectionResult:
    """Was der Ruecklernversuch ergeben hat.

    ``reason`` ist leer, wenn gelernt wurde. Sonst nennt er den Grund - die
    Gruende sind Konstanten dieses Moduls und damit pruefbar, statt nur in
    einer Logzeile zu stehen.
    """

    learned: bool
    reason: str = ""
    outcome: LearnOutcome | None = None


class TrackingCorrectionLearner:
    """Nimmt eine Korrektur an einer importierten Buchung entgegen.

    Der Ablauf ist zweiteilig, weil der Stand *vor* der Aenderung nur vorher
    zu haben ist::

        korrektur = TrackingCorrectionLearner(conn)
        vorher = korrektur.snapshot(row_id)
        ...  # Buchung speichern, Tags setzen
        korrektur.relearn(row_id, vorher, learn_enabled=...)

    ``snapshot`` darf ``None`` zurueckgeben (Buchung weg, Datenbank ohne
    Tracking); ``relearn`` kommt damit zurecht und lernt dann nichts.
    """

    def __init__(self, conn: sqlite3.Connection, ai: BankImportAI | None = None):
        self.conn = conn
        self._ai = ai

    @property
    def ai(self) -> BankImportAI:
        """Die KI wird erst beim ersten Bedarf erzeugt.

        ``BankImportAI.__init__`` legt die KI-Tabellen an. Das soll nicht schon
        beim Oeffnen eines Bearbeitungsdialogs passieren, sondern erst, wenn
        tatsaechlich eine Korrektur zu lernen ist.
        """
        if self._ai is None:
            self._ai = BankImportAI(self.conn)
        return self._ai

    def snapshot(self, tracking_id: int) -> TrackingSnapshot | None:
        row = self.conn.execute(
            "SELECT typ, category FROM tracking WHERE id=?", (int(tracking_id),)
        ).fetchone()
        if not row:
            return None
        return TrackingSnapshot(str(row[0]), str(row[1]), self._tags(tracking_id))

    def _tags(self, tracking_id: int) -> frozenset[str]:
        rows = self.conn.execute(
            "SELECT t.name FROM entry_tags e JOIN tags t ON t.id = e.tag_id "
            "WHERE e.entry_id=?",
            (int(tracking_id),),
        ).fetchall()
        return frozenset(str(row[0]) for row in rows)

    def import_origin(self, tracking_id: int) -> ImportOrigin | None:
        """Der Beleg dafuer, dass diese Buchung aus einem Bankimport stammt.

        ``None`` heisst: nicht nachweisbar - und damit nicht lernbar.
        """
        try:
            rows = self.conn.execute(
                "SELECT external_id, original_description, original_counterparty "
                "FROM bank_import_state WHERE tracking_id=?",
                (int(tracking_id),),
            ).fetchall()
        except sqlite3.OperationalError:
            # Noch nie ein Bankimport in dieser Datenbank.
            return None
        if len(rows) != 1:
            return None
        return ImportOrigin(
            str(rows[0][0]), str(rows[0][1] or ""), str(rows[0][2] or "")
        )

    def _marked_as_import(self, tracking_id: int) -> bool:
        """Zweiter, unabhaengiger Beleg - sofern die Spalte existiert.

        ``tracking.source`` kam erst spaeter dazu. Fehlt sie, traegt der
        Eintrag in ``bank_import_state`` den Nachweis allein; ihn deswegen
        abzulehnen waere strenger als noetig.
        """
        spalten = {
            str(row[1])
            for row in self.conn.execute("PRAGMA table_info(tracking)").fetchall()
        }
        if "source" not in spalten:
            return True
        row = self.conn.execute(
            "SELECT source FROM tracking WHERE id=?", (int(tracking_id),)
        ).fetchone()
        return bool(row) and str(row[0] or "") == "bank_import"

    def relearn(
        self,
        tracking_id: int,
        before: TrackingSnapshot | None,
        *,
        learn_enabled: bool,
    ) -> CorrectionResult:
        """Lernt die Korrektur zurueck - oder sagt, warum nicht."""
        if not learn_enabled:
            return CorrectionResult(False, REASON_LEARNING_DISABLED)
        after = self.snapshot(int(tracking_id))
        if after is None:
            return CorrectionResult(False, REASON_NO_ENTRY)
        if before is not None and before.predicts_same_as(after):
            return CorrectionResult(False, REASON_UNCHANGED)
        if not self._marked_as_import(int(tracking_id)):
            return CorrectionResult(False, REASON_NOT_IMPORTED)
        origin = self.import_origin(int(tracking_id))
        if origin is None:
            rows = self.conn.execute(
                "SELECT COUNT(*) FROM bank_import_state WHERE tracking_id=?",
                (int(tracking_id),),
            ).fetchone()
            mehrdeutig = bool(rows) and int(rows[0]) > 1
            return CorrectionResult(
                False,
                REASON_AMBIGUOUS_ORIGIN if mehrdeutig else REASON_NOT_IMPORTED,
            )
        if not (origin.description.strip() or origin.counterparty.strip()):
            return CorrectionResult(False, REASON_NO_ORIGINAL_TEXT)
        try:
            outcome = self.ai.learn(
                typ=after.typ,
                category=after.category,
                description=origin.description,
                counterparty=origin.counterparty,
                tags=tuple(sorted(after.tags)),
                source=SOURCE_TRACKING_CORRECTION,
            )
        except ValueError as exc:
            # Kategorie oder Tag existiert im BudgetManager nicht (mehr), oder
            # der Originaltext ergibt keinen lernbaren Fingerprint. Kein Grund
            # fuer einen Abbruch der Bearbeitung - die Buchung ist gespeichert,
            # nur gelernt wird nichts.
            logger.info("Korrektur nicht lernbar (Buchung %s): %s", tracking_id, exc)
            return CorrectionResult(False, REASON_UNKNOWN_CATEGORY)
        logger.info(
            "Korrektur zurueckgelernt (Buchung %s): gespeichert=%s, verdraengt=%s",
            tracking_id,
            outcome.stored,
            outcome.superseded,
        )
        return CorrectionResult(outcome.stored, "", outcome)


__all__ = [
    "REASON_AMBIGUOUS_ORIGIN",
    "REASON_LEARNING_DISABLED",
    "REASON_NOT_IMPORTED",
    "REASON_NO_ENTRY",
    "REASON_NO_ORIGINAL_TEXT",
    "REASON_UNCHANGED",
    "REASON_UNKNOWN_CATEGORY",
    "CorrectionResult",
    "ImportOrigin",
    "TrackingCorrectionLearner",
    "TrackingSnapshot",
]
