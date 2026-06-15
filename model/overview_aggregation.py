"""Qt-freie Aggregations-Helfer für die Übersicht-Charts.

Hier liegt reine Datenlogik, damit sie ohne PySide6 testbar ist
(siehe tests/test_overview_charts.py).
"""
from __future__ import annotations

from model.typ_constants import normalize_typ


def aggregate_top_bookings(rows, top_n: int = 5) -> list[tuple[tuple[str, str], float]]:
    """Aggregiert Buchungen pro (Typ, Kategorie) und liefert die größten N.

    Mehrere Buchungen derselben Kategorie (z.B. monatlicher Lohn im Zeitraum)
    werden zu EINER Summe zusammengefasst, statt einzeln gelistet zu werden.

    Args:
        rows: Buchungszeilen mit Attributen ``typ``, ``category``, ``amount``.
        top_n: Anzahl der größten Einträge.

    Returns:
        Liste aus ((typ_db, kategorie), summe), absteigend nach Summe,
        auf ``top_n`` begrenzt.
    """
    agg: dict[tuple[str, str], float] = {}
    for r in rows:
        typ_db = normalize_typ(str(getattr(r, "typ", "")))
        cat = str(getattr(r, "category", "")).strip()
        if not cat:
            continue
        key = (typ_db, cat)
        agg[key] = agg.get(key, 0.0) + abs(float(getattr(r, "amount", 0.0)))
    return sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
