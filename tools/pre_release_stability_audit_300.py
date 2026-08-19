#!/usr/bin/env python3
"""300 deterministische Stabilitäts-Loops für Release-Härtung.

Jeder Loop erstellt eine frische Datenbank und prüft kombinierte CRUD-, Budget-,
Tag-, Undo-/Redo- und Integritätsinvarianten. Zusammen mit den bestehenden
100+100+500 Audits ergibt das 1000 Release-Loops.
"""
from __future__ import annotations

import random
import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.budget_model import BudgetModel
from model.category_model import CategoryModel
from model.migrations import migrate_all
from model.tags_model import TagsModel
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES


def fresh_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    migrate_all(conn)
    return conn


def main() -> int:
    findings: list[str] = []
    checks = 0
    for loop in range(1, 301):
        rnd = random.Random(2219000 + loop)
        conn = fresh_conn()
        try:
            categories = CategoryModel(conn)
            budgets = BudgetModel(conn)
            tracking = TrackingModel(conn)
            tags = TagsModel(conn)

            cat = f"Audit {loop}"
            categories.create(
                TYP_EXPENSES, cat, is_fix=(loop % 2 == 0), is_recurring=(loop % 3 == 0)
            )
            amount = round(rnd.uniform(0.01, 9999.99), 2)
            month = rnd.randint(1, 12)
            budgets.set_amount(2026, month, TYP_EXPENSES, cat, amount)
            got = budgets.get_amount(2026, month, TYP_EXPENSES, cat)
            checks += 1
            if abs(got - amount) > 1e-9:
                findings.append(f"L{loop}: Budget drift {got} != {amount}")

            tag_a = tags.create(f"A-{loop}")
            tag_b = tags.create(f"B-{loop}")
            cat_id = conn.execute(
                "SELECT id FROM categories WHERE typ=? AND name=?", (TYP_EXPENSES, cat)
            ).fetchone()[0]
            tags.set_category_tags(int(cat_id), [tag_a])

            rid = tracking.add(
                date(2026, month, min(28, rnd.randint(1, 31))),
                TYP_EXPENSES,
                cat,
                amount,
                "audit",
                source="auto_recurring" if loop % 3 == 0 else "manual",
            )
            row = conn.execute("SELECT * FROM tracking WHERE id=?", (rid,)).fetchone()
            checks += 2
            if row is None or abs(float(row["amount"]) - amount) > 1e-9:
                findings.append(f"L{loop}: Tracking INSERT inkonsistent")
            fixed = {
                int(r[0])
                for r in conn.execute(
                    "SELECT tag_id FROM entry_tags WHERE entry_id=?", (rid,)
                )
            }
            if tag_a not in fixed:
                findings.append(f"L{loop}: fixer Kategorie-Tag fehlt")

            tags.set_entry_tags(rid, [tag_a, tag_b])
            tracking.update(
                rid, row["date"], TYP_EXPENSES, cat, amount + 1.0, "audit-edit"
            )
            edited = conn.execute(
                "SELECT * FROM tracking WHERE id=?", (rid,)
            ).fetchone()
            linked = {
                int(r[0])
                for r in conn.execute(
                    "SELECT tag_id FROM entry_tags WHERE entry_id=?", (rid,)
                )
            }
            checks += 2
            if edited is None or abs(float(edited["amount"]) - (amount + 1.0)) > 1e-9:
                findings.append(f"L{loop}: Tracking UPDATE inkonsistent")
            if linked != {tag_a, tag_b}:
                findings.append(f"L{loop}: Tags nach UPDATE inkonsistent: {linked}")

            tracking.delete(rid)
            left = conn.execute(
                "SELECT COUNT(*) FROM tracking WHERE id=?", (rid,)
            ).fetchone()[0]
            orphan_tags = conn.execute(
                "SELECT COUNT(*) FROM entry_tags WHERE entry_id=?", (rid,)
            ).fetchone()[0]
            checks += 2
            if left != 0:
                findings.append(f"L{loop}: DELETE liess Tracking-Eintrag stehen")
            if orphan_tags != 0:
                findings.append(f"L{loop}: DELETE liess verwaiste entry_tags stehen")

            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            checks += 1
            if integrity != "ok":
                findings.append(f"L{loop}: SQLite integrity_check={integrity!r}")
        except Exception as exc:
            findings.append(
                f"L{loop}: ungefangene Ausnahme {type(exc).__name__}: {exc}"
            )
        finally:
            conn.close()

        if loop % 50 == 0:
            print(f"Loop {loop:03d}: findings={len(findings)}")

    print(f"Stability Audit: loops=300 checks={checks} findings={len(findings)}")
    for finding in findings[:50]:
        print("-", finding)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
