#!/usr/bin/env python3
"""Bereinigt den Source-Baum vor dem Packen eines Release-ZIPs.

Entfernt nur generierbare Laufzeit-/Testartefakte, keine Quell- oder Doku-Dateien.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILE_GLOBS = [
    # Laufzeit-/Nutzerdaten dürfen niemals in einem Source- oder Release-ZIP
    # verbleiben. Tests können Settings absichtlich am Standardpfad erzeugen;
    # der Cleaner muss diesen Zustand zuverlässig zurücksetzen.
    "data/budgetmanager_settings.json",
    "data/budgetmanager_settings.tmp",
    "data/users.json",
    "data/*.db",
    "data/*.sqlite",
    "data/*.sqlite3",
    "data/*.enc",
    "data/backups/*.bmr",
    "data/*.log",
    "data/*crash*.log",
    "data/i18n_audit_report.txt",
    "*.log",
]
DIR_NAMES = {
    "__pycache__",
    "theme_profiles",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    "installer_output",
}
EXCLUDED_DIR_PREFIXES = (".venv", "venv")


def _is_local_environment(path: Path, root: Path) -> bool:
    """Virtuelle Umgebungen werden nicht als Release-Artefakte behandelt."""
    return any(
        part.startswith(EXCLUDED_DIR_PREFIXES) for part in path.relative_to(root).parts
    )


def clean(root: Path = ROOT) -> list[str]:
    removed: list[str] = []

    for pattern in FILE_GLOBS:
        for path in root.glob(pattern):
            if path.is_file():
                path.unlink()
                removed.append(str(path.relative_to(root)))

    for dirpath, dirnames, _filenames in os.walk(root):
        current = Path(dirpath)
        rel_parts = current.relative_to(root).parts
        if any(part.startswith(EXCLUDED_DIR_PREFIXES) for part in rel_parts):
            dirnames[:] = []
            continue

        dirnames[:] = [
            dirname
            for dirname in dirnames
            if not dirname.startswith(EXCLUDED_DIR_PREFIXES)
        ]

        for dirname in list(dirnames):
            if dirname not in DIR_NAMES:
                continue
            target = current / dirname
            shutil.rmtree(target)
            removed.append(str(target.relative_to(root)) + "/")
            dirnames.remove(dirname)

    backups = root / "data" / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    keep = backups / ".gitkeep"
    if not keep.exists():
        keep.write_text("", encoding="utf-8")

    return removed


def main() -> int:
    removed = clean()
    print(f"Bereinigt: {len(removed)} Artefakt(e)")
    for item in removed:
        print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
