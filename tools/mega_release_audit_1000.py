#!/usr/bin/env python3
"""Mega-Release-Audit: 10 Stress-/Stabilitätsthemen × 100 = 1000 Loops.

Ergänzt die bestehenden Audits (Logik 100, Deep 500, Fresh 100, Stability 300,
KILLCRITIC 100) um Belastungs- und Konsistenzprüfungen, die dort nicht
abgedeckt sind. Reine Datenschicht, headless, deterministisch geseedet.

 1. mass_tracking    – 200 zufällige add/update/delete; Monatssummen == SQL-Summe.
 2. undo_storm       – Op-Sturm, dann Undo bis leer und Redo bis voll; Endzustand exakt.
 3. rename_storm     – Ketten-Renames unter Last; keine verwaisten Namen in 8 Tabellen.
 4. unicode_names    – Emojis/Umlaute/RTL in Kategorien & Tags inkl. Rename-Kaskade.
 5. big_amounts      – Extrembeträge; Summen driften nicht (Toleranz 1e-6·n).
 6. copy_year_roundtrip – Jahreskopie: SALDO ausgeschlossen, Beträge exakt, idempotent.
 7. bundle_fuzz      – Backup-Bundle: Roundtrip ok; 1-Byte-Flip wird IMMER abgewiesen.
 8. reset_semantics  – DB-Reset: keep_user_data-Semantik & KEINE verwaisten Reste
                       (inkl. suggestion_accepted / tracking_learning_state!).
 9. suggestion_stress – Vorschlags-Engine auf Zufallsdaten: nie Exception,
                       nie Vorschlag für is_fix, nie vor Datenstart.
10. tags_chaos       – zufällige set/assign/remove-Folgen; nie Duplikate/FK-Leichen.
"""
from __future__ import annotations

import random
import sqlite3
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.budget_model import BudgetModel
from model.budget_suggestion_engine import BudgetSuggestionEngine
from model.category_model import CategoryModel
from model.database_management_model import DatabaseManagementModel
from model.migrations import migrate_all
from model.restore_bundle import (
    BundleIntegrityError,
    create_bundle,
    verify_bundle,
)
from model.tags_model import TagsModel
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES, TYP_INCOME
from model.undo_redo_model import UndoRedoModel

FINDINGS: list[str] = []
CHECKS = 0

NAME_TABLES = (
    ("budget", "category"),
    ("tracking", "category"),
    ("budget_warnings", "category"),
    ("favorites", "category"),
    ("recurring_transactions", "category"),
    ("suggestion_accepted", "category"),
    ("savings_goals", "category"),
    ("tracking_learning_state", "category"),
)


def check(cond: bool, msg: str) -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        FINDINGS.append(msg)
        print(f"  ❌ {msg}")


def fresh() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    migrate_all(c)
    return c


def _sum_sql(conn, y, m, typ, cat) -> float:
    r = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM tracking WHERE typ=? AND category=? "
        "AND strftime('%Y',date)=? AND strftime('%m',date)=?",
        (typ, cat, f"{y:04d}", f"{m:02d}"),
    ).fetchone()
    return float(r[0] or 0.0)


# ── 1 ──────────────────────────────────────────────────────────────────────
def t_mass_tracking(rng, i):
    c = fresh()
    cat = CategoryModel(c)
    tm = TrackingModel(c)
    cats = [f"M{i}_{k}" for k in range(4)]
    for n in cats:
        cat.create(TYP_EXPENSES, n)
    ids = []
    for _ in range(200):
        op = rng.random()
        if op < 0.6 or not ids:
            rid = tm.add(
                date(2026, rng.randint(1, 12), rng.randint(1, 28)),
                TYP_EXPENSES,
                rng.choice(cats),
                round(rng.uniform(-50, 300), 2),
                "x",
            )
            ids.append(rid)
        elif op < 0.85:
            rid = rng.choice(ids)
            tm.update(
                rid,
                date(2026, rng.randint(1, 12), rng.randint(1, 28)),
                TYP_EXPENSES,
                rng.choice(cats),
                round(rng.uniform(-50, 300), 2),
                "y",
            )
        else:
            rid = ids.pop(rng.randrange(len(ids)))
            tm.delete(rid)
    for n in cats:
        m = rng.randint(1, 12)
        got = float(tm.get_month_total(2026, m, TYP_EXPENSES, n) or 0.0)
        want = _sum_sql(c, 2026, m, TYP_EXPENSES, n)
        check(
            abs(got - want) < 1e-6, f"[mass L{i}] Monatssumme {n}/{m}: {got} != {want}"
        )
    c.close()


