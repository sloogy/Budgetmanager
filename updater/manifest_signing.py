"""Ed25519-Vertrauensanker für den Update-Manifest-Download.

Das Release enthält ``latest.json`` und die detached Signatur
``latest.json.sig``. Die App vertraut nur einem beim Build eingebetteten
öffentlichen Ed25519-Schlüssel. Fehlt Schlüssel oder Signatur, wird das Update
fail-closed abgelehnt.
"""

from __future__ import annotations

import base64
import binascii
import os
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

PUBLIC_KEY_FILENAME = "update_signing_public_key.b64"
SIGNATURE_SUFFIX = ".sig"


class ManifestSignatureError(ValueError):
    """Manifest-Signatur fehlt, ist ungültig oder nicht vertrauenswürdig."""


def _decode_exact_base64(
    value: str | bytes, *, expected_bytes: int, label: str
) -> bytes:
    raw = value.encode("ascii") if isinstance(value, str) else bytes(value)
    try:
        decoded = base64.b64decode(raw.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ManifestSignatureError(f"{label} ist kein gültiges Base64") from exc
    if len(decoded) != expected_bytes:
        raise ManifestSignatureError(
            f"{label} muss {expected_bytes} Bytes enthalten, erhalten: {len(decoded)}"
        )
    return decoded


def public_key_candidates() -> tuple[Path, ...]:
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "resources" / PUBLIC_KEY_FILENAME)
    executable_dir = Path(sys.executable).resolve().parent
    candidates.extend(
        [
            executable_dir / "resources" / PUBLIC_KEY_FILENAME,
            executable_dir / "_internal" / "resources" / PUBLIC_KEY_FILENAME,
            Path(__file__).resolve().parents[1] / "resources" / PUBLIC_KEY_FILENAME,
        ]
    )
    seen: set[Path] = set()
    result: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return tuple(result)


def load_trusted_public_key() -> Ed25519PublicKey:
    env_value = os.environ.get("BUDGETMANAGER_UPDATE_PUBLIC_KEY_B64", "").strip()
    if env_value:
        return Ed25519PublicKey.from_public_bytes(
            _decode_exact_base64(
                env_value, expected_bytes=32, label="Update-Public-Key"
            )
        )

    for path in public_key_candidates():
        if path.is_file():
            return Ed25519PublicKey.from_public_bytes(
                _decode_exact_base64(
                    path.read_bytes(), expected_bytes=32, label=str(path)
                )
            )
    raise ManifestSignatureError(
        "Kein eingebetteter Update-Public-Key gefunden; Update wird abgelehnt"
    )


def verify_manifest_signature(
    manifest_bytes: bytes,
    signature_bytes: bytes,
    *,
    public_key: Ed25519PublicKey | None = None,
) -> None:
    signature = _decode_exact_base64(
        signature_bytes, expected_bytes=64, label="Manifest-Signatur"
    )
    key = public_key or load_trusted_public_key()
    try:
        key.verify(signature, manifest_bytes)
    except InvalidSignature as exc:
        raise ManifestSignatureError("Manifest-Signatur ist ungültig") from exc


def private_key_from_base64(value: str | bytes) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(
        _decode_exact_base64(value, expected_bytes=32, label="Update-Private-Key")
    )


def sign_manifest_bytes(manifest_bytes: bytes, private_key: Ed25519PrivateKey) -> bytes:
    return base64.b64encode(private_key.sign(manifest_bytes)) + b"\n"


def public_key_base64(private_key: Ed25519PrivateKey) -> str:
    raw = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(raw).decode("ascii")


def sign_manifest_file(
    manifest_path: Path,
    *,
    private_key_b64: str,
    signature_path: Path | None = None,
    expected_public_key_b64: str = "",
) -> Path:
    manifest = Path(manifest_path)
    key = private_key_from_base64(private_key_b64)
    if expected_public_key_b64:
        expected = _decode_exact_base64(
            expected_public_key_b64,
            expected_bytes=32,
            label="erwarteter Update-Public-Key",
        )
        actual = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        if actual != expected:
            raise ManifestSignatureError(
                "Update-Private-Key passt nicht zum konfigurierten Public-Key"
            )
    out = signature_path or Path(str(manifest) + SIGNATURE_SUFFIX)
    out.write_bytes(sign_manifest_bytes(manifest.read_bytes(), key))
    return out
