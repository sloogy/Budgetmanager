#!/usr/bin/env python3
"""Schreibt docs/archive/release-evidence/README.md aus dem Verzeichnisinhalt.

Warum es diese Datei gibt: Der Index wurde von Hand gepflegt und driftete -
zuletzt nannte er 59 von 129 Dateien. Ein Index, der die Haelfte verschweigt,
ist schlimmer als keiner: Wer eine Datei nicht findet, haelt sie fuer nicht
vorhanden.

``--check`` prueft nur und schreibt nichts; so laeuft es im Test.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "archive" / "release-evidence"
INDEX = EVIDENCE / "README.md"

KOPF = """# Archivierte Release-Nachweise

Dieser Ordner enthält historische Audit-, Vergleichs-, Matrix- und Prüfdateien.
Sie bleiben zur Nachvollziehbarkeit erhalten, liegen aber nicht mehr im
Projekt-Hauptordner.

> Hinweis: Diese Dokumente beschreiben frühere Zwischenstände. Für den
> aktuellen Stand gelten `README.md`, `CHANGELOG.md`, `VERSION_INFO.txt` und
> `docs/open-tasks.md`.

`tools/final_release_audit_1000.py` legt seine Matrix beim Lauf direkt hier ab.
Im Projekt-Hauptordner bleibt kein Nachweis zurück — auch nicht der der
laufenden Fassung. Er lag dort früher, wurde aber beim nächsten Release nie
entfernt; so wuchs der Hauptordner um eine Datei je Version.

Diese Liste erzeugt `tools/release_evidence_index.py`. Von Hand gepflegt
driftete sie: Zuletzt nannte sie 59 von 129 Dateien.
"""

# (Ueberschrift, Erkennungsmerkmal) - der erste Treffer gewinnt.
ABSCHNITTE: tuple[tuple[str, str], ...] = (
    ("Matrizen und Messdaten", ".csv"),
    ("Ausführungs- und Prüfprotokolle", ".txt"),
    ("Messwerte und Readiness-Daten", ".json"),
    ("Audit- und Releaseberichte", ".md"),
)


def _erzeuge() -> str:
    dateien = sorted(
        p.name for p in EVIDENCE.iterdir() if p.is_file() and p.name != "README.md"
    )
    zugeordnet: dict[str, list[str]] = {titel: [] for titel, _ in ABSCHNITTE}
    sonstige: list[str] = []
    for name in dateien:
        for titel, endung in ABSCHNITTE:
            if name.endswith(endung):
                zugeordnet[titel].append(name)
                break
        else:
            sonstige.append(name)

    teile = [KOPF, f"\n**{len(dateien)} Nachweise.**\n"]
    for titel, _ in ABSCHNITTE:
        if not zugeordnet[titel]:
            continue
        teile.append(f"\n## {titel}\n\n")
        teile.extend(f"- `{name}`\n" for name in zugeordnet[titel])
    if sonstige:
        teile.append("\n## Weitere Dateien\n\n")
        teile.extend(f"- `{name}`\n" for name in sonstige)
    return "".join(teile)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--check", action="store_true", help="nur pruefen, nichts schreiben"
    )
    args = parser.parse_args(argv)

    erwartet = _erzeuge()
    vorhanden = INDEX.read_text(encoding="utf-8") if INDEX.is_file() else ""
    if erwartet == vorhanden:
        print(f"Index aktuell: {INDEX.relative_to(ROOT)}")
        return 0
    if args.check:
        print(
            f"Index veraltet: {INDEX.relative_to(ROOT)}\n"
            "  python3 tools/release_evidence_index.py",
            file=sys.stderr,
        )
        return 1
    INDEX.write_text(erwartet, encoding="utf-8")
    print(f"Index geschrieben: {INDEX.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
