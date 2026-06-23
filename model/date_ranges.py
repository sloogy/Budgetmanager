from __future__ import annotations

"""Zentrale Datumsbereich-Helfer für indexfreundliche SQLite-Abfragen.

Alle Tracking-Daten liegen als ISO-Datum (YYYY-MM-DD) vor. Für Monats- und
Jahresfilter verwenden wir deshalb halb-offene Bereiche [start, end), damit
SQLite Indizes auf ``tracking.date`` nutzen kann und keine ``substr(date, ...)``
Filter nötig sind.
"""


def month_bounds(year: int, month: int) -> tuple[str, str]:
    """Return [start, end) ISO bounds for one calendar month.

    Raises:
        ValueError: if month is outside 1..12.
    """
    year = int(year)
    month = int(month)
    if month < 1 or month > 12:
        raise ValueError(f"month must be in 1..12, got {month!r}")

    start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        end = f"{year + 1:04d}-01-01"
    else:
        end = f"{year:04d}-{month + 1:02d}-01"
    return start, end


def year_bounds(year: int) -> tuple[str, str]:
    """Return [start, end) ISO bounds for one calendar year."""
    year = int(year)
    return f"{year:04d}-01-01", f"{year + 1:04d}-01-01"
