#!/usr/bin/env python3
"""Build a signed LifePlanner ``.lpmodule`` from a PyInstaller onedir output."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(rel).to_bytes(4, "big"))
        digest.update(rel)
        digest.update(path.stat().st_size.to_bytes(8, "big"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def sign(data: bytes, key_b64: str) -> bytes:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    raw = base64.b64decode(key_b64.strip(), validate=True)
    if len(raw) != 32:
        raise SystemExit(
            "LIFEPLANNER_UPDATE_PRIVATE_KEY_B64 must contain a 32-byte Ed25519 key"
        )
    return (
        base64.b64encode(Ed25519PrivateKey.from_private_bytes(raw).sign(data)) + b"\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--runtime-name", required=True)
    parser.add_argument(
        "--platform", required=True, choices=["windows-x86_64", "linux-x86_64"]
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--requires-host", default=">=0.5.0")
    parser.add_argument("--allow-unsigned", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "module.json").read_text(encoding="utf-8"))
    runtime = args.runtime_dir.resolve()
    if not runtime.is_dir():
        raise SystemExit(f"runtime directory missing: {runtime}")
    with tempfile.TemporaryDirectory(prefix="lpmodule-") as temp_name:
        payload = Path(temp_name) / "payload"
        payload.mkdir()
        shutil.copy2(root / "module.json", payload / "module.json")
        shutil.copytree(runtime, payload / args.runtime_name)
        metadata = {
            "schema": "lifeplanner.component.v1",
            "id": manifest["id"],
            "name": manifest.get("name", manifest["id"]),
            "version": manifest["version"],
            "kind": "module",
            "requires_host": args.requires_host,
            "description": manifest.get("description", ""),
            "platforms": [args.platform],
            "payload_sha256": tree_sha256(payload),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        metadata_bytes = (
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        key = os.environ.get("LIFEPLANNER_UPDATE_PRIVATE_KEY_B64", "").strip()
        if not key and not args.allow_unsigned:
            raise SystemExit(
                "LIFEPLANNER_UPDATE_PRIVATE_KEY_B64 missing; remote module releases must be signed"
            )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(
            args.output, "w", zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            archive.writestr("component.json", metadata_bytes)
            if key:
                archive.writestr("component.json.sig", sign(metadata_bytes, key))
            for path in sorted(payload.rglob("*"), key=lambda p: p.as_posix()):
                if path.is_file():
                    archive.write(path, Path("payload") / path.relative_to(payload))
    with zipfile.ZipFile(args.output, "r") as archive:
        damaged = archive.testzip()
        if damaged:
            raise SystemExit(f"Erzeugtes Modulpaket ist beschädigt: {damaged}")
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    checksum_path = args.output.with_suffix(args.output.suffix + ".sha256")
    checksum_path.write_text(f"{digest}  {args.output.name}\n", encoding="ascii")
    print(args.output)
    print(checksum_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
