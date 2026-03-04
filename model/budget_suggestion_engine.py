"""budget_suggestion_engine.py

Eine zentrale, robuste Budget-Vorschlagslogik (eine Quelle der Wahrheit).

Ziele (Praxis/UX):
- Ein Vorschlag soll sowohl bei dauerhaftem Überschreiten *als auch*
  bei dauerhaftem Unterschreiten greifen.
- Ausreisser sollen nicht überproportional wirken → Median statt Mittelwert.
- Kein "effective_min=1": Vorschläge erst, wenn genug Monate vorhanden sind.
- Schwellwerte verhindern Rauschen (min CHF / min %).

Die Engine arbeitet mit Abweichungen (deviations):
  Ausgaben/Ersparnisse: dev = budget - spent (positiv = unter Budget)
  Einkommen:            dev = spent  - budget (positiv = über Plan)

v0.4.4.0 – Fixes:
- BUG-FIX: Inkompletter aktueller Monat wird nicht mehr in die Analyse
  einbezogen (→ use_current_month=False Standard).
- BUG-FIX: Fenster erweitert sich über Lückenmonate hinweg
  (max_scan statt hartem months_back-Limit).
- BUG-FIX: require_same_sign_ratio Standard von 1.0 auf 0.7 gesenkt;
  zuvor wurde jeder einzelne Ausreisser-Monat zum Blocker.
- BUG-FIX: Ersparnisse werden jetzt ebenfalls mit abs() abgesichert.
"""

from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

import sqlite3
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS, normalize_typ, is_income, rest_sign, ALL_TYPEN
from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Optional, List, Tuple


@dataclass
class SuggestionResult:
    typ: str
    category: str
    direction: str                 # "surplus" oder "deficit"
    months_considered: int
    streak_months: int
    central_deviation: float       # Median der letzten N Abweichungen
    avg_deviation: float           # Durchschnitt der letzten N Abweichungen
    current_budget: float
    suggested_budget: float
    delta: float                   # suggested - current


# Typen, deren Tracking-Beträge immer positiv interpretiert werden
_ABS_TYPEN = {"ausgaben", "ersparnisse"}

# Typen, die als Einkommen gelten
_INCOME_TYPEN = {"einkommen", "income", "einnahmen"}


