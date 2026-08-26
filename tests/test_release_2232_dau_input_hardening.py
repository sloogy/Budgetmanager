"""Regressionstests v2.2.32 – DAU-Fehleingabe-Härtung.

Befund (DAU-Audit): ``float()`` akzeptiert 'inf', 'Infinity', 'nan' und
Overflow-Strings wie '1e400' oder sehr lange Ziffernfolgen. Solche Werte
rutschten durch ``parse_money`` und jede Betrags-Eingabe in die Datenbank und
hätten dort alle Summen, Budget-/Sparziel-Grenzen und Diagramme vergiftet
(inf+x=inf; nan verunreinigt jeden Vergleich).

Fix (mehrschichtig):
1. ``parse_money`` lehnt nicht-endliche Ergebnisse fail-closed ab (Primärabwehr
   an jeder GUI-Eingabe).
2. ``require_finite_amount`` sichert die Datenbank-Schreibgrenze
   (Defense-in-Depth, greift auch bei Excel-Import/Migration).
3. Guards in ``budget_model.set_amount``, ``tracking_model.add`` und
   ``validate_savings_goal_bounds``.
"""

from __future__ import annotations

import math
import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model.budget_model import BudgetModel
from model.migrations import migrate_all
from model.savings_goals_model import (
    SavingsGoalBoundsError,
    SavingsGoalsModel,
    validate_savings_goal_bounds,
)
from model.tracking_model import TrackingModel
from tests.conftest import verbindung_merken
from utils import money
from utils.money import parse_money, require_finite_amount

NON_FINITE_STRINGS = [
    "inf",
    "Inf",
    "INF",
    "Infinity",
    "-inf",
    "nan",
    "NaN",
    "1e400",
    "9" * 400,
]


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate_all(conn)
    return verbindung_merken(conn)


def _german():
    money.set_money_locale(currency="EUR", number_format="german")


# ────────────────────────────────────────────────────────────────
# Schicht 1 – parse_money
# ────────────────────────────────────────────────────────────────


def test_parse_money_rejects_non_finite_strings():
    _german()
    for bad in NON_FINITE_STRINGS:
        try:
            result = parse_money(bad)
        except ValueError:
            continue
        raise AssertionError(
            f"parse_money({bad!r}) lieferte {result!r} statt ValueError"
        )


def test_parse_money_still_accepts_valid_values():
    _german()
    cases = [
        ("1,50", 1.5),
        ("1.234,56", 1234.56),
        ("1'234.50", 1234.5),
        ("-5", -5.0),
        ("+5", 5.0),
        ("", 0.0),
        ("1 000", 1000.0),
        ("1e10", 1e10),  # endliche wiss. Notation bleibt erlaubt
    ]
    for text, expected in cases:
        got = parse_money(text)
        assert math.isfinite(got), f"{text!r} -> nicht endlich"
        assert abs(got - expected) < 1e-9, f"{text!r} -> {got} (erwartet {expected})"


def test_parse_money_result_is_always_finite_for_accepted_input():
    _german()
    for text in ("0", "0,01", "-999999,99", "12.345.678,90"):
        assert math.isfinite(parse_money(text))


# ────────────────────────────────────────────────────────────────
# Schicht 2 – require_finite_amount
# ────────────────────────────────────────────────────────────────


def test_require_finite_amount_rejects_inf_nan():
    for bad in (float("inf"), float("-inf"), float("nan")):
        try:
            require_finite_amount(bad)
        except ValueError:
            continue
        raise AssertionError(f"require_finite_amount({bad!r}) hätte werfen müssen")


def test_require_finite_amount_none_becomes_zero():
    assert require_finite_amount(None) == 0.0


def test_require_finite_amount_passes_finite():
    for good in (0, 5, -3.5, "5", "  7.5  "):
        assert math.isfinite(require_finite_amount(good))


def test_require_finite_amount_rejects_garbage():
    for bad in ("abc", object()):
        try:
            require_finite_amount(bad)
        except ValueError:
            continue
        raise AssertionError(f"require_finite_amount({bad!r}) hätte werfen müssen")


# ────────────────────────────────────────────────────────────────
# Schicht 3 – Modelle an der DB-Schreibgrenze
# ────────────────────────────────────────────────────────────────


def test_budget_model_rejects_non_finite():
    conn = _db()
    bm = BudgetModel(conn)
    for bad in (float("inf"), float("nan")):
        try:
            bm.set_amount(2026, 7, "Ausgaben", "Miete", bad)
        except ValueError:
            continue
        raise AssertionError(f"budget.set_amount({bad!r}) hätte werfen müssen")
    # nichts davon in der DB
    rows = conn.execute("SELECT amount FROM budget").fetchall()
    assert all(math.isfinite(r[0]) for r in rows)
    conn.close()


