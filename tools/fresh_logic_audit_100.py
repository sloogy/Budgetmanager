#!/usr/bin/env python3
"""Frische Logik-Invarianten für v2.2.16+ (neue Blickwinkel, 10 Themen x 10 Loops).

Nicht die bestehenden Audits wiederholen, sondern die Nahtstellen der letzten
Umbauten und bislang ungeprüfte Randfälle der Datenschicht:

 1. edit_source     – tracking.update erhält die Buchungsquelle (source).
 2. edit_tags       – Tags nach Kategorie-Wechsel im Edit: selected ∪ fixed(neu).
 3. savings_switch  – Typwechsel savings<->expenses synchronisiert Sparziele exakt.
 4. savings_guard   – Wechsel AUF savings über Zielgrenze wird VOR Änderung geblockt.
 5. undo_update     – Undo eines Updates stellt ALLE Spalten (inkl. source) wieder her.
 6. recurring_clamp – Fälligkeitstag 29-31 wird in kurzen Monaten geklemmt (Feb!).
 7. update_details  – Leere Details beim Update bleiben leer (kein Auto-Text im Model).
 8. redo_update     – Redo nach Undo(Update) liefert exakt den neuen Stand.
 9. edit_same_cat   – Edit ohne Typ/Kategorie-Änderung lässt Sparziel-Stände unangetastet.
10. tags_idempotent – set_entry_tags ist idempotent und entfernt Entfernte wirklich.
"""
from __future__ import annotations

import calendar
import random
import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.migrations import migrate_all  # noqa: E402
from model.tracking_model import TrackingModel  # noqa: E402
from model.category_model import CategoryModel  # noqa: E402
from model.tags_model import TagsModel  # noqa: E402
from model.savings_goals_model import SavingsGoalsModel  # noqa: E402
from model.undo_redo_model import UndoRedoModel  # noqa: E402
from model.typ_constants import TYP_EXPENSES, TYP_SAVINGS  # noqa: E402

FINDINGS: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        FINDINGS.append(msg)
        print(f"  ❌ {msg}")


def fresh_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    migrate_all(conn)
    return conn


def _entry(conn, row_id):
    return conn.execute("SELECT * FROM tracking WHERE id=?", (int(row_id),)).fetchone()


def t1_edit_source(loop: int) -> None:
    conn = fresh_conn()
    cats = CategoryModel(conn)
    tm = TrackingModel(conn)
    cats.create(TYP_EXPENSES, "Miete", is_fix=True, is_recurring=True)
    rid = tm.add(
        date(2026, 3, 1), TYP_EXPENSES, "Miete", 1500.0, "März", source="auto_fixcost"
    )
    tm.update(rid, date(2026, 3, 2), TYP_EXPENSES, "Miete", 1550.0, "März korr.")
    row = _entry(conn, rid)
    check(
        row["source"] == "auto_fixcost",
        f"[edit_source L{loop}] source verloren: {row['source']!r}",
    )
    conn.close()


def t2_edit_tags(loop: int) -> None:
    conn = fresh_conn()
    cats = CategoryModel(conn)
    tm = TrackingModel(conn)
    tags = TagsModel(conn)
    cats.create(TYP_EXPENSES, "Alt")
    cats.create(TYP_EXPENSES, "Neu")
    t_free = tags.create("frei")
    t_fix = tags.create("fixneu")
    cat_id = next(c.id for c in cats.list(TYP_EXPENSES) if c.name == "Neu")
    tags.set_category_tags(cat_id, [t_fix])
    rid = tm.add(date(2026, 4, 5), TYP_EXPENSES, "Alt", 10.0, "x")
    # Edit wie der QuickAdd-Edit-Pfad: update + set_entry_tags(selected ∪ fixed(neu))
    tm.update(rid, date(2026, 4, 5), TYP_EXPENSES, "Neu", 10.0, "x")
    tags.set_entry_tags(rid, [t_free, t_fix])
    got = sorted(int(t["id"]) for t in tags.get_tags_for_entry(rid))
    check(
        got == sorted([t_free, t_fix]),
        f"[edit_tags L{loop}] {got} != {[t_free, t_fix]}",
    )
    conn.close()


