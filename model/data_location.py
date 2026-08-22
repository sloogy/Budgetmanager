"""Übernahme (Migration) von Nutzerdaten in einen neuen Datenordner.

Bewusst Qt-frei und ohne App-Abhängigkeiten, damit die Logik testbar ist und
nicht von der GUI abhängt.

Was als "Nutzerdaten" gilt (Allowlist):
- verschlüsselte Konto-Datenbanken:  *.enc
- Nutzerregister:                    users.json
- (Legacy/Plain) Datenbank:          budgetmanager.db
- Unterordner:                       backups/, exports/

Bewusst NICHT übernommen werden Einstellungsdatei (bleibt portabel), Logs,
Lock-Dateien und Crash-Logs – das sind Laufzeit-Artefakte.

Sicherheit:
- Vor dem Kopieren wird ein selbsttragendes ZIP-Backup der zu übernehmenden
  Dateien im Zielordner erstellt.
- Es wird KOPIERT, nicht verschoben: Der alte Ordner bleibt unangetastet und
  dient als zusätzliche Sicherung.
- In einen Zielordner, der bereits Nutzerdaten enthält, wird nicht migriert
  (kein Vermischen zweier Datenbestände).
"""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

USER_DATA_FILE_GLOBS = ("*.enc",)
USER_DATA_FILE_NAMES = ("users.json", "budgetmanager.db")
USER_DATA_DIR_NAMES = ("backups", "exports")


class DataMigrationError(Exception):
    """Migration konnte nicht (sicher) durchgeführt werden.

    Die Logik bleibt Qt-frei, liefert aber einen i18n-Key mit. Dadurch werden
    Fehlermeldungen in Dialogen auf Deutsch/Englisch/Französisch angezeigt,
    statt Modell-Fehlertexte hart auf Deutsch auszugeben.
    """

    def __init__(self, key: str, fallback: str):
        super().__init__(fallback)
        self.key = key
        self.fallback = fallback

    def __str__(self) -> str:
        try:
            from utils.i18n import tr

            translated = tr(self.key)
            return (
                translated if translated and translated != self.key else self.fallback
            )
        except Exception:
            return self.fallback


@dataclass
class MigrationResult:
    copied: list[str] = field(default_factory=list)
    backup_path: str | None = None
    total_bytes: int = 0


def list_user_data(directory: Path) -> list[Path]:
    """Liefert die vorhandenen Nutzerdaten-Pfade in 'directory' (Allowlist)."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    items: list[Path] = []
    for pattern in USER_DATA_FILE_GLOBS:
        items.extend(p for p in directory.glob(pattern) if p.is_file())
    for name in USER_DATA_FILE_NAMES:
        p = directory / name
        if p.is_file():
            items.append(p)
    for name in USER_DATA_DIR_NAMES:
        p = directory / name
        if p.is_dir():
            items.append(p)
    # Stabil und ohne Duplikate
    seen: set[str] = set()
    unique: list[Path] = []
    for p in items:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return sorted(unique, key=lambda p: p.name.casefold())


def has_user_data(directory: Path) -> bool:
    """True, wenn 'directory' mindestens eine Nutzerdaten-Datei/-Ordner enthält."""
    return bool(list_user_data(directory))


def _iter_files(path: Path):
    if path.is_dir():
        for sub in path.rglob("*"):
            if sub.is_file():
                yield sub
    elif path.is_file():
        yield path


def _make_backup_zip(items: list[Path], source_dir: Path, target_dir: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = target_dir / f"datenuebernahme_backup_{ts}.zip"
    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in items:
            for f in _iter_files(item):
                arc = f.relative_to(source_dir)
                zf.write(f, str(arc))
    return backup_path


def migrate_data_dir(
    old_dir: Path | str,
    new_dir: Path | str,
    *,
    make_backup: bool = True,
) -> MigrationResult:
    """Kopiert Nutzerdaten von old_dir nach new_dir (mit Sicherheits-Backup).

    Raises:
        DataMigrationError: bei gleichem Pfad, fehlenden Quelldaten oder wenn der
            Zielordner bereits Nutzerdaten enthält.
    """
    old_dir = Path(old_dir)
    new_dir = Path(new_dir)

    old_resolved = old_dir.resolve()
    new_resolved = new_dir.resolve()

    if old_resolved == new_resolved:
        raise DataMigrationError(
            "data_location.error.identical", "Quell- und Zielordner sind identisch."
        )

    # Kein Verschachteln erlauben: sonst kann z.B. ein Ziel in old/backups
    # beim Kopieren des backups-Ordners rekursiv in sich selbst laufen oder
    # alte und neue Datenbestände vermischen.
    try:
        if new_resolved.is_relative_to(old_resolved) or old_resolved.is_relative_to(
            new_resolved
        ):
            raise DataMigrationError(
                "data_location.error.nested",
                "Quell- und Zielordner dürfen nicht ineinander liegen.",
            )
    except AttributeError:  # pragma: no cover - Py<3.9 Fallback
        old_parts = old_resolved.parts
        new_parts = new_resolved.parts
        if (
            new_parts[: len(old_parts)] == old_parts
            or old_parts[: len(new_parts)] == new_parts
        ):
            raise DataMigrationError(
                "data_location.error.nested",
                "Quell- und Zielordner dürfen nicht ineinander liegen.",
            )

    items = list_user_data(old_dir)
    if not items:
        raise DataMigrationError(
            "data_location.error.no_source_data",
            "Im bisherigen Ordner wurden keine Daten gefunden.",
        )

    if has_user_data(new_dir):
        raise DataMigrationError(
            "data_location.error.target_has_data",
            "Der Zielordner enthält bereits Daten.",
        )

    new_dir.mkdir(parents=True, exist_ok=True)

    result = MigrationResult()
    if make_backup:
        result.backup_path = str(_make_backup_zip(items, old_dir, new_dir))

    for item in items:
        dest = new_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
        result.copied.append(item.name)
        for f in _iter_files(item):
            try:
                result.total_bytes += f.stat().st_size
            except OSError:
                pass

    return result
