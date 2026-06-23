#!/usr/bin/env python3
"""Deterministischer Tiefen-Audit für releasekritische Budget-Logik.

Der Audit läuft headless gegen In-Memory-Datenbanken und prüft die heiklen
Regeln rund um Forecast, Pot/inkrementelle Fixkosten, Null-Bilanz,
Jahreswechsel, 13. Monatslohn und Kategorie-Kaskaden.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.budget_suggestion_engine import BudgetSuggestionEngine  # noqa: E402
from model.budget_overview_model import BudgetOverviewModel  # noqa: E402
from model.category_model import CategoryModel  # noqa: E402
from model.income_specials import apply_13th_month_salary  # noqa: E402
from model.migrations import migrate_all  # noqa: E402
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS  # noqa: E402
from model.year_copy_rules import (  # noqa: E402
    YearCopyOverride,
    apply_year_copy_pattern,
    distribute_like_previous_year,
)

_TEMPLATE_CONN: sqlite3.Connection | None = None


def _template_conn() -> sqlite3.Connection:
    global _TEMPLATE_CONN
    if _TEMPLATE_CONN is None:
        t = sqlite3.connect(":memory:")
        t.row_factory = sqlite3.Row
        migrate_all(t)
        _TEMPLATE_CONN = t
    return _TEMPLATE_CONN


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    _template_conn().backup(c)
    return c


def _month_back(year: int, month: int, n: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    y, m = year, month
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    return out


def _cat(
    conn: sqlite3.Connection,
    typ: str,
    name: str,
    *,
    is_fix=False,
    is_recurring=False,
    forecast_mode="auto",
) -> int:
    return CategoryModel(conn).create(
        typ,
        name,
        is_fix=is_fix,
        is_recurring=is_recurring,
        recurring_day=25,
        forecast_mode=forecast_mode,
    )


def _budget(
    conn: sqlite3.Connection,
    year: int,
    month: int,
    typ: str,
    category: str,
    amount: float,
) -> None:
    conn.execute(
        """
        INSERT INTO budget(year, month, typ, category, amount)
        VALUES(?,?,?,?,?)
        ON CONFLICT(year, month, typ, category) DO UPDATE SET amount=excluded.amount
        """,
        (int(year), int(month), typ, category, float(amount)),
    )


def _book(
    conn: sqlite3.Connection,
    year: int,
    month: int,
    typ: str,
    category: str,
    amount: float,
) -> None:
    conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details) VALUES(?,?,?,?,?)",
        (f"{year:04d}-{month:02d}-15", typ, category, float(amount), "deep-audit"),
    )


def _install_fake_settings(
    *, zero_balance: bool = True, sign_ratio: float = 0.7
) -> None:
    import settings as settings_module

    class FakeSettings:
        def get(self, key, default=None):
            values = {
                "budget_zero_balance_rule": zero_balance,
                "budget_suggestion_sign_ratio": sign_ratio,
                "budget_surplus_strategy": "savings",
            }
            return values.get(key, default)

    settings_module.Settings = FakeSettings


def scenario_fixed_incremental_covered(rng: random.Random) -> None:
    conn = _conn()
    name = "Versicherung"
    _cat(conn, TYP_EXPENSES, name, is_fix=True, is_recurring=True)
    target = (2027, 7)
    months = _month_back(*target, 7)
    history = _month_back(2027, 6, 6)
    monthly_budget = rng.choice([100, 150, 200, 250, 300])
    for y, m in months:
        _budget(conn, y, m, TYP_EXPENSES, name, monthly_budget)
    # Drei aktive Monate, Gesamt bleibt innerhalb Fensterbudget.
    total_cap = monthly_budget * 6
    each = min(monthly_budget * 1.25, total_cap / 3.0)
    for y, m in history[3:]:
        _book(conn, y, m, TYP_EXPENSES, name, each)
    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        TYP_EXPENSES, name, *target, months_back=6
    )
    assert res is None, "gedeckte inkrementelle Fixkosten dürfen nicht erhöhen"


def scenario_fixed_incremental_undercovered(rng: random.Random) -> None:
    conn = _conn()
    name = "Jahresrechnung"
    _cat(conn, TYP_EXPENSES, name, is_fix=True, is_recurring=True)
    target = (2027, 7)
    months = _month_back(*target, 7)
    history = _month_back(2027, 6, 6)
    monthly_budget = rng.choice([100, 150, 200, 250])
    for y, m in months:
        _budget(conn, y, m, TYP_EXPENSES, name, monthly_budget)
    each = monthly_budget * 3.0
    for y, m in history[3:]:
        _book(conn, y, m, TYP_EXPENSES, name, each)
    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        TYP_EXPENSES, name, *target, months_back=6
    )
    assert (
        res is not None and res.delta > 0
    ), "unterdeckte inkrementelle Fixkosten müssen erhöhen dürfen"


def scenario_pot_partial_and_overuse(rng: random.Random) -> None:
    conn = _conn()
    name = "Franchise"
    _cat(conn, TYP_EXPENSES, name, is_fix=True, is_recurring=False)  # auto => pot
    target = (2027, 7)
    for y, m in _month_back(*target, 7):
        _budget(conn, y, m, TYP_EXPENSES, name, 750)
    for y, m in _month_back(2027, 6, 2):
        _book(conn, y, m, TYP_EXPENSES, name, rng.choice([100, 150, 200]))
    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        TYP_EXPENSES, name, *target, months_back=6
    )
    assert res is None, "Pot-Teilverbrauch unter Topf darf nicht senken/erhöhen"

    _book(conn, 2027, 6, TYP_EXPENSES, name, 900)
    res2 = BudgetSuggestionEngine(conn).compute_category_suggestion(
        TYP_EXPENSES, name, *target, months_back=6
    )
    assert (
        res2 is not None and res2.delta > 0
    ), "Pot-Überverbrauch muss Erhöhungsvorschlag erzeugen"


def scenario_zero_balance_type_guard() -> None:
    _install_fake_settings(zero_balance=True, sign_ratio=0.7)
    conn = _conn()
    _cat(conn, TYP_INCOME, "Lohn")
    _cat(conn, TYP_EXPENSES, "Alltag")
    _cat(conn, TYP_SAVINGS, "Sparen")
    for m in (4, 5, 6, 7):
        _budget(conn, 2027, m, TYP_INCOME, "Lohn", 5000)
        _budget(conn, 2027, m, TYP_EXPENSES, "Alltag", 3000)
        _budget(conn, 2027, m, TYP_SAVINGS, "Sparen", 1000)
    for m in (4, 5, 6):
        _book(conn, 2027, m, TYP_INCOME, "Lohn", 5000)
        _book(conn, 2027, m, TYP_EXPENSES, "Alltag", 3000)
    model = BudgetOverviewModel(conn)
    assert not any(
        s.typ == TYP_SAVINGS and s.direction == "surplus"
        for s in model.get_suggestions(2027, 7, 3)
    )
    assert not any(
        s.typ == TYP_SAVINGS and s.direction == "surplus"
        for s in model.get_type_suggestions(2027, 7, 3)
    )
    bal = model.get_balance_suggestions(2027, 7, 3, enabled=True)
    assert bal and bal[0].typ == TYP_SAVINGS and bal[0].suggested_amount >= 1000


def scenario_year_copy_distribution(rng: random.Random) -> None:
    actual = [0.0] * 12
    active_months = rng.sample(range(12), k=3)
    for idx in active_months:
        actual[idx] = float(rng.choice([100, 200, 300, 500]))
    total = float(rng.choice([600, 900, 1200, 1500]))
    out = distribute_like_previous_year([100.0] * 12, actual, total)
    assert len(out) == 12
    assert round(sum(out), 2) == round(total, 2)
    assert all(v >= 0 for v in out)
    for idx, val in enumerate(actual):
        if val == 0:
            assert out[idx] == 0, "Vorjahresmuster darf keine Nullmonate befüllen"


def scenario_13th_salary(rng: random.Random) -> None:
    conn = _conn()
    month = rng.randint(1, 12)
    amount = float(rng.choice([3000, 5200, 7000]))
    plan = apply_13th_month_salary(conn, year=2028, payout_month=month, amount=amount)
    rows = conn.execute(
        "SELECT month, amount FROM budget WHERE year=2028 AND typ=? AND category=? ORDER BY month",
        (TYP_INCOME, plan.category),
    ).fetchall()
    assert len(rows) == 12
    values = {int(r["month"]): float(r["amount"]) for r in rows}
    assert values[month] == amount
    assert round(sum(values.values()), 2) == amount
    assert all(v == 0.0 for m, v in values.items() if m != month)


def scenario_category_reassign_merge(rng: random.Random) -> None:
    conn = _conn()
    cm = CategoryModel(conn)
    old = cm.create(TYP_EXPENSES, "Alt")
    target = cm.create(TYP_EXPENSES, "Neu")
    old_amt = float(rng.choice([40, 80, 120]))
    new_amt = float(rng.choice([60, 90, 140]))
    _budget(conn, 2028, 6, TYP_EXPENSES, "Alt", old_amt)
    _budget(conn, 2028, 6, TYP_EXPENSES, "Neu", new_amt)
    _book(conn, 2028, 6, TYP_EXPENSES, "Alt", old_amt)
    conn.commit()
    cm.delete_category_safely(old, data_action="reassign", reassign_to_id=target)
    merged = conn.execute(
        "SELECT amount FROM budget WHERE year=2028 AND month=6 AND typ=? AND category='Neu'",
        (TYP_EXPENSES,),
    ).fetchone()[0]
    assert float(merged) == old_amt + new_amt
    assert (
        conn.execute("SELECT COUNT(*) FROM tracking WHERE category='Neu'").fetchone()[0]
        == 1
    )
    assert cm.get_by_id(old) is None


def run(loop_count: int, seed: int) -> dict:
    rng = random.Random(seed)
    scenarios = [
        scenario_fixed_incremental_covered,
        scenario_fixed_incremental_undercovered,
        scenario_pot_partial_and_overuse,
        lambda _rng: scenario_zero_balance_type_guard(),
        scenario_year_copy_distribution,
        scenario_13th_salary,
        scenario_category_reassign_merge,
    ]
    findings: list[dict] = []
    checks = 0
    for i in range(1, loop_count + 1):
        for scenario in scenarios:
            checks += 1
            try:
                scenario(rng)
            except (
                Exception
            ) as exc:  # noqa: BLE001 - Audit sammelt Findings bewusst breit.
                findings.append(
                    {
                        "loop": i,
                        "scenario": getattr(scenario, "__name__", str(scenario)),
                        "error": repr(exc),
                    }
                )
    return {
        "status": "PASS" if not findings else "FAIL",
        "loops": loop_count,
        "checks": checks,
        "seed": seed,
        "findings": findings,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--loops", type=int, default=500)
    ap.add_argument("--seed", type=int, default=2039)
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args()
    result = run(max(1, args.loops), args.seed)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.write_text(text + "\n", encoding="utf-8")
    print(f"BudgetManager Deep Logic Audit: {result['status']}")
    print(f"Loops: {result['loops']}")
    print(f"Checks: {result['checks']}")
    print(f"Findings: {len(result['findings'])}")
    if result["findings"]:
        print(text)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
