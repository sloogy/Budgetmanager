#!/usr/bin/env python3
"""Reproduzierbares Performance-Gate mit einer grossen realistischen SQLite-DB."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model.budget_overview_model import BudgetOverviewModel
from model.migrations import migrate_all
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS


def _timed(label: str, fn):
    started = time.perf_counter()
    value = fn()
    return label, time.perf_counter() - started, value


def _seed(conn: sqlite3.Connection, rows: int) -> dict[str, object]:
    types = (TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS)
    categories: list[tuple[str, str]] = []
    for idx in range(100):
        typ = types[idx % len(types)]
        categories.append((typ, f"{typ[:3]} Kategorie {idx + 1:03d}"))

    with conn:
        conn.executemany(
            "INSERT OR IGNORE INTO categories("
            "typ,name,is_fix,is_recurring,recurring_day,parent_id,"
            "sort_order,forecast_mode) VALUES(?,?,?,?,?,?,?,?)",
            [
                (typ, name, int(i % 7 == 0), int(i % 5 == 0), 25, None, i, "auto")
                for i, (typ, name) in enumerate(categories)
            ],
        )
        budget_rows = []
        for year in range(2017, 2027):
            for month in range(1, 13):
                for idx, (typ, name) in enumerate(categories):
                    amount = 2500.0 if typ == TYP_INCOME else 80.0 + (idx % 20) * 15.0
                    budget_rows.append((year, month, typ, name, amount))
        conn.executemany(
            "INSERT OR REPLACE INTO budget("
            "year,month,typ,category,amount) VALUES(?,?,?,?,?)",
            budget_rows,
        )

        start = date(2017, 1, 1)
        batch = []
        for idx in range(rows):
            typ, category = categories[idx % len(categories)]
            day = start + timedelta(days=idx % 3652)
            amount = (
                3000.0 + (idx % 900) if typ == TYP_INCOME else 5.0 + (idx % 500) / 3.0
            )
            batch.append(
                (
                    day.isoformat(),
                    typ,
                    category,
                    amount,
                    f"Benchmark {idx % 200}",
                    "manual",
                )
            )
            if len(batch) >= 5000:
                conn.executemany(
                    "INSERT INTO tracking("
                    "date,typ,category,amount,details,source) "
                    "VALUES(?,?,?,?,?,?)",
                    batch,
                )
                batch.clear()
        if batch:
            conn.executemany(
                "INSERT INTO tracking("
                "date,typ,category,amount,details,source) "
                "VALUES(?,?,?,?,?,?)",
                batch,
            )
        conn.execute("ANALYZE")
    return {
        "tracking_rows": rows,
        "budget_rows": len(budget_rows),
        "categories": len(categories),
    }


def run_benchmark(rows: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="budgetmanager_perf_") as tmp:
        db_path = Path(tmp) / "performance.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        migrate_all(conn, str(db_path), str(Path(tmp) / "backups"))

        _, seed_seconds, seeded = _timed("seed", lambda: _seed(conn, rows))
        tracking = TrackingModel(conn)
        overview = BudgetOverviewModel(conn)
        timings: dict[str, float] = {}
        result_sizes: dict[str, int] = {}

        label, elapsed, value = _timed(
            "tracking_year_filter", lambda: tracking.list_filtered(year=2026)
        )
        timings[label] = elapsed
        result_sizes[label] = len(value)

        label, elapsed, value = _timed(
            "tracking_combined_filter",
            lambda: tracking.list_filtered(
                typ=TYP_EXPENSES,
                categories=[
                    "Aus Kategorie 001",
                    "Aus Kategorie 004",
                    "Aus Kategorie 007",
                ],
                date_from="2025-01-01",
                date_to="2026-12-31",
                search_text="Benchmark",
            ),
        )
        timings[label] = elapsed
        result_sizes[label] = len(value)

        label, elapsed, value = _timed(
            "overview_full_year", lambda: overview.get_monthly_overview(2026)
        )
        timings[label] = elapsed
        result_sizes[label] = len(value)

        label, elapsed, value = _timed(
            "category_carryover",
            lambda: overview.get_category_carryover_view(2026, 7, TYP_EXPENSES),
        )
        timings[label] = elapsed
        result_sizes[label] = len(value)

        label, elapsed, value = _timed(
            "database_quick_check",
            lambda: conn.execute("PRAGMA quick_check(1)").fetchone(),
        )
        timings[label] = elapsed
        result_sizes[label] = 1 if value else 0

        conn.close()
        return {
            "rows": rows,
            "seed_seconds": round(seed_seconds, 4),
            "database_bytes": db_path.stat().st_size,
            "seeded": seeded,
            "timings_seconds": {k: round(v, 4) for k, v in timings.items()},
            "result_sizes": result_sizes,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=50_000)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path("audit_artifacts/performance_gate.json"),
    )
    parser.add_argument("--max-year-filter", type=float, default=2.5)
    parser.add_argument("--max-combined-filter", type=float, default=1.5)
    parser.add_argument("--max-overview", type=float, default=2.5)
    parser.add_argument("--max-carryover", type=float, default=2.5)
    parser.add_argument("--max-quick-check", type=float, default=2.0)
    args = parser.parse_args()
    if args.rows < 1_000 or args.rows > 1_000_000:
        raise SystemExit("--rows muss zwischen 1000 und 1000000 liegen")

    result = run_benchmark(args.rows)
    limits = {
        "tracking_year_filter": args.max_year_filter,
        "tracking_combined_filter": args.max_combined_filter,
        "overview_full_year": args.max_overview,
        "category_carryover": args.max_carryover,
        "database_quick_check": args.max_quick_check,
    }
    errors = [
        f"{name}: {result['timings_seconds'][name]:.4f}s > {limit:.4f}s"
        for name, limit in limits.items()
        if float(result["timings_seconds"][name]) > limit
    ]
    result["limits_seconds"] = limits
    result["passed"] = not errors
    result["errors"] = errors
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if errors:
        print("Performance-Gate FEHLGESCHLAGEN")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Performance-Gate BESTANDEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
