"""Manifest + SHA256 Generator für GitHub Releases.

Du nutzt das, wenn du ein neues Release-ZIP gebaut hast.

Beispiel (Windows + Linux ZIPs):

  python -m updater.generate_manifest \
    --version 3.0.5 \
    --release-tag v3.0.5 \
    --channel stable \
    --windows-zip dist/BudgetManager-v3.0.5-portable-windows.zip \
    --linux-zip dist/BudgetManager-v3.0.5-portable-linux.zip \
    --base-url https://github.com/sloogy/Budgetmanager/releases/download/v3.0.5 \
    --out latest.json

Danach lädst du die ZIP(s), latest.json und latest.json.sig als Release-Assets hoch.
Das Tool bricht ohne konfigurierte Ed25519-Schlüssel absichtlich ab.
Updater lädt dann automatisch latest.json über:
  .../releases/latest/download/latest.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from updater.common import enable_utf8_console, sha256_file
from updater.manifest_signing import sign_manifest_file

logger = logging.getLogger(__name__)


def _asset_entry(base_url: str, zip_path: Path) -> dict:
    return {
        "url": f"{base_url.rstrip('/')}/{zip_path.name}",
        "sha256": sha256_file(zip_path),
        "type": "portable-zip",
    }


def main() -> int:
    enable_utf8_console()
    p = argparse.ArgumentParser(
        description="Generate latest.json manifest for BudgetManager releases"
    )
    p.add_argument("--version", required=True, help="App version, e.g. 2.2.63")
    p.add_argument("--release-tag", required=True, help="Git tag, e.g. v2.2.63")
    p.add_argument(
        "--channel", default="stable", choices=["stable", "dev"], help="Update channel"
    )
    p.add_argument(
        "--base-url", required=True, help="Base download URL to the release/tag"
    )
    p.add_argument("--windows-zip", help="Path to Windows portable ZIP")
    p.add_argument("--linux-zip", help="Path to Linux portable ZIP")
    p.add_argument("--out", default="latest.json", help="Output filename")
    args = p.parse_args()

    assets = {}
    if args.windows_zip:
        wz = Path(args.windows_zip)
        if not wz.exists():
            raise SystemExit(f"Windows ZIP nicht gefunden: {wz}")
        assets["windows"] = _asset_entry(args.base_url, wz)

    if args.linux_zip:
        lz = Path(args.linux_zip)
        if not lz.exists():
            raise SystemExit(f"Linux ZIP nicht gefunden: {lz}")
        assets["linux"] = _asset_entry(args.base_url, lz)

    if not assets:
        raise SystemExit("Mindestens --windows-zip oder --linux-zip angeben")

    manifest = {
        "version": args.version,
        "release_tag": args.release_tag,
        "channel": args.channel,
        "assets": assets,
    }

    out = Path(args.out)
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    private_key = os.environ.get("UPDATE_SIGNING_PRIVATE_KEY_B64", "").strip()
    public_key = os.environ.get("UPDATE_SIGNING_PUBLIC_KEY_B64", "").strip()
    if not private_key or not public_key:
        out.unlink(missing_ok=True)
        raise SystemExit(
            "UPDATE_SIGNING_PRIVATE_KEY_B64 und UPDATE_SIGNING_PUBLIC_KEY_B64 "
            "müssen gesetzt sein; ein unsigniertes Manifest wird nicht erzeugt"
        )
    signature = sign_manifest_file(
        out,
        private_key_b64=private_key,
        expected_public_key_b64=public_key,
    )
    print(f"✓ Manifest geschrieben: {out.resolve()}")
    print(f"✓ Ed25519-Signatur geschrieben: {signature.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
