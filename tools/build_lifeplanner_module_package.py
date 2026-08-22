from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda value: value.as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(path.stat().st_size.to_bytes(8, "big"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def sign(data: bytes, private_key_b64: str) -> bytes:
    raw = base64.b64decode(private_key_b64.strip(), validate=True)
    if len(raw) != 32:
        raise ValueError(
            "LIFEPLANNER_UPDATE_PRIVATE_KEY_B64 muss einen 32-Byte-Ed25519-Schlüssel enthalten."
        )
    return (
        base64.b64encode(Ed25519PrivateKey.from_private_bytes(raw).sign(data)) + b"\n"
    )


def build(
    dist_dir: Path,
    runtime_directory: str,
    module_json: Path,
    output: Path,
    requires_host: str,
) -> Path:
    private_key = os.environ.get("LIFEPLANNER_UPDATE_PRIVATE_KEY_B64", "").strip()
    if not private_key:
        raise RuntimeError(
            "LIFEPLANNER_UPDATE_PRIVATE_KEY_B64 fehlt; Remote-Module müssen signiert sein."
        )
    manifest = json.loads(module_json.read_text(encoding="utf-8"))
    module_id = str(manifest["id"])
    name = str(manifest["name"])
    version = str(manifest["version"])
    if not dist_dir.is_dir():
        raise FileNotFoundError(f"PyInstaller-Ausgabe fehlt: {dist_dir}")
    with tempfile.TemporaryDirectory(prefix="lifeplanner-module-") as temp_name:
        payload = Path(temp_name) / "payload"
        payload.mkdir(parents=True)
        shutil.copy2(module_json, payload / "module.json")
        shutil.copytree(dist_dir, payload / runtime_directory)
        metadata = {
            "schema": "lifeplanner.component.v1",
            "id": module_id,
            "name": name,
            "version": version,
            "kind": "module",
            "requires_host": requires_host,
            "description": str(manifest.get("description", "")),
            "platforms": ["windows-x86_64"],
            "payload_sha256": tree_sha256(payload),
            "created_at": datetime.now(UTC).isoformat(),
        }
        metadata_bytes = (
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            archive.writestr("component.json", metadata_bytes)
            archive.writestr("component.json.sig", sign(metadata_bytes, private_key))
            for path in sorted(payload.rglob("*"), key=lambda value: value.as_posix()):
                if path.is_file():
                    archive.write(path, Path("payload") / path.relative_to(payload))
    with zipfile.ZipFile(output, "r") as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Erzeugtes Modulpaket ist beschädigt: {bad}")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n", encoding="ascii"
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Baut ein signiertes LifePlanner-.lpmodule aus einem Modul-Repository."
    )
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--runtime-directory", required=True)
    parser.add_argument("--module-json", type=Path, default=Path("module.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--requires-host", default=">=0.5.0")
    args = parser.parse_args()
    result = build(
        args.dist,
        args.runtime_directory,
        args.module_json,
        args.output,
        args.requires_host,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
