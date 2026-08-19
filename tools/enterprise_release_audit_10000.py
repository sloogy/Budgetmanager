#!/usr/bin/env python3
"""Reproduzierbarer Enterprise-Release-Audit mit 10.000 Zustands-Loops.

Im Gegensatz zu statischen 1000er-Scans erzeugt dieser Audit pro Loop einen
anderen, deterministisch geseedeten Datenzustand. Zehn Themen werden gleichmäßig
abgedeckt: Tags, Undo/Redo, Buchungsquelle, Sparziele, Filter, Kategorie-Rename,
Jahreskopie, wiederkehrende Termine, Update-ZIP-Sicherheit und SQLite-Integrität.
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.budget_model import BudgetModel  # noqa: E402
from model.budget_warnings_model_extended import (  # noqa: E402
    BudgetWarningsModelExtended,
)
from model.category_model import CategoryModel  # noqa: E402
from model.favorites_model import FavoritesModel  # noqa: E402
from model.migrations import migrate_all  # noqa: E402
from model.recurring_transactions_model import (  # noqa: E402
    RecurringTransactionsModel,
)
from model.savings_goals_model import (  # noqa: E402
    SavingsGoalBoundsError,
    SavingsGoalsModel,
)
from model.tags_model import TagsModel  # noqa: E402
from model.tracking_model import TrackingModel  # noqa: E402
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS  # noqa: E402
from updater.common import safe_extract_zip  # noqa: E402

_TEMPLATE: sqlite3.Connection | None = None


def _template() -> sqlite3.Connection:
    global _TEMPLATE
    if _TEMPLATE is None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        migrate_all(conn)
        _TEMPLATE = conn
    return _TEMPLATE


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _template().backup(conn)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _tag_ids(tags: TagsModel, entry_id: int) -> set[int]:
    return {int(row["id"]) for row in tags.get_tags_for_entry(entry_id)}


def scenario_tag_switch(rng: random.Random) -> int:
    conn = _conn()
    categories = CategoryModel(conn)
    tracking = TrackingModel(conn)
    tags = TagsModel(conn)
    old_id = categories.create(TYP_EXPENSES, "Alt")
    new_id = categories.create(TYP_EXPENSES, "Neu")
    old_fixed = tags.create("Alt fix")
    shared_fixed = tags.create("Gemeinsam")
    new_fixed = tags.create("Neu fix")
    manual = tags.create("Manuell")
    tags.set_category_tags(old_id, [old_fixed, shared_fixed])
    tags.set_category_tags(new_id, [new_fixed, shared_fixed])
    entry_id = tracking.add(date(2026, 1, 1), TYP_EXPENSES, "Alt", 10, "")
    tags.set_entry_tags(entry_id, [manual])
    tracking.update(
        entry_id,
        date(2026, 1, 2),
        TYP_EXPENSES,
        "Neu",
        round(rng.uniform(1, 500), 2),
        "",
    )
    assert _tag_ids(tags, entry_id) == {new_fixed, shared_fixed, manual}
    conn.close()
    return 1


def scenario_tag_undo_lifecycle(rng: random.Random) -> int:
    conn = _conn()
    categories = CategoryModel(conn)
    tracking = TrackingModel(conn)
    tags = TagsModel(conn)
    category_id = categories.create(TYP_EXPENSES, "Essen")
    fixed = tags.create("Fix")
    manual = tags.create("Manuell")
    tags.set_category_tags(category_id, [fixed])
    entry_id = tracking.add(
        date(2026, rng.randint(1, 12), rng.randint(1, 28)),
        TYP_EXPENSES,
        "Essen",
        round(rng.uniform(1, 200), 2),
        "",
    )
    tags.set_entry_tags(entry_id, [manual])
    expected = {fixed, manual}
    tracking.delete(entry_id)
    assert tracking.undo.undo()
    assert _tag_ids(tags, entry_id) == expected
    assert tracking.undo.redo()
    assert not conn.execute("SELECT 1 FROM tracking WHERE id=?", (entry_id,)).fetchone()
    assert tracking.undo.undo()
    assert _tag_ids(tags, entry_id) == expected
    conn.close()
    return 4


def scenario_source_roundtrip(rng: random.Random) -> int:
    conn = _conn()
    CategoryModel(conn).create(TYP_EXPENSES, "Miete")
    tracking = TrackingModel(conn)
    source = rng.choice(["manual", "auto_fixcost", "auto_recurring", "auto_optional"])
    entry_id = tracking.add(
        date.today(), TYP_EXPENSES, "Miete", 1500, "", source=source
    )
    readers = (
        tracking.list_all_sorted,
        lambda: tracking.list_recent_sorted(2),
        lambda: tracking.list_filtered(category="Miete"),
        lambda: tracking.last_n_by_abs_amount(5),
    )
    for reader in readers:
        row = next(item for item in reader() if item.id == entry_id)
        assert row.source == source
    conn.close()
    return len(readers)


def scenario_savings_state_machine(rng: random.Random) -> int:
    conn = _conn()
    CategoryModel(conn).create(TYP_SAVINGS, "Ziel")
    goals = SavingsGoalsModel(conn)
    goals.create("Ziel", 1_000_000, current_amount=0, category="Ziel")
    conn.execute("DELETE FROM undo_stack")
    conn.execute("DELETE FROM redo_stack")
    conn.commit()
    tracking = TrackingModel(conn)
    known_ids: list[int] = []
    checks = 0
    for _ in range(12):
        op = rng.choice(("add", "update", "delete", "undo", "redo"))
        try:
            existing = [
                int(row[0])
                for row in conn.execute("SELECT id FROM tracking").fetchall()
            ]
            if op == "add" or not known_ids:
                entry_id = tracking.add(
                    date(2026, rng.randint(1, 12), rng.randint(1, 28)),
                    TYP_SAVINGS,
                    "Ziel",
                    round(rng.uniform(0.01, 500), 2),
                    "",
                )
                known_ids.append(entry_id)
            elif op == "update" and existing:
                entry_id = rng.choice(existing)
                row = conn.execute(
                    "SELECT date FROM tracking WHERE id=?", (entry_id,)
                ).fetchone()
                tracking.update(
                    entry_id,
                    str(row[0]),
                    TYP_SAVINGS,
                    "Ziel",
                    round(rng.uniform(0.01, 500), 2),
                    "",
                )
            elif op == "delete" and existing:
                tracking.delete(rng.choice(existing))
            elif op == "undo":
                tracking.undo.undo()
            elif op == "redo":
                tracking.undo.redo()
        except SavingsGoalBoundsError:
            pass
        tracked = float(
            conn.execute(
                "SELECT COALESCE(SUM(amount),0) FROM tracking "
                "WHERE typ=? AND category='Ziel'",
                (TYP_SAVINGS,),
            ).fetchone()[0]
        )
        goal = goals.get_by_category("Ziel")
        assert goal is not None
        assert abs(float(goal.current_amount) - tracked) < 1e-6
        checks += 1
    conn.close()
    return checks


def scenario_filter_oracle(rng: random.Random) -> int:
    conn = _conn()
    categories = CategoryModel(conn)
    tracking = TrackingModel(conn)
    names = ["A", "B", "C"]
    for name in names:
        categories.create(TYP_EXPENSES, name)
    expected_rows: list[tuple[int, date, str, float, str]] = []
    for _ in range(20):
        booking_date = date(
            rng.choice((2025, 2026, 2027)),
            rng.randint(1, 12),
            rng.randint(1, 28),
        )
        category = rng.choice(names)
        amount = round(rng.uniform(-500, 500), 2)
        details = rng.choice(("foo", "bar", "baz", ""))
        entry_id = tracking.add(booking_date, TYP_EXPENSES, category, amount, details)
        expected_rows.append((entry_id, booking_date, category, amount, details))
    year = rng.choice((2025, 2026, 2027))
    category = rng.choice(names)
    min_amount = rng.choice((None, 50.0, 100.0))
    max_amount = rng.choice((None, 200.0, 400.0))
    search = rng.choice((None, "foo", "a"))
    actual = {
        row.id
        for row in tracking.list_filtered(
            typ=TYP_EXPENSES,
            category=category,
            year=year,
            min_amount=min_amount,
            max_amount=max_amount,
            search_text=search,
        )
    }
    expected: set[int] = set()
    for entry_id, booking_date, row_category, amount, details in expected_rows:
        matches = row_category == category and booking_date.year == year
        if min_amount is not None:
            matches = matches and abs(amount) >= min_amount
        if max_amount is not None:
            matches = matches and abs(amount) <= max_amount
        if search:
            needle = search.casefold()
            matches = matches and (
                needle in details.casefold() or needle in row_category.casefold()
            )
        if matches:
            expected.add(entry_id)
    assert actual == expected
    conn.close()
    return len(expected_rows) + 1


def scenario_rename_cascade(rng: random.Random) -> int:
    conn = _conn()
    categories = CategoryModel(conn)
    category_id = categories.create(TYP_EXPENSES, "Alt")
    BudgetModel(conn).set_amount(2026, 1, TYP_EXPENSES, "Alt", 100)
    TrackingModel(conn).add(date(2026, 1, 1), TYP_EXPENSES, "Alt", 10, "")
    FavoritesModel(conn).add(TYP_EXPENSES, "Alt")
    warnings = BudgetWarningsModelExtended(conn)
    warnings.create(2026, 1, TYP_EXPENSES, "Alt", 80)
    warnings.mark_suggestion_accepted(TYP_EXPENSES, "Alt", 2026, 1)
    RecurringTransactionsModel(conn).create_recurring_transaction(
        TYP_EXPENSES, "Alt", 10, "", rng.randint(1, 31), date(2026, 1, 1)
    )
    conn.execute(
        "INSERT INTO tracking_learning_state(typ,category,status,changed_at) "
        "VALUES(?,?,?,datetime('now'))",
        (TYP_EXPENSES, "Alt", "watch"),
    )
    conn.commit()
    tables = (
        "categories",
        "budget",
        "tracking",
        "favorites",
        "budget_warnings",
        "recurring_transactions",
        "suggestion_accepted",
        "tracking_learning_state",
    )

    def assert_name(name: str) -> None:
        for table in tables:
            column = "name" if table == "categories" else "category"
            values = {
                str(row[0])
                for row in conn.execute(
                    f"SELECT {column} FROM {table}"  # nosec B608
                ).fetchall()
            }
            assert values == {name}, (table, values, name)

    categories.rename_and_cascade(
        category_id, typ=TYP_EXPENSES, old_name="Alt", new_name="Neu"
    )
    assert_name("Neu")
    assert categories.undo.undo()
    assert_name("Alt")
    assert categories.undo.redo()
    assert_name("Neu")
    conn.close()
    return len(tables) * 3


def scenario_budget_copy(rng: random.Random) -> int:
    conn = _conn()
    budget = BudgetModel(conn)
    source_year = rng.randint(2020, 2030)
    target_year = source_year + 1
    values: dict[tuple[str, str, int], float] = {}
    for typ, category in (
        (TYP_INCOME, "Lohn"),
        (TYP_EXPENSES, "Miete"),
        (TYP_SAVINGS, "Puffer"),
    ):
        for month in range(1, 13):
            amount = round(rng.uniform(0, 5000), 2)
            budget.set_amount(source_year, month, typ, category, amount)
            values[(typ, category, month)] = amount
    carry = rng.choice((True, False))
    budget.copy_year(source_year, target_year, carry_amounts=carry)
    for (typ, category, month), amount in values.items():
        expected = amount if carry else 0.0
        assert budget.get_amount(target_year, month, typ, category, -1) == expected
    conn.close()
    return len(values)


def scenario_recurring_calendar(rng: random.Random) -> int:
    conn = _conn()
    model = RecurringTransactionsModel(conn)
    day = rng.randint(1, 31)
    transaction_id = model.create_recurring_transaction(
        TYP_EXPENSES,
        "Abo",
        round(rng.uniform(1, 1000), 2),
        "",
        day,
        date(2020, 1, 1),
    )
    transaction = next(
        item
        for item in model.get_all_recurring_transactions()
        if item.id == transaction_id
    )
    for year, month in ((2024, 2), (2025, 2), (2026, 4), (2026, 12)):
        result = model._calculate_booking_date(transaction, date(year, month, 1))
        assert result.year == year and result.month == month
        assert 1 <= result.day <= 31
        assert result.day <= day
    conn.close()
    return 4


def scenario_zip_safety(rng: random.Random) -> int:
    with tempfile.TemporaryDirectory(prefix="bm-audit-") as temp_dir:
        temp = Path(temp_dir)
        good_zip = temp / "good.zip"
        good_out = temp / "good"
        payload = f"loop-{rng.randrange(1_000_000)}"
        with zipfile.ZipFile(good_zip, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("BudgetManager/readme.txt", payload)
        safe_extract_zip(good_zip, good_out)
        assert (good_out / "BudgetManager" / "readme.txt").read_text() == payload

        bad_zip = temp / "bad.zip"
        with zipfile.ZipFile(bad_zip, "w") as archive:
            archive.writestr("../outside.txt", "blocked")
        try:
            safe_extract_zip(bad_zip, temp / "bad")
        except ValueError:
            pass
        else:
            raise AssertionError("Pfad-Traversal wurde nicht abgewiesen")
        assert not (temp / "outside.txt").exists()
    return 3


def scenario_sqlite_integrity(rng: random.Random) -> int:
    conn = _conn()
    categories = CategoryModel(conn)
    tracking = TrackingModel(conn)
    tags = TagsModel(conn)
    category_ids = [categories.create(TYP_EXPENSES, name) for name in ("A", "B", "C")]
    tag_ids = [tags.create(f"Tag {index}") for index in range(3)]
    entry_ids: list[int] = []
    for _ in range(12):
        category_index = rng.randrange(3)
        category = ("A", "B", "C")[category_index]
        if rng.random() < 0.5:
            tags.set_category_tags(
                category_ids[category_index], rng.sample(tag_ids, rng.randint(0, 3))
            )
        entry_id = tracking.add(
            date(2026, rng.randint(1, 12), rng.randint(1, 28)),
            TYP_EXPENSES,
            category,
            round(rng.uniform(0.01, 1000), 2),
            "",
        )
        entry_ids.append(entry_id)
        tags.set_entry_tags(entry_id, rng.sample(tag_ids, rng.randint(0, 3)))
    for entry_id in rng.sample(entry_ids, rng.randint(0, len(entry_ids))):
        tracking.delete(entry_id)
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    orphans = conn.execute(
        "SELECT COUNT(*) FROM entry_tags et "
        "LEFT JOIN tracking t ON t.id=et.entry_id WHERE t.id IS NULL"
    ).fetchone()[0]
    assert int(orphans) == 0
    conn.close()
    return 3


SCENARIOS: tuple[Callable[[random.Random], int], ...] = (
    scenario_tag_switch,
    scenario_tag_undo_lifecycle,
    scenario_source_roundtrip,
    scenario_savings_state_machine,
    scenario_filter_oracle,
    scenario_rename_cascade,
    scenario_budget_copy,
    scenario_recurring_calendar,
    scenario_zip_safety,
    scenario_sqlite_integrity,
)


def run(loop_count: int, seed: int) -> dict:
    rng = random.Random(seed)
    findings: list[dict] = []
    checks = 0
    scenario_counts = {scenario.__name__: 0 for scenario in SCENARIOS}
    for loop in range(1, loop_count + 1):
        scenario = SCENARIOS[(loop - 1) % len(SCENARIOS)]
        scenario_counts[scenario.__name__] += 1
        try:
            checks += int(scenario(rng))
        except Exception as exc:  # noqa: BLE001 - Audit sammelt alle Seeds.
            findings.append(
                {
                    "loop": loop,
                    "scenario": scenario.__name__,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        if loop % 1000 == 0 or loop == loop_count:
            print(
                f"Loop {loop:05d}: checks={checks} findings={len(findings)}",
                flush=True,
            )
    return {
        "status": "PASS" if not findings else "FAIL",
        "loops": loop_count,
        "checks": checks,
        "seed": seed,
        "scenario_counts": scenario_counts,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loops", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260717)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = run(max(1, args.loops), args.seed)
    if args.json_out:
        args.json_out.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        "ENTERPRISE RELEASE AUDIT DONE: "
        f"status={result['status']} loops={result['loops']} "
        f"checks={result['checks']} findings={len(result['findings'])}"
    )
    if result["findings"]:
        print(json.dumps(result["findings"][:20], ensure_ascii=False, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
