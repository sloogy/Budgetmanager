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
import ast
import json
import os
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

TR_CALL_RE = re.compile(r"\b(?:tr|trf)\(\s*['\"]([^'\"]+)['\"]", re.MULTILINE)

# Heuristik: UI-Calls, in denen harte Strings typischerweise user-visible sind.
HARDCODE_HINT_RE = re.compile(
    r"\b(setText|setWindowTitle|setToolTip|setPlaceholderText|setStatusTip|"
    r"setWhatsThis|setHeaderLabels|setHorizontalHeaderLabels|setVerticalHeaderLabels|"
    r"setTabText|addTab|addAction|setTitle|setLabelText|setInformativeText|setTextFormat|addRow|addItem|addItems|insertItem|setItemText|"
    r"QMessageBox\.|QAction\(|QLabel\(|QPushButton\(|QGroupBox\(|QMenu\(|QDialog\()",
    re.MULTILINE,
)

STRING_LITERAL_RE = re.compile(r"(?P<q>['\"])(?P<s>(?:\\.|(?!\1).)*)\1", re.MULTILINE)

OK_LITERAL_EXACT = {"", " ", "OK", "0", "1", "?", "|", "✓", "✗", "★", "∞", r"\n"}
OK_LITERAL_PATTERNS = [
    re.compile(r"^[\W_]+$"),
    re.compile(r"^#[0-9A-Fa-f]{3,8}$"),
    re.compile(r"^[a-z_][a-z0-9_]*$"),  # interne Datenkeys wie is_fix
    re.compile(r"^[%dmyYHMS.:%\- /]+$"),  # Datumsformate
    re.compile(r"^[Xx-]+$"),  # Masken/Placeholder ohne Sprache
    re.compile(r"^<\/?[a-z][a-z0-9]*>$"),  # HTML-Trenner wie <br>
]


def _looks_user_text_literal(s: str) -> bool:
    t = str(s or "").strip()
    if t in OK_LITERAL_EXACT:
        return False
    if any(p.match(t) for p in OK_LITERAL_PATTERNS):
        return False
    # F-Strings wie "{icon} {name}" enthalten im Quelltext Buchstaben,
    # aber keinen festen user-visible Text. Erst Platzhalter entfernen.
    without_placeholders = re.sub(r"\{[^{}]+\}", "", t).strip()
    return not (
        not without_placeholders
        or not re.search(r"[A-Za-zÄÖÜäöüßÉéÈèÀàÇç]", without_placeholders)
    )


IGNORE_PATH_PARTS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "build",
    "dist",
    "data",  # DB / Backups etc. im Projekt, nicht /mnt/data
    "locales",  # JSON selbst nicht als Code scannen
    "docs",
    "installer",
    "tests",
    "tools",
    "_attic",
}


@dataclass
class HardcodedFinding:
    file: Path
    line_no: int
    line: str


def _flatten_json_keys(obj: object, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            k_str = str(k)
            full = f"{prefix}.{k_str}" if prefix else k_str
            if isinstance(v, dict):
                keys |= _flatten_json_keys(v, full)
            else:
                keys.add(full)
    return keys


def _flatten_json_values(obj: object, prefix: str = "") -> dict[str, str]:
    values: dict[str, str] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            k_str = str(k)
            full = f"{prefix}.{k_str}" if prefix else k_str
            if isinstance(v, dict):
                values.update(_flatten_json_values(v, full))
            elif isinstance(v, str):
                values[full] = v
    return values


GERMAN_RESIDUAL_RE = re.compile(
    r"\b("
    r"Bitte|Fehler|Warnung|Erfolgreich|erfolgreich|fehlgeschlagen|Löschen|Bearbeiten|"
    r"Hinzufügen|Ausgaben|Einkommen|Ersparnisse|Kategorie|Betrag|Monat|Jahr|"
    r"Wiederkehrend|Fixkosten|Überschuss|Datenbank|Sicherung|Abbrechen|Speichern|"
    r"Übernehmen|Kopieren|Deutsch|Schweiz|Monatslohn|Passwort|Aktuelles|Neues|"
    r"Namen|anzeigen|auswählen|Sicherheitsstufe|Zeitraum|Optionen|Exportieren|"
    r"Gespeichert|Ordner|Pfad|Schlüssel|Währung|Sprache|Bedienung|Tabellen|Listen|"
    r"Umbenennen|Eigenschaften|Unterkategorie|Keine|Hauptkategorie|Benutzer|Statistiken|"
    r"erlaubt|Öffnen|Schließen|Schliessen|Weiter|Zurück|Eingabe|wiederholen|Aktuelle|Stufe|Wechseln|Schutz|entfernen|Entfernen|Erstellt|Dein|Zwischenablage|Kopiert|Erstellen|speichern|unter|verwenden|Zeile|Aktuell|keine|Neuer|existiert|bereits|Startfehler"
    r")\b"
)


def _find_german_residual_values(
    values: dict[str, str], referenced: set[str]
) -> dict[str, str]:
    findings: dict[str, str] = {}
    for key in sorted(referenced):
        if "language_select_dialog" in key:
            # This dialog intentionally displays all three languages before the
            # active locale is known. Do not treat it as an EN/FR residual.
            continue
        val = values.get(key)
        if isinstance(val, str) and GERMAN_RESIDUAL_RE.search(val):
            findings[key] = val
    return findings


def _load_locale_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"Kann JSON nicht lesen: {path}: {e}")


