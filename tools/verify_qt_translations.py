#!/usr/bin/env python3
"""Verifiziert, dass die Qt-Übersetzungen (qtbase_<lang>.qm) verfügbar sind.

Zweck (R2): Native Kontextmenüs (Kopieren/Einfügen/…) sind nur dann lokalisiert,
wenn die Qt-eigenen .qm-Kataloge mit ausgeliefert werden.

Zwei Modi:
  1) Ohne Argument: prüft die aktuelle Qt-Installation (Entwicklungsumgebung).
  2) Mit Pfad:      prüft einen gebauten App-Ordner (z. B. dist/BudgetManager),
                    erwartet die Dateien unter <pfad>/PySide6/translations.

Exit-Code 0 = alle Pflichtkataloge vorhanden, sonst 1.
"""
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED = ["qtbase_de.qm", "qtbase_fr.qm"]
OPTIONAL = ["qt_de.qm", "qt_fr.qm"]


def _source_dirs() -> list[Path]:
    """Übersetzungsverzeichnisse der Entwicklungs-/Build-Qt-Installation.

    Nutzt dieselbe Suchstrategie wie utils.qt_translator, damit der Gate nicht
    fälschlich scheitert, wenn QLibraryInfo leer ist, die Kataloge aber im
    PySide6-Paket unter PySide6/translations oder PySide6/Qt/translations liegen.
    """
    dirs: list[Path] = []
    try:
        from PySide6.QtCore import QLibraryInfo
        try:
            p = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        except Exception:
            p = QLibraryInfo.location(QLibraryInfo.TranslationsPath)  # type: ignore[attr-defined]
        if p:
            dirs.append(Path(p))
    except Exception:
        pass

    try:
        import PySide6
        base = Path(PySide6.__file__).resolve().parent
        dirs.append(base / "translations")
        dirs.append(base / "Qt" / "translations")
    except Exception:
        pass

    seen: set[str] = set()
    out: list[Path] = []
    for d in dirs:
        key = str(d)
        if key not in seen and d.is_dir():
            seen.add(key)
            out.append(d)
    return out


def _build_dirs(root: Path) -> list[Path]:
    # gängige PyInstaller-Layouts
    candidates = [
        root / "PySide6" / "translations",
        root / "_internal" / "PySide6" / "translations",
        root,
    ]
    return [d for d in candidates if d.is_dir()]


def check(dirs: list[Path]) -> bool:
    if not dirs:
        print("❌ Kein Übersetzungsverzeichnis gefunden.")
        return False
    print("Geprüfte Verzeichnisse:")
    for d in dirs:
        print(f"  - {d}")
    found = {}
    for name in REQUIRED + OPTIONAL:
        found[name] = any((d / name).is_file() for d in dirs)

    ok = True
    print("\nPflicht-Kataloge:")
    for name in REQUIRED:
        mark = "✅" if found[name] else "❌"
        if not found[name]:
            ok = False
        print(f"  {mark} {name}")
    print("\nOptional:")
    for name in OPTIONAL:
        print(f"  {'✅' if found[name] else '–'} {name}")
    return ok


def main() -> int:
    if len(sys.argv) > 1:
        root = Path(sys.argv[1]).expanduser().resolve()
        print(f"Modus: Build-Ordner ({root})\n")
        dirs = _build_dirs(root)
    else:
        print("Modus: Qt-Installation (Entwicklung)\n")
        dirs = _source_dirs()

    ok = check(dirs)
    print("\n" + ("✅ R2 erfüllt: native Kontextmenüs werden DE/FR lokalisiert."
                  if ok else
                  "❌ R2 NICHT erfüllt: qtbase_*.qm fehlt – Build/Qt-Installation prüfen."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
