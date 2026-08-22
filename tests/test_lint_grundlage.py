"""Alle vier Programme der Suite pruefen dasselbe.

Bis Loop 45 pruefte der BudgetManager nur `--select E9,F63,F7,F82` - also
Syntaxfehler und unbekannte Namen -, waehrend FreizeitManager und LifePlanner
laengst den vollen Satz aus einer `ruff.toml` fuhren. Was dazwischen lag, sah
niemand: unsortierte Importe, toter Code, 20 Module ohne Docstring.

Die Auswahl steht jetzt in `ruff.toml`. Diese Tests halten fest, dass sie dort
bleibt und dass kein Aufrufer sie wieder mit einem eigenen `--select`
uebersteuert - genau daran driftete es vorher.
"""

from __future__ import annotations

import ast
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUFF_TOML = ROOT / "ruff.toml"

# Der gemeinsame Kern der Suite. FreizeitManager und LifePlanner fuehren
# denselben; der Host hat zusaetzlich DTZ, weil er Zeitangaben schreibt, die
# andere Programme lesen.
GEMEINSAMER_KERN = {"E4", "E7", "E9", "F", "I", "UP", "SIM", "RUF100"}


def _konfiguration() -> dict:
    return tomllib.loads(RUFF_TOML.read_text(encoding="utf-8"))


def test_ruff_toml_existiert() -> None:
    assert RUFF_TOML.is_file(), "ohne ruff.toml gilt die Konfiguration des Rechners"


def test_auswahl_enthaelt_den_gemeinsamen_kern() -> None:
    ausgewaehlt = set(_konfiguration()["lint"]["select"])
    fehlend = GEMEINSAMER_KERN - ausgewaehlt
    assert not fehlend, f"Regelgruppen fehlen gegenueber der Suite: {sorted(fehlend)}"


def test_sim105_bleibt_aus() -> None:
    """contextlib.suppress ist genauso stumm wie except/pass.

    SIM105 raet zur Umschreibung. Sie wuerde den Ausnahmen-Ratchet
    (tools/exception_audit.py) kleiner aussehen lassen, ohne dass eine
    einzige Stelle besser meldet.
    """
    assert "SIM105" in _konfiguration()["lint"]["ignore"]


def test_kein_aufrufer_uebersteuert_die_auswahl() -> None:
    """`--select` an einem Aufrufer heisst: zwei Wahrheiten statt einer."""
    treffer = []
    for pfad in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        text = pfad.read_text(encoding="utf-8")
        for zeile in text.splitlines():
            blank = zeile.strip()
            if blank.startswith("#"):
                continue  # Kommentare duerfen ueber --select reden
            if "ruff" in blank and "--select" in blank:
                treffer.append(f"{pfad.name}: {zeile.strip()}")
    assert (
        not treffer
    ), "Auswahl gehoert in ruff.toml, nicht in den Aufruf: " + "; ".join(treffer)


def test_ruff_laeuft_sauber_durch() -> None:
    ergebnis = subprocess.run(
        ["python3", "-m", "ruff", "check", "."],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert ergebnis.returncode == 0, ergebnis.stdout + ergebnis.stderr


def _getrackte_module() -> list[Path]:
    ausgabe = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [ROOT / p for p in ausgabe]


def test_kein_modul_hat_seinen_docstring_verloren() -> None:
    """Ein Import vor dem Stringliteral macht aus dem Docstring Zierrat.

    Zwei automatisierte Einfuegelaeufe hatten `from __future__ import
    annotations` und einen Logger-Block davor geschoben. In 20 Modulen war
    `__doc__` danach None - der Text stand noch da, nur eben wirkungslos.
    """
    verloren = []
    for pfad in _getrackte_module():
        try:
            baum = ast.parse(pfad.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        if ast.get_docstring(baum) is not None:
            continue
        for i, knoten in enumerate(baum.body):
            if (
                i > 0
                and isinstance(knoten, ast.Expr)
                and isinstance(knoten.value, ast.Constant)
                and isinstance(knoten.value.value, str)
            ):
                verloren.append(f"{pfad.relative_to(ROOT)}:{knoten.lineno}")
                break
    assert not verloren, "Stringliteral steht nicht mehr als Docstring: " + ", ".join(
        verloren
    )
