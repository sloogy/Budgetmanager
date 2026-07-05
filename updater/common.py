from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

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
import re
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import requests
from packaging import version as _version

DEFAULT_MANIFEST_URL = (
    "https://github.com/sloogy/Budgetmanager/releases/latest/download/latest.json"
)


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


def enable_utf8_console() -> None:
    """Erzwingt UTF-8 für stdout/stderr.

    Die Windows-Konsole nutzt standardmäßig cp1252 und kann Emojis/Sonderzeichen
    (z.B. ⬇️, ❌, ✓) nicht kodieren -> UnicodeEncodeError beim print().
    Diese Funktion stellt die Streams auf UTF-8 um (mit errors='replace' als
    Sicherheitsnetz) und ist robust gegen fehlende Streams, etwa in einem
    windowed PyInstaller-Build ohne Konsole.
    """
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Ordner, in dem die App liegt (portable Root)."""
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    # DEV: Projekt-Root ist eine Ebene über updater/
    return Path(__file__).resolve().parents[1]


def _installer_data_dir_from_marker() -> Path | None:
    """Daten-/Update-Ordner aus installation.json fuer Installer-Builds.

    Der Windows-Installer legt mutable Dateien bewusst nicht in den
    Programmordner, sondern in den vom Nutzer gewaehlten Datenordner. Der
    Updater nutzt denselben Ort fuer Cache/Staging/Backup, damit nichts in
    AppData oder Program Files verstreut wird.
    """
    try:
        marker = installation_marker_path()
        if not marker.is_file():
            return None
        data = json.loads(marker.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        install_type = str(data.get("install_type", "")).strip().lower()
        if install_type not in {"windows_installer", "installer"}:
            return None
        raw = str(data.get("data_directory", "") or "").strip()
        if not raw:
            return None
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (app_dir() / path).resolve()
        return path
    except Exception as e:
        logger.debug("Installer-Datenordner konnte nicht gelesen werden: %s", e)
        return None


def updates_dir() -> Path:
    base = _installer_data_dir_from_marker() or app_dir()
    d = base / "updates"
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


def installation_marker_path() -> Path:
    """Marker fuer Installationsart neben der App.

    Der Windows-Installer schreibt ``installation.json`` nach ``{app}``.
    Portable ZIPs enthalten keinen Installer-Marker und bleiben dadurch
    updatebar per portable ZIP.
    """
    return app_dir() / "installation.json"


def read_install_type() -> str:
    try:
        marker = installation_marker_path()
        if not marker.is_file():
            return ""
        text = marker.read_text(encoding="utf-8")
    except Exception as e:
        logger.debug("Installationsart konnte nicht gelesen werden: %s", e)
        return ""

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return str(data.get("install_type", "")).strip().lower()
    except Exception as e:
        logger.debug("Installationsart-JSON konnte nicht geparst werden: %s", e)

    # Fallback für robuste Windows-Tests/Altmarker: data_directory kann
    # unescaped Backslashes enthalten; für die Asset-Priorität reicht
    # install_type. Nicht als allgemeiner JSON-Parser verwenden.
    match = re.search(
        r'"install_type"\s*:\s*"(?P<install_type>[^"]+)"',
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return match.group("install_type").strip().lower()


def preferred_asset_keys(platform_key: str) -> list[str]:
    """Asset-Prioritaet fuer die unterschiedlichen Build-Arten.

    Zwei robuste Auslieferungen haben unterschiedliche Updatepfade:
    - Windows-Installer: Setup-EXE herunterladen und starten
    - Portable onedir ZIP: Bundle mit _internal stagen und Programmdateien ersetzen, data/ bleibt

    Rohe Einzel-EXE/Binary-Assets werden bewusst nicht mehr bevorzugt: PyInstaller-onedir
    benötigt _internal/python312.dll bzw. die zugehörigen Bibliotheken.
    """
    keys: list[str] = []
    install_type = read_install_type()

    if platform_key == "windows":
        if install_type in {"windows_installer", "installer"}:
            keys.append("windows_installer")
        keys.extend(["windows", "portable_zip"])
    elif platform_key == "linux":
        keys.extend(["linux", "portable_zip"])
    else:
        keys.append(platform_key)

    # Duplikate stabil entfernen
    return list(dict.fromkeys(keys))


def is_windows() -> bool:
    return sys.platform.startswith("win")


def stable_exe_filename() -> str:
    """Stabiler App-Binary-Name im portablen Installationsordner.

    Release-Assets dürfen versioniert heißen, aber der portable ZIP enthält
    bewusst stabile Zielnamen. Dadurch kann der In-App-Updater eine neue
    Version installieren und danach zuverlässig denselben Startpunkt verwenden.
    """
    return "BudgetManager.exe" if is_windows() else "BudgetManager"


def current_exe_filename() -> str:
    """Dateiname der aktuell laufenden App-Binary.

    Bei älteren portablen Builds kann dieser Name noch versioniert sein
    (z.B. ``BudgetManager-v2.0.39-windows.exe``). Der Updater nutzt ihn zum
    Warten auf den laufenden Prozess, aber nicht zwingend als Neustart-Ziel.
    """
    if _is_frozen():
        return Path(sys.executable).name
    return stable_exe_filename()


def update_target_exe_filename() -> str:
    """Binary-Name, unter dem ein Update installiert und neu gestartet wird.

    Versionierte Alt-Binaries werden auf den stabilen Namen migriert. Für
    nicht-standardisierte Umbenennungen bleibt der aktuell laufende Name gültig.
    """
    current = current_exe_filename()
    low = current.lower()
    if low.startswith("budgetmanager-v") or low in {
        "budgetmanager-windows.exe",
        "budgetmanager-linux",
    }:
        return stable_exe_filename()
    return current


def asset_is_zip(asset_url: str, asset_type: str = "") -> bool:
    """Entscheidet, ob ein Asset ein ZIP-Archiv ist (entpacken) oder eine
    rohe Binary (direkt stagen).

    Das Manifest kann verschiedene Typen liefern:
      - ``portable-zip`` / URL endet auf ``.zip``  -> ZIP (entpacken)
      - ``portable`` mit roher ``.exe``/Binary-URL -> KEIN ZIP (direkt stagen)
    """
    t = (asset_type or "").strip().lower()
    if t.endswith("zip"):
        return True
    return asset_url.strip().lower().endswith(".zip")


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
    raw_assets = data.get("assets") or {}
    if isinstance(raw_assets, dict):
        for platform_key, info in raw_assets.items():
            if not isinstance(info, dict):
                continue
            url = str(info.get("url", "")).strip()
            sha = str(info.get("sha256", "")).strip().lower()
            a_type = str(info.get("type", "portable")).strip() or "portable"
            if url:
                assets[str(platform_key)] = AssetInfo(
                    url=url, sha256=sha, asset_type=a_type
                )

    return Manifest(
        version=str(data.get("version", "0.0.0")).strip(),
        release_tag=str(data.get("release_tag", "")).strip(),
        channel=str(data.get("channel", "stable")).strip(),
        assets=assets,
    )


def fetch_manifest(
    manifest_url: str = DEFAULT_MANIFEST_URL, timeout_s: int = 10
) -> Manifest:
    r = requests.get(manifest_url, timeout=timeout_s)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise ValueError("Manifest ist kein JSON-Objekt")
    return parse_manifest(data)


def is_newer(remote_version: str, current_version: str) -> bool:
    """SemVer-Vergleich (robust).

    Bei nicht interpretierbaren Versionsangaben wird KONSERVATIV ``False``
    geliefert (kein Update-Hinweis), statt bei blosser Ungleichheit fälschlich
    ein – womöglich älteres – "Update" zu signalisieren.
    """
    try:
        return _version.parse(remote_version) > _version.parse(current_version)
    except Exception:
        logger.warning(
            "Versionsvergleich nicht möglich (remote=%r, current=%r) – kein Update-Hinweis",
            remote_version,
            current_version,
        )
        return False


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


def prune_other_staging(
    keep_staging_dir: Path, keep_cache_file: Path | None = None
) -> None:
    """Entfernt veraltete Staging-Ordner und Cache-Dateien neben dem aktuellen.

    Warum: ``apply_update`` faellt ohne gueltiges ``last_check.json`` sicher auf
    ``latest_staged_version()`` zurueck – die hoechste vorhandene Staging-Version.
    Bleibt ein alter, hoeher nummerierter Staging-Ordner liegen (z.B. ein
    Beta-Rest ``2.1.0``), koennte dieser Fallback faelschlich angewendet werden.
    Indem ``check_update`` nach erfolgreichem Staging alle anderen Staging-Ordner
    entfernt, ist die hoechste vorhandene Version immer die gerade vorbereitete.
    Nebeneffekt: der Update-Ordner waechst nicht unbegrenzt.

    Die Pfade werden bewusst explizit uebergeben (statt intern neu berechnet),
    damit Tests, die ``staging_dir_for``/``cache_zip_path`` umbiegen, weiterhin
    nur ihren temporaeren Ordner betreffen.
    """
    try:
        keep_staging = keep_staging_dir.resolve()
        staging_root = keep_staging.parent
        if staging_root.is_dir():
            for child in staging_root.iterdir():
                if not child.is_dir():
                    continue
                if child.resolve() == keep_staging:
                    continue
                try:
                    import shutil

                    shutil.rmtree(child, ignore_errors=True)
                    logger.debug("Veralteten Staging-Ordner entfernt: %s", child)
                except OSError as e:
                    logger.debug("Staging-Ordner %s nicht entfernbar: %s", child, e)
    except Exception as e:
        logger.debug("Pruning der Staging-Ordner uebersprungen: %s", e)

    if keep_cache_file is None:
        return
    try:
        keep_cache = keep_cache_file.resolve()
        cache_root = keep_cache.parent
        if cache_root.is_dir():
            for child in cache_root.iterdir():
                if not child.is_file():
                    continue
                # Nur eigene Update-Artefakte anfassen, fremde Dateien schonen.
                if not child.name.startswith("update_"):
                    continue
                if child.resolve() == keep_cache:
                    continue
                try:
                    child.unlink()
                    logger.debug("Veraltete Update-Cache-Datei entfernt: %s", child)
                except OSError as e:
                    logger.debug("Cache-Datei %s nicht entfernbar: %s", child, e)
    except Exception as e:
        logger.debug("Pruning der Cache-Dateien uebersprungen: %s", e)


def write_staged_marker(version_str: str, manifest: Manifest, asset: AssetInfo) -> Path:
    marker = staging_dir_for(version_str) / "_update_marker.json"
    payload = {
        "version": version_str,
        "release_tag": manifest.release_tag,
        "channel": manifest.channel,
        "download_url": asset.url,
        "sha256": asset.sha256,
        "asset_type": asset.asset_type,
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


def _zip_add_dir(
    zf: zipfile.ZipFile, src: Path, arc_base: Path, exclude_names: Tuple[str, ...]
) -> None:
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


def backup_current_zip(
    backup_dir: Path, label: str, exclude_names: Tuple[str, ...]
) -> Path:
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


# ──────────────────────────────────────────────────────────────────────────
# Strukturiertes Check-Ergebnis (für GUI statt Konsolen-Text-Parsing)
# ──────────────────────────────────────────────────────────────────────────
def check_result_path() -> Path:
    return updates_dir() / "last_check.json"


def startup_check_result_path() -> Path:
    """Separates Ergebnis der leichten Startpruefung.

    Wichtig: Die Startpruefung laedt nur das Manifest und darf das normale
    ``last_check.json`` nicht ueberschreiben. Dieses normale Ergebnis wird vom
    Apply-Pfad benutzt, um die konkret gestagete Version zu installieren.
    """
    return updates_dir() / "last_startup_check.json"


def write_check_result(data: dict) -> None:
    """Schreibt das Ergebnis einer Update-Prüfung als JSON für den Update-Dialog."""
    from datetime import datetime

    payload = dict(data)
    payload.setdefault("checked_at", datetime.now().isoformat(timespec="seconds"))
    try:
        check_result_path().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as e:
        logger.debug("Update-Check-Ergebnis konnte nicht geschrieben werden: %s", e)


def read_check_result() -> dict:
    """Liest das letzte Update-Prüfergebnis oder gibt {} zurück."""
    p = check_result_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def clear_check_result() -> None:
    try:
        p = check_result_path()
        if p.exists():
            p.unlink()
    except Exception as e:
        logger.debug("Update-Check-Ergebnis konnte nicht gelöscht werden: %s", e)


def write_startup_check_result(data: dict) -> None:
    """Schreibt das Ergebnis der nicht-blockierenden Startpruefung."""
    from datetime import datetime

    payload = dict(data)
    payload.setdefault("checked_at", datetime.now().isoformat(timespec="seconds"))
    try:
        startup_check_result_path().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as e:
        logger.debug(
            "Startup-Update-Check-Ergebnis konnte nicht geschrieben werden: %s", e
        )


def read_startup_check_result() -> dict:
    """Liest das Ergebnis der letzten leichten Startpruefung."""
    p = startup_check_result_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def clear_startup_check_result() -> None:
    try:
        p = startup_check_result_path()
        if p.exists():
            p.unlink()
    except Exception as e:
        logger.debug(
            "Startup-Update-Check-Ergebnis konnte nicht gelöscht werden: %s", e
        )
