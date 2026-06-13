from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

from updater.common import (
    DEFAULT_MANIFEST_URL,
    asset_is_zip,
    cache_zip_path,
    current_exe_filename,
    detect_platform_key,
    download_file,
    enable_utf8_console,
    fetch_manifest,
    is_newer,
    read_current_version,
    sha256_file,
    safe_extract_zip,
    staging_dir_for,
    write_staged_marker,
    find_staged_root,
)


def main() -> int:
    enable_utf8_console()
    current = read_current_version()
    print(f"BudgetManager Updater (portable)\nAktuell: {current}")

    try:
        manifest = fetch_manifest(DEFAULT_MANIFEST_URL)
    except Exception as e:
        print(f"❌ Manifest nicht erreichbar: {e}")
        return 2

    platform_key = detect_platform_key()
    asset = manifest.assets.get(platform_key)
    if not asset:
        print(f"❌ Kein Asset im Manifest für Plattform '{platform_key}'")
        return 3

    remote = manifest.version
    if not is_newer(remote, current):
        print(f"✓ Kein Update verfügbar (remote: {remote})")
        return 0

    print(f"⬇️  Update verfügbar: {remote} (Tag: {manifest.release_tag or 'n/a'})")
    zip_path = cache_zip_path(remote)

    # Download
    try:
        print(f"Lade: {asset.url}")
        download_file(asset.url, zip_path)
        print(f"✓ Download: {zip_path}")
    except Exception as e:
        print(f"❌ Download fehlgeschlagen: {e}")
        return 4

    # Checksum
    if asset.sha256:
        actual = sha256_file(zip_path)
        if actual.lower() != asset.sha256.lower():
            print("❌ SHA256 stimmt nicht!")
            print(f"  erwartet: {asset.sha256}")
            print(f"  erhalten: {actual}")
            return 5
        print("✓ SHA256 OK")
    else:
        print("⚠️  Keine SHA256 im Manifest – Download wird ohne Integritätscheck akzeptiert")

    # Extract staging
    staging = staging_dir_for(remote)
    if staging.exists() and any(staging.iterdir()):
        # schon staged
        print(f"✓ Bereits staged: {staging}")
    else:
        try:
            staging.mkdir(parents=True, exist_ok=True)
            if asset_is_zip(asset.url, asset.asset_type):
                # ── ZIP-Asset: sicher entpacken ──
                safe_extract_zip(zip_path, staging)
                root = find_staged_root(staging)
                # Minimal sanity: muss irgendwas enthalten
                any_file = next(root.rglob("*"), None)
                if any_file is None:
                    print("❌ Staging leer – ZIP Inhalt unerwartet")
                    return 6
            else:
                # ── Rohe Binary (z.B. BudgetManager-windows.exe): NICHT
                #    entpacken. Direkt unter dem Ziel-Dateinamen ablegen,
                #    unter dem die App installiert ist (z.B. BudgetManager.exe).
                import shutil

                target_name = current_exe_filename()
                target = staging / target_name
                shutil.copy2(zip_path, target)
                # Unter Linux: Ausführbar-Bit setzen (geht unter Windows ins Leere)
                try:
                    import os
                    import stat

                    mode = os.stat(target).st_mode
                    os.chmod(target, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                except Exception as e:
                    logger.debug("chmod auf gestagete Binary fehlgeschlagen: %s", e)
                print(f"✓ Binary gestaged als: {target.name}")
            write_staged_marker(remote, manifest, asset)
            print(f"✓ Staged: {staging}")
        except Exception as e:
            print(f"❌ Vorbereiten (Staging) fehlgeschlagen: {e}")
            logger.exception("Staging fehlgeschlagen")
            return 6

    print("\nNächster Schritt:")
    print("1) App schließen")
    print("2) Update anwenden:  python -m updater.apply_update")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
