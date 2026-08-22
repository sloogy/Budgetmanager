"""Das README sagt zuerst, was das Programm fuer den Nutzer tut.

Vor Loop 46 begann jedes der vier mit Technik: FPM mit SSRF-Schutz und
Hash-Locks, der FreizeitManager mit einer Tabelle aus Dateipfaden, der
LifePlanner mit Modulvertraegen. Wer wissen wollte, wofuer das Programm da
ist, fand einen Satz und danach 400 Zeilen Bauanleitung.

Diese Tests halten die Reihenfolge fest: fachlich zuerst, technisch danach.
Sie pruefen nicht den Inhalt - das kann kein Test -, sondern dass der
fachliche Teil ueberhaupt da ist und vorne steht.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

# Abschnitte, die sich an Entwickler richten. Sie duerfen im README stehen -
# nur nicht vor der fachlichen Beschreibung.
TECHNISCH = re.compile(
    r"^##+\s*(fuer entwickler|für entwickler|entwicklung|release|struktur|"
    r"aufbau|installation|schnellstart|loslegen|build|tests?)\b",
    re.IGNORECASE,
)


def _ueberschriften() -> list[tuple[int, str]]:
    zeilen = README.read_text(encoding="utf-8").splitlines()
    return [(i, z) for i, z in enumerate(zeilen) if z.startswith("##")]


def test_readme_hat_einen_fachlichen_abschnitt() -> None:
    text = README.read_text(encoding="utf-8")
    assert "## Was du damit tust" in text, (
        "Das README soll sagen, was der Nutzer mit dem Programm tut - "
        "nicht nur, woraus es gebaut ist."
    )


def test_fachliches_steht_vor_technischem() -> None:
    fachlich = None
    erstes_technisches = None
    for nr, zeile in _ueberschriften():
        if zeile.strip() == "## Was du damit tust" and fachlich is None:
            fachlich = nr
        if TECHNISCH.match(zeile) and erstes_technisches is None:
            erstes_technisches = (nr, zeile.strip())
    assert fachlich is not None
    if erstes_technisches is not None:
        nr, titel = erstes_technisches
        assert fachlich < nr, (
            f'"{titel}" steht vor der fachlichen Beschreibung (Zeile {nr + 1} '
            f"gegen {fachlich + 1})."
        )


def test_der_erste_absatz_ist_kein_code() -> None:
    """Wer das README oeffnet, soll einen Satz lesen, keine Kommandozeile."""
    zeilen = README.read_text(encoding="utf-8").splitlines()
    assert zeilen[0].startswith("# "), "Die erste Zeile ist der Titel"
    for zeile in zeilen[1:12]:
        assert not zeile.startswith("```"), (
            "In den ersten Zeilen steht ein Code-Block - "
            "erst erklaeren, dann zeigen."
        )
