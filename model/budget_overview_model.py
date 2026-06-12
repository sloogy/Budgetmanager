"""
Budget-Übersicht Modell: Kategoriebasierter Budget/Ist-Vergleich mit Carryover
(Vormonat → Aktuell → Zukunft) und automatischen Anpassungsvorschlägen.

Version 0.3.2.0
"""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

import sqlite3
from dataclasses import dataclass
from datetime import date
import calendar
from utils.money import format_money
from utils.i18n import tr, trf, display_typ, db_typ_from_display

from model.budget_suggestion_engine import BudgetSuggestionEngine
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS, normalize_typ, is_income, rest_sign, ALL_TYPEN


@dataclass
class MonthBudgetRow:
    """Eine Zeile in der Budgetübersicht pro Monat + Typ/Kategorie."""
    year: int
    month: int
    typ: str
    category: str
    budget: float
    actual: float
    rest: float
    carry_over: float
    cumulative_rest: float


@dataclass
class MonthSummary:
    """Zusammenfassung eines Monats pro Typ."""
    year: int
    month: int
    typ: str
    budget_total: float
    actual_total: float
    rest: float
    carry_over: float
    cumulative_rest: float


@dataclass
class CategoryCarryoverRow:
    """Eine Zeile in der Kategorie-Carryover-Tabelle (Vormonat→Aktuell→Zukunft)."""
    category: str
    typ: str
    # Vormonat
    prev_budget: float        # Budget des Vormonats
    prev_rest: float          # Budget - Getracked Vormonat (positiv = unter Budget)
    # Aktuell
    curr_budget: float        # Budget des aktuellen Monats
    curr_budget_carry: float  # curr_budget + prev_rest (Budget + Übertrag)
    curr_tracked: float       # Tatsächlich gebucht im aktuellen Monat
    # Zukunft
    next_budget: float        # Budget des Folgemonats
    next_budget_carry: float  # (curr_budget_carry - curr_tracked) + next_budget
    # Vorschlag
    suggestion: float | None = None  # Vorgeschlagene Budget-Anpassung (oder None)


@dataclass
class BudgetSuggestion:
    """Vorschlag zur Budget-Anpassung bei dauerhaftem Überschuss/Defizit."""
    typ: str
    category: str
    direction: str           # "surplus" oder "deficit"
    avg_deviation: float     # Durchschnittliche monatliche Abweichung
    consecutive_months: int  # Anzahl aufeinanderfolgender Monate
    suggested_amount: float  # Vorgeschlagener neuer Budget-Betrag
    current_budget: float    # Aktuelles Budget
    message: str             # Anzeigetext


# Typ-Normalisierung (gleiche Logik wie overview_tab)
_TYP_ALIASES = {
    "einnahmen": TYP_INCOME,
    "einkommen": TYP_INCOME,
    "income": TYP_INCOME,
    "ausgaben": TYP_EXPENSES,
    "expenses": TYP_EXPENSES,
    "expense": TYP_EXPENSES,
    "ersparnisse": TYP_SAVINGS,
    "sparen": TYP_SAVINGS,
    "savings": TYP_SAVINGS,
}

def _norm_typ(s: str) -> str:
    return _TYP_ALIASES.get(str(s or "").strip().lower(), str(s or "").strip())


