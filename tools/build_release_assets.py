#!/usr/bin/env python3
"""Build GitHub Release assets for BudgetManager.

Erzeugt in einem sauberen Ausgabeordner:
- versionierte direkte Windows-/Linux-Binaries
- getrennte portable ZIPs fuer Windows und Linux mit stabilen Startnamen
- optional Windows-Installer-EXE und Installer-ZIP fuer SmartScreen/Browser-Blockaden
- latest.json fuer den In-App-Updater
- SHA256SUMS.txt fuer die manuelle Pruefung

Updater-Vertrag:
Die Manifest-Keys ``windows`` und ``linux`` bleiben portable ZIPs. Der Installer
ist ein separates Asset. Installer-Installationen duerfen den Key
``windows_installer`` bevorzugen; portable Fallbacks bleiben trotzdem erhalten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import zipfile
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_info import APP_NAME, APP_VERSION  # noqa: E402
from updater.manifest_signing import sign_manifest_file  # noqa: E402
from tools.generate_sbom import generate_sbom  # noqa: E402

WINDOWS_CANONICAL_EXE = "BudgetManager.exe"
LINUX_CANONICAL_BINARY = "BudgetManager"


def _die(message: str) -> None:
    raise SystemExit(message)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _first_existing(candidates: Iterable[Path]) -> Path | None:
    for path in candidates:
        if path.is_file():
            return path
    return None


def _find_windows_exe(build_dir: Path) -> Path:
    direct = _first_existing(
        [
            build_dir / WINDOWS_CANONICAL_EXE,
            build_dir / "BudgetManager-windows.exe",
            build_dir / "dist" / WINDOWS_CANONICAL_EXE,
            ROOT / "dist" / WINDOWS_CANONICAL_EXE,
        ]
    )
    if direct:
        return direct

    matches = sorted(build_dir.rglob("BudgetManager*.exe"))
    matches = [p for p in matches if "setup" not in p.name.lower()]
    if matches:
        return matches[0]
    _die(f"Windows-EXE nicht gefunden in: {build_dir}")


def _find_linux_binary(build_dir: Path) -> Path:
    direct = _first_existing(
        [
            build_dir / LINUX_CANONICAL_BINARY,
            build_dir / "BudgetManager-linux",
            build_dir / "dist" / LINUX_CANONICAL_BINARY,
            ROOT / "dist" / LINUX_CANONICAL_BINARY,
        ]
    )
    if direct:
        return direct

    matches = sorted(build_dir.rglob("BudgetManager*"))
    matches = [
        p
        for p in matches
        if p.is_file()
        and not p.name.lower().endswith((".exe", ".zip", ".txt", ".json"))
        and "setup" not in p.name.lower()
    ]
    if matches:
        return matches[0]
    _die(f"Linux-Binary nicht gefunden in: {build_dir}")


def _find_installer(build_dir: Path) -> Path | None:
    # GitHub Actions kann den Installer als BudgetManager_Setup.exe oder bereits
    # versioniert liefern. Das Release-Asset wird unten immer normalisiert.
    candidates = sorted(build_dir.rglob("BudgetManager_Setup*.exe"))
    return candidates[0] if candidates else None


def _copy_file(src: Path, dst: Path, executable: bool = False) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    if executable:
        try:
            mode = os.stat(dst).st_mode
            os.chmod(dst, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            pass


def _copy_bundle_contents(src_dir: Path, dst_dir: Path) -> None:
    """Kopiert einen PyInstaller-onedir-Bundle-Ordner ins portable Arbeitsverzeichnis."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    excluded_names = {
        "BudgetManager_Setup.exe",
        "BudgetManager_Setup.zip",
        "SHA256SUMS.txt",
        "latest.json",
    }
    for src in sorted(src_dir.rglob("*")):
        rel = src.relative_to(src_dir)
        if any(part.startswith("BudgetManager_Setup_") for part in rel.parts):
            continue
        if src.name in excluded_names:
            continue
        dst = dst_dir / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def _write_zip(zip_path: Path, src_dir: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(src_dir.rglob("*")):
            if path.is_dir():
                continue
            zf.write(path, path.relative_to(src_dir).as_posix())


def _write_windows_starter(path: Path) -> None:
    path.write_text(
        "@echo off\r\n"
        "setlocal EnableExtensions\r\n"
        'set "DIR=%~dp0"\r\n'
        "rem DPI/Scaling: System-Skalierung verwenden, Fractional Scaling nicht grob runden.\r\n"
        'set "QT_ENABLE_HIGHDPI_SCALING=1"\r\n'
        'set "QT_AUTO_SCREEN_SCALE_FACTOR=1"\r\n'
        'set "QT_SCALE_FACTOR_ROUNDING_POLICY=PassThrough"\r\n'
        f'if exist "%DIR%{WINDOWS_CANONICAL_EXE}" (\r\n'
        f'  start "" "%DIR%{WINDOWS_CANONICAL_EXE}"\r\n'
        "  exit /b 0\r\n"
        ")\r\n"
        f"echo {WINDOWS_CANONICAL_EXE} wurde nicht gefunden.\r\n"
        "pause\r\n"
        "exit /b 1\r\n",
        encoding="utf-8",
        newline="",
    )


def _write_linux_starter(path: Path) -> None:
    path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'DIR="$(cd "$(dirname "$0")" && pwd)"\n'
        "# DPI/Scaling: System-Skalierung verwenden, Fractional Scaling nicht grob runden.\n"
        'export QT_ENABLE_HIGHDPI_SCALING="${QT_ENABLE_HIGHDPI_SCALING:-1}"\n'
        'export QT_AUTO_SCREEN_SCALE_FACTOR="${QT_AUTO_SCREEN_SCALE_FACTOR:-1}"\n'
        'export QT_SCALE_FACTOR_ROUNDING_POLICY="${QT_SCALE_FACTOR_ROUNDING_POLICY:-PassThrough}"\n'
        f'chmod +x "$DIR/{LINUX_CANONICAL_BINARY}" 2>/dev/null || true\n'
        f'exec "$DIR/{LINUX_CANONICAL_BINARY}" "$@"\n',
        encoding="utf-8",
    )
    mode = os.stat(path).st_mode
    os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_portable_readme(path: Path, version: str, platform_name: str) -> None:
    start_hint = (
        "Doppelklick auf start-windows.cmd oder BudgetManager.exe"
        if platform_name == "windows"
        else "./start-linux.sh"
    )
    path.write_text(
        f"BudgetManager {version} — Portable {platform_name}\n"
        "=====================================\n\n"
        f"Start: {start_hint}\n\n"
        "Daten, Einstellungen und Backups werden in ./data/ gespeichert.\n"
        "Der Ordner ist portabel und kann z.B. auf einem USB-Stick liegen.\n\n"
        "Updater-Hinweis:\n"
        "Dieses ZIP ist absichtlich auch ein Update-Paket.\n"
        "Die ausführbare Datei hat deshalb den stabilen Namen BudgetManager.exe bzw. BudgetManager.\n"
        "Bitte diese Namen im ZIP nicht entfernen oder umbenennen.\n",
        encoding="utf-8",
    )


