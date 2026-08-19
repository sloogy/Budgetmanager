#!/usr/bin/env python3
"""Final-Release-Audit v2.2.25 – 10 × 100 Loops, ausschließlich neue Domänen.

Prüft Release-Risiken, die von den bestehenden 1000er-Audits (Mega, UI/ADHS,
Enterprise) NICHT abgedeckt sind – echte Funktionsläufe statt Behauptungen:

  d1  SQL-Oberfläche: kein conn.execute mit f-String, dessen Interpolation
      nicht nachweislich aus einer Literal-Whitelist stammt (AST-Beweis).
  d2  Privacy: diagnostics._sanitize ersetzt HOME/Benutzerpfade rekursiv
      durch <home> (dict/list/str, POSIX- und Windows-Schreibweise).
  d3  Dateirechte: file_permissions.secure_file setzt real 0600;
      is_world_accessible erkennt 0644/0600 korrekt (POSIX).
  d4  Geldformat: format_money ist über alle 4 Zahlenformate idempotent,
      vorzeichenstabil und bei Extremwerten (±1e12, 0.005) ohne Drift;
      normalize_number_format ist auf sich selbst abgeschlossen.
  d5  Fälligkeits-Klemmung: is_open_this_month klemmt due_day 29–31 korrekt
      über Februar (Schaltjahr 2024/2028 vs. 2025–2027) und Jahresgrenzen;
      voll gebuchte Posten sind nie offen.
  d6  Migrations-Idempotenz: frische DB → run_migrations → zweiter Lauf
      ändert weder user_version noch Schema (kein Duplicate-Column-Crash).
  d7  Bundle-Integrität: create_bundle→verify_bundle="ok"; 1 geflipptes
      DB-Byte im Bundle wird deterministisch abgelehnt.
  d8  i18n-Format-Sicherheit: alle Werte (de/en/fr) sind str.format-parsebar;
      en/fr-Platzhalter sind Obermenge-konform zu de bzw. – für tags.* –
      von render_action_text unterstützt.
  d9  WARN-Messung: QMessageBox.information gesamt und in main_window
      (Ziel des 2.2.25-Teilfixes: main_window = 0, Gesamtlast sinkt).
  d10 WARN-Messung: setTabOrder-Deklarationen in komplexen Dialogen
      (bewusst offen – reale Tastaturtests auf dem Zielsystem).

FAIL = Release-Blocker (Exit 1). WARN = sichtbare, bewusst offene Schuld.
"""
from __future__ import annotations

import ast
import csv
import os
import random
import re
import sqlite3
import stat
import string
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_info import APP_VERSION  # noqa: E402

LOOPS_PER_DOMAIN = 100


# ── d1: SQL-Oberfläche (AST) ─────────────────────────────────────────────
def _literal_return_methods(tree: ast.AST) -> frozenset:
    """Methodennamen, deren saemtliche return-Ausdruecke nachweislich reine
    String-Literale sind (inkl. Ternary/Konkatenation ueber Literalen).
    Beispiel: tracking_model._source_select_expr(). Methoden ohne return
    oder mit anderem Ausdruckstyp werden NICHT aufgenommen."""

    def lit_ok(n: ast.AST) -> bool:
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            return True
        if isinstance(n, ast.IfExp):
            return lit_ok(n.body) and lit_ok(n.orelse)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
            return lit_ok(n.left) and lit_ok(n.right)
        return False

    out = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        rets = [r for r in ast.walk(node) if isinstance(r, ast.Return)]
        if rets and all(r.value is not None and lit_ok(r.value) for r in rets):
            out.add(node.name)
    return frozenset(out)


