#!/usr/bin/env python3
"""Erzeugt eine deterministische CycloneDX-SBOM aus einem Hash-Lockfile."""
from __future__ import annotations

import argparse
import json
import re
import uuid
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQ_RE = re.compile(r"^([A-Za-z0-9_.-]+)==([^\\\s;]+)")
HASH_RE = re.compile(r"--hash=sha256:([0-9a-fA-F]{64})")


def parse_hashed_lock(path: Path) -> list[dict]:
    components: list[dict] = []
    current: dict | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        match = REQ_RE.match(line)
        if match:
            name, version = match.groups()
            current = {
                "type": "library",
                "name": name,
                "version": version,
                "purl": f"pkg:pypi/{name.lower().replace('_', '-')}@{version}",
                "bom-ref": f"pkg:pypi/{name.lower().replace('_', '-')}@{version}",
                "hashes": [],
            }
            components.append(current)
        if current is not None:
            for digest in HASH_RE.findall(line):
                current["hashes"].append({"alg": "SHA-256", "content": digest.lower()})
    for component in components:
        component["hashes"] = sorted(
            {item["content"]: item for item in component["hashes"]}.values(),
            key=lambda item: item["content"],
        )
    if not components:
        raise ValueError(f"Keine gepinnten Komponenten in {path}")
    if any(not component["hashes"] for component in components):
        missing = [
            component["name"] for component in components if not component["hashes"]
        ]
        raise ValueError("Komponenten ohne Hash im Lockfile: " + ", ".join(missing))
    return sorted(components, key=lambda item: item["name"].lower())


def generate_sbom(lock_path: Path, out_path: Path, *, app_version: str) -> Path:
    components = parse_hashed_lock(lock_path)
    namespace = uuid.UUID("296d0934-bc5f-4a70-8aba-b4bd17a8be7d")
    serial = uuid.uuid5(
        namespace,
        f"BudgetManager:{app_version}:{lock_path.read_text(encoding='utf-8')}",
    )
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "timestamp": f"{date.today().isoformat()}T00:00:00Z",
            "component": {
                "type": "application",
                "name": "BudgetManager",
                "version": app_version,
                "bom-ref": f"BudgetManager@{app_version}",
            },
            "tools": {
                "components": [
                    {
                        "type": "application",
                        "name": "BudgetManager generate_sbom.py",
                        "version": "1",
                    }
                ]
            },
        },
        "components": components,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, default=ROOT / "requirements.lock")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    print(generate_sbom(args.lock, args.out, app_version=args.version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
