#!/usr/bin/env python3
"""Release-Gate: prüft ein GENERIERTES latest.json auf Updater-Sicherheit.

Hintergrund (v2.2.29, RELEASE_GATE_RESYNC): Der frühere Workflow-Step
"Verify updater manifest stays updater-safe" ging beim Merge in den Step
"Build signed release assets, updater manifest and SBOM" auf, wodurch
tools/release_logic_audit_100.py fehlschlug und die explizite
Nach-Build-Verifikation des erzeugten Manifests entfiel. Dieses Werkzeug
stellt die Verifikation als eigenständiges, headless testbares Gate wieder
her (Defense-in-Depth zusätzlich zur By-Construction-Sicherheit von
tools/build_release_assets._write_latest_json).

Fail-closed-Prüfungen:
- Pflichtstruktur: app/channel/version/release_tag/assets vorhanden.
- Updater-Vertrag: assets.windows und assets.linux sind portable-zip und
  enden auf portable-windows.zip bzw. portable-linux.zip.
- Fallback-Assets portable_windows_zip / portable_linux_zip / portable_zip
  sind portable-zip.
- Optionale Installer-Assets haben exakt die Typen installer bzw.
  installer-zip (updater.check_update staget nur diese Typen korrekt).
- Verbotene Direkt-Binär-Keys (direct_windows_exe, direct_linux_binary)
  fehlen.
- Jedes Asset trägt eine https-URL und ein 64-stelliges Hex-sha256.
- Mit --signature: Signaturdatei existiert, ist nicht leer und wird mit
  einem vertrauenswürdigen Public Key (Env UPDATE_SIGNING_PUBLIC_KEY_B64
  oder eingebetteter Trusted Key) kryptografisch Ed25519-verifiziert.
  Fehlt der Public Key, schlägt das Release-Gate bewusst fehl.

Exit-Code 0 = PASS, 1 = FAIL (mit Klartextgrund auf stderr).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FORBIDDEN_ASSET_KEYS = ("direct_windows_exe", "direct_linux_binary")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Key -> (Pflicht?, erlaubter Typ, Pflicht-URL-Suffix oder None)
ASSET_CONTRACT: dict[str, tuple[bool, str, str | None]] = {
    "windows": (True, "portable-zip", "portable-windows.zip"),
    "linux": (True, "portable-zip", "portable-linux.zip"),
    "portable_windows_zip": (True, "portable-zip", "portable-windows.zip"),
    "portable_linux_zip": (True, "portable-zip", "portable-linux.zip"),
    "portable_zip": (True, "portable-zip", None),
    "windows_installer": (False, "installer", None),
    "windows_installer_zip": (False, "installer-zip", None),
}


class ManifestGateError(Exception):
    """Verstoß gegen den Updater-Manifest-Vertrag."""


def _fail(msg: str) -> None:
    raise ManifestGateError(msg)


def _check_asset(
    key: str, asset: object, allowed_type: str, suffix: str | None
) -> None:
    if not isinstance(asset, dict):
        _fail(f"Asset {key!r} ist kein Objekt")
    a_type = str(asset.get("type") or "")
    if a_type != allowed_type:
        _fail(f"Asset {key!r} hat Typ {a_type!r}, erwartet {allowed_type!r}")
    url = str(asset.get("url") or "")
    if not url.startswith("https://"):
        _fail(f"Asset {key!r} hat keine https-URL: {url!r}")
    if suffix is not None and not url.endswith(suffix):
        _fail(f"Asset {key!r} URL endet nicht auf {suffix!r}: {url!r}")
    sha = str(asset.get("sha256") or "").strip().lower()
    if not SHA256_RE.fullmatch(sha):
        _fail(f"Asset {key!r} hat kein gültiges sha256 (64 Hex): {sha!r}")


def verify_manifest_dict(manifest: object) -> None:
    """Prüft die Manifest-Struktur fail-closed. Raises ManifestGateError."""
    if not isinstance(manifest, dict):
        _fail("Manifest ist kein JSON-Objekt")
    for field in ("app", "channel", "version", "release_tag"):
        if not str(manifest.get(field) or "").strip():
            _fail(f"Pflichtfeld fehlt oder leer: {field!r}")
    assets = manifest.get("assets")
    if not isinstance(assets, dict) or not assets:
        _fail("assets fehlt oder ist leer")
    for bad in FORBIDDEN_ASSET_KEYS:
        if bad in assets:
            _fail(f"Verbotenes Direkt-Binär-Asset vorhanden: {bad!r}")
    for key, (required, allowed_type, suffix) in ASSET_CONTRACT.items():
        if key not in assets:
            if required:
                _fail(f"Pflicht-Asset fehlt: {key!r}")
            continue
        _check_asset(key, assets[key], allowed_type, suffix)
    unknown = sorted(set(assets) - set(ASSET_CONTRACT))
    if unknown:
        _fail(f"Unbekannte Asset-Keys (Vertrag erweitern statt raten): {unknown}")


def _verify_signature(manifest_path: Path, signature_path: Path) -> str:
    if not signature_path.is_file() or signature_path.stat().st_size == 0:
        _fail(f"Signaturdatei fehlt oder ist leer: {signature_path}")
    sig_bytes = signature_path.read_bytes().strip()
    manifest_bytes = manifest_path.read_bytes()

    from updater.manifest_signing import (
        ManifestSignatureError,
        verify_manifest_signature,
    )

    env_key = os.environ.get("UPDATE_SIGNING_PUBLIC_KEY_B64", "").strip()
    public_key = None
    if env_key:
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey,
            )

            public_key = Ed25519PublicKey.from_public_bytes(
                base64.b64decode(env_key, validate=True)
            )
        except Exception as exc:
            _fail(f"UPDATE_SIGNING_PUBLIC_KEY_B64 ist kein gültiger Key: {exc}")
    try:
        verify_manifest_signature(manifest_bytes, sig_bytes, public_key=public_key)
        return "Signatur kryptografisch verifiziert (Ed25519)"
    except ManifestSignatureError as exc:
        if public_key is not None:
            _fail(f"Manifest-Signatur ungültig: {exc}")
        if "Kein eingebetteter Update-Public-Key" in str(exc):
            _fail(
                "Kein vertrauenswürdiger Update-Public-Key verfügbar; "
                "Signaturprüfung kann nicht durchgeführt werden"
            )
        _fail(f"Manifest-Signatur ungültig: {exc}")
    raise AssertionError("unreachable")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verifiziert ein generiertes latest.json auf Updater-Sicherheit"
    )
    parser.add_argument("manifest", type=Path, help="Pfad zu latest.json")
    parser.add_argument(
        "--signature",
        type=Path,
        default=None,
        help="Pfad zu latest.json.sig (Pflichtprüfung, wenn angegeben)",
    )
    args = parser.parse_args(argv)

    try:
        if not args.manifest.is_file():
            _fail(f"Manifest-Datei fehlt: {args.manifest}")
        try:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _fail(f"Manifest nicht lesbar/parsebar: {exc}")
        verify_manifest_dict(manifest)
        sig_note = ""
        if args.signature is not None:
            sig_note = " | " + _verify_signature(args.manifest, args.signature)
        print(
            "Updater-Manifest-Gate BESTANDEN: "
            f"{args.manifest} (version={manifest.get('version')}){sig_note}"
        )
        return 0
    except ManifestGateError as exc:
        print(f"Updater-Manifest-Gate FEHLGESCHLAGEN: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
