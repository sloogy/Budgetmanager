#!/usr/bin/env python3
"""Bereinigt den Source-Baum vor dem Packen eines Release-ZIPs.

Entfernt nur generierbare Laufzeit-/Testartefakte, keine Quell- oder Doku-Dateien.
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILE_GLOBS = [
    "data/backups/*.bmr",
    "data/*.log",
    "data/*crash*.log",
    "data/i18n_audit_report.txt",
    "*.log",
]
DIR_NAMES = {
    "__pycache__",
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
    return any(part.startswith(EXCLUDED_DIR_PREFIXES) for part in path.relative_to(root).parts)


def clean(root: Path = ROOT) -> list[str]:
    removed: list[str] = []

    for pattern in FILE_GLOBS:
        for path in root.glob(pattern):
            if path.is_file():
                path.unlink()
                removed.append(str(path.relative_to(root)))

    for path in sorted(root.rglob("*"), reverse=True):
        if _is_local_environment(path, root):
            continue
        if path.is_dir() and path.name in DIR_NAMES:
            shutil.rmtree(path)
            removed.append(str(path.relative_to(root)) + "/")

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
