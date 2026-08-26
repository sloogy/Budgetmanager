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

import hashlib
import hmac
import json
import logging
import os
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# Harte Grenzen gelten sowohl beim Erstellen als auch beim Prüfen/Entpacken.
MAX_SETTINGS_BYTES = 5 * 1024 * 1024
MAX_USERS_BYTES = 5 * 1024 * 1024
MAX_MANIFEST_BYTES = 1 * 1024 * 1024
MAX_DB_BYTES = 4 * 1024 * 1024 * 1024
MAX_BUNDLE_COMPRESSION_RATIO = 500
MIN_RATIO_CHECK_BYTES = 16 * 1024 * 1024

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_ALLOWED_MEMBERS = frozenset(
    {"manifest.json", "database.enc", "database.db", "settings.json", "users.json"}
)


@dataclass
class BundleManifest:
    created_at: str
    app: str
    app_version: str
    db_file: str
    encryption: str  # "enc" | "db"
    sha256: str
    source_db_name: str = ""  # Originaldateiname, z.B. christian.enc
    note: str = ""
    has_settings: bool = False  # True wenn settings.json im Bundle
    has_users: bool = False  # True wenn users.json im Bundle
    settings_sha256: str = ""
    users_sha256: str = ""


def _secure_bundle_file(path: Path) -> None:
    """0600 auf Backup-Dateien. Auf FAT/Windows folgenlos.

    Scheitern darf das, schweigen nicht: Eine Sicherung traegt denselben
    Datenbestand wie die Datenbank. Blieb sie offen liegen, war das bis
    Loop 25 nirgends zu sehen.
    """
    try:
        from model.file_permissions import secure_file

        secure_file(path)
    except Exception as fehler:  # nie fatal, aber nie stumm
        logger.warning(
            "Zugriffsrechte auf %s nicht gesetzt - die Sicherung bleibt offen: %s",
            path,
            fehler,
        )


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fsync_directory(path: Path) -> None:
    """Persistiert einen Verzeichniseintrag best-effort auf POSIX."""
    if os.name == "nt":
        return
    try:
        fd = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as fehler:
        # Nicht alle Dateisysteme/Container erlauben fsync auf Verzeichnissen.
        # Kein Grund abzubrechen - aber ohne fsync ist nicht garantiert, dass
        # der Verzeichniseintrag einen Stromausfall ueberlebt.
        logger.debug("fsync auf %s nicht moeglich: %s", path, fehler)


