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

v0.4.5.0 – Fixkosten-/0-Monats-Schutz:
- REGEL: 0 darf bei Fixkosten/wiederkehrenden Kategorien nie allein
  einen senkenden Budgetvorschlag auslösen. Fehlende Buchung ist ein
  Hinweis-Thema, aber kein Budgetänderungsbeweis.
- Fixkosten können inkrementell/lumpy sein (z.B. quartalsweise, jährlich
  oder in Raten). Darum werden bei Fixkosten nur echte Buchungsmonate
  (> 0) für Budgetänderungen ausgewertet. 0-Monate werden ignoriert.
- Für Fixkosten braucht es mindestens 3 echte Buchungsmonate, bevor ein
  Vorschlag entsteht. Wiederholte echte Überschreitung darf also weiterhin
  eine Erhöhung auslösen.
- Flexible Kategorien dürfen 0-Buchungen weiter als Teil eines wiederholten
  Musters verwenden (z.B. Hobby 40 CHF, Ist 20/30/0/...).
- Mindeständerung wird nach Rundung nochmals geprüft.

v2.0.37 – Pot/inkrementell getrennt:
- Kategorie-Forecast-Modus: auto / normal / pot / incremental.
- Auto-Regel: fix ohne Wiederholung = Pot (z.B. Franchise), fix oder
  wiederkehrend = inkrementell/lumpy (z.B. Hausrat-Jahresrechnung).
- Pot prüft die Summe der Buchungen gegen EINEN Topf-Betrag, nicht gegen
  Budget × Monate. Unterbudgetierte Pots dürfen erhöhen, Teilverbrauch unter
  Topf bleibt stabil, ganzjährige 0-Pots werden als prüfbarer Vorschlag markiert.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date
from statistics import median

from model.category_forecast_mode import (
    FORECAST_MODE_INCREMENTAL,
    FORECAST_MODE_POT,
    effective_forecast_mode,
    normalize_forecast_mode,
)
from model.date_ranges import month_bounds
from model.typ_constants import (
    is_income,
)

logger = logging.getLogger(__name__)


