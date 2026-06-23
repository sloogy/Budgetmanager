"""Jahreswechsel-Regeln für Budgetübernahme.

Diese Logik hält Jahreskopien fachlich stabil: Fixkosten, wiederkehrende und
inkrementelle Kategorien können beim Kopieren sichtbar geprüft und nach dem
Vorjahresmuster auf das neue Jahr verteilt werden.
"""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from model.category_forecast_mode import (
    FORECAST_MODE_INCREMENTAL,
    FORECAST_MODE_POT,
    effective_forecast_mode,
)
from model.typ_constants import is_income


@dataclass(frozen=True)
class YearCopyReviewRow:
    typ: str
    category: str
    is_fix: bool
    is_recurring: bool
    forecast_mode: str
    budget_total: float
    actual_total: float
    suggested_months: tuple[float, ...]

    @property
    def flags_label(self) -> str:
        # Legacy/debug label only. UI must localize via view-layer i18n keys.
        parts: list[str] = []
        if self.is_fix:
            parts.append("fixed")
        if self.is_recurring:
            parts.append("recurring")
        if self.forecast_mode == FORECAST_MODE_POT:
            parts.append("pot")
        elif self.forecast_mode == FORECAST_MODE_INCREMENTAL:
            parts.append("incremental")
        return ", ".join(parts) if parts else "normal"


@dataclass(frozen=True)
class YearCopyOverride:
    typ: str
    category: str
    annual_amount: float
    include: bool = True


def _month_budget(
    conn: sqlite3.Connection, year: int, typ: str, category: str
) -> list[float]:
    rows = conn.execute(
        "SELECT month, amount FROM budget WHERE year=? AND typ=? AND category=?",
        (int(year), typ, category),
    ).fetchall()
    out = [0.0] * 12
    for r in rows:
        m = int(r["month"])
        if 1 <= m <= 12:
            out[m - 1] = float(r["amount"] or 0.0)
    return out


def _month_actuals(
    conn: sqlite3.Connection, year: int, typ: str, category: str
) -> list[float]:
    start = f"{int(year):04d}-01-01"
    end = f"{int(year) + 1:04d}-01-01"
    rows = conn.execute(
        """
        SELECT CAST(substr(date, 6, 2) AS INTEGER) AS month, SUM(amount) AS amount
        FROM tracking
        WHERE date>=? AND date<? AND typ=? AND category=?
        GROUP BY CAST(substr(date, 6, 2) AS INTEGER)
        """,
        (start, end, typ, category),
    ).fetchall()
    out = [0.0] * 12
    for r in rows:
        m = int(r["month"] or 0)
        if 1 <= m <= 12:
            value = float(r["amount"] or 0.0)
            out[m - 1] = value if is_income(typ) else abs(value)
    return out


def _round_distribution(values: list[float], target_total: float) -> list[float]:
    rounded = [round(float(v), 2) for v in values]
    diff = round(float(target_total) - sum(rounded), 2)
    if abs(diff) >= 0.01:
        idx = max(range(12), key=lambda i: rounded[i]) if rounded else 0
        rounded[idx] = round(rounded[idx] + diff, 2)
    return rounded


def distribute_like_previous_year(
    budget_months: list[float],
    actual_months: list[float],
    annual_amount: float | None = None,
) -> list[float]:
    """Verteilt den Jahresbetrag nach dem plausibelsten Vorjahresmuster.

    Priorität:
    1. Wenn echte Buchungen existieren: deren Monatsmuster verwenden und auf den
       gewünschten Jahresbetrag skalieren.
    2. Sonst die Budgetverteilung des Quelljahres verwenden.
    3. Sonst den Jahresbetrag gleichmässig über 12 Monate verteilen.
    """
    source_total = sum(float(v or 0.0) for v in budget_months)
    target_total = float(source_total if annual_amount is None else annual_amount)
    if target_total < 0:
        raise ValueError("annual_amount must not be negative")

    actual_total = sum(float(v or 0.0) for v in actual_months)
    if actual_total > 0:
        raw = [(float(v or 0.0) / actual_total) * target_total for v in actual_months]
        return _round_distribution(raw, target_total)

    if source_total > 0:
        if annual_amount is None or abs(target_total - source_total) < 0.005:
            return _round_distribution(
                [float(v or 0.0) for v in budget_months], target_total
            )
        raw = [(float(v or 0.0) / source_total) * target_total for v in budget_months]
        return _round_distribution(raw, target_total)

    monthly = round(target_total / 12.0, 2) if target_total else 0.0
    raw = [monthly] * 12
    return _round_distribution(raw, target_total)