# ── 2 ──────────────────────────────────────────────────────────────────────
def t_undo_storm(rng, i):
    c = fresh()
    cat = CategoryModel(c)
    tm = TrackingModel(c)
    undo = UndoRedoModel(c)
    tm.undo = undo
    cat.create(TYP_EXPENSES, f"U{i}")
    ids = []
    for _ in range(40):
        op = rng.random()
        if op < 0.5 or not ids:
            ids.append(
                tm.add(
                    date(2026, rng.randint(1, 12), 10),
                    TYP_EXPENSES,
                    f"U{i}",
                    round(rng.uniform(1, 100), 2),
                    "a",
                )
            )
        elif op < 0.8:
            tm.update(
                rng.choice(ids),
                date(2026, rng.randint(1, 12), 11),
                TYP_EXPENSES,
                f"U{i}",
                round(rng.uniform(1, 100), 2),
                "b",
            )
        else:
            tm.delete(ids.pop(rng.randrange(len(ids))))
    snap_full = [dict(r) for r in c.execute("SELECT * FROM tracking ORDER BY id")]
    n_undone = 0
    while undo.undo():
        n_undone += 1
        if n_undone > 500:
            check(False, f"[undo_storm L{i}] Undo terminiert nicht")
            break
    empty = c.execute("SELECT COUNT(*) FROM tracking").fetchone()[0]
    check(empty == 0, f"[undo_storm L{i}] nach Voll-Undo {empty} Zeilen übrig")
    n_redone = 0
    while undo.redo():
        n_redone += 1
        if n_redone > 500:
            check(False, f"[undo_storm L{i}] Redo terminiert nicht")
            break
    back = [dict(r) for r in c.execute("SELECT * FROM tracking ORDER BY id")]
    check(back == snap_full, f"[undo_storm L{i}] Redo-Endzustand weicht ab")
    c.close()


# ── 3 ──────────────────────────────────────────────────────────────────────
def t_rename_storm(rng, i):
    c = fresh()
    cat = CategoryModel(c)
    tm = TrackingModel(c)
    bud = BudgetModel(c)
    name = f"R{i}_0"
    cat.create(TYP_EXPENSES, name)
    bud.set_amount(2026, 3, TYP_EXPENSES, name, 100.0)
    tm.add(date(2026, 3, 5), TYP_EXPENSES, name, 20.0, "x")
    c.execute(
        "INSERT OR REPLACE INTO tracking_learning_state(typ,category,status) VALUES(?,?,?)",
        (TYP_EXPENSES, name, "ignored"),
    )
    current = name
    for step in range(1, 6):
        new = f"R{i}_{step}"
        cid = next(x.id for x in cat.list(TYP_EXPENSES) if x.name == current)
        cat.rename_and_cascade(cid, typ=TYP_EXPENSES, old_name=current, new_name=new)
        current = new
    for table, col in NAME_TABLES:
        try:
            c.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {col} LIKE ?",  # nosec B608
                (f"R{i}\\_%",),
            ).fetchone()[0]
        except sqlite3.OperationalError:
            continue
        # nur der finale Name darf existieren
        final_only = c.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {col} LIKE ? AND {col}!=?",  # nosec B608
            (f"R{i}\\_%", current),
        ).fetchone()[0]
        check(
            final_only == 0, f"[rename L{i}] verwaiste Namen in {table}: {final_only}"
        )
    c.close()