def t3_savings_switch(loop: int) -> None:
    conn = fresh_conn()
    cats = CategoryModel(conn)
    tm = TrackingModel(conn)
    sg = SavingsGoalsModel(conn)
    cats.create(TYP_SAVINGS, "Urlaub")
    cats.create(TYP_EXPENSES, "Sonstiges")
    sg.create("Urlaub", 1000.0, category="Urlaub")
    rid = tm.add(date(2026, 5, 1), TYP_SAVINGS, "Urlaub", 200.0, "s")
    cur0 = float(sg.get_by_category("Urlaub").current_amount)
    check(abs(cur0 - 200.0) < 1e-6, f"[savings_switch L{loop}] Start {cur0} != 200")
    # savings -> expenses: Ziel muss um 200 sinken
    tm.update(rid, date(2026, 5, 1), TYP_EXPENSES, "Sonstiges", 200.0, "s")
    cur1 = float(sg.get_by_category("Urlaub").current_amount)
    check(
        abs(cur1 - 0.0) < 1e-6, f"[savings_switch L{loop}] nach Wechsel weg {cur1} != 0"
    )
    # zurück expenses -> savings
    tm.update(rid, date(2026, 5, 1), TYP_SAVINGS, "Urlaub", 150.0, "s")
    cur2 = float(sg.get_by_category("Urlaub").current_amount)
    check(abs(cur2 - 150.0) < 1e-6, f"[savings_switch L{loop}] zurück {cur2} != 150")
    conn.close()


def t4_savings_guard(loop: int) -> None:
    conn = fresh_conn()
    cats = CategoryModel(conn)
    tm = TrackingModel(conn)
    sg = SavingsGoalsModel(conn)
    from model.savings_goals_model import SavingsGoalBoundsError

    cats.create(TYP_SAVINGS, "Auto")
    cats.create(TYP_EXPENSES, "Rest")
    sg.create("Auto", 100.0, category="Auto")
    rid = tm.add(date(2026, 6, 1), TYP_EXPENSES, "Rest", 500.0, "x")
    before = _entry(conn, rid)
    raised = False
    try:
        tm.update(rid, date(2026, 6, 1), TYP_SAVINGS, "Auto", 500.0, "x")
    except SavingsGoalBoundsError:
        raised = True
    after = _entry(conn, rid)
    check(raised, f"[savings_guard L{loop}] Überbuchung beim Typwechsel nicht geblockt")
    check(
        dict(before) == dict(after),
        f"[savings_guard L{loop}] Eintrag trotz Block verändert",
    )
    cur = float(sg.get_by_category("Auto").current_amount)
    check(abs(cur) < 1e-6, f"[savings_guard L{loop}] Ziel trotz Block bebucht: {cur}")
    conn.close()


def t5_undo_update(loop: int) -> None:
    conn = fresh_conn()
    cats = CategoryModel(conn)
    tm = TrackingModel(conn)
    undo = UndoRedoModel(conn)
    tm.undo = undo
    cats.create(TYP_EXPENSES, "A")
    cats.create(TYP_EXPENSES, "B")
    rid = tm.add(
        date(2026, 7, 1), TYP_EXPENSES, "A", 10.0, "alt", source="auto_recurring"
    )
    old = dict(_entry(conn, rid))
    tm.update(rid, date(2026, 7, 2), TYP_EXPENSES, "B", 20.0, "neu")
    undo.undo()
    back = dict(_entry(conn, rid))
    check(back == old, f"[undo_update L{loop}] Undo unvollständig: {back} != {old}")
    conn.close()


def t6_recurring_clamp(loop: int) -> None:
    # Klemmung 29-31 -> Monatsende (reine Kalenderlogik, wie in _collect_pending)
    for day in (29, 30, 31):
        for y, m in ((2026, 2), (2028, 2), (2026, 4), (2026, 12)):
            last = calendar.monthrange(y, m)[1]
            eff = min(max(day, 1), last)
            d = date(y, m, eff)
            check(
                d.month == m,
                f"[recurring_clamp L{loop}] {day}. in {y}-{m} kippt in Folgemonat",
            )


