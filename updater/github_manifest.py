from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional, Dict, Any


DEFAULT_MANIFEST_URL = "https://github.com/sloogy/Budgetmanager/releases/latest/download/latest.json"


@dataclass(frozen=True)
class Asset:
    url: str
    sha256: str
    type: str


@dataclass(frozen=True)
class Manifest:
    version: str
    release_tag: str
    channel: str
    assets: Dict[str, Asset]


def parse_manifest(data: Dict[str, Any]) -> Manifest:
    if not isinstance(data, dict):
        raise ValueError("Manifest ist kein JSON-Objekt")

    version = str(data.get("version", "")).strip()
    release_tag = str(data.get("release_tag", "")).strip()
    channel = str(data.get("channel", "stable")).strip()

    if not version or not release_tag:
        raise ValueError("Manifest fehlt: version oder release_tag")

    assets_raw = data.get("assets", {})
    if not isinstance(assets_raw, dict) or not assets_raw:
        raise ValueError("Manifest fehlt: assets")

    assets: Dict[str, Asset] = {}
    for key, val in assets_raw.items():
        if not isinstance(val, dict):
            continue
        url = str(val.get("url", "")).strip()
        sha256 = str(val.get("sha256", "")).strip()
        atype = str(val.get("type", ""))
        if url and sha256:
            assets[str(key)] = Asset(url=url, sha256=sha256.lower(), type=atype)

    if not assets:
        raise ValueError("Manifest enthält keine gültigen Assets")

    return Manifest(version=version, release_tag=release_tag, channel=channel, assets=assets)


def loads_manifest(text: str) -> Manifest:
    return parse_manifest(json.loads(text))