def _create_portable_windows_zip(
    out_dir: Path, version: str, windows_exe: Path
) -> Path:
    work = out_dir / "_portable_windows"
    if work.exists():
        shutil.rmtree(work)

    _copy_bundle_contents(windows_exe.parent, work)

    target_exe = work / WINDOWS_CANONICAL_EXE
    if not target_exe.is_file():
        _die(f"Windows-Bundle ohne stabilen Startnamen: {target_exe}")
    if not (work / "_internal").is_dir():
        _die("Windows-Bundle ohne _internal/ ist kein onedir-Build")

    (work / "data" / "backups").mkdir(parents=True, exist_ok=True)
    (work / "data" / ".keep").touch()
    (work / "data" / "backups" / ".keep").touch()
    _write_windows_starter(work / "start-windows.cmd")
    _write_portable_readme(work / "README.txt", version, "windows")
    zip_path = out_dir / f"BudgetManager-v{version}-portable-windows.zip"
    _write_zip(zip_path, work)
    shutil.rmtree(work)
    return zip_path


def _create_portable_linux_zip(out_dir: Path, version: str, linux_binary: Path) -> Path:
    work = out_dir / "_portable_linux"
    if work.exists():
        shutil.rmtree(work)

    _copy_bundle_contents(linux_binary.parent, work)

    target_binary = work / LINUX_CANONICAL_BINARY
    if not target_binary.is_file():
        _die(f"Linux-Bundle ohne stabilen Startnamen: {target_binary}")
    if not (work / "_internal").is_dir():
        _die("Linux-Bundle ohne _internal/ ist kein onedir-Build")
    try:
        mode = os.stat(target_binary).st_mode
        os.chmod(target_binary, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass

    (work / "data" / "backups").mkdir(parents=True, exist_ok=True)
    (work / "data" / ".keep").touch()
    (work / "data" / "backups" / ".keep").touch()
    _write_linux_starter(work / "start-linux.sh")
    _write_portable_readme(work / "README.txt", version, "linux")
    zip_path = out_dir / f"BudgetManager-v{version}-portable-linux.zip"
    _write_zip(zip_path, work)
    shutil.rmtree(work)
    return zip_path


def _create_installer_zip(
    out_dir: Path, version: str, installer_exe: Path
) -> tuple[Path, Path]:
    installer_name = f"BudgetManager_Setup_{version}.exe"
    normalized_installer = out_dir / installer_name
    _copy_file(installer_exe, normalized_installer, executable=False)

    readme = out_dir / "WINDOWS_DOWNLOAD_HINWEIS.txt"
    readme.write_text(
        "BudgetManager Windows-Download\n"
        "==============================\n\n"
        "Windows SmartScreen oder der Browser kann einen neuen, korrekt signierten Installer bis zum Aufbau von Reputation trotzdem warnend anzeigen.\n\n"
        "Empfohlen:\n"
        "1. ZIP herunterladen und entpacken.\n"
        "2. SHA256 aus SHA256SUMS.txt mit dem Download vergleichen.\n"
        "3. Installer starten. Falls SmartScreen erscheint: Weitere Informationen → Trotzdem ausführen.\n\n"
        "PowerShell-Prüfung:\n"
        f"Get-FileHash .\\{installer_name} -Algorithm SHA256\n",
        encoding="utf-8",
    )

    work = out_dir / "_installer_zip"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    shutil.copy2(normalized_installer, work / installer_name)
    shutil.copy2(readme, work / readme.name)
    zip_path = out_dir / f"BudgetManager_Setup_{version}.zip"
    _write_zip(zip_path, work)
    shutil.rmtree(work)
    readme.unlink(missing_ok=True)
    return normalized_installer, zip_path


def _asset(base_url: str, path: Path, asset_type: str) -> dict[str, str]:
    return {
        "type": asset_type,
        "url": f"{base_url.rstrip('/')}/{path.name}",
        "sha256": _sha256_file(path),
    }


def _write_latest_json(
    out_dir: Path,
    version: str,
    release_tag: str,
    base_url: str,
    portable_windows_zip: Path,
    portable_linux_zip: Path,
    installer_exe: Path | None,
    installer_zip: Path | None,
) -> Path:
    assets: dict[str, dict[str, str]] = {
        # Updater-Vertrag: Plattform-Keys bleiben portable ZIPs.
        "windows": _asset(base_url, portable_windows_zip, "portable-zip"),
        "linux": _asset(base_url, portable_linux_zip, "portable-zip"),
        # Explizite manuelle Download-/Fallback-Assets.
        "portable_windows_zip": _asset(base_url, portable_windows_zip, "portable-zip"),
        "portable_linux_zip": _asset(base_url, portable_linux_zip, "portable-zip"),
        # Kompatibilitaets-Fallback: Windows zeigt auf das Windows-ZIP.
        "portable_zip": _asset(base_url, portable_windows_zip, "portable-zip"),
    }
    if installer_exe is not None:
        # Muss exakt "installer" bleiben: updater.check_update behandelt nur
        # diesen Typ als Setup-EXE und staget ihn nicht als BudgetManager.exe.
        assets["windows_installer"] = _asset(base_url, installer_exe, "installer")
    if installer_zip is not None:
        assets["windows_installer_zip"] = _asset(
            base_url, installer_zip, "installer-zip"
        )

    manifest = {
        "app": APP_NAME,
        "channel": "stable",
        "version": version,
        "release_tag": release_tag,
        "assets": assets,
    }
    path = out_dir / "latest.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def _write_sha256sums(out_dir: Path, files: list[Path]) -> Path:
    sums = out_dir / "SHA256SUMS.txt"
    lines = [
        f"{_sha256_file(path)}  {path.name}"
        for path in sorted(files, key=lambda p: p.name)
    ]
    sums.write_text("\n".join(lines) + "\n", encoding="ascii")
    return sums


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build BudgetManager GitHub release assets"
    )
    parser.add_argument(
        "--version",
        default=APP_VERSION,
        help="Version, default from app_info.APP_VERSION",
    )
    parser.add_argument("--release-tag", help="Git tag, default v<version>")
    parser.add_argument(
        "--base-url", required=True, help="GitHub release download base URL"
    )
    parser.add_argument("--windows-build-dir", required=True, type=Path)
    parser.add_argument("--linux-build-dir", required=True, type=Path)
    parser.add_argument("--out-dir", default=Path("release_assets"), type=Path)
    parser.add_argument(
        "--require-installer",
        action="store_true",
        help="Fail if Windows installer EXE is missing",
    )
    parser.add_argument(
        "--signing-private-key-env",
        default="UPDATE_SIGNING_PRIVATE_KEY_B64",
        help="Environment variable containing the raw Ed25519 private key as Base64",
    )
    parser.add_argument(
        "--signing-public-key-env",
        default="UPDATE_SIGNING_PUBLIC_KEY_B64",
        help="Environment variable containing the matching public key as Base64",
    )
    args = parser.parse_args()

    version = str(args.version).lstrip("v")
    release_tag = args.release_tag or f"v{version}"
    out_dir = args.out_dir
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    windows_exe = _find_windows_exe(args.windows_build_dir)
    linux_binary = _find_linux_binary(args.linux_build_dir)
    installer_source = _find_installer(args.windows_build_dir)
    if args.require_installer and installer_source is None:
        _die(f"Windows-Installer wurde nicht gefunden in: {args.windows_build_dir}")

    portable_windows_zip = _create_portable_windows_zip(out_dir, version, windows_exe)
    portable_linux_zip = _create_portable_linux_zip(out_dir, version, linux_binary)

    installer_exe: Path | None = None
    installer_zip: Path | None = None
    if installer_source is not None:
        installer_exe, installer_zip = _create_installer_zip(
            out_dir, version, installer_source
        )

    latest = _write_latest_json(
        out_dir,
        version,
        release_tag,
        args.base_url,
        portable_windows_zip,
        portable_linux_zip,
        installer_exe,
        installer_zip,
    )

    private_key_b64 = os.environ.get(args.signing_private_key_env, "").strip()
    public_key_b64 = os.environ.get(args.signing_public_key_env, "").strip()
    if not private_key_b64 or not public_key_b64:
        _die(
            "Update-Signierschlüssel fehlen. Release-Manifeste werden niemals unsigned erzeugt."
        )
    latest_signature = sign_manifest_file(
        latest,
        private_key_b64=private_key_b64,
        expected_public_key_b64=public_key_b64,
    )
    sbom = generate_sbom(
        ROOT / "requirements.lock",
        out_dir / f"BudgetManager-v{version}.cdx.json",
        app_version=version,
    )

    files_for_sums = [
        portable_windows_zip,
        portable_linux_zip,
        latest,
        latest_signature,
        sbom,
    ]
    if installer_exe is not None:
        files_for_sums.append(installer_exe)
    if installer_zip is not None:
        files_for_sums.append(installer_zip)
    sums = _write_sha256sums(out_dir, files_for_sums)

    print("Release assets erzeugt:")
    for path in sorted(out_dir.iterdir()):
        if path.is_file():
            print(f"- {path}")
    print(f"SHA256: {sums}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