def _iter_py_files(root: Path) -> Iterable[Path]:
    """Iteriert Python-Dateien relativ zum Projektroot.

    Wichtig: Nicht gegen absolute Pfadbestandteile prüfen. In der Sandbox
    liegt das Projekt unter /mnt/data; sonst würde der absolute Ordnername
    "data" versehentlich das ganze Projekt ausblenden.
    """
    root = root.resolve()
    for p in root.rglob("*.py"):
        try:
            rel = p.resolve().relative_to(root)
        except ValueError:
            rel = p
        if any(part in IGNORE_PATH_PARTS for part in rel.parts):
            continue
        yield p


def _extract_referenced_locale_keys(text: str, locale_keys: set[str]) -> set[str]:
    """Findet direkte und dynamisch zusammengesetzte Locale-Key-Referenzen.

    Neben tr()/trf()-Literalen werden alle Stringkonstanten, f-String-Präfixe
    und Formatvorlagen berücksichtigt. Das vermeidet die früheren hunderten
    False-Positives bei Tabellen-, Defaultkategorie- und Dialog-Keyfamilien.
    """
    referenced = {m.group(1).strip() for m in TR_CALL_RE.finditer(text)}
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return referenced
    for node in ast.walk(tree):
        values: list[str] = []
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            values.append(node.value.strip())
        elif isinstance(node, ast.JoinedStr):
            prefix_parts: list[str] = []
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    prefix_parts.append(value.value)
                else:
                    break
            if prefix_parts:
                values.append("".join(prefix_parts).strip())
        for value in values:
            if value in locale_keys:
                referenced.add(value)
            prefixes = [value]
            for marker in ("{", "%"):
                if marker in value:
                    prefixes.append(value.split(marker, 1)[0])
            for prefix in prefixes:
                if prefix and (prefix.endswith(".") or prefix != value):
                    referenced.update(
                        key for key in locale_keys if key.startswith(prefix)
                    )
    return referenced