class BudgetSuggestionEngine:
    """Berechnet Budgetvorschläge auf Basis historischer Budget/Ist-Abweichungen."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------
    def compute_category_suggestion(
        self,
        typ: str,
        category: str,
        year: int,
        month: int,
        months_back: int = 6,
        alpha: float = 0.8,
        min_abs_change: float = 20.0,
        min_pct_change: float = 0.05,
        round_to: float = 10.0,
        require_same_sign_ratio: float = 0.7,
        # "0-Buchungen"-Reduktion (gestuft):
        enable_zero_reduction: bool = True,
        # Floor/Minimum:
        floor_abs: float = 10.0,
        floor_rel: float = 0.20,
        # Inkompletten aktuellen Monat einbeziehen?
        # Standard=False → nur abgeschlossene Monate analysieren
        use_current_month: bool = False,
    ) -> Optional[SuggestionResult]:
        """Berechnet einen Vorschlag für eine Kategorie.

        Args:
            typ/category/year/month: Zielmonat (Vorschlag gilt für diesen Monat)
            months_back: Fenstergrösse N (Anzahl benötigter Datenpunkte)
            alpha: Anpassungsfaktor (0.8 = 80%)
            min_abs_change: Mindeständerung in CHF
            min_pct_change: Mindeständerung relativ zum aktuellen Budget
            round_to: Rundung (z.B. 10 CHF)
            require_same_sign_ratio: Anteil der Monate, die gleiche Richtung
                                     zeigen müssen (0.7 = 70%)
            use_current_month: False = aktueller Monat wird übersprungen
                               (empfohlen, da unvollständig)
        """
        if months_back <= 0:
            return None

        # Aktuelles Budget im Zielmonat
        current_budget = self._get_budget_amount(year, month, typ, category)
        if current_budget is None or current_budget <= 0:
            return None

        # Floor berechnen (nur für Ausgaben/Ersparnisse; Einkommen hat keinen Floor)
        floor = 0.0
        if not self._is_income(typ):
            try:
                floor = max(float(floor_abs), float(current_budget) * float(floor_rel))
            except Exception:
                floor = float(floor_abs)

        # ── Startmonat für die Analyse bestimmen ──
        # Bei use_current_month=False starten wir einen Monat VOR dem Zielmonat,
        # damit der (ggf. unvollständige) aktuelle Monat nicht einfliesst.
        if use_current_month:
            analysis_year, analysis_month = year, month
        else:
            analysis_year, analysis_month = self._prev_month(year, month)

        # Abweichungen sammeln (erweitert sich über Lücken hinweg)
        deviations = self._get_deviations_window(
            typ, category, analysis_year, analysis_month, months_back
        )
        if len(deviations) < months_back:
            return None

        # ── 0-Buchungen-Handling ──
        if enable_zero_reduction and (not self._is_income(typ)):
            active_months = self._count_active_months(
                typ, category, analysis_year, analysis_month, months_back
            )
            if active_months == 0:
                zero_streak = self._compute_zero_streak_months(
                    typ, category, analysis_year, analysis_month
                )
                if zero_streak >= 6:
                    return self._build_zero_reduction_result(
                        typ, category, current_budget, floor, zero_streak,
                        deviations, round_to, min_abs_change, min_pct_change,
                    )

        # ── Stabilitätsprüfung: Vorzeichen-Konsistenz ──
        pos = sum(1 for d in deviations if d > 0)
        neg = sum(1 for d in deviations if d < 0)
        zero = len(deviations) - pos - neg

        if pos == 0 and neg == 0:
            return None

        dominant_sign = 1 if pos >= neg else -1
        dominant = pos if dominant_sign > 0 else neg
        non_zero_count = max(1, len(deviations) - zero)
        ratio = dominant / non_zero_count
        if ratio < require_same_sign_ratio:
            return None

        # ── Zentralwert & Mittelwert ──
        central = float(median(deviations))
        avg = float(sum(deviations) / len(deviations))

        direction = "surplus" if central > 0 else "deficit"

        # ── Budget anpassen ──
        adjustment = central * alpha
        if self._is_income(typ):
            suggested = current_budget + adjustment
        else:
            suggested = current_budget - adjustment

        # Negative Budgets verhindern + Floor
        if self._is_income(typ):
            suggested = max(0.0, suggested)
        else:
            suggested = max(float(floor), float(suggested))

        # Schwellwerte (Änderung gross genug?)
        delta = suggested - current_budget
        if abs(delta) < float(min_abs_change) and abs(delta) < (current_budget * float(min_pct_change)):
            return None

        # Runden
        if round_to and round_to > 0:
            suggested = round(suggested / round_to) * round_to
            if self._is_income(typ):
                suggested = max(0.0, suggested)
            else:
                suggested = max(float(floor), float(suggested))
            delta = suggested - current_budget

        # Nochmals prüfen nach Rundung (Rundung kann delta auf 0 bringen)
        if abs(delta) < 0.01:
            return None

        # Streak
        streak = self._compute_streak_months(
            typ, category, analysis_year, analysis_month,
            sign=(1 if central > 0 else -1),
        )

        return SuggestionResult(
            typ=typ,
            category=category,
            direction=direction,
            months_considered=len(deviations),
            streak_months=streak,
            central_deviation=central,
            avg_deviation=avg,
            current_budget=float(current_budget),
            suggested_budget=float(suggested),
            delta=float(delta),
        )

    # ------------------------------------------------------------
    # Hilfsmethoden: 0-Buchungen-Reduktion
    # ------------------------------------------------------------
    def _build_zero_reduction_result(
        self, typ, category, current_budget, floor, zero_streak,
        deviations, round_to, min_abs_change, min_pct_change,
    ) -> Optional[SuggestionResult]:
        """Erstellt einen Vorschlag für Kategorien ohne jegliche Buchungen."""
        suggested = float(current_budget)
        if 6 <= zero_streak < 12:
            rate = 0.05 * float(zero_streak - 5)
            rate = min(rate, 0.35)
            suggested = float(current_budget) * (1.0 - rate)
        elif 12 <= zero_streak < 18:
            suggested = float(current_budget) * 0.20
        else:  # >= 18
            suggested = float(current_budget) * 0.10

        suggested = max(float(floor), float(suggested))
        if round_to and round_to > 0:
            suggested = round(suggested / round_to) * round_to
            suggested = max(float(floor), float(suggested))
        delta = float(suggested) - float(current_budget)

        if abs(delta) < float(min_abs_change) and abs(delta) < (float(current_budget) * float(min_pct_change)):
            return None

        central = float(median(deviations))
        avg = float(sum(deviations) / len(deviations))
        return SuggestionResult(
            typ=typ,
            category=category,
            direction="surplus",
            months_considered=len(deviations),
            streak_months=zero_streak,
            central_deviation=central,
            avg_deviation=avg,
            current_budget=float(current_budget),
            suggested_budget=float(suggested),
            delta=float(delta),
        )

    # ------------------------------------------------------------
    # Zähler
    # ------------------------------------------------------------
    def _count_active_months(self, typ: str, category: str, year: int, month: int, months_back: int) -> int:
        """Zählt, in wie vielen der letzten N Monate überhaupt Buchungen > 0 vorkamen."""
        active = 0
        base = date(year, month, 1)
        for i in range(months_back):
            d = self._subtract_months(base, i)
            b = self._get_budget_amount(d.year, d.month, typ, category)
            if b is None or b <= 0:
                continue
            a = self._get_spent_amount(d.year, d.month, typ, category)
            if abs(float(a)) > 0.000001:
                active += 1
        return active

    def _compute_zero_streak_months(self, typ: str, category: str, year: int, month: int) -> int:
        """Zählt Monate rückwärts *in Folge* ohne Buchungen (spent == 0)."""
        streak = 0
        base = date(year, month, 1)
        for i in range(0, 60):
            d = self._subtract_months(base, i)
            b = self._get_budget_amount(d.year, d.month, typ, category)
            if b is None or b <= 0:
                break
            a = self._get_spent_amount(d.year, d.month, typ, category)
            if abs(float(a)) <= 0.000001:
                streak += 1
            else:
                break
        return streak

    # ------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------
    @staticmethod
    def _is_income(typ: str) -> bool:
        # Delegiert an zentrale Typ-Konstanten (model.typ_constants)
        return is_income(typ)

    @staticmethod
    def _prev_month(year: int, month: int) -> tuple[int, int]:
        """Gibt (year, month) des Vormonats zurück."""
        if month == 1:
            return year - 1, 12
        return year, month - 1

    def _get_budget_amount(self, year: int, month: int, typ: str, category: str) -> Optional[float]:
        row = self.conn.execute(
            "SELECT amount FROM budget WHERE year=? AND month=? AND typ=? AND category=?",
            (year, month, typ, category),
        ).fetchone()
        if not row or row[0] is None:
            return None
        try:
            return float(row[0])
        except Exception:
            return None

    def _get_spent_amount(self, year: int, month: int, typ: str, category: str) -> float:
        start = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end = f"{year + 1:04d}-01-01"
        else:
            end = f"{year:04d}-{month + 1:02d}-01"

        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) FROM tracking
            WHERE date >= ? AND date < ? AND typ = ? AND category = ?
            """,
            (start, end, typ, category),
        ).fetchone()
        val = float(row[0]) if row and row[0] is not None else 0.0
        # Ausgaben UND Ersparnisse → abs, um negative DB-Werte abzufangen
        if not is_income(typ):
            val = abs(val)
        return val

    def _subtract_months(self, d: date, months: int) -> date:
        m = d.month - months
        y = d.year
        while m < 1:
            m += 12
            y -= 1
        return date(y, m, 1)

    def _get_deviations_window(
        self, typ: str, category: str, year: int, month: int, months_back: int,
    ) -> List[float]:
        """Sammelt die letzten N Abweichungs-Datenpunkte.

        WICHTIG (v0.4.4.0-Fix): Das Fenster erweitert sich über Lückenmonate
        hinweg.  Wenn ein Monat kein Budget hat, wird er übersprungen und der
        Scan geht weiter zurück – bis zu ``months_back * 3`` Monate maximal.
        So reicht ein einzelner Monat ohne Budget nicht aus, um die gesamte
        Analyse zu blockieren.
        """
        out: List[float] = []
        base = date(year, month, 1)
        max_scan = months_back * 3  # Sicherheitslimit
        for i in range(max_scan):
            if len(out) >= months_back:
                break
            d = self._subtract_months(base, i)
            b = self._get_budget_amount(d.year, d.month, typ, category)
            if b is None or b <= 0:
                continue  # Lücke → überspringen, weiter suchen
            a = self._get_spent_amount(d.year, d.month, typ, category)
            if self._is_income(typ):
                dev = a - float(b)
            else:
                dev = float(b) - a
            out.append(float(dev))

        out.reverse()
        return out

    def _compute_streak_months(
        self, typ: str, category: str, year: int, month: int, sign: int,
    ) -> int:
        """Zählt Monate rückwärts mit konsistenter Abweichungsrichtung."""
        streak = 0
        base = date(year, month, 1)
        for i in range(0, 60):
            d = self._subtract_months(base, i)
            b = self._get_budget_amount(d.year, d.month, typ, category)
            if b is None or b <= 0:
                # Lücke: Streak nicht abbrechen, nur überspringen
                continue
            a = self._get_spent_amount(d.year, d.month, typ, category)
            dev = (a - float(b)) if self._is_income(typ) else (float(b) - a)
            if dev == 0:
                continue
            if (dev > 0 and sign > 0) or (dev < 0 and sign < 0):
                streak += 1
            else:
                break
        return streak
