"""Review-first LifePlanner bridge importer for BudgetManager.

The service reads ``budgetmanager.import.v1`` JSONL records from the shared
LifePlanner bridge directory. It never imports on its own: every new or changed
record must be accepted in the UI. Processed source IDs are stored in a small
local audit table so that repeated FPM outbox snapshots stay idempotent.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from model.category_model import CategoryModel
from model.database import db_transaction
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES, TYP_SAVINGS
from utils.atomic_write import atomar_offen
from utils.money import get_currency

BRIDGE_FILE = "fpm_to_budgetmanager.jsonl"
FPM_OUTBOX_FILE = "budgetmanager_to_fpm.jsonl"
SAVINGS_GOALS_OUTBOX_FILE = "budgetmanager_savings_goals.jsonl"
CATEGORIES_OUTBOX_FILE = "budgetmanager_categories.jsonl"
SCHEMA = "budgetmanager.import.v1"
STATE_TABLE = "lifeplanner_import_state"
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_LINE_BYTES = 1024 * 1024
MAX_RECORDS = 50_000
_EXTERNAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/@+\-]{0,254}$")


class LifePlannerImportError(ValueError):
    pass


@dataclass(frozen=True)
class ImportRecord:
    external_id: str
    source: str
    booking_date: date
    amount: float
    currency: str
    category_path: str
    description: str
    counterparty: str
    notes: str
    metadata: dict[str, Any]
    payload_hash: str
    raw: dict[str, Any]
    status: str = "pending"
    tracking_id: int | None = None


@dataclass(frozen=True)
class ImportDraft:
    external_id: str
    booking_date: date
    typ: str
    category: str
    amount: float
    details: str
    source_currency: str
    currency_confirmed: bool


@dataclass(frozen=True)
class ApplyResult:
    external_id: str
    tracking_id: int
    updated: bool


@dataclass(frozen=True)
class BridgeExportResult:
    path: Path
    count: int


def _standalone_bridge_dir() -> Path:
    """Der Brueckenordner, wenn kein Host ihn vorgibt.

    Frueher fest ``~/fpm_budgetmanager_bridge``. Das war bei einer portablen
    Installation falsch: Datenbank, Einstellungen und Backups liegen laengst
    im Datenordner (``data_dir()``, portabel neben dem Programm), nur die
    Bruecke schrieb ins Benutzerprofil. Wer den Ordner auf einen Stick kopiert, nahm damit alles
    mit ausser der Bruecke - und wunderte sich, dass am anderen Rechner keine
    Sparziele ankamen.

    Ein bereits vorhandener Ordner am alten Ort gewinnt trotzdem: Dort liegt
    der Stand des Nutzers. Ihn stillschweigend stehen zu lassen und daneben
    einen leeren zweiten zu eroeffnen, waere schlimmer als der alte Ort.
    """
    from model.app_paths import data_dir

    legacy = Path.home() / "fpm_budgetmanager_bridge"
    if legacy.is_dir():
        return legacy
    return data_dir() / "fpm_budgetmanager_bridge"


def default_bridge_dir() -> Path:
    """Gemeinsamer Brückenordner.

    Im LifePlanner gibt der Host den Ordner vor; er liegt dann im bereits
    geschützten Profil. Eigenständig landet er neben dem Programm im
    Datenordner - dort wird er beim Anlegen auf 0700 gesetzt, denn was darin
    liegt, sind Buchungen und Sparziele.
    """
    from model.bridge_registry import eintragen

    override = os.environ.get("LIFEPLANNER_BRIDGE_DIR", "").strip()
    path = (
        Path(override).expanduser().resolve() if override else _standalone_bridge_dir()
    )
    neu = not path.exists()
    path.mkdir(parents=True, exist_ok=True)
    if neu:
        from model.file_permissions import secure_dir

        secure_dir(path)
    eintragen(path)
    return path


def alle_bridge_dirs() -> tuple[Path, ...]:
    """Alle Brückenordner, aus denen gelesen wird - der aktive zuletzt.

    Wer den BudgetManager mal eigenständig und mal im LifePlanner startet, hat
    mehrere Brücken. Geschrieben wird nur in den aktiven; gelesen aus allen,
    sonst liegt der Stand aus der anderen Startart da und kommt nie an.
    """
    from model.bridge_registry import bekannte_ordner

    return bekannte_ordner(default_bridge_dir())


def default_bridge_path() -> Path:
    return default_bridge_dir() / BRIDGE_FILE


def default_inbox_path() -> Path:
    """Kompatibler Name für die eingehende FPM-/LifePlanner-Datei."""
    return default_bridge_path()


def default_fpm_outbox_path() -> Path:
    return default_bridge_dir() / FPM_OUTBOX_FILE


def default_savings_goals_path() -> Path:
    return default_bridge_dir() / SAVINGS_GOALS_OUTBOX_FILE


def ensure_state_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS lifeplanner_import_state (
            external_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('imported','rejected')),
            tracking_id INTEGER,
            processed_at TEXT NOT NULL,
            source_payload TEXT NOT NULL,
            imported_payload TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.commit()


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _clean_text(value: Any, *, limit: int) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return text[:limit]


def _parse_record(raw: dict[str, Any], line_no: int) -> ImportRecord | None:
    if raw.get("schema") != SCHEMA:
        return None
    if str(raw.get("operation") or "upsert").lower() != "upsert":
        raise LifePlannerImportError(
            f"Zeile {line_no}: Operation wird nicht unterstützt."
        )

    external_id = _clean_text(raw.get("external_id"), limit=255)
    if not _EXTERNAL_ID_RE.fullmatch(external_id):
        raise LifePlannerImportError(f"Zeile {line_no}: ungültige externe ID.")

    try:
        booking_date = date.fromisoformat(_clean_text(raw.get("date"), limit=10))
    except ValueError as exc:
        raise LifePlannerImportError(f"Zeile {line_no}: ungültiges Datum.") from exc

    try:
        amount = float(raw.get("amount"))
    except (TypeError, ValueError) as exc:
        raise LifePlannerImportError(f"Zeile {line_no}: ungültiger Betrag.") from exc
    if not math.isfinite(amount) or amount <= 0 or amount > 999_999_999:
        raise LifePlannerImportError(
            f"Zeile {line_no}: Betrag außerhalb des gültigen Bereichs."
        )

    currency = _clean_text(raw.get("currency") or "CHF", limit=3).upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise LifePlannerImportError(f"Zeile {line_no}: ungültiger Währungscode.")

    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    return ImportRecord(
        external_id=external_id,
        source=_clean_text(raw.get("source") or "LifePlanner", limit=80),
        booking_date=booking_date,
        amount=round(amount, 2),
        currency=currency,
        category_path=_clean_text(raw.get("category_path"), limit=160),
        description=_clean_text(raw.get("description") or "Import", limit=300),
        counterparty=_clean_text(raw.get("counterparty"), limit=200),
        notes=_clean_text(raw.get("notes"), limit=2000),
        metadata=metadata,
        payload_hash=_canonical_hash(raw),
        raw=raw,
    )


def _state_rows(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    ensure_state_table(conn)
    rows = conn.execute("SELECT * FROM lifeplanner_import_state").fetchall()
    return {str(row["external_id"]): row for row in rows}


def _einlesen(src: Path, parsed: dict[str, ImportRecord]) -> None:
    """Liest eine Brückendatei in ``parsed`` ein - nach Kennung, nicht als Liste.

    Steht derselbe Datensatz in zwei Brücken, gewinnt der zuletzt gelesene.
    Die Aufrufreihenfolge stellt sicher, dass das der aktive Ordner ist.

    Eine fehlende Datei ist kein Fehler: Die andere Seite hat dann noch nichts
    geschrieben. Alles andere schon - eine Brücke, die auf ein Verzeichnis
    oder auf 20 MB zeigt, soll auffallen und nicht stumm nichts liefern.
    """
    if not src.exists():
        return
    if not src.is_file():
        raise LifePlannerImportError("Der Bridge-Pfad ist keine Datei.")
    if src.stat().st_size > MAX_FILE_BYTES:
        raise LifePlannerImportError("Die Bridge-Datei ist größer als 20 MB.")

    with src.open("r", encoding="utf-8") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            if len(raw_line.encode("utf-8")) > MAX_LINE_BYTES:
                raise LifePlannerImportError(f"Zeile {line_no} ist zu groß.")
            line = raw_line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LifePlannerImportError(
                    f"Ungültige JSONL-Zeile {line_no}: {exc.msg}."
                ) from exc
            if not isinstance(raw, dict):
                continue
            record = _parse_record(raw, line_no)
            if record is not None:
                parsed[record.external_id] = record
            if len(parsed) > MAX_RECORDS:
                raise LifePlannerImportError(
                    "Die Bridge-Datei enthält zu viele Einträge."
                )


def load_import_records(
    conn: sqlite3.Connection, path: str | Path | None = None
) -> list[ImportRecord]:
    # Kein Ternary: die Begruendung im else-Zweig gehoert an ihre Stelle.
    if path is not None:  # noqa: SIM108
        quellen = [Path(path)]
    else:
        # Aus jeder bekannten Brücke, die aktive zuletzt: Wer den
        # BudgetManager mal eigenständig und mal im LifePlanner startet, sieht
        # sonst je nach Startart nur die Hälfte der offenen Buchungen.
        quellen = [o / BRIDGE_FILE for o in alle_bridge_dirs()]
    parsed: dict[str, ImportRecord] = {}
    for src in quellen:
        _einlesen(src, parsed)

    states = _state_rows(conn)
    result: list[ImportRecord] = []
    for record in parsed.values():
        state = states.get(record.external_id)
        if state is None:
            status = "pending"
            tracking_id = None
        else:
            same = str(state["payload_hash"]) == record.payload_hash
            previous = str(state["status"])
            tracking_id = (
                int(state["tracking_id"]) if state["tracking_id"] is not None else None
            )
            tracking_exists = bool(
                tracking_id
                and conn.execute(
                    "SELECT 1 FROM tracking WHERE id=?", (tracking_id,)
                ).fetchone()
            )
            if previous == "imported" and same and tracking_exists:
                status = "imported"
            elif previous == "rejected" and same:
                status = "rejected"
            elif previous == "imported" and not tracking_exists:
                status = "orphaned"
            else:
                status = "changed"
        result.append(replace(record, status=status, tracking_id=tracking_id))
    return sorted(result, key=lambda r: (r.booking_date, r.external_id), reverse=True)


def pending_count(conn: sqlite3.Connection, path: str | Path | None = None) -> int:
    return sum(
        r.status in {"pending", "changed", "orphaned"}
        for r in load_import_records(conn, path)
    )


def _category_candidates(record: ImportRecord) -> list[str]:
    leaf = record.category_path.replace("›", "/").split("/")[-1].strip()
    item_type = str(record.metadata.get("item_type") or "").lower()
    mapped = {
        "pen": ["Füller", "Fueller", "Schreibgeräte"],
        "ink": ["Tinte", "Tinten"],
        "nib": ["Federn", "Feder"],
        "paper": ["Papier", "Notizbücher"],
        "accessory": ["Zubehör", "Zubehoer"],
        "service": ["Service", "Reparatur"],
        "shipping": ["Versand/Zoll", "Versand", "Zoll"],
        "customs": ["Versand/Zoll", "Zoll"],
        "other": ["Hobby", "Sonstiges", "Sonstige Ausgaben"],
    }
    values = [
        record.category_path,
        leaf,
        *mapped.get(item_type, []),
        "Sonstiges",
        "Sonstige Ausgaben",
    ]
    return [v.strip() for v in values if v and v.strip()]


def suggest_category(
    conn: sqlite3.Connection, record: ImportRecord, typ: str = TYP_EXPENSES
) -> str:
    model = CategoryModel(conn)
    available = [value for _label, value in model.list_for_tracking_dropdown(typ)]
    by_lower = {name.casefold(): name for name in available}
    for candidate in _category_candidates(record):
        direct = by_lower.get(candidate.casefold())
        if direct:
            return direct
    for candidate in _category_candidates(record):
        key = candidate.casefold()
        for name in available:
            if key and (key in name.casefold() or name.casefold() in key):
                return name
    return ""


def default_draft(conn: sqlite3.Connection, record: ImportRecord) -> ImportDraft:
    details_parts = [record.description]
    if record.counterparty:
        details_parts.append(record.counterparty)
    if record.notes:
        details_parts.append(record.notes)
    fresh_details = " | ".join(part for part in details_parts if part)[:2000]
    active_currency = get_currency().upper()

    # Preserve the user's previous type/category choice for changed upserts.
    # Source-owned fields (date/amount/text) still follow the new FPM snapshot.
    previous: dict[str, Any] = {}
    try:
        ensure_state_table(conn)
        row = conn.execute(
            "SELECT imported_payload FROM lifeplanner_import_state WHERE external_id=?",
            (record.external_id,),
        ).fetchone()
        if row and row["imported_payload"]:
            candidate = json.loads(str(row["imported_payload"]))
            if isinstance(candidate, dict):
                previous = candidate
    except (sqlite3.Error, ValueError, TypeError, json.JSONDecodeError):
        previous = {}

    typ = str(previous.get("typ") or TYP_EXPENSES)
    previous_category = str(previous.get("category") or "").strip()
    category = (
        CategoryModel(conn).resolve_name(typ, previous_category)
        if previous_category
        else None
    ) or suggest_category(conn, record, typ)

    if record.status == "orphaned" and previous:
        try:
            prior_date = date.fromisoformat(str(previous.get("date") or ""))
        except ValueError:
            prior_date = record.booking_date
        return ImportDraft(
            external_id=record.external_id,
            booking_date=prior_date,
            typ=typ,
            category=category,
            amount=float(previous.get("amount") or record.amount),
            details=str(previous.get("details") or fresh_details)[:2000],
            source_currency=record.currency,
            currency_confirmed=bool(
                previous.get("currency_confirmed") or record.currency == active_currency
            ),
        )

    return ImportDraft(
        external_id=record.external_id,
        booking_date=record.booking_date,
        typ=typ,
        category=category,
        amount=record.amount,
        details=fresh_details,
        source_currency=record.currency,
        currency_confirmed=(record.currency == active_currency),
    )


def _validate_draft(conn: sqlite3.Connection, draft: ImportDraft) -> ImportDraft:
    if not math.isfinite(float(draft.amount)) or float(draft.amount) <= 0:
        raise LifePlannerImportError("Der Importbetrag muss größer als 0 sein.")
    category = CategoryModel(conn).resolve_name(draft.typ, draft.category)
    if category is None:
        raise LifePlannerImportError(
            "Bitte eine vorhandene Buchungskategorie auswählen."
        )
    active_currency = get_currency().upper()
    if (
        draft.source_currency.upper() != active_currency
        and not draft.currency_confirmed
    ):
        raise LifePlannerImportError(
            f"Der Quellbetrag ist in {draft.source_currency}; bitte in {active_currency} umrechnen und bestätigen."
        )
    return replace(draft, category=category, details=draft.details.strip()[:2000])


def apply_import(
    conn: sqlite3.Connection, record: ImportRecord, draft: ImportDraft
) -> ApplyResult:
    if record.external_id != draft.external_id:
        raise LifePlannerImportError(
            "Import-ID und Bearbeitungsentwurf passen nicht zusammen."
        )
    draft = _validate_draft(conn, draft)
    ensure_state_table(conn)
    state = conn.execute(
        "SELECT tracking_id, status FROM lifeplanner_import_state WHERE external_id=?",
        (record.external_id,),
    ).fetchone()
    previous_tracking_id = (
        int(state["tracking_id"])
        if state and state["tracking_id"] is not None
        else None
    )
    updated = bool(
        previous_tracking_id
        and conn.execute(
            "SELECT 1 FROM tracking WHERE id=?", (previous_tracking_id,)
        ).fetchone()
    )
    tracking = TrackingModel(conn)
    imported_payload = json.dumps(
        {
            "date": draft.booking_date.isoformat(),
            "typ": draft.typ,
            "category": draft.category,
            "amount": round(float(draft.amount), 2),
            "details": draft.details,
            "source_currency": draft.source_currency,
            "currency_confirmed": bool(draft.currency_confirmed),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    now = datetime.now(UTC).isoformat()
    with db_transaction(conn):
        if updated:
            tracking.update(
                previous_tracking_id,
                draft.booking_date,
                draft.typ,
                draft.category,
                float(draft.amount),
                draft.details,
            )
            tracking_id = previous_tracking_id
        else:
            tracking_id = tracking.add(
                draft.booking_date,
                draft.typ,
                draft.category,
                float(draft.amount),
                draft.details,
                source=f"lifeplanner:{record.source.lower()}",
            )
        conn.execute(
            """
            INSERT INTO lifeplanner_import_state
                (external_id, source, payload_hash, status, tracking_id,
                 processed_at, source_payload, imported_payload)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(external_id) DO UPDATE SET
                source=excluded.source,
                payload_hash=excluded.payload_hash,
                status='imported',
                tracking_id=excluded.tracking_id,
                processed_at=excluded.processed_at,
                source_payload=excluded.source_payload,
                imported_payload=excluded.imported_payload
            """,
            (
                record.external_id,
                record.source,
                record.payload_hash,
                "imported",
                int(tracking_id),
                now,
                json.dumps(record.raw, ensure_ascii=False, sort_keys=True),
                imported_payload,
            ),
        )
    return ApplyResult(record.external_id, int(tracking_id), updated)


def reject_import(conn: sqlite3.Connection, record: ImportRecord) -> None:
    ensure_state_table(conn)
    existing = conn.execute(
        "SELECT tracking_id FROM lifeplanner_import_state WHERE external_id=?",
        (record.external_id,),
    ).fetchone()
    tracking_id = existing["tracking_id"] if existing else None
    conn.execute(
        """
        INSERT INTO lifeplanner_import_state
            (external_id, source, payload_hash, status, tracking_id,
             processed_at, source_payload, imported_payload)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(external_id) DO UPDATE SET
            source=excluded.source,
            payload_hash=excluded.payload_hash,
            status='rejected',
            processed_at=excluded.processed_at,
            source_payload=excluded.source_payload
        """,
        (
            record.external_id,
            record.source,
            record.payload_hash,
            "rejected",
            tracking_id,
            datetime.now(UTC).isoformat(),
            json.dumps(record.raw, ensure_ascii=False, sort_keys=True),
            "",
        ),
    )
    conn.commit()


def records_by_id(records: Iterable[ImportRecord]) -> dict[str, ImportRecord]:
    return {record.external_id: record for record in records}


# --- Bidirektionale Bridge-Exporte aus der verbindlichen v2.2.56-Basis ---
def export_fpm_expense_proposals(
    conn, path: str | Path | None = None
) -> BridgeExportResult:
    out = Path(path) if path is not None else default_fpm_outbox_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(
        "SELECT id, date, category, amount, details FROM tracking WHERE typ=? ORDER BY date, id",
        (TYP_EXPENSES,),
    ).fetchall()
    count = 0
    with atomar_offen(out) as handle:
        handle.write(
            json.dumps(
                {
                    "schema": "fpm.import.manifest.v1",
                    "source": "BudgetManager",
                    "created_at": datetime.now(UTC).isoformat(),
                    "mode": "reviewable_bridge_import",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )
        for row in rows:
            category = str(row[2] or "")
            details = str(row[4] or "")
            haystack = f"{category} {details}".lower()
            if not any(
                token in haystack
                for token in (
                    "füller",
                    "fueller",
                    "fountain",
                    "tinte",
                    "ink",
                    "feder",
                    "nib",
                    "papier",
                    "paper",
                )
            ):
                continue
            amount = round(abs(float(row[3] or 0.0)), 2)
            if amount <= 0:
                continue
            record = {
                "schema": "fpm.import.v1",
                "operation": "upsert",
                "external_id": f"budgetmanager:tracking:{int(row[0])}",
                "source": "BudgetManager",
                "date": str(row[1]),
                "amount": amount,
                "currency": "CHF",
                "category_path": category,
                "description": details.splitlines()[0] if details else category,
                "notes": details,
            }
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    # Die Datei trägt Beträge und Sparziele - dieselben Rechte wie der Ordner.
    from model.file_permissions import secure_file

    secure_file(out)
    return BridgeExportResult(out, count)


def export_savings_goals(conn, path: str | Path | None = None) -> BridgeExportResult:
    out = Path(path) if path is not None else default_savings_goals_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(savings_goals)")}
    if not columns:
        rows = []
    else:
        contributed = (
            "contributed_amount"
            if "contributed_amount" in columns
            else "current_amount"
        )
        withdrawn = "withdrawn_amount" if "withdrawn_amount" in columns else "0"
        # Nur, was der Nutzer freigegeben hat. Ein Sparziel trägt seinen Namen,
        # seinen Betrag und sein Datum - "Notgroschen 5000 bis März" gehört
        # niemandem sonst, auch keinem Schwesterprogramm. Fehlt die Spalte
        # (Datenbank vor v19), bleibt es beim alten Verhalten: Sonst wäre die
        # Spiegelung nach einem Downgrade wortlos leer.
        wo = " WHERE bridge_share=1" if "bridge_share" in columns else ""
        rows = conn.execute(
            f"SELECT id, name, target_amount, current_amount, deadline, category, notes, "
            f"status, {contributed} AS contributed_amount, {withdrawn} AS withdrawn_amount "
            f"FROM savings_goals{wo} ORDER BY id"  # nosec B608 -- identifiers are fixed from audited allow-list
        ).fetchall()
    count = 0
    with atomar_offen(out) as handle:
        handle.write(
            json.dumps(
                {
                    "schema": "fpm.savings-goals.manifest.v1",
                    "source": "BudgetManager",
                    "created_at": datetime.now(UTC).isoformat(),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )
        for row in rows:
            target = float(row[2] or 0.0)
            stock = float(row[3] or 0.0)
            contributed_value = float(row[8] or 0.0)
            withdrawn_value = float(row[9] or 0.0)
            record = {
                "schema": "fpm.savings-goal.v1",
                "external_id": f"budgetmanager:savings-goal:{int(row[0])}",
                "source": "BudgetManager",
                "item_type": "savings_goal",
                # Ausgeschrieben, obwohl hier nur noch Freigegebenes ankommt:
                # FPM wertet das Feld seit jeher aus und wirft ohne es nichts
                # weg - ein zurückgenommenes Ziel verschwände sonst erst beim
                # nächsten vollständigen Schreiben der Datei.
                "visible": True,
                "label": str(row[1] or ""),
                "goal_name": str(row[1] or ""),
                "status": str(row[7] or "sparend"),
                "target_amount": round(target, 2),
                "current_amount": round(stock, 2),
                "contributed_amount": round(contributed_value, 2),
                "withdrawn_amount": round(withdrawn_value, 2),
                "remaining_amount": round(max(0.0, target - contributed_value), 2),
                "progress_percent": round(
                    (contributed_value / target * 100.0) if target > 0 else 0.0, 2
                ),
                "currency": "CHF",
                "deadline": str(row[4] or ""),
                "category": str(row[5] or ""),
                "notes": str(row[6] or ""),
            }
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    # Die Datei trägt Beträge und Sparziele - dieselben Rechte wie der Ordner.
    from model.file_permissions import secure_file

    secure_file(out)
    return BridgeExportResult(out, count)


@dataclass(frozen=True)
class BridgeDateiBefund:
    """Was in einer der drei Brückendateien steht."""

    name: str
    pfad: Path
    vorhanden: bool
    eintraege: int


def bridge_zustand() -> tuple[Path, tuple[BridgeDateiBefund, ...]]:
    """Der aktive Brückenordner und was darin liegt.

    Warum das sichtbar sein muss: Der Ordner hängt davon ab, wie BudgetManager
    gestartet wurde. Im LifePlanner gibt ihn der Host über
    LIFEPLANNER_BRIDGE_DIR vor, eigenständig liegt er im Datenordner neben
    dem Programm.
    Wer beides gemischt nutzt, hat zwei getrennte Brücken - und wundert sich,
    warum nichts ankommt.

    Unterschieden wird zwischen "Datei fehlt" (das andere Programm hat noch
    nichts geschrieben) und "leer": Fehlt sie, liegt es dort und nicht hier.

    Gegenstück zu FPM/logic/budget_export_service.py, bridge_zustand().
    """
    ordner = default_bridge_dir()
    befunde = []
    for name, dateiname, schemas in (
        ("FPM → BudgetManager", BRIDGE_FILE, {SCHEMA}),
        ("BudgetManager → FPM", FPM_OUTBOX_FILE, {"fpm.import.v1", "fpm.expense.v1"}),
        (
            "Sparziele → FPM",
            SAVINGS_GOALS_OUTBOX_FILE,
            {"fpm.savings-goal.v1", "fpm.savings_goal.v1"},
        ),
    ):
        pfad = ordner / dateiname
        if not pfad.is_file():
            befunde.append(BridgeDateiBefund(name, pfad, False, 0))
            continue
        anzahl = 0
        for zeile in pfad.read_text(encoding="utf-8", errors="replace").splitlines():
            if not zeile.strip():
                continue
            try:
                eintrag = json.loads(zeile)
            except json.JSONDecodeError:
                # Eine unlesbare Zeile soll die Anzeige nicht sprengen; dass
                # etwas nicht stimmt, sieht man an der Zahl.
                continue
            if isinstance(eintrag, dict) and eintrag.get("schema") in schemas:
                anzahl += 1
        befunde.append(BridgeDateiBefund(name, pfad, True, anzahl))
    return ordner, tuple(befunde)


def default_categories_path() -> Path:
    return default_bridge_dir() / CATEGORIES_OUTBOX_FILE


def export_categories(conn, path: str | Path | None = None) -> BridgeExportResult:
    """Veroeffentlicht den Kategorienkatalog fuer andere Module.

    Ohne ihn muss ein Modul raten, wie die Kategorien des Nutzers heissen.
    FPM schickte darum bis Loop 49 fest verdrahtete Namen ("Hobby/Fueller"),
    die es hier meist gar nicht gibt - der Import legte sie an oder der Nutzer
    ordnete jede Zahlung von Hand zu.

    Uebertragen werden nur Name und Typ. Kein Budgetwert, kein Ist-Stand,
    keine Buchung: Der Katalog sagt, *wohin* etwas gebucht werden kann, nicht
    was dort steht.

    Und seit v19 auch nur noch, was freigegeben ist. Der ganze Katalog waren
    bei 40 gefuehrten Kategorien 40 Namen fuer ein Programm, das drei davon
    braucht - Kontonamen und Lebensumstaende stehen in solchen Namen drin.
    """
    out = Path(path) if path is not None else default_categories_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    kategorien = CategoryModel(conn)

    count = 0
    with atomar_offen(out) as handle:
        handle.write(
            json.dumps(
                {
                    "schema": "budgetmanager.categories.manifest.v1",
                    "source": "BudgetManager",
                    "created_at": datetime.now(UTC).isoformat(),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )
        # Einkommen bleibt aussen vor: Ein anderes Modul meldet Ausgaben und
        # Ersparnisse, keine Einnahmen.
        for typ in (TYP_EXPENSES, TYP_SAVINGS):
            for name in kategorien.list_shared_names(typ):
                handle.write(
                    json.dumps(
                        {
                            "schema": "budgetmanager.category.v1",
                            "typ": typ,
                            "name": name,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                )
                count += 1
    return BridgeExportResult(path=out, count=count)


def sync_default_outboxes(conn) -> tuple[BridgeExportResult, BridgeExportResult]:
    ergebnis = export_fpm_expense_proposals(conn), export_savings_goals(conn)
    export_categories(conn)
    return ergebnis


def sync_host_notices(conn, heute: date | None = None) -> int:
    """Schreibt den Meldungsstand fuer das LifePlanner-Dashboard.

    Getrennt von ``sync_default_outboxes``, weil das etwas anderes ist: Die
    Outboxen tragen Vorschlaege fuer ein anderes Fachmodul, die Meldungen
    tragen nur Anzeige. Faellt eines aus, soll das andere trotzdem laufen.
    """
    from model.lifeplanner_notices import sammle_meldungen, schreibe_meldungen

    stichtag = heute or date.today()
    meldungen = sammle_meldungen(conn, stichtag.year, stichtag.month, stichtag)
    return schreibe_meldungen(meldungen)
