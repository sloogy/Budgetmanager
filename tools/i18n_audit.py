#!/usr/bin/env python3
"""i18n Audit Tool for BudgetManager

Zweck
-----
Dieses Skript hilft dir, das neue i18n-System sauber zu halten.

Es prüft:
1) Fehlende Keys zwischen locales/de.json und locales/en.json
2) Ungenutzte Keys (in JSON vorhanden, aber im Code nicht referenziert)
3) Verdächtige hardcoded UI-Strings im Python-Code (heuristische Suche)

Usage
-----
  python tools/i18n_audit.py
  python tools/i18n_audit.py --root . --locales locales --lang de --lang en
  python tools/i18n_audit.py --out data/i18n_audit_report.txt

Exit Codes
----------
0 = alles ok
1 = Warnungen/Probleme gefunden
2 = schwere Fehler (z.B. JSON nicht lesbar)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Set


TR_CALL_RE = re.compile(r"\b(?:tr|trf)\(\s*['\"]([^'\"]+)['\"]", re.MULTILINE)

# Heuristik: UI-Calls, in denen harte Strings typischerweise user-visible sind.
HARDCODE_HINT_RE = re.compile(
    r"\b(setText|setWindowTitle|setToolTip|setPlaceholderText|setStatusTip|"
    r"setWhatsThis|setHeaderLabels|setHorizontalHeaderLabels|setVerticalHeaderLabels|"
    r"setTabText|addTab|addAction|setTitle|setLabelText|setInformativeText|setTextFormat|"
    r"QMessageBox\.|QAction\(|QLabel\(|QPushButton\(|QGroupBox\(|QMenu\(|QDialog\()",
    re.MULTILINE,
)

STRING_LITERAL_RE = re.compile(r"(?P<q>['\"])(?P<s>(?:\\.|(?!\1).)*)\1", re.MULTILINE)

IGNORE_PATH_PARTS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "build",
    "dist",
    "data",  # DB / Backups etc.
    "locales",  # JSON selbst nicht als Code scannen
}


@dataclass
class HardcodedFinding:
    file: Path
    line_no: int
    line: str


def _flatten_json_keys(obj: object, prefix: str = "") -> Set[str]:
    keys: Set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            k_str = str(k)
            full = f"{prefix}.{k_str}" if prefix else k_str
            if isinstance(v, dict):
                keys |= _flatten_json_keys(v, full)
            else:
                keys.add(full)
    return keys


def _load_locale_json(path: Path) -> Dict:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"Kann JSON nicht lesen: {path}: {e}")


def _iter_py_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.py"):
        if any(part in IGNORE_PATH_PARTS for part in p.parts):
            continue
        yield p


def _extract_tr_keys_from_code(text: str) -> Set[str]:
    return {m.group(1).strip() for m in TR_CALL_RE.finditer(text)}


def _find_hardcoded_ui_strings(py_path: Path) -> List[HardcodedFinding]:
    """Heuristik: Findet Zeilen mit UI-Aufrufen + Stringliteral,
    die nicht offensichtlich via tr()/trf() laufen.
    """
    findings: List[HardcodedFinding] = []
    try:
        raw = py_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = py_path.read_text(encoding="latin-1", errors="replace")

    for idx, line in enumerate(raw.splitlines(), start=1):
        if "tr(" in line or "trf(" in line:
            continue
        if not HARDCODE_HINT_RE.search(line):
            continue
        if not STRING_LITERAL_RE.search(line):
            continue
        if "print(" in line or "logger." in line or "logging." in line:
            continue
        if re.search(r"\(['\"]\s*['\"]\)", line):
            continue
        findings.append(HardcodedFinding(file=py_path, line_no=idx, line=line.strip()))
    return findings


def _write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="BudgetManager i18n Audit")
    ap.add_argument("--root", default=".", help="Projekt-Root (Default: .)")
    ap.add_argument("--locales", default="locales", help="Locales-Ordner (Default: locales)")
    ap.add_argument(
        "--lang",
        action="append",
        default=["de", "en"],
        help="Sprache(n) prüfen (Default: --lang de --lang en)",
    )
    ap.add_argument("--out", default="", help="Optional: Report-Datei schreiben")
    ap.add_argument("--max-hardcoded", type=int, default=80, help="Max. Hardcoded-Zeilen im Output")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    locales_dir = (root / args.locales).resolve()

    # Load locales
    locale_keys: Dict[str, Set[str]] = {}
    try:
        for lang in args.lang:
            p = locales_dir / f"{lang}.json"
            if not p.exists():
                raise RuntimeError(f"Locale fehlt: {p}")
            data = _load_locale_json(p)
            locale_keys[lang] = _flatten_json_keys(data)
    except Exception as e:
        print(f"[FATAL] {e}")
        return 2

    # Extract referenced keys + hardcoded strings
    referenced: Set[str] = set()
    hardcoded: List[HardcodedFinding] = []
    for py in _iter_py_files(root):
        txt = py.read_text(encoding="utf-8", errors="replace")
        referenced |= _extract_tr_keys_from_code(txt)
        hardcoded.extend(_find_hardcoded_ui_strings(py))

    base_lang = args.lang[0]
    base = locale_keys[base_lang]

    missing_by_lang: Dict[str, Set[str]] = {}
    extra_by_lang: Dict[str, Set[str]] = {}
    for lang in args.lang[1:]:
        missing_by_lang[lang] = base - locale_keys[lang]
        extra_by_lang[lang] = locale_keys[lang] - base

    unused_in_base = base - referenced
    missing_in_base = referenced - base

    out_lines: List[str] = []
    out_lines.append("BudgetManager i18n Audit")
    out_lines.append("=" * 24)
    out_lines.append(f"Root: {root}")
    out_lines.append(f"Locales: {locales_dir}")
    out_lines.append("")

    if missing_in_base:
        out_lines.append(
            f"[ERROR] {len(missing_in_base)} Key(s) werden im Code genutzt, fehlen aber in {base_lang}.json:"
        )
        for k in sorted(missing_in_base):
            out_lines.append(f"  - {k}")
        out_lines.append("")
    else:
        out_lines.append(f"[OK] Alle referenzierten Keys existieren in {base_lang}.json")
        out_lines.append("")

    for lang in args.lang[1:]:
        miss = missing_by_lang.get(lang, set())
        extra = extra_by_lang.get(lang, set())

        if miss:
            out_lines.append(f"[WARN] {len(miss)} Key(s) fehlen in {lang}.json (gegenüber {base_lang}.json):")
            for k in sorted(miss)[:200]:
                out_lines.append(f"  - {k}")
            if len(miss) > 200:
                out_lines.append(f"  ... (+{len(miss)-200} weitere)")
            out_lines.append("")
        else:
            out_lines.append(f"[OK] {lang}.json hat alle Keys von {base_lang}.json")
            out_lines.append("")

        if extra:
            out_lines.append(f"[INFO] {len(extra)} extra Key(s) in {lang}.json (nicht in {base_lang}.json):")
            for k in sorted(extra)[:80]:
                out_lines.append(f"  - {k}")
            if len(extra) > 80:
                out_lines.append(f"  ... (+{len(extra)-80} weitere)")
            out_lines.append("")

    if unused_in_base:
        out_lines.append(
            f"[INFO] {len(unused_in_base)} Key(s) in {base_lang}.json wirken ungenutzt (kein tr()/trf() Treffer):"
        )
        for k in sorted(unused_in_base)[:200]:
            out_lines.append(f"  - {k}")
        if len(unused_in_base) > 200:
            out_lines.append(f"  ... (+{len(unused_in_base)-200} weitere)")
        out_lines.append("")
    else:
        out_lines.append(f"[OK] Keine ungenutzten Keys in {base_lang}.json gefunden")
        out_lines.append("")

    if hardcoded:
        out_lines.append(f"[WARN] {len(hardcoded)} verdächtige hardcoded UI-Strings gefunden (Heuristik):")
        for f in hardcoded[: args.max_hardcoded]:
            rel = f.file.relative_to(root)
            out_lines.append(f"  - {rel}:{f.line_no}: {f.line}")
        if len(hardcoded) > args.max_hardcoded:
            out_lines.append(f"  ... (+{len(hardcoded)-args.max_hardcoded} weitere)")
        out_lines.append("")
    else:
        out_lines.append("[OK] Keine verdächtigen hardcoded UI-Strings gefunden")
        out_lines.append("")

    report = "\n".join(out_lines)
    print(report)

    if args.out:
        out_path = (root / args.out).resolve() if not os.path.isabs(args.out) else Path(args.out)
        _write_report(out_path, report)
        print(f"\nReport geschrieben nach: {out_path}")

    problems = bool(missing_in_base) or any(missing_by_lang.get(l) for l in args.lang[1:]) or bool(hardcoded)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