class BudgetOverviewModel:
    """Berechnet Budgetübersicht mit Monatsübertrag und Anpassungsvorschlägen."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._engine = BudgetSuggestionEngine(conn)

    # ------------------------------------------------------------------
    # Kernmethode: Monatsweise Budget-Übersicht mit Carry-Over
    # ------------------------------------------------------------------
    def get_monthly_overview(
        self,
        year: int,
        types: list[str] | None = None,
        months: list[int] | None = None,
        start_month: int = 1,
        start_year: int | None = None,
    ) -> list[MonthSummary]:
        """
        Berechnet für jedes Monat im Jahr eine Zusammenfassung pro Typ
        mit Übertrag aus dem Vormonat – optional jahresübergreifend.
        
        Args:
            year: Das angezeigte Jahr
            types: Filter auf Typen (None = alle: Ausgaben, Ersparnisse, Einkommen)
            months: Filter auf Monate (None = 1-12)
            start_month: Ab welchem Monat kumuliert wird (1-12)
            start_year: Ab welchem Jahr kumuliert wird (None = gleich wie year)
        
        Returns:
            Liste von MonthSummary, sortiert nach Typ und Monat
        """
        if types is None:
            types = [TYP_EXPENSES, TYP_SAVINGS, TYP_INCOME]
        if months is None:
            months = list(range(1, 13))
        start_month = max(1, min(12, start_month))
        if start_year is None:
            start_year = year

        results: list[MonthSummary] = []

        for typ in types:
            # DB speichert Typen immer auf Deutsch. UI kann übersetzt sein.
            # Daher: Anzeige-String -> DB-Typ normalisieren.
            try:
                typ_db = db_typ_from_display(typ)
            except Exception:
                typ_db = typ
            # ── Übertrag aus Vorjahren berechnen (start_year..year-1) ──
            carry_over = 0.0
            if start_year < year:
                for y in range(start_year, year):
                    first_m = start_month if y == start_year else 1
                    for m in range(first_m, 13):
                        b = self._budget_sum(y, m, typ_db)
                        a = self._actual_sum(y, m, typ_db)
                        carry_over += rest_sign(typ_db, b, a)

            # ── Aktuelles Jahr: Monat für Monat ──
            for m in range(1, 13):
                budget_total = self._budget_sum(year, m, typ_db)
                actual_total = self._actual_sum(year, m, typ_db)

                rest = rest_sign(typ_db, budget_total, actual_total)

                # Kumulation: Im Startjahr erst ab start_month,
                # in Folgejahren ab Januar (carry_over > 0 aus Vorjahren)
                if year == start_year and m < start_month:
                    cumulative = rest
                    show_carry = 0.0
                else:
                    cumulative = rest + carry_over
                    show_carry = carry_over

                if m in months:
                    results.append(MonthSummary(
                        year=year,
                        month=m,
                        typ=typ,
                        budget_total=budget_total,
                        actual_total=actual_total,
                        rest=rest,
                        carry_over=show_carry,
                        cumulative_rest=cumulative,
                    ))

                # Übertrag für nächsten Monat
                if year == start_year and m < start_month:
                    pass  # carry_over bleibt unverändert
                else:
                    carry_over = cumulative

        return results

    # ------------------------------------------------------------------
    # Kategoriebasierte Carryover-Ansicht (Vormonat → Aktuell → Zukunft)
    # ------------------------------------------------------------------
    def get_category_carryover_view(
        self,
        year: int,
        month: int,
        typ: str,
    ) -> list[CategoryCarryoverRow]:
        """
        Berechnet pro Kategorie die Carryover-Tabelle:
        Vormonat | Aktuell (mit Übertrag) | Zukunft (mit Übertrag) | Vorschlag.

        Args:
            year: Das Jahr
            month: Der aktuell ausgewählte Monat (1-12)
            typ: Typ-Filter (Ausgaben / Ersparnisse / Einkommen)

        Returns:
            Liste von CategoryCarryoverRow, sortiert nach Kategorie
        """
        # Vormonat bestimmen
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1

        # Folgemonat bestimmen
        if month == 12:
            next_year, next_month = year + 1, 1
        else:
            next_year, next_month = year, month + 1

        # Daten laden
        prev_budget = self._budget_by_category(prev_year, prev_month, typ)
        prev_actual = self._actual_by_category(prev_year, prev_month, typ)

        curr_budget = self._budget_by_category(year, month, typ)
        curr_actual = self._actual_by_category(year, month, typ)

        next_budget = self._budget_by_category(next_year, next_month, typ)

        # Kumulierten Carryover VOR dem Vormonat berechnen
        # (alles von Jan bis prev_month-1 im prev_year)
        pre_carry = self._carry_over_by_category(prev_year, prev_month, typ)

        # Alle Kategorien sammeln
        all_cats = sorted(
            set(prev_budget.keys())
            | set(prev_actual.keys())
            | set(curr_budget.keys())
            | set(curr_actual.keys())
            | set(next_budget.keys())
        )

        # Vorschläge berechnen (für Vorschlag-Spalte)
        # Vorschläge an den übergeben Monat koppeln, nicht an date.today()
        # (Stift-Feedback: Auswahl März + heute Februar → falsche Vorschläge)
        current_check_month = month
        min_months = 3  # Default; wird ggf. von UI überschrieben
        try:
            suggestions = self.get_suggestions(
                year=year,
                current_month=current_check_month,
                min_consecutive_months=min_months,
                types=[typ],
            )
            suggestion_map = {s.category: s.suggested_amount for s in suggestions}
        except Exception:
            suggestion_map = {}

        rows: list[CategoryCarryoverRow] = []
        for cat in all_cats:
            pb = prev_budget.get(cat, 0.0)
            pa = prev_actual.get(cat, 0.0)
            cb = curr_budget.get(cat, 0.0)
            ca = curr_actual.get(cat, 0.0)
            nb = next_budget.get(cat, 0.0)

            # Vormonat-Rest: Budget - Getracked (+ kumulierter Vorübertrag)
            pre_co = pre_carry.get(cat, 0.0)
            if typ == TYP_INCOME:
                prev_rest = (pa - pb) + pre_co
            else:
                prev_rest = (pb - pa) + pre_co

            # Aktuell: Budget + Übertrag aus Vormonat
            curr_budget_carry = cb + prev_rest

            # Zukunft: (Budget_carry_aktuell - Gebucht_aktuell) + Budget_Folge
            if typ == TYP_INCOME:
                curr_rest_for_next = ca - curr_budget_carry
            else:
                curr_rest_for_next = curr_budget_carry - ca
            next_budget_carry = nb + curr_rest_for_next

            # Vorschlag
            sugg = suggestion_map.get(cat, None)

            rows.append(CategoryCarryoverRow(
                category=cat,
                typ=typ,
                prev_budget=pb,
                prev_rest=prev_rest,
                curr_budget=cb,
                curr_budget_carry=curr_budget_carry,
                curr_tracked=ca,
                next_budget=nb,
                next_budget_carry=next_budget_carry,
                suggestion=sugg,
            ))

        return rows

    # ------------------------------------------------------------------
    # Detail: Aufschlüsselung pro Kategorie
    # ------------------------------------------------------------------
    def get_category_overview(
        self,
        year: int,
        month: int,
        typ: str,
    ) -> list[MonthBudgetRow]:
        """
        Gibt Budget vs. Ist pro Kategorie für einen Monat zurück,
        inkl. Übertrag aus dem Vormonat.
        """
        # Budget pro Kategorie
        budget_by_cat = self._budget_by_category(year, month, typ)
        # Ist pro Kategorie
        actual_by_cat = self._actual_by_category(year, month, typ)
        # Vormonats-Rest pro Kategorie (kumuliert Jan → month-1)
        carry_by_cat = self._carry_over_by_category(year, month, typ)

        all_cats = sorted(set(budget_by_cat.keys()) | set(actual_by_cat.keys()))
        rows: list[MonthBudgetRow] = []

        for cat in all_cats:
            b = budget_by_cat.get(cat, 0.0)
            a = actual_by_cat.get(cat, 0.0)
            co = carry_by_cat.get(cat, 0.0)

            rest = rest_sign(typ, b, a)

            rows.append(MonthBudgetRow(
                year=year, month=month, typ=typ, category=cat,
                budget=b, actual=a, rest=rest,
                carry_over=co, cumulative_rest=rest + co,
            ))

        return rows

    # ------------------------------------------------------------------
    # Anpassungsvorschläge
    # ------------------------------------------------------------------
    def get_suggestions(
        self,
        year: int,
        current_month: int,
        min_consecutive_months: int = 3,
        types: list[str] | None = None,
    ) -> list[BudgetSuggestion]:
        """
        Prüft ob Kategorien dauerhaft über oder unter Budget liegen
        und generiert Anpassungsvorschläge.
        
        Logik (Einheitslogik):
        - Rolling Window über die letzten N Monate (min_consecutive_months)
        - Median statt Durchschnitt (robust gegen Ausreisser)
        - Kein "effective_min=1" → Vorschläge erst ab N Monaten
        - Schwellwerte verhindern Rauschen
        
        Args:
            year: Das Jahr
            current_month: Bis zu welchem Monat geprüft wird
            min_consecutive_months: Mindestanzahl aufeinanderfolgender Monate (default: 3)
            types: Zu prüfende Typen (default: Ausgaben, Ersparnisse)
        """
        if types is None:
            # Einkommen eingeschlossen: dauerhaft zu wenig gebuchtes Einkommen
            # soll ebenfalls einen Vorschlag erzeugen.
            types = [TYP_EXPENSES, TYP_SAVINGS, TYP_INCOME]

        suggestions: list[BudgetSuggestion] = []
        # Monate im aktuellen Jahr, für die Budget-Daten existieren könnten
        check_months = list(range(1, min(current_month + 1, 13)))
        if not check_months:
            return suggestions
        # KEIN vorzeitiger Abbruch bei len(check_months) < min_consecutive_months!
        # Die Engine schaut über die Jahresgrenze hinweg zurück (z.B. Dez/Nov/Okt
        # des Vorjahres). check_months dient nur zum Sammeln der Kategorien.

        for typ in types:
            # typ → DB-internes Format (z.B. TYP_EXPENSES → TYP_EXPENSES)
            try:
                from utils.i18n import db_typ_from_display
                typ_db = db_typ_from_display(typ)
            except Exception:
                typ_db = typ

            # Alle Kategorien sammeln (auch aus Vorjahr, falls aktuelles Jahr wenig Monate hat)
            all_cats: set[str] = set()
            for m in check_months:
                budget_cats = self._budget_by_category(year, m, typ_db)
                actual_cats = self._actual_by_category(year, m, typ_db)
                all_cats.update(budget_cats.keys())
                all_cats.update(actual_cats.keys())
            # Bei wenigen Monaten im aktuellen Jahr: auch Vorjahres-Kategorien einbeziehen
            if len(check_months) < min_consecutive_months:
                prev_year = year - 1
                for m in range(1, 13):
                    try:
                        budget_cats = self._budget_by_category(prev_year, m, typ_db)
                        all_cats.update(budget_cats.keys())
                    except Exception as e:
                        logger.debug("_budget_by_category prev_year month=%s: %s", m, e)

            for cat in sorted(all_cats):
                # Einheitliche Engine-Parameter (wie Budgetwarnungen)
                # WICHTIG: require_same_sign_ratio darf NICHT 1.0 sein, sonst blockiert
                # ein einzelner Ausreisser-Monat den gesamten Vorschlag.
                try:
                    from settings import Settings
                    sign_ratio = float(Settings().get("budget_suggestion_sign_ratio", 0.7) or 0.7)
                except Exception:
                    sign_ratio = 0.7
                try:
                    res = self._engine.compute_category_suggestion(
                        typ=typ_db,
                        category=cat,
                        year=year,
                        month=current_month,
                        months_back=min_consecutive_months,
                        alpha=0.8,
                        min_abs_change=20.0,
                        min_pct_change=0.05,
                        round_to=10.0,
                        require_same_sign_ratio=sign_ratio,
                    )
                except Exception:
                    res = None

                if not res:
                    continue

                avg_dev = res.avg_deviation
                consecutive = max(min_consecutive_months, res.streak_months)
                direction = res.direction
                current_budget = res.current_budget
                suggested = res.suggested_budget

                if direction == "surplus":
                    msg = trf("suggestion.suggestion_surplus", typ=display_typ(typ_db), cat=cat, n=consecutive, amount=format_money(abs(avg_dev)), current=format_money(current_budget), suggested=format_money(suggested))
                else:
                    msg = trf("suggestion.suggestion_deficit", typ=display_typ(typ_db), cat=cat, n=consecutive, amount=format_money(abs(avg_dev)), current=format_money(current_budget), suggested=format_money(suggested))

                suggestions.append(BudgetSuggestion(
                    typ=typ_db,
                    category=cat,
                    direction=direction,
                    avg_deviation=avg_dev,
                    consecutive_months=consecutive,
                    suggested_amount=suggested,
                    current_budget=current_budget,
                    message=msg,
                ))

        return suggestions

    def get_type_suggestions(
        self,
        year: int,
        current_month: int,
        min_consecutive_months: int = 3,
    ) -> list[BudgetSuggestion]:
        """
        Wie get_suggestions, aber auf Typ-Ebene (Gesamt-Ausgaben, Gesamt-Ersparnisse).
        v0.4.4.0-Fix: Jahresübergreifende Analyse.
        """
        suggestions: list[BudgetSuggestion] = []
        # Kein vorzeitiger Abbruch – wir nutzen jahresübergreifende Fenster

        from statistics import median

        for typ in [TYP_EXPENSES, TYP_SAVINGS]:
            # Fenster der letzten N abgeschlossenen Monate (jahresübergreifend)
            # Wir schauen VOR dem aktuellen Monat (da dieser unvollständig sein kann)
            deviations: list[float] = []
            d = date(year, current_month, 1)
            # Einen Monat zurück starten (aktueller Monat überspringen)
            if d.month == 1:
                d = date(d.year - 1, 12, 1)
            else:
                d = date(d.year, d.month - 1, 1)

            max_scan = min_consecutive_months * 3
            for _ in range(max_scan):
                if len(deviations) >= min_consecutive_months:
                    break
                b = self._budget_sum(d.year, d.month, typ)
                a = self._actual_sum(d.year, d.month, typ)
                if b > 0:
                    dev = rest_sign(typ, b, a)
                    deviations.append(float(dev))
                # Einen Monat zurück
                if d.month == 1:
                    d = date(d.year - 1, 12, 1)
                else:
                    d = date(d.year, d.month - 1, 1)

            deviations.reverse()

            if len(deviations) < min_consecutive_months:
                continue

            pos = sum(1 for d in deviations if d > 0)
            neg = sum(1 for d in deviations if d < 0)
            zero_count = len(deviations) - pos - neg
            non_zero = max(1, len(deviations) - zero_count)
            dominant = max(pos, neg)
            if dominant / non_zero < 0.7:
                continue

            central = float(median(deviations))
            avg_dev = float(sum(deviations) / len(deviations))
            direction = "surplus" if central > 0 else "deficit"

            # Budget des aktuellen Monats
            current_budget = self._budget_sum(year, current_month, typ)
            if current_budget <= 0:
                continue

            suggested = current_budget - (central * 0.8)
            suggested = max(0.0, round(suggested / 10) * 10)
            delta = suggested - current_budget
            if abs(delta) < 20 and abs(delta) < (current_budget * 0.05):
                continue

            if direction == "surplus":
                msg = trf("suggestion.suggestion_surplus", typ=display_typ(typ), cat=tr("suggestion.total_label"), n=min_consecutive_months, amount=format_money(abs(avg_dev)), current=format_money(current_budget), suggested=format_money(suggested))
            else:
                msg = trf("suggestion.suggestion_deficit", typ=display_typ(typ), cat=tr("suggestion.total_label"), n=min_consecutive_months, amount=format_money(abs(avg_dev)), current=format_money(current_budget), suggested=format_money(suggested))

            suggestions.append(BudgetSuggestion(
                typ=typ,
                category="(Gesamt)",
                direction=direction,
                avg_deviation=avg_dev,
                consecutive_months=min_consecutive_months,
                suggested_amount=suggested,
                current_budget=current_budget,
                message=msg,
            ))

        return suggestions

    # ------------------------------------------------------------------
    # Hilfsmethoden
    # ------------------------------------------------------------------
    def _check_consecutive_pattern(
        self,
        typ: str,
        cat: str,
        deviations: list[float],
        months: list[int],
        year: int,
        min_months: int,
    ) -> BudgetSuggestion | None:
        """Prüft ob die letzten N Monate konsistent positiv oder negativ sind."""
        if len(deviations) < min_months:
            return None

        # Von hinten prüfen (neueste Monate zuerst)
        recent = deviations[-min_months:]

        # Alle positiv (Überschuss)?
        all_positive = all(d > 0 for d in recent)
        # Alle negativ (Defizit)?
        all_negative = all(d < 0 for d in recent)

        if not (all_positive or all_negative):
            return None

        # Wie viele aufeinanderfolgende Monate (von hinten)?
        consecutive = 0
        sign = 1 if all_positive else -1
        for d in reversed(deviations):
            if (d > 0 and sign > 0) or (d < 0 and sign < 0):
                consecutive += 1
            else:
                break

        if consecutive < min_months:
            return None

        avg_dev = sum(deviations[-consecutive:]) / consecutive
        direction = "surplus" if all_positive else "deficit"

        # Aktuelles Budget (letzter geprüfter Monat)
        last_month = months[-1]
        current_budget = self._budget_by_category(year, last_month, typ).get(cat, 0.0)
        if cat == "(Gesamt)":
            current_budget = self._budget_sum(year, last_month, typ)

        # Vorschlag: Budget anpassen um ~80% der Abweichung
        adjustment = avg_dev * 0.8
        if typ == TYP_INCOME:
            suggested = current_budget + adjustment
        else:
            suggested = current_budget - adjustment

        suggested = max(0, round(suggested, 2))

        if direction == "surplus":
            msg = trf("suggestion.suggestion_surplus", typ=display_typ(typ), cat=cat, n=consecutive, amount=format_money(abs(avg_dev)), current=format_money(current_budget), suggested=format_money(suggested))
        else:
            msg = trf("suggestion.suggestion_deficit", typ=display_typ(typ), cat=cat, n=consecutive, amount=format_money(abs(avg_dev)), current=format_money(current_budget), suggested=format_money(suggested))

        return BudgetSuggestion(
            typ=typ,
            category=cat,
            direction=direction,
            avg_deviation=avg_dev,
            consecutive_months=consecutive,
            suggested_amount=suggested,
            current_budget=current_budget,
            message=msg,
        )

    def check_income_coverage(
        self,
        year: int,
        month: int,
        suggestions: list[BudgetSuggestion],
    ) -> dict | None:
        """
        Prüft ob die vorgeschlagenen Budget-Anpassungen das Einkommen übersteigen.
        
        Vergleicht:
        - Aktuelles Gesamt-Einkommen (Budget) für den Monat
        - Aktuelle Ausgaben+Ersparnisse Budgets PLUS vorgeschlagene Erhöhungen
        
        Returns:
            None wenn alles ok, sonst dict mit Warn-Infos:
            {
                'income_budget': float,
                'current_expenses': float,
                'suggested_expenses': float,
                'deficit': float,
                'deficit_categories': list[str],
            }
        """
        # Einkommen für den Monat
        income_budget = self._budget_sum(year, month, TYP_INCOME)
        if income_budget <= 0:
            return None  # Kein Einkommen budgetiert → kann nicht prüfen

        # Aktuelle Ausgaben + Ersparnisse Budgets
        current_ausgaben = self._budget_sum(year, month, TYP_EXPENSES)
        current_ersparnisse = self._budget_sum(year, month, TYP_SAVINGS)
        current_total = current_ausgaben + current_ersparnisse

        # Vorgeschlagene Änderungen berechnen
        suggested_total = current_total
        deficit_categories: list[str] = []

        for s in suggestions:
            if s.typ not in (TYP_EXPENSES, TYP_SAVINGS):
                continue
            if s.category == "(Gesamt)":
                continue  # Gesamt-Vorschläge nicht doppelt zählen

            # Differenz: neues Budget minus altes Budget
            diff = s.suggested_amount - s.current_budget
            if diff > 0:
                # Nur Erhöhungen zählen (Senkungen helfen ja)
                suggested_total += diff
                deficit_categories.append(
                    f"{s.typ}/{s.category}: {format_money(s.current_budget)} → {format_money(s.suggested_amount)} "
                    f"(+{format_money(diff)})"
                )

        if suggested_total <= income_budget:
            return None  # Alles im Rahmen

        deficit = suggested_total - income_budget

        return {
            'income_budget': income_budget,
            'current_expenses': current_total,
            'suggested_expenses': suggested_total,
            'deficit': deficit,
            'deficit_categories': deficit_categories,
        }

    def _get_initial_carry_over(self, year: int, typ: str) -> float:
        """Übertrag aus Dezember des Vorjahres (optional)."""
        prev_year = year - 1
        # Prüfe ob es Budget-Daten im Vorjahr gibt
        row = self.conn.execute(
            "SELECT COUNT(*) FROM budget WHERE year=? AND typ=?",
            (prev_year, typ)
        ).fetchone()

        if not row or row[0] == 0:
            return 0.0

        # Kumulierten Rest des Vorjahres berechnen
        total_rest = 0.0
        for m in range(1, 13):
            b = self._budget_sum(prev_year, m, typ)
            a = self._actual_sum(prev_year, m, typ)
            total_rest += rest_sign(typ, b, a)

        return total_rest

    def _budget_sum(self, year: int, month: int, typ: str) -> float:
        """Summe aller Budget-Einträge für Jahr/Monat/Typ."""
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM budget WHERE year=? AND month=? AND typ=?",
            (year, month, typ)
        ).fetchone()
        return float(row[0]) if row else 0.0

    def budget_sum(self, year: int, month: int, typ: str) -> float:
        """Öffentliche API: Summe aller Budget-Einträge für Jahr/Monat/Typ."""
        return self._budget_sum(year, month, typ)

    def _actual_sum(self, year: int, month: int, typ: str) -> float:
        """Summe aller Tracking-Einträge für Jahr/Monat/Typ."""
        start = f"{year:04d}-{month:02d}-01"
        last_day = calendar.monthrange(year, month)[1]
        end = f"{year:04d}-{month:02d}-{last_day:02d}"
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM tracking "
            "WHERE date >= ? AND date <= ? AND typ=?",
            (start, end, typ)
        ).fetchone()
        val = float(row[0]) if row else 0.0
        if typ == TYP_EXPENSES:
            return abs(val)
        return val

    def _budget_by_category(self, year: int, month: int, typ: str) -> dict[str, float]:
        """Budget pro Kategorie."""
        cur = self.conn.execute(
            "SELECT category, amount FROM budget WHERE year=? AND month=? AND typ=?",
            (year, month, typ)
        )
        return {str(r[0]): float(r[1]) for r in cur.fetchall()}

    def _actual_by_category(self, year: int, month: int, typ: str) -> dict[str, float]:
        """Ist-Werte pro Kategorie."""
        start = f"{year:04d}-{month:02d}-01"
        last_day = calendar.monthrange(year, month)[1]
        end = f"{year:04d}-{month:02d}-{last_day:02d}"
        cur = self.conn.execute(
            "SELECT category, SUM(amount) FROM tracking "
            "WHERE date >= ? AND date <= ? AND typ=? GROUP BY category",
            (start, end, typ)
        )
        result = {}
        for r in cur.fetchall():
            val = float(r[1])
            if typ == TYP_EXPENSES:
                val = abs(val)
            result[str(r[0])] = val
        return result

    def carry_over_by_category(self, year: int, month: int, typ: str,
                               start_month: int = 1, start_year: int | None = None) -> dict[str, float]:
        """Öffentliche API für kumulierten Rest pro Kategorie von start_month bis month-1.
        
        Wrapper um _carry_over_by_category() – Views sollen diese öffentliche Methode
        verwenden, nicht die private Variante.
        """
        return self._carry_over_by_category(year, month, typ, start_month, start_year)

    def _carry_over_by_category(self, year: int, month: int, typ: str,
                                  start_month: int = 1, start_year: int | None = None) -> dict[str, float]:
        """Kumulierter Rest pro Kategorie von start_month bis month-1.
        
        Args:
            year: Aktuelles Jahr
            month: Aktueller Monat (Carry-Over wird bis month-1 berechnet)
            typ: Typ-Filter (Ausgaben/Ersparnisse/Einkommen)
            start_month: Ab welchem Monat kumuliert wird (1-12, aus Einstellungen)
            start_year: Ab welchem Jahr kumuliert wird (None = gleich wie year)
        """
        if start_year is None:
            start_year = year

        # Wenn aktueller Monat <= start_month (im Startjahr): kein Übertrag
        if year == start_year and month <= start_month:
            return {}

        carry: dict[str, float] = {}

        # Vorjahre kumulieren (start_year bis year-1)
        if start_year < year:
            for y in range(start_year, year):
                first_m = start_month if y == start_year else 1
                carry = self._accumulate_carry_batch(carry, y, first_m, 12, typ)

        # Aktuelles Jahr: von (start_month oder 1) bis month-1
        first_m_this_year = start_month if year == start_year else 1
        end_m = month - 1
        if end_m >= first_m_this_year:
            carry = self._accumulate_carry_batch(carry, year, first_m_this_year, end_m, typ)

        return carry

    def _accumulate_carry_batch(self, carry: dict[str, float],
                                 year: int, from_month: int, to_month: int,
                                 typ: str) -> dict[str, float]:
        """Batch-Version: kumuliert Budget-Rest pro Kategorie über einen Monatsbereich.
        Verwendet nur 2 SQL-Queries statt 2 × Anzahl-Monate.
        """
        if from_month > to_month:
            return carry

        # Budget: alle Monate in einer Query
        cur_b = self.conn.execute(
            "SELECT category, SUM(amount) FROM budget "
            "WHERE year=? AND month>=? AND month<=? AND typ=? "
            "GROUP BY category",
            (year, from_month, to_month, typ)
        )
        budget_totals = {str(r[0]): float(r[1]) for r in cur_b.fetchall()}

        # Actual: alle Monate in einer Query
        start_date = f"{year:04d}-{from_month:02d}-01"
        last_day = calendar.monthrange(year, to_month)[1]
        end_date = f"{year:04d}-{to_month:02d}-{last_day:02d}"
        cur_a = self.conn.execute(
            "SELECT category, SUM(amount) FROM tracking "
            "WHERE date >= ? AND date <= ? AND typ=? "
            "GROUP BY category",
            (start_date, end_date, typ)
        )
        actual_totals = {}
        for r in cur_a.fetchall():
            val = float(r[1])
            if typ == TYP_EXPENSES:
                val = abs(val)
            actual_totals[str(r[0])] = val

        # Rest pro Kategorie berechnen und akkumulieren
        all_cats = set(budget_totals.keys()) | set(actual_totals.keys())
        for cat in all_cats:
            b = budget_totals.get(cat, 0.0)
            a = actual_totals.get(cat, 0.0)
            rest = rest_sign(typ, b, a)
            carry[cat] = carry.get(cat, 0.0) + rest

        return carry

    # ──────── Öffentliche Aggregat-Methoden ────────

    def budget_by_category_range(
        self, year: int, months: list[int], typ: str
    ) -> dict[str, float]:
        """Budget pro Kategorie, summiert über mehrere Monate (Batch-Query)."""
        if not months:
            return {}
        placeholders = ",".join("?" for _ in months)
        cur = self.conn.execute(
            f"SELECT category, SUM(amount) FROM budget "
            f"WHERE year=? AND month IN ({placeholders}) AND typ=? "
            f"GROUP BY category",
            (year, *months, typ)
        )
        return {str(r[0]): float(r[1]) for r in cur.fetchall()}

    def actual_by_category_range(
        self, year: int, months: list[int], typ: str
    ) -> dict[str, float]:
        """Ist-Werte pro Kategorie, summiert über mehrere Monate (Batch-Query)."""
        if not months:
            return {}
        min_m, max_m = min(months), max(months)
        start_date = f"{year:04d}-{min_m:02d}-01"
        last_day = calendar.monthrange(year, max_m)[1]
        end_date = f"{year:04d}-{max_m:02d}-{last_day:02d}"

        # Wenn nicht alle Monate im Bereich, filtern wir per SQL-Ausdruck
        if len(months) == (max_m - min_m + 1):
            # Zusammenhängender Bereich → einfache Range-Query
            cur = self.conn.execute(
                "SELECT category, SUM(amount) FROM tracking "
                "WHERE date >= ? AND date <= ? AND typ=? "
                "GROUP BY category",
                (start_date, end_date, typ)
            )
        else:
            # Nicht zusammenhängend → CAST(substr) für Monatsfilter
            placeholders = ",".join("?" for _ in months)
            cur = self.conn.execute(
                f"SELECT category, SUM(amount) FROM tracking "
                f"WHERE date >= ? AND date <= ? AND typ=? "
                f"AND CAST(substr(date, 6, 2) AS INTEGER) IN ({placeholders}) "
                f"GROUP BY category",
                (start_date, end_date, typ, *months)
            )

        result = {}
        for r in cur.fetchall():
            val = float(r[1])
            if typ == TYP_EXPENSES:
                val = abs(val)
            result[str(r[0])] = val
        return result