def t7_update_details(loop: int) -> None:
    conn = fresh_conn()
    cats = CategoryModel(conn)
    tm = TrackingModel(conn)
    cats.create(TYP_EXPENSES, "X")
    rid = tm.add(date(2026, 8, 1), TYP_EXPENSES, "X", 5.0, "voll")
    tm.update(rid, date(2026, 8, 1), TYP_EXPENSES, "X", 5.0, "")
    row = _entry(conn, rid)
    check(
        (row["details"] or "") == "",
        f"[update_details L{loop}] Details nicht leer: {row['details']!r}",
    )
    conn.close()


def t8_redo_update(loop: int) -> None:
    conn = fresh_conn()
    cats = CategoryModel(conn)
    tm = TrackingModel(conn)
    undo = UndoRedoModel(conn)
    tm.undo = undo
    cats.create(TYP_EXPENSES, "A")
    rid = tm.add(date(2026, 9, 1), TYP_EXPENSES, "A", 1.0, "v1")
    tm.update(rid, date(2026, 9, 3), TYP_EXPENSES, "A", 2.0, "v2")
    new = dict(_entry(conn, rid))
    undo.undo()
    undo.redo()
    again = dict(_entry(conn, rid))
    check(again == new, f"[redo_update L{loop}] Redo weicht ab: {again} != {new}")
    conn.close()


def t9_edit_same_cat(loop: int) -> None:
    conn = fresh_conn()
    cats = CategoryModel(conn)
    tm = TrackingModel(conn)
    sg = SavingsGoalsModel(conn)
    cats.create(TYP_SAVINGS, "Puffer")
    sg.create("Puffer", 1000.0, category="Puffer")
    rid = tm.add(date(2026, 10, 1), TYP_SAVINGS, "Puffer", 300.0, "a")
    tm.update(rid, date(2026, 10, 2), TYP_SAVINGS, "Puffer", 300.0, "nur Datum/Text")
    cur = float(sg.get_by_category("Puffer").current_amount)
    check(
        abs(cur - 300.0) < 1e-6, f"[edit_same_cat L{loop}] Stand driftet: {cur} != 300"
    )
    conn.close()


def t10_tags_idempotent(loop: int) -> None:
    conn = fresh_conn()
    cats = CategoryModel(conn)
    tm = TrackingModel(conn)
    tags = TagsModel(conn)
    cats.create(TYP_EXPENSES, "T")
    a = tags.create("a")
    b = tags.create("b")
    c = tags.create("c")
    rid = tm.add(date(2026, 11, 1), TYP_EXPENSES, "T", 1.0, "x")
    tags.set_entry_tags(rid, [a, b])
    tags.set_entry_tags(rid, [a, b])  # idempotent
    tags.set_entry_tags(rid, [b, c])  # a entfernen, c ergänzen
    got = sorted(int(t["id"]) for t in tags.get_tags_for_entry(rid))
    check(got == sorted([b, c]), f"[tags_idempotent L{loop}] {got} != {[b, c]}")
    n = conn.execute(
        "SELECT COUNT(*) FROM entry_tags WHERE entry_id=?", (rid,)
    ).fetchone()[0]
    check(n == 2, f"[tags_idempotent L{loop}] Duplikate in entry_tags: {n}")
    conn.close()


THEMES = [
    t1_edit_source,
    t2_edit_tags,
    t3_savings_switch,
    t4_savings_guard,
    t5_undo_update,
    t6_recurring_clamp,
    t7_update_details,
    t8_redo_update,
    t9_edit_same_cat,
    t10_tags_idempotent,
]


def main() -> int:
    random.seed(226)
    loop = 0
    for i in range(10):
        for theme in THEMES:
            loop += 1
            try:
                theme(loop)
            except Exception as e:  # harte Fehler sind selbst Findings
                FINDINGS.append(
                    f"[{theme.__name__} L{loop}] EXCEPTION {type(e).__name__}: {e}"
                )
                print(f"  💥 {theme.__name__} L{loop}: {type(e).__name__}: {e}")
            if loop % 10 == 0:
                print(f"Loop {loop:03d}: findings={len(FINDINGS)}")
    print(f"\n=== FRESH-LOGIC 100 LOOPS DONE: {len(FINDINGS)} findings ===")
    return 1 if FINDINGS else 0


if __name__ == "__main__":
    raise SystemExit(main())
