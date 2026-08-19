"""Fixkosten-/Wiederkehrend-Fälligkeit (v2.2.4, Qt-frei).

Entscheidet, ob eine fixe oder wiederkehrende Kategorie in einem Monat als
"offen" (noch zu buchen) gilt. Kern der Regel: Im LAUFENDEN Monat ist eine
Position, deren Fälligkeitstag noch nicht erreicht ist, NICHT offen – sonst
meldet das Cockpit am Monatsanfang jede Miete mit Soll-Tag 25 fälschlich als
fehlend. Für vergangene Monate ist die Fälligkeit immer überschritten.

Ausgelagert aus dem Cockpit, damit die Logik headless regressionsgesichert ist.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date

EPS = 1e-6


def is_open_this_month(
    *,
    is_fix: bool,
    is_recurring: bool,
    budget: float,
    booked: float,
    due_day: int,
    year: int,
    month: int,
    today: date | None = None,
) -> tuple[bool, float]:
    """Gibt (offen?, Restbetrag) für eine Fix-/Wiederkehrend-Position zurück.

    - fix UND wiederkehrend: fixer Monatsbetrag → offen, solange nichts gebucht.
    - fix XOR wiederkehrend: offen, solange das Monatsbudget nicht erreicht ist.
    - Fälligkeit: im laufenden Monat erst ab ``due_day`` offen; früher "noch
      nicht fällig". In vergangenen Monaten immer fällig.
    """
    today = today or date.today()
    booked = float(booked or 0.0)
    budget = float(budget or 0.0)

    both = bool(is_fix) and bool(is_recurring)
    open_item = False
    rest = 0.0
    if both:
        if abs(booked) < EPS:
            open_item = True
            rest = budget
    else:
        if budget > EPS and abs(booked) < abs(budget) - EPS:
            open_item = True
            rest = budget - booked

    if open_item and year == today.year and month == today.month:
        try:
            dd = int(due_day or 1)
        except (TypeError, ValueError):
            dd = 1
        # v2.2.25: Fälligkeitstag auf den letzten Tag des Monats klemmen.
        # Ohne Klemmung wurde eine Position mit due_day 29–31 in kürzeren
        # Monaten (Februar, 30-Tage-Monate) NIE fällig: am Monatsletzten
        # galt weiterhin today.day < dd -> "noch nicht fällig".
        dd = max(1, min(dd, monthrange(year, month)[1]))
        if today.day < dd:
            open_item = False
            rest = 0.0

    return open_item, rest
