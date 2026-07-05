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


def aggregate_category_amounts(
    rows,
    typ_filter: str | None = None,
    *,
    top_n: int = 8,
    other_label: str | None = None,
) -> list[tuple[str, float]]:
    """Aggregiert Beträge pro Kategorie für lesbare Ranking-Diagramme.

    Anders als ein Kreisdiagramm ist ein Ranking bei vielen Kategorien leichter
    lesbar. Optional werden alle Kategorien hinter ``top_n`` zu ``other_label``
    zusammengefasst, damit das Diagramm kurz bleibt.

    Args:
        rows: Buchungszeilen mit Attributen ``typ``, ``category``, ``amount``.
        typ_filter: Optionaler DB-Typ (z.B. ``TYP_EXPENSES``).
        top_n: Anzahl der sichtbaren Hauptkategorien.
        other_label: Label für die zusammengefassten Restkategorien.

    Returns:
        Liste aus (kategorie, betrag), absteigend nach Betrag.
    """
    wanted = normalize_typ(typ_filter) if typ_filter else None
    agg: dict[str, float] = {}
    for r in rows:
        typ_db = normalize_typ(str(getattr(r, "typ", "")))
        if wanted and typ_db != wanted:
            continue
        cat = str(getattr(r, "category", "")).strip()
        if not cat:
            continue
        agg[cat] = agg.get(cat, 0.0) + abs(float(getattr(r, "amount", 0.0)))

    ranked = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)
    if top_n <= 0 or len(ranked) <= top_n:
        return ranked

    head = ranked[:top_n]
    rest = sum(v for _cat, v in ranked[top_n:])
    if other_label and rest > 0.0:
        head.append((other_label, rest))
    return head
