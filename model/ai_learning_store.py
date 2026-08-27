"""Bestand und Rueckstellung des lokalen KI-Lernspeichers.

Die Import-KI lernt ausschliesslich in der bereits verschluesselten
Benutzer-Datenbank (Architekturregel 1.5). Dieses Modul beantwortet zwei
Fragen ueber diesen Speicher, ohne die Oberflaeche zu kennen:

* Wie viele Muster hat die KI gelernt?
* Wie werden genau diese Muster - und sonst nichts - wieder geloescht?

**Warum das getrennt steht.** Ein Reset, der zu viel loescht, ist ein
Datenverlust ohne Rueckweg. Die Liste der betroffenen Tabellen gehoert
deshalb an genau eine Stelle, wird von genau einem Test bewacht und darf
nicht in einem Dialog verstreut nachgebaut werden.

**Warum jedes SQL hier ausgeschrieben steht.** Eine Schleife ueber Tabellennamen
mit ``f"DELETE FROM {name}"`` waere kuerzer, aber ``DELETE`` aus einem
zusammengesetzten String ist genau die Bauart, die der Release-Audit
``d1_sql_surface`` zu Recht beanstandet - von aussen ist einem solchen Aufruf
nicht anzusehen, welche Tabelle er trifft. Bei einer Loeschoperation ist das
keine Stilfrage.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from model.database import db_transaction

logger = logging.getLogger(__name__)

#: Haendler-/Fingerprint-Gedaechtnis der Import-KI.
#:
#: ``ai_merchant_memory`` traegt die bestaetigten Haendlerzuordnungen des
#: allgemeinen Bankimports, ``ai_twint_memory`` dieselbe Art Wissen fuer
#: TWINT-Eingaenge. Beides sind Verallgemeinerungen ueber Buchungstexte -
#: also gelernte Muster, nicht Buchungen.
MEMORY_TABLES: tuple[str, ...] = ("ai_merchant_memory", "ai_twint_memory")

#: Einzelne Lernbeispiele samt Tokens ("KI-Feedback").
FEEDBACK_TABLES: tuple[str, ...] = ("ai_feedback",)

#: Lernmetadaten: die Kostenanteil-Regeln, die eine Vorhersage nachtraeglich
#: gewichten. Sie sind nirgends in der Oberflaeche einstellbar und existieren
#: nur, um Vorhersagen zu formen - sie gehoeren damit zum Lernstand und nicht
#: zu den Stammdaten. Die Tags selbst bleiben unberuehrt.
METADATA_TABLES: tuple[str, ...] = ("ai_tag_rules",)

#: Alles, was ein Reset leeren darf - und nichts sonst.
RESET_TABLES: tuple[str, ...] = MEMORY_TABLES + FEEDBACK_TABLES + METADATA_TABLES

#: Ausdruecklich **nicht** vom Reset betroffen. Die Liste steht hier, damit der
#: Test sie nicht selbst erfinden muss und eine spaetere Erweiterung von
#: :data:`RESET_TABLES` sofort auffaellt.
#:
#: ``bank_import_state`` und ``bank_import_marker_state`` sind bewusst dabei:
#: Sie sind die Duplikaterkennung des Imports. Wer sie mitloescht, bietet
#: bereits gebuchte Zeilen erneut an - der Reset wuerde Doppelbuchungen
#: vorbereiten, statt Wissen zu loeschen.
PROTECTED_TABLES: tuple[str, ...] = (
    "tracking",
    "budget",
    "categories",
    "tags",
    "category_tags",
    "entry_tags",
    "savings_goals",
    "bank_import_state",
    "bank_import_marker_state",
)


@dataclass(frozen=True)
class AILearningStats:
    """Bestand des Lernspeichers, aufgeschluesselt nach Art des Wissens."""

    merchant_patterns: int = 0
    twint_patterns: int = 0
    feedback_examples: int = 0
    tag_rules: int = 0

    @property
    def learned_patterns(self) -> int:
        """Anzahl gelernter Muster fuer die Anzeige in den Einstellungen.

        Gezaehlt werden die Verallgemeinerungen - Haendlergedaechtnis und
        TWINT-Gedaechtnis. Die Lernbeispiele in ``ai_feedback`` sind der
        Rohstoff dazu; sie mitzuzaehlen wuerde dieselben Faelle ein zweites
        Mal auffuehren.
        """
        return self.merchant_patterns + self.twint_patterns

    @property
    def is_empty(self) -> bool:
        """True, wenn die KI nichts gelernt hat (Zustand ``untrained``)."""
        return not any(
            (
                self.merchant_patterns,
                self.twint_patterns,
                self.feedback_examples,
                self.tag_rules,
            )
        )


def existing_tables(conn: sqlite3.Connection) -> frozenset[str]:
    """Tabellennamen der Datenbank.

    Die KI-Tabellen entstehen erst, wenn ein Bankimport zum ersten Mal
    geoeffnet wird. Vorher darf weder die Zaehlung noch der Reset scheitern,
    also wird gefragt statt geraten - ein ``try/except OperationalError`` um
    jede Abfrage waere dieselbe Auskunft, nur stumm.
    """
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return frozenset(str(row[0]) for row in rows)


def _zaehlung(cursor: sqlite3.Cursor) -> int:
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def learning_stats(conn: sqlite3.Connection) -> AILearningStats:
    """Liest den aktuellen Bestand des KI-Lernspeichers."""
    vorhanden = existing_tables(conn)
    merchant = 0
    twint = 0
    feedback = 0
    rules = 0
    if "ai_merchant_memory" in vorhanden:
        merchant = _zaehlung(conn.execute("SELECT COUNT(*) FROM ai_merchant_memory"))
    if "ai_twint_memory" in vorhanden:
        twint = _zaehlung(conn.execute("SELECT COUNT(*) FROM ai_twint_memory"))
    if "ai_feedback" in vorhanden:
        feedback = _zaehlung(conn.execute("SELECT COUNT(*) FROM ai_feedback"))
    if "ai_tag_rules" in vorhanden:
        rules = _zaehlung(conn.execute("SELECT COUNT(*) FROM ai_tag_rules"))
    return AILearningStats(
        merchant_patterns=merchant,
        twint_patterns=twint,
        feedback_examples=feedback,
        tag_rules=rules,
    )


def reset_learning_data(conn: sqlite3.Connection) -> AILearningStats:
    """Leert den KI-Lernspeicher und gibt zurueck, was dabei geloescht wurde.

    Geloescht werden ausschliesslich die Tabellen aus :data:`RESET_TABLES`.
    Buchungen, Budgets, Kategorien, Tags, Sparziele und die Importzustaende
    (Duplikaterkennung) bleiben unberuehrt - der Reset nimmt der KI ihr
    Wissen, nicht dem Benutzer seine Daten.

    Alles laeuft in einer Transaktion: entweder ist der Lernspeicher danach
    vollstaendig leer, oder er ist unveraendert.
    """
    vorher = learning_stats(conn)
    vorhanden = existing_tables(conn)
    with db_transaction(conn):
        if "ai_merchant_memory" in vorhanden:
            conn.execute("DELETE FROM ai_merchant_memory")
        if "ai_twint_memory" in vorhanden:
            conn.execute("DELETE FROM ai_twint_memory")
        if "ai_feedback" in vorhanden:
            conn.execute("DELETE FROM ai_feedback")
        if "ai_tag_rules" in vorhanden:
            conn.execute("DELETE FROM ai_tag_rules")
    logger.info(
        "KI-Lerndaten zurueckgesetzt: %s Haendlermuster, %s TWINT-Muster, "
        "%s Lernbeispiele, %s Kostenanteil-Regeln geloescht",
        vorher.merchant_patterns,
        vorher.twint_patterns,
        vorher.feedback_examples,
        vorher.tag_rules,
    )
    return vorher