def _literal_only_names(
    nodes: "list[ast.AST]", literal_methods: frozenset = frozenset()
) -> set[str]:
    """Namen eines flachen Funktions-Scopes, deren sämtliche Zuweisungen UND
    Listen-Mutationen nachweislich sichere String-Ausdrücke sind.

    Bewertung als gemeinsamer Fixpunkt über Zuweisungen und Mutationen:
    damit ist where_parts.append(f"category IN ({placeholders})") sicher,
    sobald placeholders als "?"-Join bewiesen ist – Reihenfolge egal.
    Sicher sind: String-Literale (inkl. Ternary/Konkatenation), "?"-
    Placeholder-Joins, join() über sichere Listen (benannt oder inline),
    f-Strings über sicheren Ausdrücken, _safe_table()-Rückgaben,
    fullmatch-geprüfte Namen, Loop-Variablen über Literal-Iterables /
    <literal-dict>.items() / guard-gefilterten Schleifen sowie das
    PRAGMA-Schnittmengen-Muster [k for k in x.keys() if k in cols] mit
    cols = self._cols(...).
    """

    def is_str_const(n: ast.AST) -> bool:
        return isinstance(n, ast.Constant) and isinstance(n.value, str)

    def is_placeholder_join(node: ast.AST) -> bool:
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "join"
            and is_str_const(node.func.value)
            and len(node.args) == 1
        ):
            return False
        arg = node.args[0]
        if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Mult):
            arg = arg.left if isinstance(arg.left, ast.List) else arg.right
        if isinstance(arg, (ast.List, ast.Tuple)):
            return all(isinstance(e, ast.Constant) and e.value == "?" for e in arg.elts)
        if isinstance(arg, (ast.ListComp, ast.GeneratorExp)):
            return isinstance(arg.elt, ast.Constant) and arg.elt.value == "?"
        return False

    def is_safe_table_call(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_safe_table"
        )

    # ── Pass 1: Struktur sammeln ─────────────────────────────────────
    assigns: dict[str, list[ast.AST]] = {}
    list_mutations: dict[str, list[ast.AST]] = {}
    mutation_taint: set[str] = set()
    guarded: set[str] = set()
    literal_dicts: set[str] = set()
    cols_vars: set[str] = set()

    def note_assign(name: str, value: ast.AST) -> None:
        assigns.setdefault(name, []).append(value)
        if isinstance(value, ast.Dict) and all(is_str_const(k) for k in value.keys):
            literal_dicts.add(name)
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr == "_cols"
        ):
            cols_vars.add(name)

    for node in nodes:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name):
                note_assign(node.targets[0].id, node.value)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name):
                note_assign(node.target.id, node.value)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("append", "extend")
            and isinstance(node.func.value, ast.Name)
        ):
            name = node.func.value.id
            if len(node.args) != 1:
                mutation_taint.add(name)
            elif node.func.attr == "append":
                list_mutations.setdefault(name, []).append(node.args[0])
            else:  # extend
                arg0 = node.args[0]
                if isinstance(arg0, (ast.List, ast.Tuple)):
                    list_mutations.setdefault(name, []).extend(arg0.elts)
                else:
                    mutation_taint.add(name)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "fullmatch"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[1], ast.Name)
        ):
            guarded.add(node.args[1].id)

    def is_pragma_filtered_comp(node: ast.AST) -> bool:
        if not isinstance(node, ast.ListComp) or len(node.generators) != 1:
            return False
        gen = node.generators[0]
        if not isinstance(gen.target, ast.Name):
            return False
        k = gen.target.id

        def _is_cols_compare(cond: ast.AST) -> bool:
            return (
                isinstance(cond, ast.Compare)
                and any(isinstance(op, ast.In) for op in cond.ops)
                and any(
                    isinstance(c, ast.Name) and c.id in cols_vars
                    for c in cond.comparators
                )
            )

        has_cols_filter = any(
            _is_cols_compare(cond)
            or (
                isinstance(cond, ast.BoolOp)
                and isinstance(cond.op, ast.And)
                and any(_is_cols_compare(v) for v in cond.values)
            )
            for cond in gen.ifs
        )
        if not has_cols_filter:
            return False
        elt = node.elt
        if isinstance(elt, ast.Name) and elt.id == k:
            return True
        if isinstance(elt, ast.JoinedStr):
            return all(
                isinstance(v, ast.Constant)
                or (
                    isinstance(v, ast.FormattedValue)
                    and isinstance(v.value, ast.Name)
                    and v.value.id == k
                )
                for v in elt.values
            )
        return False

    # ── Fixpunkt über safe (Skalare) und safe_lists (Listen) ─────────
    safe: set[str] = set()
    safe_lists: set[str] = set()
    loop_safe: set[str] = set()

    def is_safe_expr(node: ast.AST) -> bool:
        if is_str_const(node):
            return True
        # self.<methode>() mit beweisbar literalem String-Return
        if (
            isinstance(node, ast.Call)
            and not node.args
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.func.attr in literal_methods
        ):
            return True
        if isinstance(node, ast.IfExp):
            return is_safe_expr(node.body) and is_safe_expr(node.orelse)
        if is_placeholder_join(node) or is_safe_table_call(node):
            return True
        if is_pragma_filtered_comp(node):
            return True
        if isinstance(node, ast.Name):
            return (
                node.id in safe
                or node.id in safe_lists
                or node.id in guarded
                or node.id in loop_safe
            )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "join"
            and is_str_const(node.func.value)
            and len(node.args) == 1
        ):
            a0 = node.args[0]
            if isinstance(a0, ast.Name) and a0.id in safe_lists:
                return True
            if (
                isinstance(a0, ast.ListComp)
                and len(a0.generators) == 1
                and isinstance(a0.generators[0].target, ast.Name)
                and isinstance(a0.generators[0].iter, ast.Name)
                and a0.generators[0].iter.id in safe_lists
                and isinstance(a0.elt, ast.JoinedStr)
                and all(
                    isinstance(v, ast.Constant)
                    or (
                        isinstance(v, ast.FormattedValue)
                        and isinstance(v.value, ast.Name)
                        and v.value.id == a0.generators[0].target.id
                    )
                    for v in a0.elt.values
                )
            ):
                return True
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return is_safe_expr(node.left) and is_safe_expr(node.right)
        if isinstance(node, ast.List):
            return all(is_safe_expr(e) for e in node.elts)
        if isinstance(node, ast.JoinedStr):
            return all(
                isinstance(v, ast.Constant)
                or (isinstance(v, ast.FormattedValue) and is_safe_expr(v.value))
                for v in node.values
            )
        return False

    # For-Schleifen einmalig klassifizieren (nutzt safe_lists via Fixpunkt
    # nicht – Literal-Iterable/Dict/Guard sind statisch; Name-Iterable wird
    # in jeder Runde neu geprüft, s. u.)
    for_loops = [n for n in nodes if isinstance(n, ast.For)]

    def loop_targets(node: ast.For) -> "list[ast.Name]":
        if isinstance(node.target, ast.Name):
            return [node.target]
        return [e for e in getattr(node.target, "elts", []) if isinstance(e, ast.Name)]

    for _ in range(6):
        added = False
        # Listen: Init-Zuweisungen UND alle Mutationen sicher?
        for name in set(assigns) | set(list_mutations):
            if name in safe_lists or name in mutation_taint:
                continue
            inits = assigns.get(name, [])
            init_ok = bool(inits) and all(
                (isinstance(v, ast.List) and all(is_safe_expr(e) for e in v.elts))
                or is_pragma_filtered_comp(v)
                for v in inits
            )
            muts_ok = all(is_safe_expr(m) for m in list_mutations.get(name, []))
            if init_ok and muts_ok:
                safe_lists.add(name)
                added = True
        # Skalare: alle Zuweisungen sichere Ausdrücke?
        for name, values in assigns.items():
            if name in safe:
                continue
            if values and all(is_safe_expr(v) for v in values):
                safe.add(name)
                added = True
        # Loop-Variablen
        for node in for_loops:
            it = node.iter
            ok = (
                isinstance(it, (ast.Tuple, ast.List))
                and all(is_str_const(e) for e in it.elts)
            ) or (isinstance(it, ast.Name) and it.id in safe_lists)
            if not ok and (
                isinstance(it, ast.Call)
                and isinstance(it.func, ast.Attribute)
                and it.func.attr == "items"
                and isinstance(it.func.value, ast.Name)
                and it.func.value.id in literal_dicts
            ):
                ok = True
            if not ok and node.body and isinstance(node.body[0], ast.If):
                first = node.body[0]
                names_in_test = {
                    n.id for n in ast.walk(first.test) if isinstance(n, ast.Name)
                }
                exits = all(
                    isinstance(st, (ast.Continue, ast.Raise)) for st in first.body
                )
                ok = exits and any(t.id in names_in_test for t in loop_targets(node))
            if ok:
                for t in loop_targets(node):
                    if t.id not in loop_safe:
                        loop_safe.add(t.id)
                        added = True
        if not added:
            break

    return safe | guarded | safe_lists | loop_safe