@dataclass
class SuggestionResult:
    typ: str
    category: str
    direction: str  # "surplus" oder "deficit"
    months_considered: int
    streak_months: int
    central_deviation: float  # Median der letzten N Abweichungen
    avg_deviation: float  # Durchschnitt der letzten N Abweichungen
    current_budget: float
    suggested_budget: float
    delta: float  # suggested - current


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
        # Fixkosten-/wiederkehrende Kategorien schützen:
        # 0-Monate dürfen dort keine Senkung beweisen.
        respect_fixed_costs: bool = True,
    ) -> SuggestionResult | None:
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
            respect_fixed_costs: True = Kategorien mit is_fix=1 oder
                               is_recurring=1 werden geschützt. 0-Monate
                               werden dort für Budgetänderungen ignoriert;
                               es braucht wiederholte echte Buchungen.
        """
        if months_back <= 0:
            return None

        # Aktuelles/Ziel-Budget bestimmen.
        #
        # KILLCRITIC v2.2.5: In der Praxis wird der Vorschlagsdialog oft im
        # aktuellen Monat geöffnet, während die auswertbaren Daten aus bereits
        # abgeschlossenen Vormonaten stammen. Wenn der Zielmonat selbst noch kein
        # Budget hat (z.B. Juli leer, Jan-Jun budgetiert+gebucht), darf die
        # Forecast-Engine nicht mit ``None`` abbrechen. Sonst sieht der Nutzer
        # trotz mehrerer Monate über Budget keinen Vorschlag.
        #
        # Darum: erst Budget im Zielmonat nehmen; falls leer, die letzte positive
        # Budgetbasis vor dem Zielmonat verwenden. Die Abweichungsfenster unten
        # bleiben unverändert und prüfen weiterhin echte historische Monate.
        current_budget = self._get_budget_amount(year, month, typ, category)
        if current_budget is None or current_budget <= 0:
            current_budget = self._get_latest_budget_before(year, month, typ, category)
        if current_budget is None or current_budget <= 0:
            return None

        # Floor berechnen (nur für Ausgaben/Ersparnisse; Einkommen hat keinen Floor)
        floor = 0.0
        if not self._is_income(typ):
            try:
                floor = max(float(floor_abs), float(current_budget) * float(floor_rel))
            except Exception:
                floor = float(floor_abs)

        # Kategorie-Flags + Forecast-Modus bestimmen.
        # v2.0.37 trennt Pot/Rückstellung von inkrementellen Fixkosten:
        # - auto + fix ohne Wiederholung => Pot
        # - auto + fix/wiederkehrend    => inkrementell
        # - normale Kategorien bleiben flexibel
        is_fix, is_recurring = self._get_category_flags(typ, category)
        forecast_mode = self._get_category_forecast_mode(
            typ, category, is_fix, is_recurring
        )
        pot_like = (
            bool(respect_fixed_costs)
            and (not self._is_income(typ))
            and forecast_mode == FORECAST_MODE_POT
        )
        fixed_like = (
            bool(respect_fixed_costs)
            and (not self._is_income(typ))
            and forecast_mode == FORECAST_MODE_INCREMENTAL
        )

        # ── Startmonat für die Analyse bestimmen ──
        # Bei use_current_month=False darf nur der wirklich laufende/zukünftige
        # Zielmonat übersprungen werden. Ein bereits abgeschlossener Zielmonat
        # (z.B. im Juli rückwirkend Juni prüfen) muss in die Analyse einfliessen,
        # sonst verschwinden genau die Praxisfälle "mehrere Monate über Budget".
        today = date.today()
        target_is_past_month = (int(year), int(month)) < (today.year, today.month)
        target_has_real_booking = self._get_spent_amount(year, month, typ, category) > 0
        if use_current_month or (target_is_past_month and target_has_real_booking):
            analysis_year, analysis_month = year, month
        else:
            analysis_year, analysis_month = self._prev_month(year, month)

        # ── Datengrenze: nicht vor dem tatsächlichen Tracking-Beginn analysieren ──
        # Spätester von (erste echte Buchung global, konfigurierter Startmonat).
        # Monate davor sind keine "0-Ausgaben"-Monate, sondern liegen vor Beginn
        # der Nutzung und dürfen keine Vorschläge auslösen. None = keine Grenze
        # bekannt (keine Buchung UND kein Startmonat) → kein Clamping, damit die
        # Langzeit-0-Reduktion (Budget gesetzt, nie gebucht) weiter greifen kann.
        not_before = self._data_start_boundary()

        # Abweichungen sammeln (erweitert sich über Lücken hinweg)
        deviations = self._get_deviations_window(
            typ,
            category,
            analysis_year,
            analysis_month,
            months_back,
            not_before=not_before,
        )

        # ── Pot/Rückstellungs-Logik ──
        # Pot = ein Topf pro Zeitraum/Jahr (z.B. Franchise/Selbstbehalt).
        # Der Betrag wird NICHT mit den Monaten multipliziert. Als Topfwert wird
        # der höchste Budgetwert im Analysefenster verwendet, damit auch
        # bestehende "Alle Monate mit 750"-Budgets korrekt als EIN 750er-Topf
        # interpretiert werden können.
        # Wichtig: Die allgemeine Abweichungsfenster-Grenze darf Pots nicht
        # ausblenden. Bei spät begonnener Nutzung kann ein Pot bereits real
        # überzogen sein, obwohl vor dem Tracking-Start keine Abweichungen
        # gesammelt werden dürfen. Pot-Logik validiert ihr Budget-/Ist-Fenster
        # deshalb selbst.
        if pot_like:
            return self._build_pot_suggestion_result(
                typ=typ,
                category=category,
                analysis_year=analysis_year,
                analysis_month=analysis_month,
                months_back=months_back,
                current_budget=current_budget,
                floor=floor,
                alpha=alpha,
                round_to=round_to,
                min_abs_change=min_abs_change,
                min_pct_change=min_pct_change,
                not_before=not_before,
            )

        if len(deviations) < months_back:
            return None

        # ── Fixkosten-/0-Monats-Schutz ──
        # Bei Fixkosten/wiederkehrenden Kategorien bedeutet "0 gebucht" nicht
        # automatisch "Budget zu hoch". Es kann auch heissen: Buchung fehlt,
        # Zahlung kommt später, Jahres-/Quartalsrechnung oder Importlücke.
        #
        # Release-Regel v2.0.30:
        # - 0-Monate dürfen keine Senkung beweisen.
        # - Aktive Einzelzahlungen über Monatsbudget dürfen aber auch keine
        #   Erhöhung beweisen, solange das Gesamtbudget des Fensters ausreicht.
        #   Beispiel: Budget 200, Ist 250/250/250/0/0/0 → 750 Ist gegen
        #   1200 Budget. Das ist keine Unterdeckung und darf nicht auf 240
        #   hochvorschlagen.
        # - Wenn es 0-Monate gibt, wird eine Erhöhung nur aus der gesamten
        #   Fensterdeckung abgeleitet (Summe Ist > Summe Budget), nicht aus
        #   den aktiven Monaten allein. So bleiben lumpy/inkrementelle
        #   Fixkosten stabil.
        if fixed_like:
            active_months = self._count_active_months(
                typ,
                category,
                analysis_year,
                analysis_month,
                months_back,
                not_before=not_before,
            )
            if active_months < min(3, months_back):
                return None

            # Zero-Reduction für Fixkosten hart deaktivieren.
            enable_zero_reduction = False

            if active_months < months_back:
                # Es gibt echte 0-Monate im aktuellen Analysefenster.
                # Deshalb: keine Senkung, und Erhöhung nur bei Gesamtunterdeckung.
                total_deviation = float(sum(deviations))
                if total_deviation >= 0:
                    return None

                avg_window_deviation = total_deviation / float(len(deviations))
                # Normale Sign-Ratio/Median-Logik wäre bei lumpy Fixkosten
                # irreführend (0-Monate haben positives Vorzeichen). Wir nutzen
                # stattdessen die durchschnittliche Gesamtunterdeckung pro Monat
                # als konservativen Anpassungswert.
                deviations = [avg_window_deviation for _ in deviations]

        # ── 0-Buchungen-Handling ──
        # Nur flexible Kategorien dürfen wegen wiederholten 0-Monaten reduziert
        # werden. Fixkosten/Rückstellungen sind oben geschützt.
        if enable_zero_reduction and (not self._is_income(typ)) and (not fixed_like):
            active_months = self._count_active_months(
                typ,
                category,
                analysis_year,
                analysis_month,
                months_back,
                not_before=not_before,
            )
            if active_months == 0:
                zero_streak = self._compute_zero_streak_months(
                    typ,
                    category,
                    analysis_year,
                    analysis_month,
                    not_before=not_before,
                )
                if zero_streak >= 6:
                    return self._build_zero_reduction_result(
                        typ,
                        category,
                        current_budget,
                        floor,
                        zero_streak,
                        deviations,
                        round_to,
                        min_abs_change,
                        min_pct_change,
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
        suggested = (
            current_budget + adjustment
            if self._is_income(typ)
            else current_budget - adjustment
        )

        # Negative Budgets verhindern + Floor
        suggested = (
            max(0.0, suggested)
            if self._is_income(typ)
            else max(float(floor), float(suggested))
        )

        # Schwellwerte (Änderung gross genug?)
        delta = suggested - current_budget
        if abs(delta) < float(min_abs_change) and abs(delta) < (
            current_budget * float(min_pct_change)
        ):
            return None

        # Runden
        if round_to and round_to > 0:
            suggested = round(suggested / round_to) * round_to
            suggested = (
                max(0.0, suggested)
                if self._is_income(typ)
                else max(float(floor), float(suggested))
            )
            delta = suggested - current_budget

        # Nochmals prüfen nach Rundung. Rundung kann delta auf 0 bringen oder
        # künstlich eine zu kleine Änderung erzeugen. Gleiche Schwelle wie vor
        # der Rundung, damit 10-CHF-Rauschen nicht als Vorschlag erscheint.
        if abs(delta) < 0.01:
            return None
        if abs(delta) < float(min_abs_change) and abs(delta) < (
            current_budget * float(min_pct_change)
        ):
            return None

        # Streak
        streak = self._compute_streak_months(
            typ,
            category,
            analysis_year,
            analysis_month,
            sign=(1 if central > 0 else -1),
            not_before=not_before,
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
        self,
        typ,
        category,
        current_budget,
        floor,
        zero_streak,
        deviations,
        round_to,
        min_abs_change,
        min_pct_change,
    ) -> SuggestionResult | None:
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

        if abs(delta) < float(min_abs_change) and abs(delta) < (
            float(current_budget) * float(min_pct_change)
        ):
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
    # Pot/Rückstellungs-Logik
    # ------------------------------------------------------------
    def _budgeted_months_window(
        self,
        typ: str,
        category: str,
        year: int,
        month: int,
        months_back: int,
        not_before: date | None = None,
    ) -> list[date]:
        """Liefert die letzten N Monate mit Budgeteintrag im Analysefenster."""
        out: list[date] = []
        base = date(year, month, 1)
        max_scan = months_back * 3
        for i in range(max_scan):
            if len(out) >= months_back:
                break
            d = self._subtract_months(base, i)
            if not_before is not None and d < not_before:
                break
            b = self._get_budget_amount(d.year, d.month, typ, category)
            if b is None or b <= 0:
                continue
            out.append(d)
        out.reverse()
        return out

    def _build_pot_suggestion_result(
        self,
        *,
        typ: str,
        category: str,
        analysis_year: int,
        analysis_month: int,
        months_back: int,
        current_budget: float,
        floor: float,
        alpha: float,
        round_to: float,
        min_abs_change: float,
        min_pct_change: float,
        not_before: date | None = None,
    ) -> SuggestionResult | None:
        """Forecast für Pot/Rückstellungen.

        Pot-Regeln:
        - Vergleicht Summe der Buchungen im Fenster mit EINEM Topf-Budget.
        - Topf-Budget = höchster Monats-Budgetwert im Fenster/current_budget.
        - Verbrauch unter Topf erzeugt keinen Senkungsvorschlag.
        - Verbrauch über Topf erzeugt einen vorsichtigen Erhöhungsvorschlag.
        - 12+ Monate komplett 0 erzeugen einen Prüf-/Senkungsvorschlag.
        """
        # Pot-Überverbrauch muss auch dann erkannt werden, wenn die erste
        # echte Buchung erst spät im Jahr erfasst wurde. Die allgemeine
        # Tracking-Startgrenze schützt vor falschen 0-Monats-Senkungen, darf
        # aber einen bereits überzogenen Topf nicht unsichtbar machen.
        months = self._budgeted_months_window(
            typ, category, analysis_year, analysis_month, months_back, None
        )
        if len(months) < months_back:
            return None

        budgets = [
            float(self._get_budget_amount(d.year, d.month, typ, category) or 0.0)
            for d in months
        ]
        spent_values = [
            float(self._get_spent_amount(d.year, d.month, typ, category))
            for d in months
        ]
        total_spent = float(sum(spent_values))
        active_months = sum(1 for v in spent_values if abs(v) > 0.000001)

        monthly_budget = float(current_budget)
        window_budget = float(sum(budgets))

        # Kein Verbrauch über den ganzen Jahres-/Langzeit-Zeitraum: bewusst als
        # Vorschlag/Review markieren. Für kurze Fenster bleiben Pots stabil.
        if active_months == 0:
            zero_streak = self._compute_zero_streak_months(
                typ, category, analysis_year, analysis_month, not_before=not_before
            )
            if zero_streak >= 12:
                deviations = [monthly_budget for _ in months]
                return self._build_zero_reduction_result(
                    typ,
                    category,
                    monthly_budget,
                    floor,
                    zero_streak,
                    deviations,
                    round_to,
                    min_abs_change,
                    min_pct_change,
                )
            return None

        # Regelmässige Nutzung in (nahezu) jedem Fenstermonat ist kein Topf,
        # sondern eine laufende Monatsausgabe (z.B. Lebensmittel, versehentlich
        # als Fix/Pot klassifiziert). Echte Töpfe (Franchise/Selbstbehalt) werden
        # lumpy bezogen – nur in einzelnen Monaten. Unterscheidungssignal:
        # Buchungs-Regelmässigkeit. Ein einzelner Null-Monat (Ferien o.ä.) darf
        # eine sonst monatliche Kategorie nicht in die Topf-Inflation zurückkippen.
        # KILLCRITIC v2.2.5: Bei kurzen Fenstern (3 Monate) darf eine
        # Franchise/POT-Kategorie mit 2 aktiven Monaten + 1 Nullmonat nicht als
        # normale Monatsausgabe fehlklassifiziert werden. Sonst wird gegen
        # Budget×Monate geprüft und ein überzogener Topf bleibt stumm. Erst
        # nahezu durchgehend aktive Reihen ab mindestens 3 Buchungsmonaten
        # gelten als laufende Monatsausgabe.
        regular_monthly = active_months >= max(3, len(months) - 1)

        if regular_monthly:
            # Pro-Monat-Vergleich: Fenster-Verbrauch gegen Fenster-Budget (Summe
            # der Monatsbudgets), Vorschlag als MONATLICHE Erhöhung normiert.
            if monthly_budget <= 0 or window_budget <= 0:
                return None
            if total_spent <= window_budget:
                return None
            deficit_per_month = (total_spent - window_budget) / float(len(months))
            base = monthly_budget
            suggested = monthly_budget + (deficit_per_month * float(alpha))
            central_dev = -float(deficit_per_month)
            avg_dev = -float(deficit_per_month)
        else:
            # Echter Topf: Gesamtverbrauch gegen Topf-Cap (höchstes Monatsbudget
            # im Fenster). Teilverbrauch unter dem Topf ist normal und senkt nicht.
            pot_budget = max([monthly_budget, *budgets])
            if pot_budget <= 0:
                return None
            if total_spent <= pot_budget:
                return None
            deficit = total_spent - pot_budget
            base = pot_budget
            suggested = pot_budget + (deficit * float(alpha))
            central_dev = -float(deficit)
            avg_dev = (pot_budget - total_spent) / float(len(months))

        suggested = max(float(floor), float(suggested))
        if round_to and round_to > 0:
            suggested = round(suggested / round_to) * round_to
            suggested = max(float(floor), float(suggested))
        delta = float(suggested) - float(base)

        if abs(delta) < 0.01:
            return None
        if abs(delta) < float(min_abs_change) and abs(delta) < (
            float(base) * float(min_pct_change)
        ):
            return None

        return SuggestionResult(
            typ=typ,
            category=category,
            direction="deficit",
            months_considered=len(months),
            streak_months=int(active_months),
            central_deviation=float(central_dev),
            avg_deviation=float(avg_dev),
            current_budget=float(base),
            suggested_budget=float(suggested),
            delta=float(delta),
        )

    # ------------------------------------------------------------
    # Kategorie-Flags
    # ------------------------------------------------------------
    def _get_category_flags(self, typ: str, category: str) -> tuple[bool, bool]:
        """Liest (is_fix, is_recurring) robust aus categories.

        Bestandsdatenbanken oder Tests können ältere Schemas haben. Dann wird
        sicher auf (False, False) zurückgefallen.
        """
        try:
            cols = {
                row[1]
                for row in self.conn.execute("PRAGMA table_info(categories)").fetchall()
            }
            if not {"typ", "name", "is_fix", "is_recurring"}.issubset(cols):
                return (False, False)
            row = self.conn.execute(
                "SELECT is_fix, is_recurring FROM categories WHERE typ=? AND name=?",
                (typ, category),
            ).fetchone()
            if not row:
                return (False, False)

            return (self._as_bool(row[0]), self._as_bool(row[1]))
        except Exception:
            logger.exception(
                "Kategorie-Flags konnten nicht gelesen werden: %s/%s", typ, category
            )
            return (False, False)

    @staticmethod
    def _as_bool(value) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "ja"}
        try:
            return bool(int(value))
        except (TypeError, ValueError):
            return bool(value)

    def _get_category_forecast_mode(
        self, typ: str, category: str, is_fix: bool, is_recurring: bool
    ) -> str:
        """Liest den gespeicherten Forecast-Modus und wendet Auto-Defaults an."""
        try:
            cols = {
                row[1]
                for row in self.conn.execute("PRAGMA table_info(categories)").fetchall()
            }
            stored = None
            if "forecast_mode" in cols:
                row = self.conn.execute(
                    "SELECT forecast_mode FROM categories WHERE typ=? AND name=?",
                    (typ, category),
                ).fetchone()
                if row:
                    stored = normalize_forecast_mode(row[0])
            return effective_forecast_mode(stored, is_fix, is_recurring)
        except Exception:
            logger.exception(
                "Kategorie-Forecast-Modus konnte nicht gelesen werden: %s/%s",
                typ,
                category,
            )
            return effective_forecast_mode(None, is_fix, is_recurring)

    # ------------------------------------------------------------
    # Zähler
    # ------------------------------------------------------------
    def _count_active_months(
        self,
        typ: str,
        category: str,
        year: int,
        month: int,
        months_back: int,
        not_before: date | None = None,
    ) -> int:
        """Zählt, in wie vielen der letzten N Monate überhaupt Buchungen > 0 vorkamen."""
        active = 0
        base = date(year, month, 1)
        for i in range(months_back):
            d = self._subtract_months(base, i)
            if not_before is not None and d < not_before:
                break  # vor Tracking-Beginn → nicht weiter zurück
            b = self._get_budget_amount(d.year, d.month, typ, category)
            if b is None or b <= 0:
                continue
            a = self._get_spent_amount(d.year, d.month, typ, category)
            if abs(float(a)) > 0.000001:
                active += 1
        return active

    def _compute_zero_streak_months(
        self,
        typ: str,
        category: str,
        year: int,
        month: int,
        not_before: date | None = None,
    ) -> int:
        """Zählt Monate rückwärts *in Folge* ohne Buchungen (spent == 0)."""
        streak = 0
        base = date(year, month, 1)
        for i in range(0, 60):
            d = self._subtract_months(base, i)
            if not_before is not None and d < not_before:
                break  # vor Tracking-Beginn → Strähne endet hier
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

    def _get_budget_amount(
        self, year: int, month: int, typ: str, category: str
    ) -> float | None:
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

    def _get_latest_budget_before(
        self, year: int, month: int, typ: str, category: str, max_scan: int = 24
    ) -> float | None:
        """Letzte positive Budgetbasis vor dem Zielmonat.

        Wird nur als Basis für Vorschläge genutzt, wenn der Zielmonat selbst
        noch kein Budget hat. Damit können mehrere abgeschlossene Monate trotz
        leerem aktuellem Monat einen sinnvollen Vorschlag erzeugen.
        """
        base = date(int(year), max(1, min(12, int(month or 1))), 1)
        for i in range(1, max(1, int(max_scan)) + 1):
            d = self._subtract_months(base, i)
            amount = self._get_budget_amount(d.year, d.month, typ, category)
            if amount is not None and float(amount) > 0:
                return float(amount)
        return None

    def _get_spent_amount(
        self, year: int, month: int, typ: str, category: str
    ) -> float:
        start, end = month_bounds(year, month)

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

    # ------------------------------------------------------------
    # Datengrenze (Tracking-Beginn)
    # ------------------------------------------------------------
    def _first_booking_month(self) -> tuple[int, int] | None:
        """Frühester Monat mit irgendeiner echten Buchung (global, alle Kategorien).

        Dient als automatische untere Analysegrenze: Monate davor liegen vor
        Beginn der Nutzung. Robust: bei leerer/fehlender Tabelle → None.
        """
        try:
            row = self.conn.execute("SELECT MIN(date) FROM tracking").fetchone()
        except Exception:
            return None
        if not row or row[0] is None:
            return None
        s = str(row[0])
        try:
            y = int(s[0:4])
            m = int(s[5:7])
        except (ValueError, IndexError):
            return None
        if 1 <= m <= 12 and y >= 1:
            return (y, m)
        return None

    def _configured_start_month(self) -> tuple[int, int] | None:
        """Konfigurierter Startmonat (carryover_start_*), falls explizit gesetzt.

        Nur gültig, wenn carryover_start_year > 0. Der Standard (Jahr 0) gilt als
        "nicht gesetzt" → None. Robust gegen fehlende/fehlerhafte Settings.
        """
        try:
            from settings import Settings

            s = Settings()
            y = int(s.get("carryover_start_year", 0) or 0)
            m = int(s.get("carryover_start_month", 1) or 1)
        except Exception:
            return None
        if y <= 0:
            return None
        m = max(1, min(12, m))
        return (y, m)

    def _data_start_boundary(self) -> date | None:
        """Untere Analysegrenze als ``date`` oder ``None``.

        = der spätere von (erste echte Buchung, konfigurierter Startmonat).
        ``None`` bedeutet: keine Grenze bekannt (keine Buchung UND kein
        Startmonat). Dann wird NICHT geklammert, damit die Langzeit-0-Reduktion
        (Budget gesetzt, nie gebucht) wie gewünscht weiter greifen kann.
        """
        bounds: list[tuple[int, int]] = []
        fb = self._first_booking_month()
        if fb is not None:
            bounds.append(fb)
        cfg = self._configured_start_month()
        if cfg is not None:
            bounds.append(cfg)
        if not bounds:
            return None
        y, m = max(bounds)  # Tupel-Vergleich (Jahr, Monat) ist chronologisch
        return date(y, m, 1)

    def _get_deviations_window(
        self,
        typ: str,
        category: str,
        year: int,
        month: int,
        months_back: int,
        active_only: bool = False,
        not_before: date | None = None,
    ) -> list[float]:
        """Sammelt die letzten N Abweichungs-Datenpunkte.

        WICHTIG (v0.4.4.0-Fix): Das Fenster erweitert sich über Lückenmonate
        hinweg.  Wenn ein Monat kein Budget hat, wird er übersprungen und der
        Scan geht weiter zurück – bis zu ``months_back * 3`` Monate maximal.
        So reicht ein einzelner Monat ohne Budget nicht aus, um die gesamte
        Analyse zu blockieren.

        active_only=True: Monate ohne Buchung werden übersprungen. Das wird
        für Fixkosten genutzt, damit 0-Buchungen keine Senkung beweisen.
        """
        out: list[float] = []
        base = date(year, month, 1)
        max_scan = months_back * 3  # Sicherheitslimit
        for i in range(max_scan):
            if len(out) >= months_back:
                break
            d = self._subtract_months(base, i)
            if not_before is not None and d < not_before:
                break  # vor Tracking-Beginn → nicht weiter zurück scannen
            b = self._get_budget_amount(d.year, d.month, typ, category)
            if b is None or b <= 0:
                continue  # Lücke → überspringen, weiter suchen
            a = self._get_spent_amount(d.year, d.month, typ, category)
            if active_only and abs(float(a)) <= 0.000001:
                continue
            dev = a - float(b) if self._is_income(typ) else float(b) - a
            out.append(float(dev))

        out.reverse()
        return out

    def _compute_streak_months(
        self,
        typ: str,
        category: str,
        year: int,
        month: int,
        sign: int,
        not_before: date | None = None,
    ) -> int:
        """Zählt Monate rückwärts mit konsistenter Abweichungsrichtung."""
        streak = 0
        base = date(year, month, 1)
        for i in range(0, 60):
            d = self._subtract_months(base, i)
            if not_before is not None and d < not_before:
                break  # vor Tracking-Beginn → Strähne endet hier
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
