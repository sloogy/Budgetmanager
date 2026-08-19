"""Lohnbasierter Zeitraum für den Cockpit-Monatsstatus.

Der BudgetManager budgetiert weiterhin in Kalendermonaten. Der Cockpit-
Monatsstatus soll jedoch den realen Geldfluss zwischen zwei Lohnterminen
zeigen. Beispiel bei Lohntermin 25.:

    25. Januar bis 24. Februar

Die Abfragen verwenden einen halb-offenen Bereich ``[start, end)``. Als
Budgetreferenz gilt der Kalendermonat, in dem der letzte Tag des Zyklus liegt
(im Beispiel Februar).

Die Logik ist Qt-frei und damit vollständig headless testbar.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
import sqlite3
import unicodedata

from model.typ_constants import TYP_INCOME

_SALARY_TOKENS = (
    "lohn",
    "gehalt",
    "salary",
    "salaire",
    "wage",
    "payroll",
)
_ACTUAL_MATCH_TOLERANCE_DAYS = 7


@dataclass(frozen=True)
class SalaryCycle:
    """Aufgelöster Cockpit-Zeitraum zwischen zwei Lohnterminen."""

    start: date
    end_exclusive: date
    budget_year: int
    budget_month: int
    anchor_day: int
    category: str | None = None
    source: str = "calendar"  # actual | recurring | calendar

    @property
    def end_inclusive(self) -> date:
        return self.end_exclusive - timedelta(days=1)

    @property
    def start_iso(self) -> str:
        return self.start.isoformat()

    @property
    def end_iso(self) -> str:
        return self.end_exclusive.isoformat()


@dataclass(frozen=True)
class _IncomeCategory:
    name: str
    recurring_day: int
    recurring: bool
    activity: float


def _ascii_lower(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower()


def _salary_name_score(name: str) -> int:
    normalized = _ascii_lower(name)
    score = 0
    if any(token in normalized for token in _SALARY_TOKENS):
        score += 1000
    if "netto" in normalized or "net" in normalized:
        score += 50
    return score


def _clamped_date(year: int, month: int, day: int) -> date:
    day = max(1, min(31, int(day or 1)))
    return date(int(year), int(month), min(day, monthrange(int(year), int(month))[1]))


def _month_offset(year: int, month: int, delta: int) -> tuple[int, int]:
    absolute = int(year) * 12 + (int(month) - 1) + int(delta)
    return divmod(absolute, 12)[0], divmod(absolute, 12)[1] + 1


def _scheduled_anchor(reference: date, day: int, offset: int = 0) -> date:
    year, month = _month_offset(reference.year, reference.month, offset)
    return _clamped_date(year, month, day)


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        if table == "categories":
            rows = conn.execute("PRAGMA table_info(categories)")
        elif table == "tracking":
            rows = conn.execute("PRAGMA table_info(tracking)")
        elif table == "budget":
            rows = conn.execute("PRAGMA table_info(budget)")
        else:
            return set()
        return {str(row[1]) for row in rows}
    except sqlite3.Error:
        return set()


def _category_activity(
    conn: sqlite3.Connection, category: str, *, on_date: date
) -> float:
    """Positive Aktivität als stabiler Tie-Breaker bei mehreren Einkommen."""
    try:
        start = (on_date - timedelta(days=120)).isoformat()
        row = conn.execute(
            """
            SELECT COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0)
            FROM tracking
            WHERE typ=? AND category=? AND date>=? AND date<=?
            """,
            (TYP_INCOME, str(category), start, on_date.isoformat()),
        ).fetchone()
        return float(row[0] if row and row[0] is not None else 0.0)
    except sqlite3.Error:
        return 0.0


def _primary_salary_category(
    conn: sqlite3.Connection, *, on_date: date
) -> _IncomeCategory | None:
    """Wählt die wahrscheinlich primäre Lohnkategorie nachvollziehbar aus.

    Priorität:
    1. Name enthält Lohn/Gehalt/Salary/Salaire/Wage.
    2. Kategorie ist als wiederkehrendes Einkommen markiert.
    3. Höhere positive Aktivität der letzten 120 Tage.
    """
    columns = _table_columns(conn, "categories")
    if not {"typ", "name"} <= columns:
        return None

    recurring_expr = "COALESCE(is_recurring,0)" if "is_recurring" in columns else "0"
    day_expr = "COALESCE(recurring_day,1)" if "recurring_day" in columns else "1"
    try:
        rows = conn.execute(
            f"SELECT name, {recurring_expr}, {day_expr} "  # nosec B608
            "FROM categories WHERE typ=? ORDER BY name",
            (TYP_INCOME,),
        ).fetchall()
    except sqlite3.Error:
        return None

    candidates: list[_IncomeCategory] = []
    for row in rows:
        name = str(row[0] or "").strip()
        if not name:
            continue
        recurring = bool(int(row[1] or 0))
        try:
            recurring_day = max(1, min(31, int(row[2] or 1)))
        except (TypeError, ValueError):
            recurring_day = 1
        candidates.append(
            _IncomeCategory(
                name=name,
                recurring_day=recurring_day,
                recurring=recurring,
                activity=_category_activity(conn, name, on_date=on_date),
            )
        )

    if not candidates:
        return None

    # Ohne Lohnbegriff verwenden wir nur eine explizit wiederkehrende
    # Einkommenskategorie. Einmalige Verkäufe/Erstattungen dürfen den
    # Monatsstatus nicht unbemerkt auf einen anderen Tag verschieben.
    named = [c for c in candidates if _salary_name_score(c.name) > 0]
    pool = named or [c for c in candidates if c.recurring]
    if not pool:
        return None

    return max(
        pool,
        key=lambda c: (
            _salary_name_score(c.name),
            1 if c.recurring else 0,
            float(c.activity),
            c.name.casefold(),
        ),
    )


def _latest_positive_income_date(
    conn: sqlite3.Connection, *, category: str, on_date: date
) -> date | None:
    try:
        row = conn.execute(
            """
            SELECT date
            FROM tracking
            WHERE typ=? AND category=? AND amount>0 AND date<=?
            ORDER BY date DESC, amount DESC
            LIMIT 1
            """,
            (TYP_INCOME, str(category), on_date.isoformat()),
        ).fetchone()
        if not row:
            return None
        return date.fromisoformat(str(row[0])[:10])
    except (sqlite3.Error, TypeError, ValueError):
        return None


def _actual_salary_start(
    conn: sqlite3.Connection,
    *,
    category: str,
    on_date: date,
    anchor_day: int,
) -> tuple[date, date] | None:
    """Findet den echten Lohneingang nahe dem geplanten Lohntermin.

    Rückgabe ist ``(actual_date, matched_scheduled_anchor)``. Ein 13. Lohn oder
    eine Korrektur ausserhalb des ±7-Tage-Fensters verschiebt den Zyklus nicht.
    """
    if not {"date", "typ", "category", "amount"} <= _table_columns(conn, "tracking"):
        return None

    current_anchor = _scheduled_anchor(on_date, anchor_day, 0)
    previous_anchor = _scheduled_anchor(on_date, anchor_day, -1)
    window_start = previous_anchor - timedelta(days=_ACTUAL_MATCH_TOLERANCE_DAYS)
    window_end = min(
        on_date,
        current_anchor + timedelta(days=_ACTUAL_MATCH_TOLERANCE_DAYS),
    )
    try:
        rows = conn.execute(
            """
            SELECT date, amount
            FROM tracking
            WHERE typ=? AND category=? AND amount>0 AND date>=? AND date<=?
            ORDER BY date DESC, amount DESC
            """,
            (
                TYP_INCOME,
                str(category),
                window_start.isoformat(),
                window_end.isoformat(),
            ),
        ).fetchall()
    except sqlite3.Error:
        return None

    matches: list[tuple[date, date, float, int]] = []
    for raw_date, raw_amount in rows:
        try:
            actual = date.fromisoformat(str(raw_date)[:10])
            amount = float(raw_amount or 0.0)
        except (TypeError, ValueError):
            continue
        nearest = min(
            (previous_anchor, current_anchor),
            key=lambda scheduled: abs((actual - scheduled).days),
        )
        distance = abs((actual - nearest).days)
        if distance <= _ACTUAL_MATCH_TOLERANCE_DAYS:
            matches.append((actual, nearest, amount, distance))

    if not matches:
        return None

    # Neuester geplanter Lohntermin gewinnt. Bei mehreren Buchungen um diesen
    # Termin ist die grösste Buchung der wahrscheinlich echte Nettolohn.
    actual, scheduled, _amount, _distance = max(
        matches,
        key=lambda item: (
            item[1],
            item[2],
            -item[3],
            item[0],
        ),
    )
    return actual, scheduled


def calendar_month_cycle(on_date: date) -> SalaryCycle:
    start = date(on_date.year, on_date.month, 1)
    next_year, next_month = _month_offset(on_date.year, on_date.month, 1)
    end = date(next_year, next_month, 1)
    return SalaryCycle(
        start=start,
        end_exclusive=end,
        budget_year=on_date.year,
        budget_month=on_date.month,
        anchor_day=1,
        category=None,
        source="calendar",
    )


def resolve_salary_cycle(
    conn: sqlite3.Connection, *, on_date: date | None = None
) -> SalaryCycle:
    """Bestimmt den für den Cockpit-Monatsstatus gültigen Lohnzyklus.

    Bei fehlender geeigneter Lohnkategorie bleibt das bisherige Verhalten
    (Kalendermonat) erhalten.
    """
    today = on_date or date.today()
    category = _primary_salary_category(conn, on_date=today)
    if category is None:
        return calendar_month_cycle(today)

    anchor_day = category.recurring_day
    if not category.recurring:
        # Bestehende Benutzer können eine Lohnkategorie haben, die noch nicht
        # als wiederkehrend markiert ist. Dann wird der Tag aus dem letzten
        # echten Lohneingang abgeleitet statt stillschweigend der 1. genutzt.
        latest = _latest_positive_income_date(
            conn, category=category.name, on_date=today
        )
        if latest is not None:
            anchor_day = latest.day
    current_anchor = _scheduled_anchor(today, anchor_day, 0)
    previous_anchor = _scheduled_anchor(today, anchor_day, -1)

    actual_match = _actual_salary_start(
        conn,
        category=category.name,
        on_date=today,
        anchor_day=anchor_day,
    )
    if actual_match is not None:
        actual_start, matched_anchor = actual_match
        # Ein vorzeitig eingegangener Lohn eröffnet sofort den neuen Zyklus.
        # Ein alter Treffer darf den aktuellen geplanten Zyklus dagegen nicht
        # überlagern, sobald dessen Termin erreicht wurde.
        if matched_anchor == current_anchor or today < current_anchor:
            scheduled_start = matched_anchor
            start = actual_start
            source = "actual"
        else:
            scheduled_start = current_anchor
            start = current_anchor
            source = "recurring"
    else:
        scheduled_start = current_anchor if today >= current_anchor else previous_anchor
        start = scheduled_start
        source = "recurring"

    next_year, next_month = _month_offset(
        scheduled_start.year, scheduled_start.month, 1
    )
    end = _clamped_date(next_year, next_month, anchor_day)
    if start >= end:
        start = scheduled_start

    # Sollte mehrere Monate keine Buchung vorliegen, bleibt der Zyklus dennoch
    # genau einen Monat lang und wandert nicht endlos weiter.
    while today >= end:
        scheduled_start = end
        start = scheduled_start
        next_year, next_month = _month_offset(end.year, end.month, 1)
        end = _clamped_date(next_year, next_month, anchor_day)
        source = "recurring"

    budget_day = end - timedelta(days=1)
    return SalaryCycle(
        start=start,
        end_exclusive=end,
        budget_year=budget_day.year,
        budget_month=budget_day.month,
        anchor_day=anchor_day,
        category=category.name,
        source=source,
    )


def previous_salary_cycle(cycle: SalaryCycle) -> SalaryCycle:
    """Erzeugt den direkt vorherigen Vergleichszeitraum ohne DB-Zugriff."""
    previous_year, previous_month = _month_offset(
        cycle.start.year, cycle.start.month, -1
    )
    scheduled_start = _clamped_date(previous_year, previous_month, cycle.anchor_day)
    previous_end = cycle.start
    # Bei einem tatsächlichen vorgezogenen/verspäteten Lohneingang ist der
    # aktuelle Start die fachlich korrekte exklusive Grenze des Vorzyklus.
    budget_day = previous_end - timedelta(days=1)
    return SalaryCycle(
        start=scheduled_start,
        end_exclusive=previous_end,
        budget_year=budget_day.year,
        budget_month=budget_day.month,
        anchor_day=cycle.anchor_day,
        category=cycle.category,
        source="recurring",
    )