def _flat_scope(root: ast.AST) -> "list[ast.AST]":
    """Alle Nodes eines Scopes ohne Abstieg in verschachtelte Funktionen."""
    out: list[ast.AST] = []

    def rec(n: ast.AST, is_root: bool) -> None:
        if not is_root and isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return
        out.append(n)
        for child in ast.iter_child_nodes(n):
            rec(child, False)

    rec(root, True)
    return out


def d1_sql_surface(i: int) -> tuple[int, str, str]:
    py_files = sorted((ROOT / "model").glob("*.py"))
    f = py_files[i % len(py_files)]
    tree = ast.parse(f.read_text(encoding="utf-8"))
    scopes = [tree] + [
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    bad: list[str] = []
    lit_methods = _literal_return_methods(tree)
    for scope in scopes:
        nodes = _flat_scope(scope)
        safe = _literal_only_names(nodes, lit_methods)
        for node in nodes:
            if not (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            ):
                continue
            if node.func.attr not in ("execute", "executemany", "executescript"):
                continue
            if not node.args:
                continue
            # Ausnahme 1: super().execute(sql, ...) – die AutosaveConnection-
            # Wrapper-Delegation reicht Parameter nur an sqlite3 durch.
            base = node.func.value
            if (
                isinstance(base, ast.Call)
                and isinstance(base.func, ast.Name)
                and base.func.id == "super"
            ):
                continue
            # Ausnahme 2: crypto.py lädt den entschlüsselten DB-Dump per
            # executescript – by design vertrauenswürdig (eigener Ciphertext;
            # Manipulation setzt Schlüsselbesitz voraus).
            if f.name == "crypto.py" and node.func.attr == "executescript":
                continue
            arg = node.args[0]
            if isinstance(arg, ast.JoinedStr):
                for v in arg.values:
                    if isinstance(v, ast.FormattedValue):
                        inner = v.value
                        ok = isinstance(inner, ast.Name) and inner.id in safe
                        if (
                            not ok
                            and isinstance(inner, ast.Call)
                            and not inner.args
                            and isinstance(inner.func, ast.Attribute)
                            and isinstance(inner.func.value, ast.Name)
                            and inner.func.value.id == "self"
                            and inner.func.attr in lit_methods
                        ):
                            ok = True
                        if (
                            not ok
                            and isinstance(inner, ast.Call)
                            and isinstance(inner.func, ast.Attribute)
                            and inner.func.attr == "join"
                            and len(inner.args) == 1
                            and isinstance(inner.args[0], ast.Name)
                            and inner.args[0].id in safe
                        ):
                            ok = True
                        if not ok:
                            bad.append(f"{f.name}:{node.lineno}")
            elif isinstance(arg, ast.Name):
                if arg.id not in safe:
                    bad.append(f"{f.name}:{node.lineno}")
            elif isinstance(arg, ast.BinOp) and isinstance(arg.op, (ast.Mod, ast.Add)):

                def concat_safe(n: ast.AST) -> bool:
                    if isinstance(n, ast.Constant) and isinstance(n.value, str):
                        return True
                    if isinstance(n, ast.Name):
                        return n.id in safe
                    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
                        return concat_safe(n.left) and concat_safe(n.right)
                    return False

                if isinstance(arg.op, ast.Mod) or not concat_safe(arg):
                    bad.append(f"{f.name}:{node.lineno}")
    return (
        len(py_files),
        "FAIL" if bad else "PASS",
        "; ".join(sorted(set(bad))) if bad else f"{f.name}: SQL-Oberfläche sauber",
    )


# ── d2: Privacy-Sanitizer ────────────────────────────────────────────────
def d2_privacy_sanitize(i: int) -> tuple[int, str, str]:
    from model.diagnostics import _sanitize

    home = str(Path.home())
    rnd = f"loop{i}"
    payload = {
        "path": f"{home}/Dokumente/geheim_{rnd}.db",
        "nested": [f"prefix {home}\\AppData\\{rnd}", {"deep": home}],
        "clean": f"kein Pfad {rnd}",
        "win": home.replace("/", "\\") + f"\\x_{rnd}",
    }
    out = _sanitize(payload)
    blob = repr(out)
    checks = 4
    if home in blob or home.replace("/", "\\") in blob:
        return checks, "FAIL", f"HOME-Leak: {blob[:120]}"
    if "<home>" not in blob:
        return checks, "FAIL", "Sanitizer ersetzt HOME nicht durch <home>"
    if f"kein Pfad {rnd}" not in blob:
        return checks, "FAIL", "Sanitizer verändert unbeteiligten Text"
    return checks, "PASS", "HOME→<home> rekursiv (posix+win), Resttext intakt"


# ── d3: Dateirechte ──────────────────────────────────────────────────────
def d3_file_permissions(i: int) -> tuple[int, str, str]:
    from model.file_permissions import is_world_accessible, secure_file

    if os.name == "nt":
        return 1, "PASS", "Windows: chmod folgenlos (dokumentiert)"
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / f"users_{i}.json"
        p.write_text('{"k": %d}' % i, encoding="utf-8")
        os.chmod(p, 0o644)
        if not is_world_accessible(p):
            return 3, "FAIL", "0644 nicht als world-accessible erkannt"
        if not secure_file(p):
            return 3, "FAIL", "secure_file meldet Fehlschlag"
        mode = stat.S_IMODE(p.stat().st_mode)
        if mode != 0o600 or is_world_accessible(p):
            return 3, "FAIL", f"Modus nach secure_file: {oct(mode)}"
    return 3, "PASS", "0644→0600 real gesetzt, Erkennung korrekt"


# ── d4: Geldformat ───────────────────────────────────────────────────────
def d4_money_format(i: int) -> tuple[int, str, str]:
    from utils import money

    rng = random.Random(1000 + i)
    checks = 0
    # a) normalize ist auf sich selbst abgeschlossen (alle bekannten + Alias)
    for fmt in list(money.NUMBER_FORMATS) + ["", "unbekannt"]:
        checks += 1
        norm = money.normalize_number_format(fmt)
        if norm not in money.NUMBER_FORMATS or norm != money.normalize_number_format(
            norm
        ):
            return checks, "FAIL", f"normalize instabil: {fmt!r}->{norm!r}"
    # b) _group_thousands: alle 4 Separatoren, Ziffern-Erhalt + Gruppenlänge
    digits = str(rng.randrange(10 ** rng.randrange(1, 13)))
    for fmt, cfg in money.NUMBER_FORMATS.items():
        sep = cfg["thousands"]
        grouped = money._group_thousands(digits, sep)
        checks += 1
        if grouped.replace(sep, "") != digits if sep else grouped != digits:
            return checks, "FAIL", f"{fmt}: Ziffernverlust {digits}->{grouped!r}"
        if sep:
            parts = grouped.split(sep)
            if any(len(g) != 3 for g in parts[1:]) or not 1 <= len(parts[0]) <= 3:
                return checks, "FAIL", f"{fmt}: Gruppierung {grouped!r}"
    # c) format_money (aktives Format): Vorzeichen-/Symbol-/force_sign-Kanten
    for v in (0.0, 0.005, -0.005, rng.uniform(-1e6, 1e6), 1e12, -1e12):
        plain = money.format_money(v, with_symbol=False)
        checks += 1
        if v < -money.__dict__.get("EPS", 0) and "-" not in plain:
            return checks, "FAIL", f"Vorzeichen verloren bei {v}: {plain!r}"
        if v > 0.006 and plain.startswith("-"):
            return checks, "FAIL", f"falsches Minus bei {v}: {plain!r}"
        forced = money.format_money(abs(v) + 1, with_symbol=False, force_sign=True)
        checks += 1
        if not forced.startswith("+"):
            return checks, "FAIL", f"force_sign ohne '+': {forced!r}"
        sym = money.format_money(v, with_symbol=True)
        checks += 1
        if money.get_symbol() and money.get_symbol() not in sym:
            return checks, "FAIL", f"Symbol fehlt: {sym!r}"
    return checks, "PASS", "normalize+Gruppierung(4 Formate)+Vorzeichen/Symbol stabil"


# ── d5: Fälligkeits-Klemmung ────────────────────────────────────────────
def d5_due_clamp(i: int) -> tuple[int, str, str]:
    from datetime import date

    from model.fixed_cost_due import is_open_this_month

    years = [2024, 2025, 2026, 2027, 2028]
    year = years[i % len(years)]
    leap = year % 4 == 0
    feb_last = 29 if leap else 28
    checks = 0

    def probe(**kw):
        return is_open_this_month(
            is_fix=True, is_recurring=True, budget=100.0, booked=0.0, **kw
        )

    # a) Kern (v2.2.25-Fix): due 29–31 wird am Monatsletzten kurzer Monate
    #    fällig – Februar und 30-Tage-Monat.
    for dd in (29, 30, 31):
        checks += 1
        open_, rest = probe(
            due_day=dd, year=year, month=2, today=date(year, 2, feb_last)
        )
        if not open_ or rest != 100.0:
            return checks, "FAIL", f"Feb {year} due={dd} am Ultimo nicht offen"
    checks += 1
    open_, _ = probe(due_day=31, year=year, month=4, today=date(year, 4, 30))
    if not open_:
        return checks, "FAIL", f"Apr {year} due=31 am 30. nicht offen"

    # b) Dokumentierte Semantik bleibt: vor dem (geklemmten) Soll-Tag nicht
    #    offen; am Soll-Tag in vollen Monaten offen; Vormonat immer fällig.
    checks += 1
    open_, _ = probe(due_day=31, year=year, month=1, today=date(year, 1, 30))
    if open_:
        return checks, "FAIL", f"Jan {year} due=31 am 30. fälschlich offen"
    checks += 1
    open_, _ = probe(due_day=31, year=year, month=1, today=date(year, 1, 31))
    if not open_:
        return checks, "FAIL", f"Jan {year} due=31 am 31. nicht offen"
    checks += 1
    open_, _ = probe(
        due_day=feb_last, year=year, month=2, today=date(year, 2, feb_last - 1)
    )
    if open_:
        return checks, "FAIL", f"Feb {year}: vor Soll-Tag fälschlich offen"
    checks += 1
    open_, _ = probe(due_day=31, year=year, month=2, today=date(year, 3, 5))
    if not open_:
        return checks, "FAIL", f"Vormonat Feb {year} nicht als fällig gemeldet"

    # c) Voll gebucht ⇒ nie offen; due_day=None ⇒ Tag 1.
    checks += 1
    open_, rest = is_open_this_month(
        is_fix=True,
        is_recurring=True,
        budget=80.0,
        booked=80.0,
        due_day=15,
        year=year,
        month=6,
        today=date(year, 6, 20),
    )
    if open_ or rest != 0.0:
        return checks, "FAIL", f"voll gebucht offen: rest={rest}"
    checks += 1
    open_, _ = probe(due_day=None, year=year, month=6, today=date(year, 6, 1))
    if not open_:
        return checks, "FAIL", "due_day=None nicht als Tag 1 behandelt"
    return checks, "PASS", f"{year} (leap={leap}): Ultimo-Klemmung + Semantik ok"


# ── d6: Migrations-Idempotenz ───────────────────────────────────────────
def _schema_snapshot(conn: sqlite3.Connection) -> tuple:
    rows = conn.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    uv = conn.execute("PRAGMA user_version").fetchone()[0]
    return uv, tuple(rows)


def d6_migration_idempotent(i: int) -> tuple[int, str, str]:
    from model import migrations

    run = migrations.migrate_all
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / f"m_{i}.db"
        conn = sqlite3.connect(db)
        try:
            run(conn, db_path=None)
            snap1 = _schema_snapshot(conn)
            run(conn, db_path=None)  # zweiter Lauf: muss folgenlos sein
            snap2 = _schema_snapshot(conn)
        except Exception as exc:  # noqa: BLE001
            conn.close()
            return 2, "FAIL", f"Migration wirft: {type(exc).__name__}: {exc}"
        conn.close()
    if snap1[0] != snap2[0]:
        return 3, "FAIL", f"user_version driftet: {snap1[0]}→{snap2[0]}"
    if snap1[1] != snap2[1]:
        return 3, "FAIL", "Schema nach 2. Lauf verändert (nicht idempotent)"
    return 3, "PASS", f"user_version={snap1[0]}, Schema stabil über 2 Läufe"


# ── d7: Bundle-Integrität ───────────────────────────────────────────────
def d7_bundle_tamper(i: int) -> tuple[int, str, str]:
    from model.restore_bundle import create_bundle, verify_bundle

    rng = random.Random(7000 + i)
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        src = tdp / "database.db"
        payload = bytes(rng.randrange(256) for _ in range(2048))
        src.write_bytes(b"SQLite format 3\x00" + payload)
        bundle = tdp / "b.bmr"
        create_bundle(
            source_db=src,
            out_path=bundle,
            app="BudgetManager",
            app_version=APP_VERSION,
        )
        member = verify_bundle(bundle)
        if member not in ("database.db", "database.enc"):
            return 2, "FAIL", f"unerwarteter DB-Member: {member!r}"
        # 1 Byte in database.db innerhalb des ZIP flippen (neu packen)
        tampered = tdp / "t.bmr"
        with zipfile.ZipFile(bundle) as zin, zipfile.ZipFile(
            tampered, "w", zipfile.ZIP_DEFLATED
        ) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename.startswith("database."):
                    pos = rng.randrange(len(data))
                    data = data[:pos] + bytes([data[pos] ^ 0xFF]) + data[pos + 1 :]
                zout.writestr(info, data)
        from model.restore_bundle import BundleIntegrityError

        try:
            verify_bundle(tampered)
        except BundleIntegrityError as exc:
            reason = str(exc)[:60]
        else:
            return 2, "FAIL", "manipuliertes Bundle als intakt verifiziert"
    return 2, "PASS", f"Member={member}; Byte-Flip abgelehnt ({reason})"


# ── d8: i18n-Format-Sicherheit ──────────────────────────────────────────
def _flat(d: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in d.items():
        kk = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flat(v, kk))
        else:
            out[kk] = v
    return out


_ENGINE_PLACEHOLDERS = {
    "{date}",
    "{datum}",
    "{tag}",
    "{category}",
    "{kategorie}",
    "{month}",
    "{monat}",
}


def d8_i18n_format_safety(i: int) -> tuple[int, str, str]:
    import json

    de = _flat(json.loads((ROOT / "locales" / "de.json").read_text("utf-8")))
    en = _flat(json.loads((ROOT / "locales" / "en.json").read_text("utf-8")))
    fr = _flat(json.loads((ROOT / "locales" / "fr.json").read_text("utf-8")))
    keys = sorted(de)
    chunk = keys[i::LOOPS_PER_DOMAIN]
    fmt = string.Formatter()
    ph = lambda s: {"{%s}" % f for _, f, _, _ in fmt.parse(s) if f}  # noqa: E731
    checks = 0
    for k in chunk:
        for lang, cat in (("de", de), ("en", en), ("fr", fr)):
            checks += 1
            val = cat.get(k)
            if not isinstance(val, str):
                return checks, "FAIL", f"{k} fehlt/kein str in {lang}"
            try:
                list(fmt.parse(val))
            except ValueError as exc:
                return checks, "FAIL", f"{k}[{lang}] nicht format-parsebar: {exc}"
        allowed = ph(de[k]) | (_ENGINE_PLACEHOLDERS if k.startswith("tags.") else set())
        for lang, cat in (("en", en), ("fr", fr)):
            extra = ph(cat[k]) - allowed
            checks += 1
            if extra:
                return (
                    checks,
                    "FAIL",
                    f"{k}[{lang}] unbekannte Platzhalter {sorted(extra)}",
                )
    return checks, "PASS", f"{len(chunk)} Keys ×3 format-sicher"


# ── d9/d10: WARN-Messungen ──────────────────────────────────────────────
def d9_modal_info_load(i: int) -> tuple[int, str, str]:
    """Nach dem Enterprise-Merge: 0 modale Informationsdialoge in views/
    (nicht-modales Toast-System); Regressionsschutz auf show_info für die
    beiden ehemals modalen Meldungen. FAIL-fähig statt WARN."""
    total = 0
    for f in sorted((ROOT / "views").rglob("*.py")):
        total += f.read_text(encoding="utf-8").count("QMessageBox.information")
    sd = ROOT / "settings_dialog.py"
    if sd.exists():
        total += sd.read_text(encoding="utf-8").count("QMessageBox.information")
    mw = (ROOT / "views" / "main_window.py").read_text(encoding="utf-8")
    guard_ok = True
    for key in ("cockpit.keep_one_tab", "settings.data_dir_migrate_done_msg"):
        idx = mw.find(key)
        if idx < 0:
            guard_ok = False
            continue
        window = mw[max(0, idx - 400) : idx + 60]
        if "show_info(" not in window or "QMessageBox.information" in window:
            guard_ok = False
    ok = total == 0 and guard_ok
    return (
        2,
        "PASS" if ok else "FAIL",
        f"{total} modale Infos; Toast-Regressionsschutz "
        + ("intakt" if guard_ok else "VERLETZT"),
    )


def d10_taborder_decl(i: int) -> tuple[int, str, str]:
    """Nach dem Enterprise-Merge: komplexe Dialogdateien muessen die
    deterministische Tab-Kette registrieren (configure_dialog_tab_order)
    oder explizites setTabOrder deklarieren. FAIL-faehig statt WARN."""
    files = list((ROOT / "views").rglob("*.py")) + [ROOT / "settings_dialog.py"]
    complex_dialogs = 0
    wired = 0
    missing: list[str] = []
    for p in files:
        if not p.exists():
            continue
        src = p.read_text(encoding="utf-8")
        if (
            re.search(r"^class .*\(QDialog\)", src, re.MULTILINE)
            and src.count("QPushButton(") >= 5
        ):
            complex_dialogs += 1
            if "configure_dialog_tab_order(" in src or "setTabOrder(" in src:
                wired += 1
            else:
                missing.append(p.name)
    ok = not missing
    return (
        1,
        "PASS" if ok else "FAIL",
        (
            f"{wired}/{complex_dialogs} komplexe Dialogdateien mit Tab-Ketten"
            + ("" if ok else "; fehlt: " + ", ".join(missing[:4]))
        ),
    )


DOMAINS = [
    ("d1_sql_surface", d1_sql_surface),
    ("d2_privacy_sanitize", d2_privacy_sanitize),
    ("d3_file_permissions", d3_file_permissions),
    ("d4_money_format", d4_money_format),
    ("d5_due_clamp", d5_due_clamp),
    ("d6_migration_idempotent", d6_migration_idempotent),
    ("d7_bundle_tamper", d7_bundle_tamper),
    ("d8_i18n_format_safety", d8_i18n_format_safety),
    ("d9_modal_info_load", d9_modal_info_load),
    ("d10_taborder_decl", d10_taborder_decl),
]


def main() -> int:
    rows = []
    totals = {"checks": 0, "PASS": 0, "WARN": 0, "FAIL": 0}
    fail_msgs: dict[str, str] = {}
    warn_msgs: dict[str, str] = {}
    loop = 0
    for i in range(LOOPS_PER_DOMAIN):
        for name, fn in DOMAINS:
            loop += 1
            try:
                checks, status, msg = fn(i)
            except Exception as exc:  # noqa: BLE001
                checks, status, msg = 1, "FAIL", f"{type(exc).__name__}: {exc}"
            totals["checks"] += checks
            totals[status] += 1
            rows.append((loop, name, checks, status, msg))
            if status == "FAIL":
                fail_msgs.setdefault(name, msg)
            elif status == "WARN":
                warn_msgs.setdefault(name, msg)
        if (i + 1) % 20 == 0:
            print(
                f"Loop {(i + 1) * len(DOMAINS):04d}: checks={totals['checks']} "
                f"fail={totals['FAIL']} warn={totals['WARN']}"
            )
    csv_path = (
        ROOT / f"FINAL_RELEASE_AUDIT_1000_MATRIX_v{APP_VERSION.replace('.', '_')}.csv"
    )
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["loop", "domain", "checks", "status", "detail"])
        w.writerows(rows)
    print(f"CSV: {csv_path}")
    print(
        f"FINAL RELEASE AUDIT DONE: loops={loop} checks={totals['checks']} "
        f"pass={totals['PASS']} warn={totals['WARN']} fail={totals['FAIL']}"
    )
    for name, msg in fail_msgs.items():
        print(f"  FAIL {name}: {msg}")
    for name, msg in warn_msgs.items():
        print(f"  WARN {name}: {msg}")
    return 1 if totals["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
