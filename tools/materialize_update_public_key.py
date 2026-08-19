#!/usr/bin/env python3
"""Materialisiert den Build-Vertrauensanker aus einer CI-Variable."""
from __future__ import annotations

import argparse
import base64
import binascii
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--value",
        default=os.environ.get("UPDATE_SIGNING_PUBLIC_KEY_B64", ""),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "resources" / "update_signing_public_key.b64",
    )
    args = parser.parse_args()
    value = args.value.strip()
    if not value:
        raise SystemExit(
            "UPDATE_SIGNING_PUBLIC_KEY_B64 fehlt. Release-Build wird fail-closed beendet."
        )
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SystemExit(f"Update-Public-Key ist kein gültiges Base64: {exc}") from exc
    if len(raw) != 32:
        raise SystemExit(f"Update-Public-Key muss 32 Bytes haben, erhalten: {len(raw)}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(value + "\n", encoding="ascii")
    print(f"Update-Vertrauensanker materialisiert: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
