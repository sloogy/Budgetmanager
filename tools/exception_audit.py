#!/usr/bin/env python3
"""Ausnahmen-Ratchet.

Prueft den Produktionscode auf Fehlerbehandlung, die Fehler verschwinden
laesst, und erzwingt vier Regeln:

1. Nackte ``except:``-Klauseln sind verboten. Sie fangen auch
   ``KeyboardInterrupt`` und ``SystemExit`` - das Programm laesst sich dann
   nicht mehr sauber abbrechen.
2. ``except BaseException`` ist aus demselben Grund verboten. Es ist die
   ausgeschriebene Form derselben Klausel und rutschte frueher durch, weil
   nur nach dem Doppelpunkt gesucht wurde.
3. Stumme Schlucker - ``except Exception: pass`` oder ein Handler, dessen
   ganzer Rumpf aus einem Docstring besteht - duerfen die festgeschriebene
   Obergrenze nicht ueberschreiten. Sie sind der gefaehrlichste Fall: kein
   Log, keine Meldung, keine Spur. Ein Fehler passiert und niemand erfaehrt
   davon.
4. ``except Exception`` insgesamt darf seine Obergrenze nicht
   ueberschreiten.

Beide Obergrenzen werden bei jeder Praezisierungsrunde von Hand GESENKT, nie
erhoeht. So baut sich der Bestand messbar ab, ohne dass ein riskanter Umbau
auf einen Schlag noetig waere.

Warum ueberhaupt: Ein ``except Exception`` faengt auch den Tippfehler im
Attributnamen. Der Fehler verschwindet dann in einem Rueckfallwert, und
niemand sieht, dass etwas nicht stimmt - genau die Sorte Fehler, die erst
Monate spaeter als "die Anzeige stimmt manchmal nicht" auftaucht.

Geprueft wird der Baum ueber den Syntaxbaum, nicht ueber Textsuche. Eine
Textsuche zaehlt Beispiele in Docstrings mit und verpasst mehrzeilige
Formen. Und geprueft wird alles, was nicht ausdruecklich ausgenommen ist -
eine Positivliste von Paketen liesse jede neu angelegte Datei ungeprueft
durch, was hier schon vorgekommen ist.

    python3 tools/exception_audit.py            # Gate: Exit 0 oder 1
    python3 tools/exception_audit.py --list     # Fundstellen zum Abbauen

Wortgleich in FPM, BudgetManager, FreizeitManager und LifePlanner; nur die
beiden Obergrenzen unterscheiden sich.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Negativliste: alles ausserhalb dieser Verzeichnisse ist Produktionscode und
# wird geprueft. Umgekehrt herum - eine Positivliste der Pakete - war der
# Ratchet blind fuer alles, was spaeter dazukam.
EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "env",
        "legacy",
        "node_modules",
        "test",
        "tests",
        "tools",
        "venv",
    }
)

# Einzeldateien, die kein ausgeliefertes Programm sind.
EXCLUDED_FILES = frozenset({"conftest.py", "dev_check.py", "setup.py"})

# Ratchet-Obergrenzen. Nur senken, nie erhoehen.
BARE_EXCEPT_LIMIT = 0
BASE_EXCEPTION_LIMIT = 0
SILENT_EXCEPT_LIMIT = 48
BROAD_EXCEPTION_LIMIT = 662


def _production_files() -> list[Path]:
    out: list[Path] = []
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if any(part in EXCLUDED_DIRS for part in rel.parts[:-1]):
            continue
        if rel.name in EXCLUDED_FILES:
            continue
        out.append(path)
    return out


def _caught_names(node: ast.expr | None) -> tuple[str, ...] | None:
    """Die gefangenen Ausnahmenamen, oder None bei nacktem ``except:``."""
    if node is None:
        return None
    if isinstance(node, ast.Tuple):
        names: list[str] = []
        for element in node.elts:
            found = _caught_names(element)
            if found:
                names.extend(found)
        return tuple(names)
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        return (node.attr,)
    return ("<berechnet>",)


def _is_silent(handler: ast.ExceptHandler) -> bool:
    """Wahr, wenn der Handler den Fehler ohne jede Spur verschwinden laesst."""
    body = handler.body
    if len(body) != 1:
        return False
    only = body[0]
    if isinstance(only, ast.Pass):
        return True
    # Ein Handler, dessen Rumpf nur aus einer Zeichenkette besteht ("das darf
    # ruhig scheitern"), ist genauso stumm wie ``pass``.
    return isinstance(only, ast.Expr) and isinstance(only.value, ast.Constant)


class Findings:
    def __init__(self) -> None:
        self.bare: list[str] = []
        self.base: list[str] = []
        self.silent: list[str] = []
        self.broad = 0
        self.files = 0


def scan() -> Findings:
    result = Findings()
    for path in _production_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as exc:
            print(f"exception audit: {path} laesst sich nicht lesen: {exc}")
            continue
        result.files += 1
        rel = path.relative_to(ROOT)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            names = _caught_names(node.type)
            where = f"{rel}:{node.lineno}"
            if names is None:
                result.bare.append(where)
            elif "BaseException" in names:
                result.base.append(where)
            elif "Exception" in names:
                result.broad += 1
                if _is_silent(node):
                    result.silent.append(where)
    return result


def _report(titel: str, hits: list[str], limit: int) -> bool:
    if len(hits) <= limit:
        return True
    print(f"exception audit: {len(hits)} {titel} (erlaubt: {limit})")
    for hit in hits:
        print(f"  - {hit}")
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--list",
        action="store_true",
        help="alle Fundstellen ausgeben, auch die innerhalb der Grenzen",
    )
    args = parser.parse_args(argv)
    result = scan()

    if args.list:
        for titel, hits in (
            ("nackte except:", result.bare),
            ("except BaseException", result.base),
            ("stumme Schlucker", result.silent),
        ):
            print(f"--- {titel} ({len(hits)}) ---")
            for hit in hits:
                print(f"  {hit}")

    ok = True
    ok &= _report("nackte 'except:'-Klauseln", result.bare, BARE_EXCEPT_LIMIT)
    ok &= _report("'except BaseException'", result.base, BASE_EXCEPTION_LIMIT)
    ok &= _report(
        "stumme Schlucker (Ratchet-Obergrenze)", result.silent, SILENT_EXCEPT_LIMIT
    )
    if result.broad > BROAD_EXCEPTION_LIMIT:
        ok = False
        print(
            f"exception audit: {result.broad} breite 'except Exception' "
            f"(Ratchet-Obergrenze: {BROAD_EXCEPTION_LIMIT})"
        )
    if not ok:
        return 1
    print(
        f"exception audit: OK ({result.files} Dateien, "
        f"{result.broad} breite Handler <= {BROAD_EXCEPTION_LIMIT}, "
        f"{len(result.silent)} stumme <= {SILENT_EXCEPT_LIMIT}, "
        f"{len(result.bare)} nackte except, "
        f"{len(result.base)} BaseException)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
