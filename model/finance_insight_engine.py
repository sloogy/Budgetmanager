"""Fachschicht des Finanz-Coachs: rechnet aus der Datenbank, nicht aus der KI.

Warum es diese Datei gibt: Der Coach ab Phase 3 soll aus dem *echten*
Finanzbestand lernen - Buchungen, Budgets, Kategorien, Tags, Sparziele,
Fixkosten-/Wiederholungsattribute, Forecast-Modi und wiederkehrende
Belastungen. Die Import-KI ist ein Hilfsmittel fuer den Bankimport und
sonst nichts; ein Coach, der ohne sie verstummt, waere fuer jeden nutzlos,
der seine Zahlen von Hand bucht.

**Diese Datei importiert darum kein einziges KI-Modul.** Das ist keine
Absichtserklaerung, sondern gepruefte Eigenschaft:
``tests/test_finance_insight_engine_p31.py`` liest die Importe dieser Datei
und faehrt saemtliche Auswertungen an einer Datenbank, in der die
``ai_*``-Tabellen nicht nur leer, sondern geloescht sind. Faellt hier je ein
Import auf ``model.bank_import_ai`` & Co. hinein, wird der Testlauf rot.

Konventionen, die hier bewusst *nicht* neu erfunden werden
-----------------------------------------------------------

**Vorzeichen.** ``model/budget_suggestion_engine.py`` liest den Ist-Wert
einer Kategorie als ``abs(SUM(amount))`` - der Betrag faengt Datenbanken ab,
in denen Ausgaben durchgaengig negativ gespeichert wurden. Diese Datei haelt
sich an dieselbe Regel, damit Coach und Budgetvorschlag ueber derselben
Kategorie nie zwei verschiedene Zahlen nennen. Der Betrag wirkt auf die
*Summe* eines Monats, nicht auf die einzelne Zeile: Eine Rueckerstattung
innerhalb des Monats verrechnet sich also korrekt, statt die Ausgaben zu
erhoehen.

Weil die Kategoriewerte je Kategorie und die Monatssumme je Typ gebildet
werden, koennen beide bei gemischten Vorzeichen innerhalb eines Monats
auseinanderlaufen. Das ist gewollt: Die Kategoriewerte stehen spaeter dem
Kategoriebudget gegenueber und muessen dessen Rechnung folgen. In einer
einheitlich vorzeichenrichtigen Datenbank sind beide Wege identisch.

**Ersparnisse.** Ein Bezug vom Sparkonto ist keine negative Einzahlung.
``tracking.savings_action`` trennt beides; fehlt die Spalte oder ist sie
leer, entscheidet das Vorzeichen - dieselbe Regel wie in
``TrackingModel._normalize_savings_action``.

**Median statt Mittelwert** (Architekturregel 1.3): Ein einzelner
Ausreissermonat darf einen Trend nicht kippen.

**Der laufende Monat zaehlt nicht mit.** Ein Monat, der noch laeuft, ist
kein Vergleichswert - er ist nur noch nicht fertig. ``budget_suggestion_engine``
schliesst ihn aus demselben Grund aus; wer ihn trotzdem braucht, fragt
``month_totals`` direkt.

**Kein Cache.** Die Roadmap erlaubt einen Performance-Cache unter Auflagen
(vollstaendig neu aufbaubar, nie Quelle der Wahrheit, Invalidierung bei
Buchungsaenderungen). Der einfachste Weg, diese Auflagen einzuhalten, ist,
gar keinen zu fuehren: Jede Methode liest die Datenbank frisch. Die
Auswertungen sind indexgestuetzte Aggregate ueber eine Haushaltsdatenbank,
keine Rechenlast, die einen zweiten Wahrheitsstand rechtfertigt.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from statistics import median

from model.category_forecast_mode import effective_forecast_mode
from model.savings_goals_model import (
    ACTION_WITHDRAWAL,
    STATUS_SAVING,
)
from model.typ_constants import (
    TYP_EXPENSES,
    TYP_INCOME,
    TYP_SAVINGS,
    is_income,
    normalize_typ,
    rest_sign,
)

#: Monate je Vergleichsfenster eines Trends. Unter drei Monaten ist ein
#: Median kein Median, sondern eine Meinung ueber zwei Zahlen.
MIN_TREND_MONTHS = 3

#: Rauschgrenzen fuer die Trendrichtung. Erst wenn eine Verschiebung *beide*
#: Grenzen reisst, heisst sie "up"/"down". Sonst bleibt es "flat" - eine
#: Abweichung von acht Franken auf achthundert ist keine Nachricht wert.
TREND_MIN_DELTA = 25.0
TREND_MIN_PERCENT = 5.0

DIRECTION_UP = "up"
DIRECTION_DOWN = "down"
DIRECTION_FLAT = "flat"


@dataclass(frozen=True)
class Totals:
    """Summen eines Zeitraums, getrennt nach Typ.

    ``surplus`` ist bewusst ``income - expenses`` und zieht die Ersparnisse
    *nicht* ab: Geld, das zur Seite gelegt wird, ist nicht verbraucht. Wer
    den Fluss aufs Sparkonto braucht, nimmt ``net_savings``.
    """

    months: int
    income: float
    expenses: float
    savings_deposits: float
    savings_withdrawals: float

    @property
    def surplus(self) -> float:
        """Was am Ende uebrig blieb, bevor etwas zur Seite gelegt wurde."""
        return self.income - self.expenses

    @property
    def net_savings(self) -> float:
        """Einzahlungen minus Bezuege - der echte Zuwachs des Sparbestands."""
        return self.savings_deposits - self.savings_withdrawals

    @property
    def average_monthly_surplus(self) -> float:
        """Ueberschuss je beruecksichtigtem Monat (0.0 ohne Monate)."""
        if self.months <= 0:
            return 0.0
        return self.surplus / float(self.months)


@dataclass(frozen=True)
class CategoryTotal:
    """Was eine Kategorie im Zeitraum ausmacht - mit ihren Attributen."""

    typ: str
    category: str
    amount: float
    #: Anteil an der Summe *desselben Typs* im selben Zeitraum (0.0 - 1.0).
    share: float
    #: Monate im Zeitraum, in denen ueberhaupt gebucht wurde. Trennt die
    #: Jahresrechnung (ein Monat, grosser Betrag) vom Dauerlaeufer.
    months_with_bookings: int
    is_fix: bool
    is_recurring: bool
    forecast_mode: str


@dataclass(frozen=True)
class TagTotal:
    """Summe je Tag. Tags sind eine eigene Datenquelle, keine Kategorie."""

    tag: str
    typ: str
    amount: float
    bookings: int


@dataclass(frozen=True)
class RecurringCommitment:
    """Eine geplante wiederkehrende Belastung aus ``recurring_transactions``."""

    typ: str
    category: str
    amount: float
    day_of_month: int
    details: str


@dataclass(frozen=True)
class Trend:
    """Zwei gleich lange Fenster im Vergleich, Median gegen Median."""

    typ: str
    #: ``None`` = ueber alle Kategorien dieses Typs.
    category: str | None
    months_per_window: int
    recent_median: float
    previous_median: float
    direction: str

    @property
    def delta(self) -> float:
        """Verschiebung des juengeren gegen das aeltere Fenster."""
        return self.recent_median - self.previous_median

    @property
    def delta_percent(self) -> float | None:
        """Verschiebung in Prozent, oder ``None`` bei Nullbasis."""
        if abs(self.previous_median) < 1e-9:
            return None
        return self.delta / abs(self.previous_median) * 100.0


@dataclass(frozen=True)
class BudgetDeviation:
    """Budget gegen Ist fuer genau eine Kategorie in genau einem Monat."""

    year: int
    month: int
    typ: str
    category: str
    budget: float
    actual: float
    #: Vorzeichen nach ``typ_constants.rest_sign``: positiv = gut.
    rest: float
    #: Ob fuer diesen Monat ueberhaupt ein Budget hinterlegt ist. Ohne diese
    #: Unterscheidung sieht "nie budgetiert" wie "um den vollen Betrag
    #: ueberzogen" aus - und verdraengt beim Sortieren die echte Ueberschreitung.
    has_budget: bool
    is_fix: bool
    is_recurring: bool
    forecast_mode: str

    @property
    def deviation_percent(self) -> float | None:
        """Abweichung vom Budget in Prozent, oder ``None`` ohne Budget."""
        if not self.has_budget or abs(self.budget) < 1e-9:
            return None
        return (self.actual - self.budget) / abs(self.budget) * 100.0

    @property
    def is_over(self) -> bool:
        """True nur bei einer echten Ueberschreitung eines gesetzten Budgets."""
        return self.has_budget and self.rest < 0.0

    @property
    def is_unbudgeted(self) -> bool:
        """Gebucht, aber nie budgetiert - eine eigene Aussage, keine Abweichung."""
        return not self.has_budget and abs(self.actual) > 1e-9


@dataclass(frozen=True)
class SavingsGoalState:
    """Beobachteter Stand eines Sparziels.

    Bewusst nur Beobachtung: Zielbetrag, Stand, Rest und die tatsaechlich
    beobachtete Einzahlungsrate. Die Prognose (wann ist es erreicht, ist es
    auf Kurs) ist ein eigener Schritt und gehoert nicht hierher.
    """

    goal_id: int
    name: str
    category: str | None
    status: str
    target_amount: float
    current_amount: float
    deadline: str | None
    #: Median der Einzahlungen ueber die Monate, in denen eingezahlt wurde.
    observed_monthly_contribution: float
    #: Anzahl dieser Monate - ohne sie ist die Rate oben nicht belastbar.
    contribution_months: int

    @property
    def remaining_amount(self) -> float:
        """Was bis zum Zielbetrag fehlt (nie negativ)."""
        return max(0.0, self.target_amount - self.current_amount)

    @property
    def progress_percent(self) -> float:
        """Fortschritt in Prozent (0.0 ohne Zielbetrag)."""
        if abs(self.target_amount) < 1e-9:
            return 0.0
        return self.current_amount / self.target_amount * 100.0


def _month_key(value: str) -> tuple[int, int]:
    """(Jahr, Monat) aus einem ISO-Datum ``YYYY-MM-DD``."""
    return int(value[0:4]), int(value[5:7])


def _previous_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


class FinanceInsightEngine:
    """Auswertungen ueber den echten Finanzbestand einer geoeffneten DB.

    Die Engine besitzt die Verbindung nicht, sie leiht sie sich - genau wie
    ``BudgetSuggestionEngine``. Damit bleibt sie im verschluesselten
    Datenbankkontext des angemeldeten Kontos und legt nichts daneben ab.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ── Zeitachse ───────────────────────────────────────────────────────

    def booking_months(self) -> list[tuple[int, int]]:
        """Alle Monate mit mindestens einer Buchung, aufsteigend."""
        rows = self.conn.execute(
            "SELECT DISTINCT substr(date,1,7) AS ym FROM tracking ORDER BY ym"
        ).fetchall()
        return [(int(str(r[0])[0:4]), int(str(r[0])[5:7])) for r in rows if r[0]]

    def last_complete_month(self, today: date | None = None) -> tuple[int, int] | None:
        """Juengster Monat mit Buchungen, der nicht mehr laeuft.

        Ein Monat gilt als abgeschlossen, sobald der heutige Tag in einem
        spaeteren Monat liegt. Gibt es nur den laufenden Monat, ist die
        Antwort ``None`` - ehrlicher als ein halber Monat als Vergleichswert.
        """
        heute = today or date.today()
        laufend = (heute.year, heute.month)
        vergangene = [m for m in self.booking_months() if m < laufend]
        return vergangene[-1] if vergangene else None

    def recent_complete_months(
        self, count: int, today: date | None = None
    ) -> list[tuple[int, int]]:
        """Die letzten ``count`` abgeschlossenen Kalendermonate, aufsteigend.

        Bewusst ueber den Kalender und nicht ueber die Buchungsmonate: Ein
        Monat ohne Buchung ist eine Aussage ("da war nichts") und darf im
        Vergleichsfenster nicht stillschweigend durch einen aelteren Monat
        ersetzt werden. Genau daran ist der Budgetvorschlag frueher gestrauchelt.
        """
        if count <= 0:
            return []
        letzter = self.last_complete_month(today)
        if letzter is None:
            return []
        monate: list[tuple[int, int]] = [letzter]
        while len(monate) < count:
            monate.append(_previous_month(*monate[-1]))
        return list(reversed(monate))

    # ── Summen ──────────────────────────────────────────────────────────

    def monthly_totals(
        self, months: list[tuple[int, int]]
    ) -> dict[tuple[int, int], Totals]:
        """Summen je Monat. Monate ohne Buchung stehen mit Nullen drin."""
        gewuenscht = list(dict.fromkeys(months))
        if not gewuenscht:
            return {}

        roh = self._typ_sums_by_month()
        spar = self._savings_flow_by_month()
        ergebnis: dict[tuple[int, int], Totals] = {}
        for monat in gewuenscht:
            summen = roh.get(monat, {})
            deposits, withdrawals = spar.get(monat, (0.0, 0.0))
            ergebnis[monat] = Totals(
                months=1,
                income=float(summen.get(TYP_INCOME, 0.0)),
                # abs auf der Monatssumme: faengt durchgaengig negativ
                # gespeicherte Ausgaben ab, laesst aber eine Rueckerstattung
                # innerhalb des Monats korrekt verrechnen.
                expenses=abs(float(summen.get(TYP_EXPENSES, 0.0))),
                savings_deposits=deposits,
                savings_withdrawals=withdrawals,
            )
        # Monate ohne jede Buchung fehlen in beiden Abzuegen und stehen ueber
        # die Vorgaben oben trotzdem mit Nullen in der Antwort.
        return ergebnis

    def month_totals(self, year: int, month: int) -> Totals:
        """Summen genau eines Monats - auch des laufenden."""
        return self.monthly_totals([(year, month)])[(year, month)]

    def period_totals(self, months: list[tuple[int, int]]) -> Totals:
        """Summen ueber mehrere Monate.

        Beantwortet zugleich "Gesamtausgaben", "Einkommen" und - ueber
        ``surplus`` - den Monatsueberschuss des Zeitraums.
        """
        je_monat = self.monthly_totals(months)
        return Totals(
            months=len(je_monat),
            income=sum(t.income for t in je_monat.values()),
            expenses=sum(t.expenses for t in je_monat.values()),
            savings_deposits=sum(t.savings_deposits for t in je_monat.values()),
            savings_withdrawals=sum(t.savings_withdrawals for t in je_monat.values()),
        )

    # ── Kategorien ──────────────────────────────────────────────────────

    def category_totals(
        self, typ: str, months: list[tuple[int, int]]
    ) -> list[CategoryTotal]:
        """Summen je Kategorie eines Typs, absteigend nach Betrag.

        Der Anteil bezieht sich auf die Summe *dieses* Typs im Zeitraum, nicht
        auf alles Gebuchte: "Restaurant sind 12 % deiner Ausgaben" ist die
        Aussage, die jemand erwartet.
        """
        typ_db = normalize_typ(typ)
        gewuenscht = set(months)
        if not gewuenscht:
            return []

        je_kategorie = self._category_sums_by_month(typ_db)
        attribute = self._category_attributes(typ_db)

        summen: dict[str, float] = {}
        monate: dict[str, int] = {}
        for (monat, kategorie), betrag in je_kategorie.items():
            if monat not in gewuenscht:
                continue
            wert = betrag if is_income(typ_db) else abs(betrag)
            summen[kategorie] = summen.get(kategorie, 0.0) + wert
            if abs(betrag) > 1e-9:
                monate[kategorie] = monate.get(kategorie, 0) + 1

        gesamt = sum(abs(v) for v in summen.values())
        ergebnis: list[CategoryTotal] = []
        for kategorie, betrag in summen.items():
            is_fix, is_recurring, modus = attribute.get(
                kategorie, (False, False, effective_forecast_mode("", False, False))
            )
            ergebnis.append(
                CategoryTotal(
                    typ=typ_db,
                    category=kategorie,
                    amount=betrag,
                    share=(abs(betrag) / gesamt) if gesamt > 1e-9 else 0.0,
                    months_with_bookings=monate.get(kategorie, 0),
                    is_fix=is_fix,
                    is_recurring=is_recurring,
                    forecast_mode=modus,
                )
            )
        ergebnis.sort(key=lambda c: (-abs(c.amount), c.category))
        return ergebnis

    # ── Trends ──────────────────────────────────────────────────────────

    def category_trend(
        self,
        typ: str,
        category: str | None,
        *,
        months_per_window: int = MIN_TREND_MONTHS,
        today: date | None = None,
    ) -> Trend | None:
        """Vergleicht die juengsten ``n`` Monate mit den ``n`` davor.

        ``category=None`` wertet den ganzen Typ aus. Ergebnis ist ``None``,
        wenn das Fenster zu klein ist oder die Buchungshistorie nicht bis
        hinter das aeltere Fenster reicht - ein Trend ueber Monate, die es
        nie gab, waere erfunden.
        """
        fenster = max(int(months_per_window), MIN_TREND_MONTHS)
        alle = self.recent_complete_months(fenster * 2, today=today)
        if len(alle) < fenster * 2:
            return None

        erster = self.booking_months()
        if not erster or erster[0] > alle[0]:
            return None

        typ_db = normalize_typ(typ)
        aelter, juenger = alle[:fenster], alle[fenster:]
        werte_alt = self._series(typ_db, category, aelter)
        werte_neu = self._series(typ_db, category, juenger)

        median_alt = float(median(werte_alt))
        median_neu = float(median(werte_neu))
        return Trend(
            typ=typ_db,
            category=category,
            months_per_window=fenster,
            recent_median=median_neu,
            previous_median=median_alt,
            direction=self._direction(typ_db, median_alt, median_neu),
        )

    @staticmethod
    def _direction(typ_db: str, previous: float, recent: float) -> str:
        """Richtung mit Rauschgrenze.

        "up"/"down" beschreiben die Bewegung der Zahl, nicht ihre Bewertung -
        ob mehr Einkommen gut und mehr Ausgaben schlecht ist, entscheidet
        nicht diese Schicht.
        """
        delta = recent - previous
        if abs(delta) < TREND_MIN_DELTA:
            return DIRECTION_FLAT
        if abs(previous) > 1e-9:
            prozent = abs(delta) / abs(previous) * 100.0
            if prozent < TREND_MIN_PERCENT:
                return DIRECTION_FLAT
        return DIRECTION_UP if delta > 0 else DIRECTION_DOWN

    def _series(
        self, typ_db: str, category: str | None, months: list[tuple[int, int]]
    ) -> list[float]:
        """Monatswerte fuer Trendfenster - fehlende Monate zaehlen als 0."""
        if category is None:
            je_monat = self.monthly_totals(months)
            if is_income(typ_db):
                return [je_monat[m].income for m in months]
            if typ_db == TYP_SAVINGS:
                return [je_monat[m].net_savings for m in months]
            return [je_monat[m].expenses for m in months]

        roh = self._category_sums_by_month(typ_db)
        werte: list[float] = []
        for monat in months:
            betrag = roh.get((monat, category), 0.0)
            werte.append(betrag if is_income(typ_db) else abs(betrag))
        return werte

    # ── Budgetabweichungen ──────────────────────────────────────────────

    def budget_deviations(
        self, year: int, month: int, typ: str | None = None
    ) -> list[BudgetDeviation]:
        """Budget gegen Ist fuer einen Monat, groesste Ueberschreitung zuerst.

        Beruecksichtigt werden Kategorien mit Budget *und* Kategorien, in
        denen ohne Budget gebucht wurde - eine ungeplante Ausgabe fiele bei
        einem reinen Budget-Join heraus, und gerade sie ist erklaerungsbeduerftig.
        Beides bleibt aber getrennt: Budgetierte Kategorien stehen zuerst und
        nach ihrer Abweichung sortiert, die nie budgetierten danach nach Betrag.
        Sonst waere die Liste immer von Kategorien angefuehrt, fuer die schlicht
        kein Budget gepflegt ist.
        """
        typ_db = normalize_typ(typ) if typ else None

        budgets: dict[tuple[str, str], float] = {}
        for row in self.conn.execute(
            "SELECT typ, category, amount FROM budget WHERE year=? AND month=?",
            (int(year), int(month)),
        ):
            budgets[(normalize_typ(str(row[0])), str(row[1]))] = float(row[2] or 0.0)

        ist: dict[tuple[str, str], float] = {}
        for row in self.conn.execute(
            "SELECT typ, category, SUM(amount) FROM tracking "
            "WHERE substr(date,1,7)=? GROUP BY typ, category",
            (f"{int(year):04d}-{int(month):02d}",),
        ):
            ist[(normalize_typ(str(row[0])), str(row[1]))] = float(row[2] or 0.0)

        attribute_je_typ: dict[str, dict[str, tuple[bool, bool, str]]] = {}
        ergebnis: list[BudgetDeviation] = []
        for schluessel in sorted(set(budgets) | set(ist)):
            eintrag_typ, kategorie = schluessel
            if typ_db and eintrag_typ != typ_db:
                continue
            roh = ist.get(schluessel, 0.0)
            actual = roh if is_income(eintrag_typ) else abs(roh)
            has_budget = schluessel in budgets
            budget = budgets.get(schluessel, 0.0)
            if eintrag_typ not in attribute_je_typ:
                attribute_je_typ[eintrag_typ] = self._category_attributes(eintrag_typ)
            is_fix, is_recurring, modus = attribute_je_typ[eintrag_typ].get(
                kategorie, (False, False, effective_forecast_mode("", False, False))
            )
            ergebnis.append(
                BudgetDeviation(
                    year=int(year),
                    month=int(month),
                    typ=eintrag_typ,
                    category=kategorie,
                    budget=budget,
                    actual=actual,
                    rest=rest_sign(eintrag_typ, budget, actual),
                    has_budget=has_budget,
                    is_fix=is_fix,
                    is_recurring=is_recurring,
                    forecast_mode=modus,
                )
            )
        ergebnis.sort(
            key=lambda d: (
                0 if d.has_budget else 1,
                d.rest if d.has_budget else -abs(d.actual),
                d.typ,
                d.category,
            )
        )
        return ergebnis

    # ── Sparziele ───────────────────────────────────────────────────────

    def savings_goal_states(
        self, *, only_active: bool = False
    ) -> list[SavingsGoalState]:
        """Stand aller Sparziele samt beobachteter Einzahlungsrate.

        Die Rate kommt aus den Buchungen, nicht aus ``current_amount``: Ein
        Ziel, das einmal mit einem grossen Betrag angelegt wurde, hat keine
        Rate - und soll auch keine vortaeuschen.
        """
        spalten = {
            str(row[1]) for row in self.conn.execute("PRAGMA table_info(savings_goals)")
        }
        hat_status = "status" in spalten
        auswahl = "id, name, target_amount, current_amount, deadline, category" + (
            ", status" if hat_status else ""
        )
        einzahlungen = self._savings_deposits_by_category_month()

        ergebnis: list[SavingsGoalState] = []
        for row in self.conn.execute(
            f"SELECT {auswahl} FROM savings_goals ORDER BY name"  # nosec B608
        ):
            status = str(row[6]) if hat_status and row[6] else STATUS_SAVING
            if only_active and status != STATUS_SAVING:
                continue
            kategorie = str(row[5]) if row[5] else None
            monatswerte = (
                sorted(einzahlungen.get(kategorie, {}).values()) if kategorie else []
            )
            echte = [w for w in monatswerte if w > 1e-9]
            ergebnis.append(
                SavingsGoalState(
                    goal_id=int(row[0]),
                    name=str(row[1]),
                    category=kategorie,
                    status=status,
                    target_amount=float(row[2] or 0.0),
                    current_amount=float(row[3] or 0.0),
                    deadline=str(row[4]) if row[4] else None,
                    observed_monthly_contribution=(
                        float(median(echte)) if echte else 0.0
                    ),
                    contribution_months=len(echte),
                )
            )
        return ergebnis

    # ── Tags und wiederkehrende Belastungen ─────────────────────────────

    def tag_totals(self, typ: str, months: list[tuple[int, int]]) -> list[TagTotal]:
        """Summen je Tag, absteigend. Eine Buchung kann mehrere Tags tragen.

        Die Betraege addieren sich deshalb bewusst *nicht* zur Gesamtsumme
        auf - ein Tag ist eine Sicht auf die Buchung, keine Aufteilung.
        """
        typ_db = normalize_typ(typ)
        gewuenscht = {f"{j:04d}-{m:02d}" for j, m in months}
        if not gewuenscht:
            return []

        summen: dict[str, float] = {}
        anzahl: dict[str, int] = {}
        for row in self.conn.execute(
            "SELECT substr(t.date,1,7) AS ym, g.name, t.amount "
            "FROM tracking t "
            "JOIN entry_tags et ON et.entry_id = t.id "
            "JOIN tags g ON g.id = et.tag_id "
            "WHERE t.typ = ?",
            (typ_db,),
        ):
            if str(row[0]) not in gewuenscht:
                continue
            name = str(row[1])
            betrag = float(row[2] or 0.0)
            summen[name] = summen.get(name, 0.0) + (
                betrag if is_income(typ_db) else abs(betrag)
            )
            anzahl[name] = anzahl.get(name, 0) + 1

        ergebnis = [
            TagTotal(tag=name, typ=typ_db, amount=betrag, bookings=anzahl[name])
            for name, betrag in summen.items()
        ]
        ergebnis.sort(key=lambda t: (-abs(t.amount), t.tag))
        return ergebnis

    def recurring_commitments(self) -> list[RecurringCommitment]:
        """Die aktiven Daueraufträge - geplante, noch nicht gebuchte Last.

        Getrennt von den Buchungen zu halten ist der Punkt: Was gebucht ist,
        steht in ``tracking``; was regelmaessig kommt, steht hier. Der Coach
        braucht beides und darf es nicht vermischen.
        """
        ergebnis: list[RecurringCommitment] = []
        for row in self.conn.execute(
            "SELECT typ, category, amount, day_of_month, COALESCE(details,'') "
            "FROM recurring_transactions WHERE is_active = 1 "
            "ORDER BY typ, category"
        ):
            typ_db = normalize_typ(str(row[0]))
            betrag = float(row[2] or 0.0)
            ergebnis.append(
                RecurringCommitment(
                    typ=typ_db,
                    category=str(row[1]),
                    amount=betrag if is_income(typ_db) else abs(betrag),
                    day_of_month=int(row[3] or 1),
                    details=str(row[4]),
                )
            )
        return ergebnis

    # ── Datenzugriff ────────────────────────────────────────────────────

    def _typ_sums_by_month(self) -> dict[tuple[int, int], dict[str, float]]:
        """Rohsummen je (Monat, Typ) - ohne Vorzeichenkorrektur."""
        ergebnis: dict[tuple[int, int], dict[str, float]] = {}
        for row in self.conn.execute(
            "SELECT substr(date,1,7) AS ym, typ, SUM(amount) FROM tracking "
            "GROUP BY ym, typ"
        ):
            monat = _month_key(str(row[0]) + "-01")
            ergebnis.setdefault(monat, {})[normalize_typ(str(row[1]))] = float(
                row[2] or 0.0
            )
        return ergebnis

    def _category_sums_by_month(
        self, typ_db: str
    ) -> dict[tuple[tuple[int, int], str], float]:
        """Rohsummen je (Monat, Kategorie) eines Typs."""
        ergebnis: dict[tuple[tuple[int, int], str], float] = {}
        for row in self.conn.execute(
            "SELECT substr(date,1,7) AS ym, category, SUM(amount) FROM tracking "
            "WHERE typ = ? GROUP BY ym, category",
            (typ_db,),
        ):
            monat = _month_key(str(row[0]) + "-01")
            ergebnis[(monat, str(row[1]))] = float(row[2] or 0.0)
        return ergebnis

    def _savings_flow_by_month(self) -> dict[tuple[int, int], tuple[float, float]]:
        """Einzahlungen und Bezuege je Monat, getrennt.

        Fehlt ``savings_action`` (aeltere Datenbank) oder ist sie leer,
        entscheidet das Vorzeichen - dieselbe Regel wie beim Schreiben.
        """
        hat_spalte = self._has_savings_action_column()
        auswahl = "savings_action" if hat_spalte else "NULL"
        ergebnis: dict[tuple[int, int], list[float]] = {}
        for row in self.conn.execute(
            f"SELECT substr(date,1,7) AS ym, amount, {auswahl} "  # nosec B608
            "FROM tracking WHERE typ = ?",
            (TYP_SAVINGS,),
        ):
            monat = _month_key(str(row[0]) + "-01")
            betrag = float(row[1] or 0.0)
            aktion = str(row[2] or "").strip().lower()
            eimer = ergebnis.setdefault(monat, [0.0, 0.0])
            if aktion == ACTION_WITHDRAWAL or (not aktion and betrag < 0):
                eimer[1] += abs(betrag)
            else:
                eimer[0] += abs(betrag)
        return {m: (w[0], w[1]) for m, w in ergebnis.items()}

    def _savings_deposits_by_category_month(
        self,
    ) -> dict[str, dict[tuple[int, int], float]]:
        """Einzahlungen je Sparziel-Kategorie und Monat (ohne Bezuege)."""
        hat_spalte = self._has_savings_action_column()
        auswahl = "savings_action" if hat_spalte else "NULL"
        ergebnis: dict[str, dict[tuple[int, int], float]] = {}
        for row in self.conn.execute(
            f"SELECT substr(date,1,7) AS ym, category, amount, {auswahl} "  # nosec B608
            "FROM tracking WHERE typ = ?",
            (TYP_SAVINGS,),
        ):
            betrag = float(row[2] or 0.0)
            aktion = str(row[3] or "").strip().lower()
            if aktion == ACTION_WITHDRAWAL or (not aktion and betrag < 0):
                continue
            monat = _month_key(str(row[0]) + "-01")
            je_kategorie = ergebnis.setdefault(str(row[1]), {})
            je_kategorie[monat] = je_kategorie.get(monat, 0.0) + abs(betrag)
        return ergebnis

    def _has_savings_action_column(self) -> bool:
        return "savings_action" in {
            str(row[1]) for row in self.conn.execute("PRAGMA table_info(tracking)")
        }

    def _category_attributes(self, typ_db: str) -> dict[str, tuple[bool, bool, str]]:
        """Fixkosten-, Wiederholungs- und Forecast-Attribute je Kategorie."""
        spalten = {
            str(row[1]) for row in self.conn.execute("PRAGMA table_info(categories)")
        }
        hat_modus = "forecast_mode" in spalten
        auswahl = "name, is_fix, is_recurring" + (
            ", forecast_mode" if hat_modus else ", ''"
        )
        ergebnis: dict[str, tuple[bool, bool, str]] = {}
        for row in self.conn.execute(
            f"SELECT {auswahl} FROM categories WHERE typ = ?",  # nosec B608
            (typ_db,),
        ):
            is_fix = bool(row[1])
            is_recurring = bool(row[2])
            ergebnis[str(row[0])] = (
                is_fix,
                is_recurring,
                effective_forecast_mode(row[3], is_fix, is_recurring),
            )
        return ergebnis
