from __future__ import annotations

"""Leichte Update-Pruefung fuer den App-Start.

Dieses Modul prueft nur das kleine Release-Manifest. Es laedt keine EXE,
keinen Installer und kein ZIP herunter und schreibt auch kein normales
``last_check.json``. Dadurch bleibt der eigentliche Installationspfad erst
nach aktiver Nutzerbestaetigung im Update-Dialog scharf.
"""

import logging

logger = logging.getLogger(__name__)

from updater.common import (
    DEFAULT_MANIFEST_URL,
    clear_startup_check_result,
    detect_platform_key,
    enable_utf8_console,
    fetch_manifest,
    is_newer,
    preferred_asset_keys,
    read_current_version,
    write_startup_check_result,
)


def main() -> int:
    enable_utf8_console()
    current = read_current_version()
    clear_startup_check_result()

    try:
        manifest = fetch_manifest(DEFAULT_MANIFEST_URL, timeout_s=5)
    except Exception as exc:
        # Beim Start darf fehlendes Internet nie stoeren. Fehler wird nur
        # strukturiert abgelegt und geloggt.
        logger.debug("Startup-Update-Pruefung fehlgeschlagen: %s", exc)
        write_startup_check_result({
            "available": False,
            "error": str(exc),
            "current": current,
            "downloaded": False,
            "staged": False,
        })
        return 2

    platform_key = detect_platform_key()
    preferred_keys = preferred_asset_keys(platform_key)
    asset_key = next((key for key in preferred_keys if key in manifest.assets), "")
    asset = manifest.assets.get(asset_key) if asset_key else None
    remote = manifest.version

    if not asset:
        write_startup_check_result({
            "available": False,
            "error": f"Kein Asset fuer Plattform {platform_key}",
            "current": current,
            "remote": remote,
            "release_tag": manifest.release_tag,
            "asset_keys_tried": preferred_keys,
            "downloaded": False,
            "staged": False,
        })
        return 3

    available = is_newer(remote, current)
    write_startup_check_result({
        "available": bool(available),
        "current": current,
        "remote": remote,
        "release_tag": manifest.release_tag,
        "channel": manifest.channel,
        "asset_key": asset_key,
        "asset_type": asset.asset_type,
        "asset_url": asset.url,
        "downloaded": False,
        "staged": False,
    })

    if available:
        print(f"Update verfuegbar: {remote} ({asset_key}/{asset.asset_type})")
    else:
        print(f"Kein Update verfuegbar (aktuell: {current}, remote: {remote})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