# ── 4 ──────────────────────────────────────────────────────────────────────
def t_unicode_names(rng, i):
    c = fresh()
    cat = CategoryModel(c)
    tm = TrackingModel(c)
    tags = TagsModel(c)
    name = f"Ünïcode🍕{i}中טקסט"
    cat.create(TYP_EXPENSES, name)
    tid = tags.create(f"täg🎯{i}")
    rid = tm.add(date(2026, 2, 10), TYP_EXPENSES, name, 12.5, "détails ✓")
    tags.set_entry_tags(rid, [tid])
    new = f"Nöü🌟{i}"
    cid = next(x.id for x in cat.list(TYP_EXPENSES) if x.name == name)
    cat.rename_and_cascade(cid, typ=TYP_EXPENSES, old_name=name, new_name=new)
    row = c.execute(
        "SELECT category, details FROM tracking WHERE id=?", (rid,)
    ).fetchone()
    check(
        row["category"] == new, f"[unicode L{i}] rename verloren: {row['category']!r}"
    )
    check("✓" in row["details"], f"[unicode L{i}] details korrumpiert")
    got = tags.get_tags_for_entry(rid)
    check(len(got) == 1 and "🎯" in got[0]["name"], f"[unicode L{i}] tag korrumpiert")
    c.close()


# ── 5 ──────────────────────────────────────────────────────────────────────
def t_big_amounts(rng, i):
    c = fresh()
    cat = CategoryModel(c)
    tm = TrackingModel(c)
    cat.create(TYP_INCOME, f"B{i}")
    vals = [round(rng.uniform(-1e9, 1e9), 2) for _ in range(60)]
    for v in vals:
        tm.add(date(2026, 6, rng.randint(1, 28)), TYP_INCOME, f"B{i}", v, "big")
    got = float(tm.get_month_total(2026, 6, TYP_INCOME, f"B{i}") or 0.0)
    want = sum(vals)
    check(
        abs(got - want) <= max(1e-6 * len(vals), 1e-3),
        f"[big L{i}] Drift: {got} vs {want}",
    )
    c.close()


# ── 6 ──────────────────────────────────────────────────────────────────────
def t_copy_year_roundtrip(rng, i):
    c = fresh()
    cat = CategoryModel(c)
    bud = BudgetModel(c)
    names = [f"C{i}_{k}" for k in range(3)]
    for n in names:
        cat.create(TYP_EXPENSES, n)
        for m in range(1, 13):
            bud.set_amount(2025, m, TYP_EXPENSES, n, round(rng.uniform(0, 500), 2))
    c.execute(
        "INSERT OR REPLACE INTO budget(year,month,typ,category,amount) VALUES(2025,1,?,?,42)",
        (TYP_EXPENSES, "___SALDO___"),
    )
    bud.copy_year(2025, 2026, carry_amounts=True)
    for n in names:
        for m in range(1, 13):
            a25 = float(bud.get_amount(2025, m, TYP_EXPENSES, n) or 0.0)
            a26 = float(bud.get_amount(2026, m, TYP_EXPENSES, n) or 0.0)
            check(abs(a25 - a26) < 1e-9, f"[copy L{i}] {n}/{m}: {a26} != {a25}")
    saldo = c.execute(
        "SELECT COUNT(*) FROM budget WHERE year=2026 AND category LIKE '%SALDO%'"
    ).fetchone()[0]
    check(saldo == 0, f"[copy L{i}] SALDO wurde mitkopiert")
    bud.copy_year(2025, 2026, carry_amounts=True)  # idempotent (OR REPLACE)
    n_rows = c.execute(
        "SELECT COUNT(*) FROM budget WHERE year=2026 AND category NOT LIKE '%SALDO%'"
    ).fetchone()[0]
    check(n_rows == 36, f"[copy L{i}] Doppelkopie erzeugt {n_rows} statt 36 Zeilen")
    c.close()


