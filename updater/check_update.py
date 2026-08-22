from __future__ import annotations

import logging
from pathlib import Path

from updater.common import (
    DEFAULT_MANIFEST_URL,
    asset_is_zip,
    cache_zip_path,
    current_exe_filename,
    detect_platform_key,
    download_file,
    enable_utf8_console,
    fetch_manifest,
    find_staged_root,
    is_newer,
    preferred_asset_keys,
    prune_other_staging,
    read_current_version,
    safe_extract_zip,
    sha256_file,
    staged_tree_sha256,
    staging_dir_for,
    update_target_exe_filename,
    validate_staged_payload,
    write_check_result,
    write_staged_marker,
)
from updater.manifest_signing import ManifestSignatureError

logger = logging.getLogger(__name__)


def main() -> int:
    enable_utf8_console()
    import sys

    gui_mode = "--gui" in sys.argv
    current = read_current_version()
    print(f"BudgetManager Updater\nAktuell: {current}")

    try:
        manifest = fetch_manifest(DEFAULT_MANIFEST_URL)
    except ManifestSignatureError as e:
        # Das Manifest kann erreichbar sein; hier ist die Vertrauenskette das
        # Problem. Eine pauschale Netzwerk-Meldung waere irrefuehrend.
        print(f"❌ Update-Sicherheitsprüfung fehlgeschlagen: {e}")
        if "Kein eingebetteter Update-Public-Key" in str(e):
            print(
                "   Diese installierte Version besitzt keinen Update-Vertrauensanker."
            )
            print(
                "   Bei v2.2.61 kann der offizielle Trust Bridge den Public Key einmalig"
            )
            print("   hinterlegen; danach kann diese Installation das signierte Update")
            print("   ohne Neuinstallation pruefen und einspielen.")
        write_check_result(
            {
                "available": False,
                "error": str(e),
                "error_type": "manifest_signature",
                "current": current,
            }
        )
        return 2
    except Exception as e:
        print(f"❌ Update-Manifest konnte nicht geladen werden: {e}")
        write_check_result(
            {
                "available": False,
                "error": str(e),
                "error_type": "manifest_fetch",
                "current": current,
            }
        )
        return 2

    platform_key = detect_platform_key()
    preferred_keys = preferred_asset_keys(platform_key)
    asset_key = next((key for key in preferred_keys if key in manifest.assets), "")
    asset = manifest.assets.get(asset_key) if asset_key else None
    if not asset:
        print(f"❌ Kein Asset im Manifest für Plattform '{platform_key}'")
        print(f"   Erwartete Keys: {', '.join(preferred_keys)}")
        write_check_result(
            {
                "available": False,
                "error": f"Kein Asset für Plattform {platform_key}",
                "current": current,
                "remote": manifest.version,
                "release_tag": manifest.release_tag,
                "asset_keys_tried": preferred_keys,
            }
        )
        return 3

    remote = manifest.version
    if not is_newer(remote, current):
        print(f"✓ Kein Update verfügbar (remote: {remote})")
        write_check_result(
            {
                "available": False,
                "current": current,
                "remote": remote,
                "release_tag": manifest.release_tag,
            }
        )
        return 0

    print(f"⬇️  Update verfügbar: {remote} (Tag: {manifest.release_tag or 'n/a'})")
    zip_path = cache_zip_path(remote)
    if asset.asset_type.strip().lower() == "installer":
        zip_path = zip_path.with_suffix(".exe")

    # Download
    try:
        print(f"Lade ({asset_key}/{asset.asset_type}): {asset.url}")
        download_file(asset.url, zip_path)
        print(f"✓ Download: {zip_path}")
    except Exception as e:
        print(f"❌ Download fehlgeschlagen: {e}")
        write_check_result(
            {
                "available": False,
                "error": f"Download fehlgeschlagen: {e}",
                "current": current,
                "remote": remote,
            }
        )
        return 4

    # Checksum – FAIL-CLOSED (Sicherheits-Härtung v2.0.36):
    # Ein Auto-Update darf nur mit nachgewiesener Integrität installiert werden.
    # Fehlt der SHA256 im Manifest, wird das Update abgelehnt statt blind
    # akzeptiert. Der GitHub-Build setzt für jedes Asset immer einen echten
    # SHA256 ein, daher blockiert das keine legitimen Releases.
    if asset.sha256:
        actual = sha256_file(zip_path)
        if actual.lower() != asset.sha256.lower():
            print("❌ SHA256 stimmt nicht!")
            print(f"  erwartet: {asset.sha256}")
            print(f"  erhalten: {actual}")
            write_check_result(
                {
                    "available": False,
                    "error": "SHA256 stimmt nicht",
                    "current": current,
                    "remote": remote,
                }
            )
            return 5
        print("✓ SHA256 OK")
    else:
        print("❌ Kein SHA256 im Manifest – Update aus Sicherheitsgründen abgelehnt")
        write_check_result(
            {
                "available": False,
                "error": "Kein SHA256 im Manifest – Update aus Sicherheitsgründen abgelehnt",
                "current": current,
                "remote": remote,
            }
        )
        return 5

    # Staging wird nach jedem frisch verifizierten Download komplett neu gebaut.
    # Vorhandene Inhalte duerfen niemals ungeprueft wiederverwendet werden.
    staging = staging_dir_for(remote)
    try:
        import shutil

        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True, exist_ok=True)
        asset_type = asset.asset_type.strip().lower()
        if asset_type == "installer":
            from urllib.parse import urlparse

            url_name = (
                Path(urlparse(asset.url).path).name
                or f"BudgetManager_Setup_{remote}.exe"
            )
            if not url_name.lower().endswith(".exe"):
                url_name = f"BudgetManager_Setup_{remote}.exe"
            shutil.copy2(zip_path, staging / url_name)
        elif asset_is_zip(asset.url, asset.asset_type):
            safe_extract_zip(zip_path, staging)
        else:
            if asset_key == "direct_windows_exe":
                target_name = current_exe_filename()
            else:
                target_name = update_target_exe_filename()
            target = staging / target_name
            shutil.copy2(zip_path, target)
            try:
                import os
                import stat

                os.chmod(
                    target,
                    os.stat(target).st_mode
                    | stat.S_IXUSR
                    | stat.S_IXGRP
                    | stat.S_IXOTH,
                )
            except Exception as e:
                logger.debug("chmod auf gestagete Binary fehlgeschlagen: %s", e)

        root = find_staged_root(staging)
        validate_staged_payload(root, asset.asset_type)
        # Die Marke traegt genau die Pruefsumme, die hier ueber den soeben
        # validierten Baum lief. Ohne sie berechnet write_staged_marker sie
        # selbst noch einmal - ueber einen Baum, der inzwischen ein anderer
        # sein kann, und mit einem zweiten vollen Lauf ueber alle Dateien.
        tree_hash = staged_tree_sha256(root)
        write_staged_marker(remote, manifest, asset, tree_sha256=tree_hash)
        print(f"✓ Staged und validiert: {staging}")
    except Exception as e:
        shutil.rmtree(staging, ignore_errors=True)
        print(f"❌ Vorbereiten (Staging) fehlgeschlagen: {e}")
        write_check_result(
            {
                "available": False,
                "error": f"Staging fehlgeschlagen: {e}",
                "current": current,
                "remote": remote,
            }
        )
        logger.exception("Staging fehlgeschlagen")
        return 6

    # Veraltete Staging-Ordner/Cache entfernen, damit der sichere Fallback in
    # apply_update (latest_staged_version) niemals eine alte, hoeher nummerierte
    # Version aufgreift und der Update-Ordner nicht unbegrenzt waechst. Die
    # lokalen Pfade respektieren ein etwaiges Monkeypatching in Tests.
    prune_other_staging(staging, zip_path)

    write_check_result(
        {
            "available": True,
            "staged": True,
            "current": current,
            "remote": remote,
            "staged_version": remote,
            "release_tag": manifest.release_tag,
            "asset_key": asset_key,
            "asset_type": asset.asset_type,
            "asset_url": asset.url,
        }
    )

    print("\nUpdate wurde vorbereitet.")
    if gui_mode:
        print("Das Update-Fenster schaltet die Installation jetzt frei.")
        print("Klicke auf Jetzt aktualisieren & neu starten und bestätige die Abfrage.")
    else:
        print(
            "Nächster Schritt: App schließen und Update anwenden: python main.py --apply-update"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
