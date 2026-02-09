from __future__ import annotations

import shutil
from pathlib import Path

from updater.common import (
    app_dir,
    backup_current_zip,
    find_staged_root,
    staging_dir_for,
    updates_dir,
)


EXCLUDE = (
    "data",        # DB, Settings, Backups
    "updates",     # update cache/backups behalten
    ".git",
    "__pycache__",
)


def read_marker(staging: Path) -> dict:
    marker = staging / "_update_marker.json"
    if marker.exists():
        import json
        return json.loads(marker.read_text(encoding="utf-8"))
    return {}


def latest_staged_version() -> str | None:
    staging_root = updates_dir() / "staging"
    if not staging_root.exists():
        return None
    versions = [p.name for p in staging_root.iterdir() if p.is_dir()]
    if not versions:
        return None
    # sortiert grob lexikographisch; Versionsvergleich erfolgt im Check
    versions.sort()
    return versions[-1]


def remove_paths(target: Path, exclude: tuple[str, ...]) -> None:
    """Entfernt alles im App-Ordner außer exclude."""
    for item in target.iterdir():
        if item.name in exclude:
            continue
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            try:
                item.unlink()
            except Exception:
                pass


def copy_new(src_root: Path, dst_root: Path, exclude: tuple[str, ...]) -> None:
    for item in src_root.iterdir():
        if item.name in exclude:
            continue
        dst = dst_root / item.name
        if item.is_dir():
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(item, dst)
        else:
            shutil.copy2(item, dst)


def main() -> int:
    v = latest_staged_version()
    if not v:
        print("❌ Kein staged Update gefunden. Erst ausführen: python -m updater.check_update")
        return 2

    staging_dir = staging_dir_for(v)
    if not staging_dir.exists():
        print(f"❌ Staging-Ordner fehlt: {staging_dir}")
        return 3

    src_root = find_staged_root(staging_dir)
    marker = read_marker(staging_dir)

    print("BudgetManager Updater (portable) – APPLY")
    print(f"App-Ordner: {app_dir()}")
    print(f"Staged Version: {v}")
    if marker.get("download_url"):
        print(f"Quelle: {marker.get('download_url')}")

    # Rollback-Backup (ZIP)
    backup_dir = updates_dir() / "backup"
    b = backup_current_zip(backup_dir, label=v, exclude_names=EXCLUDE)
    print(f"✓ Rollback-Backup erstellt: {b}")

    # Replace (ohne data/ und updates/)
    print("⟲ Ersetze Programmdateien (data/ bleibt bestehen)...")
    remove_paths(app_dir(), exclude=EXCLUDE)
    copy_new(src_root, app_dir(), exclude=EXCLUDE)

    print("✓ Update angewendet.")
    print("Starte die App jetzt neu.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