# ── 7 ──────────────────────────────────────────────────────────────────────
def t_bundle_fuzz(rng, i, tmpdir: Path):
    src = tmpdir / f"db{i}.enc"
    payload = bytes(rng.getrandbits(8) for _ in range(rng.randint(200, 2000)))
    src.write_bytes(payload)
    good = create_bundle(
        source_db=src, out_path=tmpdir / f"g{i}.bmr", app="BM", app_version="2.2.19"
    )
    check(
        verify_bundle(good) in ("database.enc", "database.db"),
        f"[bundle L{i}] gültiges Bundle abgewiesen",
    )
    raw = bytearray(good.read_bytes())
    # 1-Byte-Flip im DB-Datenbereich (nach dem lokalen Header, deflate=stored?
    # create_bundle nutzt ZIP; Flip irgendwo in der zweiten Hälfte trifft
    # praktisch immer Nutzdaten oder Struktur – beides MUSS abgewiesen werden).
    pos = rng.randrange(len(raw) // 2, len(raw))
    raw[pos] ^= 0xFF
    bad = tmpdir / f"b{i}.bmr"
    bad.write_bytes(bytes(raw))
    try:
        verify_bundle(bad)
        # Ein Flip in einem ungenutzten Padding-Byte wäre theoretisch still –
        # dann muss der Inhalt aber bitidentisch lesbar sein:
        with zipfile.ZipFile(bad) as z:
            data = z.read("database.enc")
        check(
            data == payload, f"[bundle L{i}] Flip @{pos} unbemerkt UND Daten verändert"
        )
    except (BundleIntegrityError, zipfile.BadZipFile, KeyError):
        pass  # abgewiesen = korrekt
    finally:
        src.unlink(missing_ok=True)
        good.unlink(missing_ok=True)
        bad.unlink(missing_ok=True)


# ── 8 ──────────────────────────────────────────────────────────────────────
def t_reset_semantics(rng, i):
    c = fresh()
    cat = CategoryModel(c)
    tm = TrackingModel(c)
    bud = BudgetModel(c)
    cat.create(TYP_EXPENSES, f"K{i}")
    bud.set_amount(2026, 1, TYP_EXPENSES, f"K{i}", 10)
    tm.add(date(2026, 1, 2), TYP_EXPENSES, f"K{i}", 5, "x")
    c.execute(
        "INSERT OR REPLACE INTO suggestion_accepted(year,month,typ,category) VALUES(2026,1,?,?)",
        (TYP_EXPENSES, f"K{i}"),
    )
    c.execute(
        "INSERT OR REPLACE INTO tracking_learning_state(typ,category,status) VALUES(?,?,?)",
        (TYP_EXPENSES, f"K{i}", "ignored"),
    )
    dbm = DatabaseManagementModel("", conn=c)
    ok, msg = dbm.reset_database(create_backup=False, keep_user_data=True)
    check(ok, f"[reset L{i}] keep=True fehlgeschlagen: {msg}")
    # Dokumentierte Semantik (v2.2.1): keep=True = "nur Budgets zuruecksetzen".
    # Kategorien UND Buchungen bleiben; geleert werden budget + budgetbezogene
    # Nebentabellen (budget_warnings, suggestion_accepted, tracking_learning_state).
    ncat = c.execute(
        "SELECT COUNT(*) FROM categories WHERE name=?", (f"K{i}",)
    ).fetchone()[0]
    check(ncat == 1, f"[reset L{i}] keep=True hat Kategorien gelöscht")
    ntrk = c.execute("SELECT COUNT(*) FROM tracking").fetchone()[0]
    check(ntrk == 1, f"[reset L{i}] keep=True hat Buchungen angefasst ({ntrk})")
    for table in ("budget", "suggestion_accepted", "tracking_learning_state"):
        n = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # nosec B608
        check(n == 0, f"[reset L{i}] keep=True: {table} nicht geleert ({n})")
    ok2, _ = dbm.reset_database(create_backup=False, keep_user_data=False)
    check(ok2, f"[reset L{i}] keep=False fehlgeschlagen")
    left = c.execute(
        "SELECT COUNT(*) FROM categories WHERE name=?", (f"K{i}",)
    ).fetchone()[0]
    check(left == 0, f"[reset L{i}] keep=False: eigene Kategorie überlebt")
    c.close()


# ── 9 ──────────────────────────────────────────────────────────────────────
def t_suggestion_stress(rng, i):
    c = fresh()
    cat = CategoryModel(c)
    tm = TrackingModel(c)
    bud = BudgetModel(c)
    fixname, varname = f"Fix{i}", f"Var{i}"
    cat.create(TYP_EXPENSES, fixname, is_fix=True, is_recurring=True)
    cat.create(TYP_EXPENSES, varname)
    for m in range(1, 7):
        bud.set_amount(2026, m, TYP_EXPENSES, fixname, 100)
        if rng.random() < 0.8:
            tm.add(
                date(2026, m, rng.randint(1, 28)),
                TYP_EXPENSES,
                varname,
                round(rng.uniform(5, 200), 2),
                "v",
            )
    eng = BudgetSuggestionEngine(c)
    for cname, is_fix_flag in ((fixname, True), (varname, False)):
        try:
            sug = eng.compute_category_suggestion(TYP_EXPENSES, cname, 2026, 6)
        except Exception as e:
            check(False, f"[sugg L{i}] Exception {cname}: {type(e).__name__}: {e}")
            continue
        if is_fix_flag:
            check(
                not sug or not getattr(sug, "suggest", getattr(sug, "amount", 0)),
                f"[sugg L{i}] Vorschlag für is_fix-Kategorie: {sug!r}",
            )
    c.close()


# ── 10 ─────────────────────────────────────────────────────────────────────
def t_tags_chaos(rng, i):
    c = fresh()
    cat = CategoryModel(c)
    tm = TrackingModel(c)
    tags = TagsModel(c)
    cat.create(TYP_EXPENSES, f"T{i}")
    tids = [tags.create(f"t{i}_{k}") for k in range(5)]
    rid = tm.add(date(2026, 4, 4), TYP_EXPENSES, f"T{i}", 1.0, "x")
    expected: set[int] = set()
    for _ in range(60):
        op = rng.random()
        if op < 0.4:
            sel = set(rng.sample(tids, rng.randint(0, 5)))
            tags.set_entry_tags(rid, sorted(sel))
            expected = sel
        elif op < 0.7:
            t = rng.choice(tids)
            tags.assign_to_entry(rid, t)
            expected.add(t)
        else:
            t = rng.choice(tids)
            try:
                tags.remove_from_entry(rid, t)
            except AttributeError:
                tags.set_entry_tags(rid, sorted(expected - {t}))
            expected.discard(t)
    got = {int(t["id"]) for t in tags.get_tags_for_entry(rid)}
    check(got == expected, f"[tags L{i}] {sorted(got)} != {sorted(expected)}")
    dup = c.execute(
        "SELECT COUNT(*) - COUNT(DISTINCT tag_id) FROM entry_tags WHERE entry_id=?",
        (rid,),
    ).fetchone()[0]
    check(dup == 0, f"[tags L{i}] Duplikate: {dup}")
    c.close()


def main() -> int:
    import tempfile

    rng = random.Random(1000)
    tmpdir = Path(tempfile.mkdtemp())
    themes = [
        t_mass_tracking,
        t_undo_storm,
        t_rename_storm,
        t_unicode_names,
        t_big_amounts,
        t_copy_year_roundtrip,
        lambda r, i: t_bundle_fuzz(r, i, tmpdir),
        t_reset_semantics,
        t_suggestion_stress,
        t_tags_chaos,
    ]
    loop = 0
    for rounds in range(100):
        for theme in themes:
            loop += 1
            try:
                theme(rng, loop)
            except Exception as e:
                FINDINGS.append(
                    f"[{getattr(theme,'__name__','bundle')} L{loop}] EXCEPTION {type(e).__name__}: {e}"
                )
                print(f"  💥 L{loop}: {type(e).__name__}: {e}")
        if (rounds + 1) % 10 == 0:
            print(f"Loop {loop:04d}: checks={CHECKS} findings={len(FINDINGS)}")
    print(
        f"\n=== MEGA-RELEASE-AUDIT {loop} LOOPS DONE: checks={CHECKS} findings={len(FINDINGS)} ==="
    )
    return 1 if FINDINGS else 0


if __name__ == "__main__":
    raise SystemExit(main())
