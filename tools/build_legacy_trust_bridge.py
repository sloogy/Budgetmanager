#!/usr/bin/env python3
"""Erzeugt den einmaligen Windows-Trust-Bridge fuer alte BudgetManager-Builds.

BudgetManager 2.2.61 kann bereits einen externen Ed25519-Public-Key aus
``<InstallDir>/_internal/resources/update_signing_public_key.b64`` laden. Der
Bridge legt dort ausschliesslich den oeffentlichen Vertrauensanker ab und
startet danach den normalen, signaturpruefenden In-App-Updater.

Der private Signierschluessel wird hier niemals verwendet oder eingebettet.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import os
from pathlib import Path


def _validate_public_key(value: str) -> str:
    value = value.strip()
    if not value:
        raise SystemExit("UPDATE_SIGNING_PUBLIC_KEY_B64 fehlt")
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SystemExit(f"Update-Public-Key ist kein gueltiges Base64: {exc}") from exc
    if len(raw) != 32:
        raise SystemExit(
            f"Update-Public-Key muss 32 Bytes haben, erhalten: {len(raw)}"
        )
    return value


def render_bridge(public_key_b64: str) -> str:
    key = _validate_public_key(public_key_b64)
    return rf'''# BudgetManager v2.2.61 -> v2.2.67 Trust Bridge
# Einmalige Vertrauensanker-Nachruestung. Keine Neuinstallation, keine Nutzerdaten-Aenderung.
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\BudgetManager")
)

$ErrorActionPreference = "Stop"
$PublicKey = "{key}"

try {{
    $decoded = [Convert]::FromBase64String($PublicKey)
    if ($decoded.Length -ne 32) {{
        throw "Public Key hat nicht die erwarteten 32 Bytes."
    }}

    $exe = Join-Path $InstallDir "BudgetManager.exe"
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {{
        throw "BudgetManager.exe nicht gefunden: $exe`nFalls BudgetManager an einem anderen Ort installiert ist, starte:`n  powershell -NoProfile -ExecutionPolicy Bypass -File .\BudgetManager-v2.2.61-Trust-Bridge.ps1 -InstallDir 'C:\Pfad\zu\BudgetManager'"
    }}

    # v2.2.61 sucht diesen Pfad bereits selbst. Deshalb muss die alte EXE nicht
    # veraendert und die Signaturpruefung nicht abgeschaltet werden.
    $resourceDir = Join-Path $InstallDir "_internal\resources"
    $keyPath = Join-Path $resourceDir "update_signing_public_key.b64"
    New-Item -ItemType Directory -Force -Path $resourceDir | Out-Null

    if (Test-Path -LiteralPath $keyPath -PathType Leaf) {{
        $existing = (Get-Content -LiteralPath $keyPath -Raw).Trim()
        if ($existing -and $existing -ne $PublicKey) {{
            throw "Abbruch: In der Installation liegt bereits ein anderer Update-Public-Key. Dieser wird aus Sicherheitsgruenden nicht ueberschrieben: $keyPath"
        }}
    }}

    [IO.File]::WriteAllText(
        $keyPath,
        $PublicKey + [Environment]::NewLine,
        [Text.Encoding]::ASCII
    )

    $written = (Get-Content -LiteralPath $keyPath -Raw).Trim()
    if ($written -ne $PublicKey) {{
        throw "Der Public Key konnte nicht korrekt geschrieben/verifiziert werden."
    }}

    Write-Host ""
    Write-Host "BudgetManager Trust Bridge" -ForegroundColor Cyan
    Write-Host "OK: Update-Public-Key wurde hinterlegt:" -ForegroundColor Green
    Write-Host "    $keyPath"
    Write-Host ""
    Write-Host "Jetzt wird der normale signierte BudgetManager-Updater gestartet."
    Write-Host "Die vorhandene Installation und deine Nutzerdaten bleiben erhalten."

    Start-Process -FilePath $exe -ArgumentList @("--check-update", "--gui")
    exit 0
}}
catch {{
    Write-Host ""
    Write-Host "Trust Bridge fehlgeschlagen:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Read-Host "Enter zum Schliessen"
    exit 1
}}
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--public-key",
        default=os.environ.get("UPDATE_SIGNING_PUBLIC_KEY_B64", ""),
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    script = render_bridge(args.public_key)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(script, encoding="utf-8", newline="\r\n")
    print(f"Legacy Trust Bridge erzeugt: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
