"""Restore-Bundles (.bmr) für Backups und Austausch.

Ein .bmr ist technisch ein ZIP, das alles enthält um ein Backup in der App
einfach wiederherzustellen:

  - manifest.json (Metadaten + Checksummen)
  - database.enc oder database.db

Wichtig:
  - Der Restore-Key wird NIE im Bundle gespeichert.
  - Bei verschlüsselten DBs kann zum Öffnen ein Restore-Key nötig sein.
"""

from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

import hashlib
import json
import os
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class BundleManifest:
    created_at: str
    app: str
    app_version: str
    db_file: str
    encryption: str  # "enc" | "db"
    sha256: str
    note: str = ""
    has_settings: bool = False  # True wenn settings.json im Bundle
    has_users: bool = False     # True wenn users.json im Bundle


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def create_bundle(*,
                  source_db: Path,
                  out_path: Path,
                  app: str,
                  app_version: str,
                  note: str = "",
                  settings_path: Path | None = None,
                  users_json_path: Path | None = None) -> Path:
    """Erzeugt ein .bmr Restore-Bundle.

    source_db:        Pfad zur .db oder .enc
    out_path:         Zielpfad (.bmr)
    settings_path:    Optional – Pfad zur settings.json
    users_json_path:  Optional – Pfad zur users.json (Benutzerkonto-Daten)
    """

    source_db = Path(source_db)
    if not source_db.exists():
        raise FileNotFoundError(str(source_db))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Name im Bundle
    if source_db.suffix.lower() == ".enc":
        db_file = "database.enc"
        enc = "enc"
    else:
        db_file = "database.db"
        enc = "db"

    # Settings optional mitbackupen
    settings_file = Path(settings_path) if settings_path else None
    has_settings = settings_file is not None and settings_file.exists()

    # users.json optional mitbackupen
    users_file = Path(users_json_path) if users_json_path else None
    has_users = users_file is not None and users_file.exists()

    sha = _sha256_file(source_db)
    manifest = BundleManifest(
        created_at=datetime.now().isoformat(timespec="seconds"),
        app=app,
        app_version=app_version,
        db_file=db_file,
        encryption=enc,
        sha256=sha,
        note=note or "",
        has_settings=has_settings,
        has_users=has_users,
    )

    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink(missing_ok=True)

    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest.__dict__, indent=2, ensure_ascii=False))
        zf.write(source_db, arcname=db_file)
        if has_settings:
            zf.write(settings_file, arcname="settings.json")
            logger.debug("Settings in Backup aufgenommen: %s", settings_file)
        if has_users:
            zf.write(users_file, arcname="users.json")
            logger.debug("users.json in Backup aufgenommen: %s", users_file)

    os.replace(str(tmp), str(out_path))
    logger.info("Backup erstellt: %s (DB: %s, Settings: %s, Users: %s)",
                out_path.name, db_file, has_settings, has_users)
    return out_path

def extract_settings(bundle_path: Path, dest_path: Path) -> bool:
    """Extrahiert settings.json aus einem .bmr Bundle, falls vorhanden.

    Returns True wenn Settings erfolgreich extrahiert wurden.
    """
    bundle_path = Path(bundle_path)
    if not bundle_path.exists():
        return False
    try:
        with zipfile.ZipFile(bundle_path, "r") as zf:
            if "settings.json" not in zf.namelist():
                logger.debug("Kein settings.json in Bundle: %s", bundle_path.name)
                return False
            dest_path = Path(dest_path)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            data = zf.read("settings.json")
            dest_path.write_bytes(data)
            logger.info("Settings aus Backup wiederhergestellt: %s", dest_path)
            return True
    except Exception as e:
        logger.warning("extract_settings fehlgeschlagen: %s", e)
        return False


def bundle_has_settings(bundle_path: Path) -> bool:
    """Prüft ob ein .bmr Bundle eine settings.json enthält."""
    try:
        with zipfile.ZipFile(bundle_path, "r") as zf:
            return "settings.json" in zf.namelist()
    except Exception:
        return False


def extract_users(bundle_path: Path, dest_path: Path) -> bool:
    """Extrahiert users.json aus einem .bmr Bundle, falls vorhanden.

    Returns True wenn users.json erfolgreich extrahiert wurde.
    """
    bundle_path = Path(bundle_path)
    if not bundle_path.exists():
        return False
    try:
        with zipfile.ZipFile(bundle_path, "r") as zf:
            if "users.json" not in zf.namelist():
                logger.debug("Kein users.json in Bundle: %s", bundle_path.name)
                return False
            dest_path = Path(dest_path)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            data = zf.read("users.json")
            dest_path.write_bytes(data)
            logger.info("users.json aus Backup wiederhergestellt: %s", dest_path)
            return True
    except Exception as e:
        logger.warning("extract_users fehlgeschlagen: %s", e)
        return False


def bundle_has_users(bundle_path: Path) -> bool:
    """Prüft ob ein .bmr Bundle eine users.json enthält."""
    try:
        with zipfile.ZipFile(bundle_path, "r") as zf:
            return "users.json" in zf.namelist()
    except Exception:
        return False