def list_year_copy_review_rows(
    conn: sqlite3.Connection, src_year: int, typ: str | None = None
) -> list[YearCopyReviewRow]:
    """Listet Kategorien, die beim Jahreswechsel bewusst geprüft werden sollten."""
    params: list[object] = [int(src_year)]
    typ_clause = ""
    if typ:
        typ_clause = " AND b.typ=?"
        params.append(typ)
    rows = conn.execute(
        f"""
        SELECT b.typ, b.category,
               COALESCE(c.is_fix, 0) AS is_fix,
               COALESCE(c.is_recurring, 0) AS is_recurring,
               COALESCE(c.forecast_mode, 'auto') AS forecast_mode,
               SUM(b.amount) AS budget_total
        FROM budget b
        LEFT JOIN categories c ON c.typ=b.typ AND c.name=b.category
        WHERE b.year=? {typ_clause}
          AND b.category NOT LIKE '%SALDO%'
        GROUP BY b.typ, b.category, c.is_fix, c.is_recurring, c.forecast_mode
        ORDER BY b.typ, b.category COLLATE NOCASE
        """,
        params,
    ).fetchall()

    result: list[YearCopyReviewRow] = []
    for r in rows:
        is_fix = bool(r["is_fix"])
        is_rec = bool(r["is_recurring"])
        mode = effective_forecast_mode(r["forecast_mode"], is_fix, is_rec)
        if not (
            is_fix or is_rec or mode in {FORECAST_MODE_INCREMENTAL, FORECAST_MODE_POT}
        ):
            continue
        typ_val = str(r["typ"])
        cat = str(r["category"])
        budget_months = _month_budget(conn, src_year, typ_val, cat)
        actual_months = _month_actuals(conn, src_year, typ_val, cat)
        suggested = distribute_like_previous_year(budget_months, actual_months)
        result.append(
            YearCopyReviewRow(
                typ=typ_val,
                category=cat,
                is_fix=is_fix,
                is_recurring=is_rec,
                forecast_mode=mode,
                budget_total=float(r["budget_total"] or 0.0),
                actual_total=sum(actual_months),
                suggested_months=tuple(suggested),
            )
        )
    return result


def apply_year_copy_pattern(
    conn: sqlite3.Connection,
    *,
    src_year: int,
    dst_year: int,
    overrides: list[YearCopyOverride] | None = None,
    typ: str | None = None,
) -> None:
    """Überschreibt Zieljahr-Budgets für ausgewählte Jahreswechsel-Kategorien."""
    override_map = {
        (o.typ, o.category): o for o in (overrides or []) if bool(o.include)
    }
    review_rows = list_year_copy_review_rows(conn, src_year, typ=typ)
    for row in review_rows:
        key = (row.typ, row.category)
        if overrides is not None and key not in override_map:
            # bewusst nicht übernommen: Zieljahr auf 0 setzen, damit keine alte
            # Fixkostenposition unbemerkt weiterläuft.
            months = [0.0] * 12
        else:
            annual = (
                override_map[key].annual_amount
                if key in override_map
                else row.budget_total
            )
            budget_months = _month_budget(conn, src_year, row.typ, row.category)
            actual_months = _month_actuals(conn, src_year, row.typ, row.category)
            months = distribute_like_previous_year(budget_months, actual_months, annual)
        for month, amount in enumerate(months, start=1):
            conn.execute(
                """
                INSERT INTO budget(year, month, typ, category, amount)
                VALUES(?,?,?,?,?)
                ON CONFLICT(year, month, typ, category) DO UPDATE SET amount=excluded.amount
                """,
                (int(dst_year), month, row.typ, row.category, float(amount)),
            )
    conn.commit()
