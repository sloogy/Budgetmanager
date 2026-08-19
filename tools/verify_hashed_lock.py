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


def direct_pins(path: Path, seen: set[Path] | None = None) -> dict[str, str]:
    """Liest direkte Pins einschließlich rekursiver ``-r``-Includes."""
    resolved = path.resolve()
    visited = seen if seen is not None else set()
    if resolved in visited:
        return {}
    visited.add(resolved)

    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("-r ") or line.startswith("--requirement "):
            included = line.split(maxsplit=1)[1]
            for name, version in direct_pins(path.parent / included, visited).items():
                current = result.get(name)
                if current is not None and current != version:
                    raise ValueError(
                        f"widersprüchliche direkte Pins für {name}: {current}, {version}"
                    )
                result[name] = version
            continue
        match = PIN_RE.match(line)
        if match:
            name = match.group(1).lower().replace("_", "-")
            version = match.group(2)
            current = result.get(name)
            if current is not None and current != version:
                raise ValueError(
                    f"widersprüchliche direkte Pins für {name}: {current}, {version}"
                )
            result[name] = version
    return result


def validate(lock: Path, direct: Path | None = None) -> list[str]:
    packages, errors = parse_lock(lock)
    if direct:
        try:
            expected = direct_pins(direct)
        except (OSError, ValueError) as exc:
            errors.append(f"{direct}: direkte Pins konnten nicht gelesen werden: {exc}")
            return errors
        missing = sorted(set(expected) - set(packages))
        errors.extend(f"{lock}: direkte Abhängigkeit fehlt: {name}" for name in missing)
        for name in sorted(set(expected) & set(packages)):
            actual_version = packages[name][0]
            if actual_version != expected[name]:
                errors.append(
                    f"{lock}: direkter Pin {name} ist {actual_version}, "
                    f"erwartet {expected[name]}"
                )
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
