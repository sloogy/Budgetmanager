from __future__ import annotations

"""Gemeinsame Updater-Helfer.

Ziele:
- Portable (alles relativ zum App-Ordner)
- Funktioniert in DEV (python main.py) und in PyInstaller (EXE)
- SemVer sauber (packaging.version)
- Sichere ZIP-Extraktion (ZipSlip-Schutz)
"""

import hashlib
import json
import os
import shutil
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import requests
from packaging import version as _version


DEFAULT_MANIFEST_URL = "https://github.com/sloogy/Budgetmanager/releases/latest/download/latest.json"


@dataclass(frozen=True)
class AssetInfo:
    url: str
    sha256: str
    asset_type: str = "portable"


@dataclass(frozen=True)
class Manifest:
    version: str
    release_tag: str
    channel: str
    assets: Dict[str, AssetInfo]


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Ordner, in dem die App liegt (portable Root)."""
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    # DEV: Projekt-Root ist eine Ebene über updater/
    return Path(__file__).resolve().parents[1]


def updates_dir() -> Path:
    d = app_dir() / "updates"
    (d / "cache").mkdir(parents=True, exist_ok=True)
    (d / "staging").mkdir(parents=True, exist_ok=True)
    (d / "backup").mkdir(parents=True, exist_ok=True)
    return d


def detect_platform_key() -> str:
    """Key wie im Manifest: windows|linux."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    return "linux"


def read_current_version() -> str:
    """Liest die aktuelle Version aus app_info.APP_VERSION."""
    try:
        from app_info import APP_VERSION  # type: ignore

        return str(APP_VERSION)
    except Exception:
        p = app_dir() / "version.json"
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            return str(data.get("version", "0.0.0"))
        return "0.0.0"


def parse_manifest(data: dict) -> Manifest:
    assets: Dict[str, AssetInfo] = {}
    raw_assets = (data.get("assets") or {})
    if isinstance(raw_assets, dict):
        for platform_key, info in raw_assets.items():
            if not isinstance(info, dict):
                continue
            url = str(info.get("url", "")).strip()
            sha = str(info.get("sha256", "")).strip().lower()
            a_type = str(info.get("type", "portable")).strip() or "portable"
            if url:
                assets[str(platform_key)] = AssetInfo(url=url, sha256=sha, asset_type=a_type)

    return Manifest(
        version=str(data.get("version", "0.0.0")).strip(),
        release_tag=str(data.get("release_tag", "")).strip(),
        channel=str(data.get("channel", "stable")).strip(),
        assets=assets,
    )


def fetch_manifest(manifest_url: str = DEFAULT_MANIFEST_URL, timeout_s: int = 10) -> Manifest:
    r = requests.get(manifest_url, timeout=timeout_s)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise ValueError("Manifest ist kein JSON-Objekt")
    return parse_manifest(data)


def is_newer(remote_version: str, current_version: str) -> bool:
    """SemVer-Vergleich (robust)."""
    try:
        return _version.parse(remote_version) > _version.parse(current_version)
    except Exception:
        return remote_version.strip() != current_version.strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_file(url: str, dest: Path, timeout_s: int = 30) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout_s) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 128):
                if chunk:
                    f.write(chunk)


def safe_extract_zip(zip_path: Path, dest_dir: Path) -> None:
    """Extrahiert ZIP ohne ZipSlip (Pfad-Traversal)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        for member in z.infolist():
            if not member.filename:
                continue
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                continue
            target = (dest_dir / member_path).resolve()
            if not str(target).startswith(str(dest_dir.resolve())):
                continue
            z.extract(member, dest_dir)


def staging_dir_for(version_str: str) -> Path:
    return updates_dir() / "staging" / version_str


def cache_zip_path(version_str: str) -> Path:
    return updates_dir() / "cache" / f"update_{version_str}.zip"


def write_staged_marker(version_str: str, manifest: Manifest, asset: AssetInfo) -> Path:
    marker = staging_dir_for(version_str) / "_update_marker.json"
    payload = {
        "version": version_str,
        "release_tag": manifest.release_tag,
        "channel": manifest.channel,
        "download_url": asset.url,
        "sha256": asset.sha256,
        "staged_at": int(time.time()),
    }
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return marker


def find_staged_root(staging_dir: Path) -> Path:
    """Viele ZIPs enthalten einen Top-Level-Ordner. Wir finden den eigentlichen Root."""
    items = list(staging_dir.iterdir())
    if not items:
        return staging_dir
    dirs = [p for p in items if p.is_dir() and p.name not in {"__MACOSX"}]
    files = [p for p in items if p.is_file()]
    if len(dirs) == 1 and not files:
        return dirs[0]
    return staging_dir


def _zip_add_dir(zf: zipfile.ZipFile, src: Path, arc_base: Path, exclude_names: Tuple[str, ...]) -> None:
    for root, dirs, files in os.walk(src):
        root_p = Path(root)
        rel = root_p.relative_to(src)
        # keine Traversal in excluded dirs
        dirs[:] = [d for d in dirs if d not in exclude_names]
        for fn in files:
            if fn in exclude_names:
                continue
            s = root_p / fn
            arc = (arc_base / rel / fn).as_posix()
            zf.write(s, arc)


def backup_current_zip(backup_dir: Path, label: str, exclude_names: Tuple[str, ...]) -> Path:
    """Erstellt ein ZIP-Backup des aktuellen App-Ordners (Rollback).

    - exclude_names wird sowohl auf Top-Level als auch in der Tiefe respektiert.
    - Standard: data/ und updates/ werden vom Aufrufer ausgeschlossen.
    """
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = backup_dir / f"pre_update_{label}_{ts}.zip"
    root = app_dir()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _zip_add_dir(zf, root, arc_base=Path(root.name), exclude_names=exclude_names)
    return out
