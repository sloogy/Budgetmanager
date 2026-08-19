#!/usr/bin/env python3
"""Erzeugt lokal ein Ed25519-Schlüsselpaar für Update-Manifeste.

Der private Schlüssel darf nie committed oder als Release-Artefakt hochgeladen
werden. Er gehört als GitHub Secret ``UPDATE_SIGNING_PRIVATE_KEY_B64`` in das
Repository. Der Public-Key gehört als GitHub Variable
``UPDATE_SIGNING_PUBLIC_KEY_B64`` hinein.
"""
from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=Path("update-signing-key"))
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    private_raw = private_key.private_bytes(
        Encoding.Raw, PrivateFormat.Raw, NoEncryption()
    )
    public_raw = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    private_path = args.out_dir / "UPDATE_SIGNING_PRIVATE_KEY_B64.txt"
    public_path = args.out_dir / "UPDATE_SIGNING_PUBLIC_KEY_B64.txt"
    private_path.write_text(
        base64.b64encode(private_raw).decode("ascii") + "\n", encoding="ascii"
    )
    public_path.write_text(
        base64.b64encode(public_raw).decode("ascii") + "\n", encoding="ascii"
    )
    try:
        os.chmod(private_path, 0o600)
        os.chmod(public_path, 0o644)
    except OSError:
        pass
    print(f"Private Secret: {private_path}")
    print(f"Public Variable: {public_path}")
    print("Private Datei nach Eintragen in GitHub Secrets sicher löschen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