def test_budget_model_accepts_normal_value():
    conn = _db()
    bm = BudgetModel(conn)
    bm.set_amount(2026, 7, "Ausgaben", "Miete", 800.0)
    val = conn.execute("SELECT amount FROM budget WHERE category='Miete'").fetchone()[0]
    assert val == 800.0
    conn.close()


def test_tracking_model_rejects_non_finite():
    conn = _db()
    tm = TrackingModel(conn)
    for bad in (float("inf"), float("nan")):
        try:
            tm.add(date(2026, 7, 1), "Ausgaben", "Miete", bad, "x")
        except ValueError:
            continue
        raise AssertionError(f"tracking.add({bad!r}) hätte werfen müssen")
    rows = conn.execute("SELECT amount FROM tracking").fetchall()
    assert all(math.isfinite(r[0]) for r in rows)
    conn.close()


def test_tracking_model_accepts_normal_booking():
    conn = _db()
    tm = TrackingModel(conn)
    rid = tm.add(date(2026, 7, 1), "Ausgaben", "Miete", -50.0, "echt")
    assert rid > 0
    conn.close()


def test_savings_goal_bounds_rejects_non_finite_target():
    for bad in (float("inf"), float("nan")):
        try:
            validate_savings_goal_bounds(
                goal_name="T",
                target_amount=bad,
                current_amount=0.0,
                resulting_amount=0.0,
                delta_amount=0.0,
            )
        except SavingsGoalBoundsError:
            continue
        raise AssertionError(f"bounds(target={bad!r}) hätte werfen müssen")


def test_savings_goal_create_rejects_non_finite():
    conn = _db()
    sm = SavingsGoalsModel(conn)
    for bad in (float("inf"), float("nan")):
        try:
            sm.create(name="T", target_amount=bad, current_amount=0)
        except SavingsGoalBoundsError:
            continue
        raise AssertionError(f"create(target={bad!r}) hätte werfen müssen")
    rows = conn.execute("SELECT target_amount FROM savings_goals").fetchall()
    assert all(r[0] is None or math.isfinite(r[0]) for r in rows)
    conn.close()


def test_savings_goal_bounds_error_carries_i18n_key():
    try:
        validate_savings_goal_bounds(
            goal_name="T",
            target_amount=float("inf"),
            current_amount=0.0,
            resulting_amount=0.0,
        )
    except SavingsGoalBoundsError as exc:
        assert exc.message_key == "savings.bounds.not_finite"
    else:
        raise AssertionError("erwartete SavingsGoalBoundsError")


# ────────────────────────────────────────────────────────────────
# End-to-End: kein nicht-endlicher Wert erreicht die DB
# ────────────────────────────────────────────────────────────────


def test_no_non_finite_reaches_db_after_bad_input_storm():
    conn = _db()
    bm = BudgetModel(conn)
    tm = TrackingModel(conn)
    sm = SavingsGoalsModel(conn)
    for bad in (float("inf"), float("-inf"), float("nan")):
        for op in (
            lambda: bm.set_amount(2026, 7, "Ausgaben", "X", bad),
            lambda: tm.add(date(2026, 7, 1), "Ausgaben", "X", bad, "x"),
            lambda: sm.create(name="X", target_amount=bad, current_amount=0),
        ):
            try:
                op()
            except (ValueError, SavingsGoalBoundsError):
                pass
    # trotzdem funktioniert ein echter Durchlauf
    bm.set_amount(2026, 7, "Ausgaben", "Miete", 800.0)
    tm.add(date(2026, 7, 1), "Ausgaben", "Miete", -100.0, "echt")
    for tbl, col in (
        ("budget", "amount"),
        ("tracking", "amount"),
        ("savings_goals", "target_amount"),
        ("savings_goals", "current_amount"),
    ):
        for r in conn.execute(f"SELECT {col} FROM {tbl}").fetchall():  # nosec B608
            assert r[0] is None or math.isfinite(
                float(r[0])
            ), f"{tbl}.{col} nicht endlich"
    conn.close()


def test_i18n_not_finite_key_parity():
    """Der neue Fehlertext existiert in allen drei Sprachen (Hard Rule)."""
    import json

    keys = []
    for lang in ("de", "en", "fr"):
        data = json.loads(
            (ROOT / "locales" / f"{lang}.json").read_text(encoding="utf-8")
        )
        assert "not_finite" in data["savings"]["bounds"], f"{lang}: not_finite fehlt"
        keys.append(data["savings"]["bounds"]["not_finite"])
    assert all(k.strip() for k in keys), "leerer Übersetzungstext"
    # Platzhalter-Parität: {goal_name} in allen Sprachen
    assert all("{goal_name}" in k for k in keys)
