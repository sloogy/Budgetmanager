"""Qt-freie Textregeln der UI-Härtung.

v2.2.22 (UI/ADHS-Audit): Die Destruktiv-Erkennung lebt hier, damit sie ohne
PySide6 test- und auditierbar ist (``tools/ui_adhs_audit_1000.py`` und die
Regressionstests rufen sie direkt auf). ``utils/ui_usability.py`` importiert
von hier.

Matching erfolgt auf WORT-Ebene (nicht Substring), damit z.B. "Preset
speichern" nicht über das enthaltene "reset" fälschlich als destruktiv gilt.
Die Wortliste deckt Deutsch, Englisch und Französisch ab – vorher fehlten
u.a. ``réinitialiser``, ``retirer``, ``clear`` und ``verwerfen``.
"""

from __future__ import annotations

import re

_DESTRUCTIVE_WORDS = {
    # Deutsch
    "löschen",
    "loeschen",
    "zurücksetzen",
    "zuruecksetzen",
    "entfernen",
    "verwerfen",
    "leeren",
    # Englisch
    "delete",
    "remove",
    "reset",
    "clear",
    "discard",
    "purge",
    # Französisch
    "supprimer",
    "effacer",
    "réinitialiser",
    "reinitialiser",
    "retirer",
    "vider",
    "purger",
}

_WORD_RE = re.compile(r"[\wäöüÄÖÜßéèêàçîïôûùÉÈÊÀÇÎÏÔÛÙ]+", re.UNICODE)


def clean_ui_text(text: str) -> str:
    """Entfernt Mnemonic-'&' und normalisiert Whitespace."""
    text = re.sub(r"&", "", str(text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_destructive_text(text: str) -> bool:
    """Erkennt destruktive Button-Beschriftungen (de/en/fr, wortgrenzen-basiert)."""
    words = {w.casefold() for w in _WORD_RE.findall(clean_ui_text(text))}
    return bool(words & _DESTRUCTIVE_WORDS)
