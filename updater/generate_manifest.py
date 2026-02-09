from __future__ import annotations

"""Manifest + SHA256 Generator für GitHub Releases.

Du nutzt das, wenn du ein neues Release-ZIP gebaut hast.

Beispiel (Windows + Linux ZIPs):

  python -m updater.generate_manifest \
    --version 0.2.0.4 \
    --release-tag v0.2.0.4 \
    --channel stable \
    --windows-zip dist/BudgetManager_PORTABLE_WINDOWS.zip \
    --linux-zip dist/BudgetManager_PORTABLE_LINUX.zip \
    --base-url https://github.com/<user>/<repo>/releases/download/v0.2.0.4 \
    --out latest.json

Danach lädst du die ZIP(s) + latest.json als Release-Assets hoch.
Updater lädt dann automatisch latest.json über:
  .../releases/latest/download/latest.json
"""

import argparse
import json
from pathlib import Path

from updater.common import sha256_file


def _asset_entry(base_url: str, zip_path: Path) -> dict:
    return {
        "url": f"{base_url.rstrip('/')}/{zip_path.name}",
        "sha256": sha256_file(zip_path),
        "type": "portable",
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Generate latest.json manifest for BudgetManager releases")
    p.add_argument("--version", required=True, help="App version, e.g. 0.2.0.4")
    p.add_argument("--release-tag", required=True, help="Git tag, e.g. v0.2.0.4")
    p.add_argument("--channel", default="stable", choices=["stable", "dev"], help="Update channel")
    p.add_argument("--base-url", required=True, help="Base download URL to the release/tag")
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
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"✓ Manifest geschrieben: {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