def atomic_copy_verified(
    source: Path, destination: Path, *, expected_sha256: str | None = None
) -> Path:
    """Kopiert eine Datei absturzsicher und installiert sie erst nach Prüfung.

    Bei Schreibfehler, vollem Datenträger oder fehlenden Rechten bleibt eine
    bestehende Zieldatei unangetastet. Die temporäre Datei wird vor
    ``os.replace`` geflusht, gehasht und mit restriktiven Rechten versehen.
    """
    source = Path(source)
    destination = Path(destination)
    if not source.is_file():
        raise FileNotFoundError(str(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    before = source.stat()
    tmp = destination.with_name(
        f".{destination.name}.restore_tmp_{os.getpid()}_"
        f"{datetime.now().strftime('%H%M%S%f')}"
    )
    digest = hashlib.sha256()
    written = 0
    try:
        with source.open("rb") as src, tmp.open("xb") as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
                digest.update(chunk)
                written += len(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        after = source.stat()
        if (
            written != before.st_size
            or after.st_size != before.st_size
            or after.st_mtime_ns != before.st_mtime_ns
        ):
            raise OSError("Quelldatei hat sich während des Restore-Kopierens verändert")
        actual = digest.hexdigest()
        expected = str(expected_sha256 or "").strip().lower()
        if expected and not hmac.compare_digest(actual, expected):
            raise BundleIntegrityError(
                "Restore-Kopie stimmt nicht mit der erwarteten "
                "SHA-256-Prüfsumme überein"
            )
        _secure_bundle_file(tmp)
        os.replace(str(tmp), str(destination))
        _secure_bundle_file(destination)
        _fsync_directory(destination.parent)
        return destination
    finally:
        tmp.unlink(missing_ok=True)


def _read_small_file(path: Path, limit: int, label: str) -> bytes:
    size = path.stat().st_size
    if size > limit:
        raise ValueError(f"{label} ist mit {size} Bytes unplausibel gross")
    data = path.read_bytes()
    if len(data) > limit:
        raise ValueError(f"{label} ueberschreitet das Limit von {limit} Bytes")
    return data


def _account_users_snapshot(users_file: Path, source_db: Path) -> bytes | None:
    """Erzeugt ein selbstkonsistentes Konto-Snapshot fuer genau diese DB.

    ``users.json`` kann mehrere Konten enthalten, ein .bmr aber nur eine
    Datenbank. Die komplette Benutzerliste mitzunehmen wuerde beim Restore
    Konten ohne zugehoerige DB erzeugen. Deshalb wird nur der Eintrag gesichert,
    dessen ``db_filename`` zur gesicherten Datenbank passt.
    """
    raw_bytes = _read_small_file(users_file, MAX_USERS_BYTES, "users.json")
    try:
        raw = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"users.json ist unlesbar: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("users"), list):
        raise ValueError("users.json hat kein gueltiges Benutzerlisten-Format")

    source_name = source_db.name
    source_key = source_name.casefold()
    matching = []
    for entry in raw["users"]:
        if not isinstance(entry, dict):
            continue
        db_filename = Path(str(entry.get("db_filename") or "")).name
        if db_filename.casefold() == source_key:
            matching.append(entry)
    if not matching:
        logger.warning(
            "users.json enthaelt keinen Eintrag fuer %s; "
            "Konto-Metadaten werden nicht gesichert",
            source_name,
        )
        return None
    if len(matching) != 1:
        raise ValueError(f"users.json enthaelt mehrere Konten fuer {source_name}")

    snapshot = dict(raw)
    snapshot["users"] = matching
    data = (json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if len(data) > MAX_USERS_BYTES:
        raise ValueError("Konto-Snapshot ueberschreitet das users.json-Limit")
    return data


def merge_user_snapshot_bytes(
    existing_bytes: bytes | None,
    incoming_bytes: bytes,
    *,
    source_db_name: str,
) -> bytes:
    """Führt ein einzelnes Konto-Backup sicher mit lokalen Konten zusammen.

    Ein vollständiger Konto-Restore darf nicht alle bereits vorhandenen lokalen
    Konten löschen. Ein identisches Konto (gleicher Benutzername UND gleiche
    DB-Datei) wird ersetzt. Teilkollisionen werden fail-closed abgelehnt, weil
    sie sonst ein fremdes Konto oder dessen Datenbank unbemerkt überschreiben
    könnten.
    """

    def _decode(data: bytes, label: str) -> dict:
        if len(data) > MAX_USERS_BYTES:
            raise ValueError(f"{label} ueberschreitet das users.json-Limit")
        try:
            raw = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{label} ist unlesbar: {exc}") from exc
        if not isinstance(raw, dict) or not isinstance(raw.get("users"), list):
            raise ValueError(f"{label} hat kein gueltiges Benutzerlisten-Format")
        if any(not isinstance(entry, dict) for entry in raw["users"]):
            raise ValueError(f"{label} enthaelt einen ungueltigen Kontoeintrag")
        return raw

    incoming_raw = _decode(incoming_bytes, "Backup-users.json")
    source_key = Path(source_db_name).name.casefold()
    incoming_matches = [
        entry
        for entry in incoming_raw["users"]
        if isinstance(entry, dict)
        and Path(str(entry.get("db_filename") or "")).name.casefold() == source_key
    ]
    if len(incoming_matches) != 1:
        raise ValueError(
            "Das Konto-Backup enthaelt nicht genau ein zur Datenbank passendes Konto"
        )

    incoming = dict(incoming_matches[0])
    username = str(incoming.get("username") or "").strip()
    db_filename = Path(str(incoming.get("db_filename") or "")).name
    if not username or not db_filename:
        raise ValueError("Das Konto-Backup enthaelt unvollstaendige Kontodaten")
    incoming["db_filename"] = db_filename
    username_key = username.casefold()
    db_key = db_filename.casefold()

    if existing_bytes is None:
        merged = dict(incoming_raw)
        merged["users"] = [incoming]
    else:
        existing_raw = _decode(existing_bytes, "Lokale users.json")
        existing_users = [dict(entry) for entry in existing_raw["users"]]
        seen_usernames: set[str] = set()
        seen_databases: set[str] = set()
        for entry in existing_users:
            existing_username = str(entry.get("username") or "").strip().casefold()
            existing_db = Path(str(entry.get("db_filename") or "")).name.casefold()
            if not existing_username or not existing_db:
                raise ValueError(
                    "Lokale users.json enthaelt unvollstaendige Kontodaten"
                )
            if existing_username in seen_usernames or existing_db in seen_databases:
                raise ValueError("Lokale users.json enthaelt doppelte Kontozuordnungen")
            seen_usernames.add(existing_username)
            seen_databases.add(existing_db)
        retained: list[dict] = []
        replaced_existing_default = False
        for entry in existing_users:
            existing_username = str(entry.get("username") or "").strip().casefold()
            existing_db = Path(str(entry.get("db_filename") or "")).name.casefold()
            same_username = (
                bool(existing_username) and existing_username == username_key
            )
            same_db = bool(existing_db) and existing_db == db_key
            if same_username or same_db:
                if not (same_username and same_db):
                    raise ValueError(
                        "Konto-Kollision: Benutzername oder Datenbankdatei ist bereits "
                        "einem anderen lokalen Konto zugeordnet"
                    )
                replaced_existing_default = bool(entry.get("is_default", False))
                continue
            retained.append(entry)

        # Auf einer bestehenden Mehrkonto-Installation darf ein importiertes
        # Konto nicht ungefragt den Standard übernehmen. Beim Ersetzen des
        # bisherigen Standardkontos bleibt dessen Rolle dagegen erhalten.
        if retained and not replaced_existing_default:
            incoming["is_default"] = False
        elif replaced_existing_default:
            incoming["is_default"] = True

        merged = dict(existing_raw)
        merged["users"] = retained + [incoming]

    result = (json.dumps(merged, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if len(result) > MAX_USERS_BYTES:
        raise ValueError("Zusammengefuehrte users.json ist unplausibel gross")
    return result


def _wal_consistent_snapshot(source_db: Path) -> Path | None:
    """Konsistente Kopie der DB inklusive noch nicht ausgecheckpointetem WAL.

    Warum die SQLite-Backup-API und nicht ``PRAGMA wal_checkpoint``: Der
    Checkpoint schreibt in die produktive .db-Datei und braucht dafuer kurz
    exklusiven Zugriff. Haelt irgendein Leser die Datei gerade, meldet er nur
    "busy" zurueck - das Bundle waere dann wieder veraltet, ohne dass es
    auffaellt. ``Connection.backup()`` liest stattdessen einen konsistenten
    Stand heraus, ohne das Original anzufassen. Denselben Weg geht
    ``views/backup_restore_dialog.py`` bereits fuer die Gegenrichtung.

    Rueckgabe: Pfad der Momentaufnahme (der Aufrufer loescht sie) oder
    ``None``, wenn die Datei keine lesbare SQLite-DB ist - dann bleibt es beim
    bisherigen Verhalten und die rohe Datei wandert ins Bundle.
    """
    import sqlite3

    snapshot = source_db.with_name(source_db.name + ".snapshot_tmp")
    snapshot.unlink(missing_ok=True)
    src: sqlite3.Connection | None = None
    dst: sqlite3.Connection | None = None
    try:
        # Die Handles muessen VOR dem Aufraeumen zu sein, nicht erst danach:
        # Windows verweigert das Loeschen einer Datei, auf der noch ein
        # offenes Handle liegt (WinError 32). Deshalb schliesst das innere
        # finally, und erst das aeussere except loescht.
        try:
            src = sqlite3.connect(str(source_db), timeout=10.0)
            dst = sqlite3.connect(str(snapshot))
            src.backup(dst)
            dst.commit()
        finally:
            for conn in (dst, src):
                if conn is not None:
                    conn.close()
    except (sqlite3.Error, OSError) as exc:
        # sqlite3.DatabaseError trifft jede Quelle, die gar keine SQLite-Datei
        # ist (verschluesselte oder fremde Altbestaende). Das ist kein Fehler,
        # sondern der vorgesehene Rueckfall auf die reine Dateikopie.
        logger.warning(
            "WAL-konsistente Momentaufnahme nicht moeglich (%s) - es wird die "
            "Datei selbst gesichert: %s",
            exc,
            source_db.name,
        )
        try:
            snapshot.unlink(missing_ok=True)
        except OSError as aufraeum_exc:
            # Das Bundle entsteht trotzdem - aus der Quelldatei selbst. Eine
            # liegengebliebene Zwischendatei ist ein Aufraeumproblem, kein
            # Grund, die Sicherung scheitern zu lassen.
            logger.warning(
                "Zwischendatei der Momentaufnahme liess sich nicht entfernen: %s",
                aufraeum_exc,
            )
        return None
    # Die Momentaufnahme enthaelt dieselben Daten wie das Original und darf
    # deshalb genauso wenig world-readable sein.
    _secure_bundle_file(snapshot)
    return snapshot


def create_bundle(
    *,
    source_db: Path,
    out_path: Path,
    app: str,
    app_version: str,
    note: str = "",
    settings_path: Path | None = None,
    users_json_path: Path | None = None,
) -> Path:
    """Erzeugt ein .bmr Restore-Bundle.

    source_db:        Pfad zur .db oder .enc
    out_path:         Zielpfad (.bmr)
    settings_path:    Optional – Pfad zur settings.json
    users_json_path:  Optional – Pfad zur users.json (Benutzerkonto-Daten)
    """

    source_db = Path(source_db)
    if not source_db.exists():
        raise FileNotFoundError(str(source_db))
    if source_db.stat().st_size > MAX_DB_BYTES:
        raise ValueError("Datenbank ist fuer ein Backup unplausibel gross")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Name im Bundle
    if source_db.suffix.lower() == ".enc":
        db_file = "database.enc"
        enc = "enc"
    else:
        db_file = "database.db"
        enc = "db"

    # Settings optional mitbackupen und mit eigener Pruefsumme absichern.
    settings_file = Path(settings_path) if settings_path else None
    settings_bytes = (
        _read_small_file(settings_file, MAX_SETTINGS_BYTES, "settings.json")
        if settings_file is not None and settings_file.exists()
        else None
    )
    has_settings = settings_bytes is not None

    # users.json optional mitbackupen. Bei mehreren lokalen Konten kommt nur
    # der zur gesicherten DB passende Eintrag ins Bundle.
    users_file = Path(users_json_path) if users_json_path else None
    users_bytes = (
        _account_users_snapshot(users_file, source_db)
        if users_file is not None and users_file.exists()
        else None
    )
    has_users = users_bytes is not None

    # WAL-konsistente Momentaufnahme statt der rohen Datei. Die App haelt
    # ihre Connection waehrend des Backups offen und aktiv, und
    # model/database.py schaltet fuer jede Datei-DB WAL ein: Die zuletzt
    # committeten Transaktionen stehen dann noch in budgetmanager.db-wal und
    # nicht in budgetmanager.db. Ohne diesen Schritt landete ein veralteter
    # Stand im Bundle - und weil die Pruefsumme im Manifest genau zu dieser
    # veralteten Datei passt, faellt es weder beim Erstellen noch beim
    # spaeteren verify_bundle auf.
    snapshot = _wal_consistent_snapshot(source_db) if enc == "db" else None
    payload = snapshot if snapshot is not None else source_db

    try:
        sha = _sha256_file(payload)
        manifest = BundleManifest(
            created_at=datetime.now().isoformat(timespec="seconds"),
            app=app,
            app_version=app_version,
            db_file=db_file,
            encryption=enc,
            sha256=sha,
            source_db_name=source_db.name,
            note=note or "",
            has_settings=has_settings,
            has_users=has_users,
            settings_sha256=(
                _sha256_bytes(settings_bytes) if settings_bytes is not None else ""
            ),
            users_sha256=(
                _sha256_bytes(users_bytes) if users_bytes is not None else ""
            ),
        )

        tmp = out_path.with_suffix(out_path.suffix + ".tmp")
        tmp.unlink(missing_ok=True)

        try:
            with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(
                    "manifest.json",
                    json.dumps(manifest.__dict__, indent=2, ensure_ascii=False),
                )
                zf.write(payload, arcname=db_file)
                if settings_bytes is not None:
                    zf.writestr("settings.json", settings_bytes)
                    logger.debug("Settings in Backup aufgenommen: %s", settings_file)
                if users_bytes is not None:
                    zf.writestr("users.json", users_bytes)
                    logger.debug(
                        "Passender Konto-Eintrag aus users.json in Backup aufgenommen: %s",
                        users_file,
                    )

            # Das gerade erzeugte Bundle vor der Installation selbst verifizieren.
            # So kann weder ein Teilarchiv noch ein fehlerhaftes Manifest als Backup
            # erscheinen, falls Schreiben/Komprimieren unerwartet schiefging.
            verify_bundle(tmp)

            # SICHERHEIT (v2.2.11): Ein Bundle enthaelt die DB und ggf. users.json
            # (mit db_key bei Quick-Konten). Nicht world-readable ablegen.
            _secure_bundle_file(tmp)
            os.replace(str(tmp), str(out_path))
            _secure_bundle_file(out_path)
        finally:
            tmp.unlink(missing_ok=True)
    finally:
        if snapshot is not None:
            snapshot.unlink(missing_ok=True)

    logger.info(
        "Backup erstellt: %s (DB: %s, Settings: %s, Users: %s)",
        out_path.name,
        db_file,
        has_settings,
        has_users,
    )
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
            verify_open_bundle(zf)
            if "settings.json" not in zf.namelist():
                logger.debug("Kein settings.json in Bundle: %s", bundle_path.name)
                return False
            dest_path = Path(dest_path)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            data = _read_limited(zf, "settings.json", MAX_SETTINGS_BYTES)
            tmp = dest_path.with_suffix(dest_path.suffix + ".restore_tmp")
            try:
                with open(tmp, "wb") as fh:
                    fh.write(data)
                    fh.flush()
                    os.fsync(fh.fileno())
                _secure_bundle_file(tmp)
                os.replace(tmp, dest_path)
                _secure_bundle_file(dest_path)
            finally:
                tmp.unlink(missing_ok=True)
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
            verify_open_bundle(zf)
            if "users.json" not in zf.namelist():
                logger.debug("Kein users.json in Bundle: %s", bundle_path.name)
                return False
            dest_path = Path(dest_path)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            data = _read_limited(zf, "users.json", MAX_USERS_BYTES)
            tmp = dest_path.with_suffix(dest_path.suffix + ".restore_tmp")
            try:
                with open(tmp, "wb") as fh:
                    fh.write(data)
                    fh.flush()
                    os.fsync(fh.fileno())
                _secure_bundle_file(tmp)
                os.replace(tmp, dest_path)
                _secure_bundle_file(dest_path)
            finally:
                tmp.unlink(missing_ok=True)
            logger.info("users.json aus Backup wiederhergestellt: %s", dest_path)
            return True
    except Exception as e:
        logger.warning("extract_users fehlgeschlagen: %s", e)
        return False


def bundle_user_security_modes(bundle_path: Path) -> set[str]:
    """Liest die Sicherheitsarten aus einer enthaltenen users.json.

    Rückgabe z. B. {"quick"}, {"password"} oder leer, wenn keine users.json
    enthalten ist oder sie nicht gelesen werden kann. Der Restore-Key wird dadurch
    nicht ersetzt; die Info dient nur für UI-Warnungen und Tests.
    """
    try:
        with zipfile.ZipFile(Path(bundle_path), "r") as zf:
            if "users.json" not in zf.namelist():
                return set()
            raw = json.loads(
                _read_limited(zf, "users.json", MAX_USERS_BYTES).decode("utf-8")
            )
            modes: set[str] = set()
            for entry in raw.get("users", []):
                sec = str(dict(entry).get("security", "")).strip()
                if sec:
                    modes.add(sec)
            return modes
    except Exception as exc:
        logger.debug("bundle_user_security_modes fehlgeschlagen: %s", exc)
        return set()


def bundle_has_users(bundle_path: Path) -> bool:
    """Prüft ob ein .bmr Bundle eine users.json enthält."""
    try:
        with zipfile.ZipFile(bundle_path, "r") as zf:
            return "users.json" in zf.namelist()
    except Exception:
        return False


# ── Sicherheit: Integritaet & Groessenlimits (v2.2.11) ────────────────────
#
# Das Manifest enthielt schon immer den SHA256 der Quell-DB, aber niemand hat
# ihn je geprueft. Ein manipuliertes oder halb uebertragenes .bmr wurde
# kommentarlos ueber die aktive Datenbank gespielt.
#
# Zusaetzlich werden Groessen begrenzt: Ein .bmr ist ein ZIP, und ein ZIP kann
# beim Entpacken um Groessenordnungen wachsen ("Zip-Bomb"). Die kleinen
# Metadateien haben harte Obergrenzen, die DB eine grosszuegige.


class BundleIntegrityError(Exception):
    """Das Bundle ist beschaedigt, manipuliert oder unplausibel gross."""


class LegacyBundleIntegrityError(BundleIntegrityError):
    """Altes Bundle ohne kryptografisch prüfbare SHA-256-Integrität."""


def _member_size(zf: zipfile.ZipFile, name: str) -> int:
    try:
        return int(zf.getinfo(name).file_size)
    except KeyError:
        return 0


def _read_limited(zf: zipfile.ZipFile, name: str, limit: int) -> bytes:
    """Liest ein Member, aber nur bis ``limit`` Bytes (Zip-Bomb-Schutz).

    Prueft zuerst die deklarierte Groesse und liest dann hart begrenzt: ein
    geloegener Header darf nicht ausreichen, um den Speicher zu fluten.
    """
    declared = _member_size(zf, name)
    if declared > limit:
        raise BundleIntegrityError(
            f"{name}: {declared} Bytes ueberschreiten das Limit von {limit} Bytes"
        )
    with zf.open(name, "r") as fh:
        data = fh.read(limit + 1)
    if len(data) > limit:
        raise BundleIntegrityError(
            f"{name}: entpackte Groesse ueberschreitet {limit} Bytes"
        )
    return data


def read_member_limited(zf: zipfile.ZipFile, name: str, limit: int) -> bytes:
    """Oeffentliche, hart begrenzte Lesefunktion fuer verifizierte Bundles."""
    return _read_limited(zf, name, limit)


def copy_member_limited(
    zf: zipfile.ZipFile, name: str, destination: Path, limit: int
) -> int:
    """Streamt ein ZIP-Member mit harter Obergrenze in eine Datei.

    Anders als ``zf.read()`` bleibt der Speicherbedarf konstant, auch wenn ein
    grosses, aber gueltiges Datenbank-Backup wiederhergestellt wird.
    """
    declared = _member_size(zf, name)
    if declared > limit:
        raise BundleIntegrityError(
            f"{name}: {declared} Bytes ueberschreiten das Limit von {limit} Bytes"
        )
    destination = Path(destination)
    written = 0
    with zf.open(name, "r") as source, open(destination, "wb") as target:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > limit:
                raise BundleIntegrityError(
                    f"{name}: entpackte Groesse ueberschreitet {limit} Bytes"
                )
            target.write(chunk)
        target.flush()
        os.fsync(target.fileno())
    return written


def _member_sha256(zf: zipfile.ZipFile, name: str, limit: int) -> str:
    declared = _member_size(zf, name)
    if declared > limit:
        raise BundleIntegrityError(
            f"{name}: {declared} Bytes ueberschreiten das Limit von {limit} Bytes"
        )
    digest = hashlib.sha256()
    total = 0
    with zf.open(name, "r") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise BundleIntegrityError(
                    f"{name}: entpackte Groesse ueberschreitet {limit} Bytes"
                )
            digest.update(chunk)
    return digest.hexdigest()


def _read_manifest_from_zip(zf: zipfile.ZipFile) -> dict:
    """Liest das Manifest aus genau dem bereits geöffneten Archiv.

    Das vermeidet einen zweiten Dateizugriff während einer laufenden Prüfung
    (TOCTOU): Manifest und Nutzdaten stammen garantiert aus demselben ZIP-Handle.
    """
    if "manifest.json" not in zf.namelist():
        raise BundleIntegrityError("manifest.json fehlt")
    raw = _read_limited(zf, "manifest.json", MAX_MANIFEST_BYTES)
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise BundleIntegrityError(f"manifest.json unlesbar: {e}") from e
    if not isinstance(manifest, dict):
        raise BundleIntegrityError("manifest.json hat kein Objekt")
    return manifest


def read_manifest(bundle_path: Path) -> dict:
    """Liest und validiert das Manifest eines .bmr."""
    with zipfile.ZipFile(Path(bundle_path), "r") as zf:
        return _read_manifest_from_zip(zf)


def read_manifest_from_zip(zf: zipfile.ZipFile) -> dict:
    """Öffentliche Variante für Aufrufer, die das Archiv bereits geöffnet haben."""
    return _read_manifest_from_zip(zf)


def resolve_db_member(zf: zipfile.ZipFile, manifest: dict) -> str:
    """Ermittelt den DB-Eintrag im Bundle – ausschliesslich aus der Whitelist."""
    names = set(zf.namelist())
    candidate = str(manifest.get("db_file") or "").strip()
    if candidate not in _ALLOWED_MEMBERS or candidate not in names:
        candidate = ""
    if not candidate:
        for fallback in ("database.enc", "database.db"):
            if fallback in names:
                candidate = fallback
                break
    if not candidate:
        raise BundleIntegrityError("Keine Datenbankdatei im Bundle")
    return candidate


def _validated_sha256(value: object, label: str) -> str:
    candidate = str(value or "").strip().lower()
    if candidate and not _SHA256_RE.fullmatch(candidate):
        raise BundleIntegrityError(f"{label} ist keine gueltige SHA-256-Pruefsumme")
    return candidate


def _verify_open_bundle_impl(
    zf: zipfile.ZipFile, *, allow_legacy_without_hash: bool = False
) -> str:
    """Prüft ein bereits geöffnetes Bundle und gibt sein DB-Member zurück."""
    member_names = zf.namelist()
    if len(member_names) != len(set(member_names)):
        raise BundleIntegrityError("Doppelte Dateinamen im Backup-Archiv")
    bad = zf.testzip()
    if bad is not None:
        raise BundleIntegrityError(f"Beschaedigter Eintrag im Archiv: {bad}")

    names = set(member_names)
    unexpected = names - _ALLOWED_MEMBERS
    if unexpected:
        raise BundleIntegrityError(
            "Unerwartete Dateien im Backup: " + ", ".join(sorted(unexpected))
        )

    db_members = names & {"database.enc", "database.db"}
    if len(db_members) != 1:
        raise BundleIntegrityError("Backup muss genau eine Datenbankdatei enthalten")

    for info in zf.infolist():
        if info.compress_size <= 0 or info.file_size < MIN_RATIO_CHECK_BYTES:
            continue
        if info.file_size / info.compress_size > MAX_BUNDLE_COMPRESSION_RATIO:
            raise BundleIntegrityError(
                f"Auffaellige Kompressionsrate im Backup: {info.filename}"
            )

    manifest = _read_manifest_from_zip(zf)
    db_member = resolve_db_member(zf, manifest)
    encryption = str(manifest.get("encryption") or "").strip().lower()
    expected_encryption = "enc" if db_member.endswith(".enc") else "db"
    if encryption and encryption != expected_encryption:
        raise BundleIntegrityError(
            "Manifest und Datenbank-Verschluesselungsart widersprechen sich"
        )

    expected = _validated_sha256(manifest.get("sha256"), "Datenbank-Pruefsumme")
    if not expected:
        if not allow_legacy_without_hash:
            raise LegacyBundleIntegrityError(
                "Backup ohne SHA-256-Prüfsumme wird standardmässig abgelehnt"
            )
        logger.warning("Legacy-Modus ausdrücklich bestätigt; Backup ohne SHA256")
    else:
        actual = _member_sha256(zf, db_member, MAX_DB_BYTES)
        if not hmac.compare_digest(actual, expected):
            raise BundleIntegrityError(
                "Pruefsumme stimmt nicht – Backup beschaedigt oder veraendert"
            )

    optional_members = (
        ("settings.json", "has_settings", "settings_sha256", MAX_SETTINGS_BYTES),
        ("users.json", "has_users", "users_sha256", MAX_USERS_BYTES),
    )
    for name, flag_name, hash_name, limit in optional_members:
        present = name in names
        declared = bool(manifest.get(flag_name, False))
        if present != declared:
            raise BundleIntegrityError(
                f"Manifest-Angabe {flag_name} passt nicht zum Archiv"
            )
        if not present:
            continue
        optional_expected = _validated_sha256(
            manifest.get(hash_name), f"Pruefsumme fuer {name}"
        )
        if not optional_expected:
            if allow_legacy_without_hash:
                logger.warning("Legacy-Modus: %s besitzt keine eigene Pruefsumme", name)
                continue
            raise LegacyBundleIntegrityError(
                f"Backup ohne SHA-256-Pruefsumme fuer {name}"
            )
        optional_actual = _member_sha256(zf, name, limit)
        if not hmac.compare_digest(optional_actual, optional_expected):
            raise BundleIntegrityError(f"Pruefsumme fuer {name} stimmt nicht")
    return db_member


def verify_open_bundle(
    zf: zipfile.ZipFile, *, allow_legacy_without_hash: bool = False
) -> str:
    """Fehlernormalisierende Sicherheitsgrenze für ein geöffnetes ZIP."""
    try:
        return _verify_open_bundle_impl(
            zf, allow_legacy_without_hash=allow_legacy_without_hash
        )
    except BundleIntegrityError:
        raise
    except (
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        NotImplementedError,
        RuntimeError,
        OSError,
        EOFError,
    ) as exc:
        raise BundleIntegrityError(f"Kein gueltiges Backup-Archiv: {exc}") from exc


def verify_bundle(bundle_path: Path, *, allow_legacy_without_hash: bool = False) -> str:
    """Prueft ein .bmr auf Struktur, Groesse und SHA256-Integritaet.

    Returns: der Name des DB-Members im Bundle.
    Raises:  BundleIntegrityError bei jedem Verstoss.
    """
    bundle_path = Path(bundle_path)
    if not bundle_path.exists():
        raise BundleIntegrityError(f"Backup nicht gefunden: {bundle_path.name}")

    try:
        with zipfile.ZipFile(bundle_path, "r") as zf:
            return verify_open_bundle(
                zf, allow_legacy_without_hash=allow_legacy_without_hash
            )
    except (
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        NotImplementedError,
        RuntimeError,
        OSError,
        EOFError,
    ) as e:
        # Auch exotische/absichtlich manipulierte ZIP-Methoden muessen am
        # Sicherheitsrand als normaler Integritaetsfehler enden. Andernfalls
        # koennte ein fremdes Backup ungefangene Low-Level-Ausnahmen bis in
        # die GUI durchreichen und den Restore-Dialog abbrechen.
        raise BundleIntegrityError(f"Kein gueltiges Backup-Archiv: {e}") from e


def upgrade_legacy_bundle(bundle_path: Path, out_path: Path) -> Path:
    """Konvertiert ein bestätigtes Legacy-Bundle in ein aktuelles Hash-Bundle.

    Das Original wird nie überschrieben. Die Datenbank wird gestreamt, sodass
    auch grosse, aber zulässige Backups nicht vollständig in den RAM geladen
    werden.
    """
    source = Path(bundle_path)
    target = Path(out_path)
    if source.resolve() == target.resolve():
        raise ValueError("Legacy-Backup darf nicht in-place überschrieben werden")
    with zipfile.ZipFile(source, "r") as src:
        db_member = verify_open_bundle(src, allow_legacy_without_hash=True)
        manifest = _read_manifest_from_zip(src)
        names = set(src.namelist())
        manifest["sha256"] = _member_sha256(src, db_member, MAX_DB_BYTES)
        manifest["has_settings"] = "settings.json" in names
        manifest["has_users"] = "users.json" in names
        manifest["settings_sha256"] = (
            _member_sha256(src, "settings.json", MAX_SETTINGS_BYTES)
            if "settings.json" in names
            else ""
        )
        manifest["users_sha256"] = (
            _member_sha256(src, "users.json", MAX_USERS_BYTES)
            if "users.json" in names
            else ""
        )
        manifest["integrity_upgraded_at"] = datetime.now().isoformat(timespec="seconds")
        # Historisches Feld fuer Kompatibilitaet beibehalten; das neue Feld
        # kennzeichnet die zusaetzlichen Pruefsummen fuer Settings und Konto.
        manifest["integrity_format"] = "sha256-v1"
        manifest["member_integrity_format"] = "sha256-members-v2"

        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.unlink(missing_ok=True)
        try:
            with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as dst:
                dst.writestr(
                    "manifest.json",
                    json.dumps(manifest, indent=2, ensure_ascii=False),
                )
                for name in src.namelist():
                    if name == "manifest.json":
                        continue
                    with src.open(name, "r") as in_stream, dst.open(
                        name, "w"
                    ) as out_stream:
                        shutil.copyfileobj(in_stream, out_stream, length=1024 * 1024)
            _secure_bundle_file(tmp)
            verify_bundle(tmp)
            os.replace(tmp, target)
            _secure_bundle_file(target)
        finally:
            tmp.unlink(missing_ok=True)
    return target
