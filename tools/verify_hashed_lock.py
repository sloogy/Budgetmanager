#!/usr/bin/env python3
"""Validiert BudgetManager-Lockfiles auf vollständige, exakte SHA-256-Pins."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

PIN_RE = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)")
HASH_RE = re.compile(r"--hash=sha256:([0-9a-f]{64})")


def parse_lock(path: Path) -> tuple[dict[str, tuple[str, set[str]]], list[str]]:
    errors: list[str] = []
    packages: dict[str, tuple[str, set[str]]] = {}
    current_name: str | None = None
    current_version = ""
    current_hashes: set[str] = set()

    def finish() -> None:
        nonlocal current_name, current_version, current_hashes
        if current_name is None:
            return
        if not current_hashes:
            errors.append(
                f"{path}: {current_name}=={current_version} ohne SHA-256-Hash"
            )
        key = current_name.lower().replace("_", "-")
        if key in packages:
            errors.append(f"{path}: doppelter Paket-Pin {current_name}")
        packages[key] = (current_version, set(current_hashes))
        current_name = None
        current_version = ""
        current_hashes = set()

    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("--only-binary"):
            continue
        match = PIN_RE.match(line)
        if match:
            finish()
            current_name, current_version = match.groups()
            current_hashes.update(HASH_RE.findall(line))
            continue
        if line.startswith("--hash="):
            if current_name is None:
                errors.append(f"{path}:{lineno}: Hash ohne vorherigen Paket-Pin")
            current_hashes.update(HASH_RE.findall(line))
            if not HASH_RE.search(line):
                errors.append(f"{path}:{lineno}: ungültiger oder nicht-SHA-256-Hash")
            continue
        if line == "\\":
            continue
        errors.append(f"{path}:{lineno}: nicht unterstützte/ungehashte Zeile: {line}")
    finish()
    if not packages:
        errors.append(f"{path}: keine Pakete gefunden")
    return packages, errors


def direct_names(path: Path) -> set[str]:
    result: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = PIN_RE.match(raw.strip())
        if match:
            result.add(match.group(1).lower().replace("_", "-"))
    return result


def validate(lock: Path, direct: Path | None = None) -> list[str]:
    packages, errors = parse_lock(lock)
    if direct:
        missing = sorted(direct_names(direct) - set(packages))
        errors.extend(f"{lock}: direkte Abhängigkeit fehlt: {name}" for name in missing)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("locks", nargs="*", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    pairs = {
        root / "requirements.lock": root / "requirements.in",
        root / "requirements-dev.lock": root / "requirements-dev.in",
        root / "requirements-build.lock": root / "requirements-build.in",
    }
    targets = args.locks or list(pairs)
    errors: list[str] = []
    for item in targets:
        path = item if item.is_absolute() else root / item
        errors.extend(validate(path, pairs.get(path)))
    if errors:
        print("Hash-Lock-Prüfung FEHLGESCHLAGEN")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Hash-Lock-Prüfung BESTANDEN: {len(targets)} Lockfile(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