def _find_hardcoded_ui_strings(py_path: Path) -> list[HardcodedFinding]:
    """Heuristik: Findet Zeilen mit UI-Aufrufen + Stringliteral,
    die nicht offensichtlich via tr()/trf() laufen.
    """
    findings: list[HardcodedFinding] = []
    try:
        raw = py_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = py_path.read_text(encoding="latin-1", errors="replace")

    for idx, line in enumerate(raw.splitlines(), start=1):
        if "tr(" in line or "trf(" in line or "display_typ(" in line:
            continue
        if not HARDCODE_HINT_RE.search(line):
            continue
        literals = [m.group("s") for m in STRING_LITERAL_RE.finditer(line)]
        if not any(_looks_user_text_literal(x) for x in literals):
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


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="BudgetManager i18n Audit")
    ap.add_argument("--root", default=".", help="Projekt-Root (Default: .)")
    ap.add_argument(
        "--locales", default="locales", help="Locales-Ordner (Default: locales)"
    )
    ap.add_argument(
        "--lang",
        action="append",
        default=None,
        help="Sprache(n) prüfen (Default: --lang de --lang en)",
    )
    ap.add_argument("--out", default="", help="Optional: Report-Datei schreiben")
    ap.add_argument(
        "--max-hardcoded", type=int, default=80, help="Max. Hardcoded-Zeilen im Output"
    )
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    locales_dir = (root / args.locales).resolve()
    langs = args.lang or ["de", "en"]

    # Load locales
    locale_keys: dict[str, set[str]] = {}
    locale_values: dict[str, dict[str, str]] = {}
    try:
        for lang in langs:
            p = locales_dir / f"{lang}.json"
            if not p.exists():
                raise RuntimeError(f"Locale fehlt: {p}")
            data = _load_locale_json(p)
            locale_keys[lang] = _flatten_json_keys(data)
            locale_values[lang] = _flatten_json_values(data)
    except Exception as e:
        print(f"[FATAL] {e}")
        return 2

    base_lang = langs[0]
    base = locale_keys[base_lang]

    # Extract referenced keys + hardcoded strings
    referenced: set[str] = set()
    hardcoded: list[HardcodedFinding] = []
    for py in _iter_py_files(root):
        txt = py.read_text(encoding="utf-8", errors="replace")
        referenced |= _extract_referenced_locale_keys(txt, base)
        hardcoded.extend(_find_hardcoded_ui_strings(py))

    # Nicht-Python-Ressourcen können Locale-Keys deklarativ referenzieren.
    for resource in (root / "data").rglob("*.json"):
        raw = resource.read_text(encoding="utf-8", errors="replace")
        referenced.update(key for key in base if key in raw)

    missing_by_lang: dict[str, set[str]] = {}
    extra_by_lang: dict[str, set[str]] = {}
    for lang in langs[1:]:
        missing_by_lang[lang] = base - locale_keys[lang]
        extra_by_lang[lang] = locale_keys[lang] - base

    unused_in_base = base - referenced
    missing_in_base = referenced - base

    out_lines: list[str] = []
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
        out_lines.append(
            f"[OK] Alle referenzierten Keys existieren in {base_lang}.json"
        )
        out_lines.append("")

    for lang in langs[1:]:
        miss = missing_by_lang.get(lang, set())
        extra = extra_by_lang.get(lang, set())

        if miss:
            out_lines.append(
                f"[WARN] {len(miss)} Key(s) fehlen in {lang}.json (gegenüber {base_lang}.json):"
            )
            for k in sorted(miss)[:200]:
                out_lines.append(f"  - {k}")
            if len(miss) > 200:
                out_lines.append(f"  ... (+{len(miss)-200} weitere)")
            out_lines.append("")
        else:
            out_lines.append(f"[OK] {lang}.json hat alle Keys von {base_lang}.json")
            out_lines.append("")

        if extra:
            out_lines.append(
                f"[INFO] {len(extra)} extra Key(s) in {lang}.json (nicht in {base_lang}.json):"
            )
            for k in sorted(extra)[:80]:
                out_lines.append(f"  - {k}")
            if len(extra) > 80:
                out_lines.append(f"  ... (+{len(extra)-80} weitere)")
            out_lines.append("")

    german_residual_by_lang: dict[str, dict[str, str]] = {}
    for lang in langs[1:]:
        residual = _find_german_residual_values(locale_values.get(lang, {}), referenced)
        german_residual_by_lang[lang] = residual
        if residual:
            out_lines.append(
                f"[ERROR] {len(residual)} mutmaßlich deutsche Restübersetzung(en) in referenzierten {lang}.json-Werten:"
            )
            for k, v in list(residual.items())[:120]:
                one_line = str(v).replace("\n", " / ")
                out_lines.append(f"  - {k}: {one_line}")
            if len(residual) > 120:
                out_lines.append(f"  ... (+{len(residual)-120} weitere)")
            out_lines.append("")
        else:
            out_lines.append(
                f"[OK] Keine deutschen Restübersetzungen in referenzierten {lang}.json-Werten"
            )
            out_lines.append("")

    if unused_in_base:
        out_lines.append(
            f"[ERROR] {len(unused_in_base)} Key(s) in {base_lang}.json wirken ungenutzt (keine statische oder dynamische Referenz):"
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
        out_lines.append(
            f"[WARN] {len(hardcoded)} verdächtige hardcoded UI-Strings gefunden (Heuristik):"
        )
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
        out_path = (
            (root / args.out).resolve()
            if not os.path.isabs(args.out)
            else Path(args.out)
        )
        _write_report(out_path, report)
        print(f"\nReport geschrieben nach: {out_path}")

    problems = (
        bool(missing_in_base)
        or any(missing_by_lang.get(lang) for lang in langs[1:])
        or any(german_residual_by_lang.get(lang) for lang in langs[1:])
        or bool(hardcoded)
        or bool(unused_in_base)
    )
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
