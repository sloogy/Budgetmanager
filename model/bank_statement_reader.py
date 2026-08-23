"""Lokaler CSV/PDF-Kontoauszug-Reader für BudgetManager.

Keine Netzwerkzugriffe. CSV unterstützt u.a. ZKB-Exporte; PDF nutzt pypdf
für Text-PDFs. Scan-PDFs werden bewusst abgelehnt, bis lokale OCR vorhanden ist.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

MAX_SOURCE_BYTES = 50 * 1024 * 1024
MAX_CSV_ROWS = 50_000
MAX_PDF_PAGES = 500
MAX_PDF_TEXT_CHARS = 10_000_000


class BankStatementError(ValueError):
    pass


@dataclass(frozen=True)
class BankTransaction:
    source_kind: str
    source_name: str
    source_index: int
    booking_date: date
    amount: Decimal
    currency: str
    description: str
    counterparty: str = ""
    raw: dict[str, str] = field(default_factory=dict)

    @property
    def direction(self) -> str:
        return "income" if self.amount > 0 else "expense"


_BOOKING_DATE_ALIASES = (
    "datum",
    "buchungsdatum",
    "buchungstag",
    "date",
    "bookingdate",
    "transactiondate",
)
_VALUE_DATE_ALIASES = ("valuta", "valutadatum", "valuedate")
_DESC_ALIASES = {
    "description",
    "beschreibung",
    "buchungstext",
    "text",
    "details",
    "zahlungszweck",
    "verwendungszweck",
    "purpose",
    "memo",
}
_PARTY_ALIASES = {
    "counterparty",
    "gegenpartei",
    "empfaenger",
    "empfänger",
    "beguenstigter",
    "begünstigter",
    "auftraggeber",
    "merchant",
    "payee",
}
_AMOUNT_ALIASES = {"amount", "betrag", "umsatz", "value"}
_DEBIT_ALIASES = {"debit", "belastung", "soll"}
_CREDIT_ALIASES = {"credit", "gutschrift", "haben"}
_CURRENCY_ALIASES = {"currency", "waehrung", "währung", "whg", "ccy"}


def _validate_source(path: Path) -> None:
    if not path.exists() or not path.is_file():
        raise BankStatementError(f"Datei nicht gefunden: {path}")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise BankStatementError(
            f"Dateigröße konnte nicht gelesen werden: {exc}"
        ) from exc
    if size > MAX_SOURCE_BYTES:
        raise BankStatementError("Datei ist größer als 50 MB.")


def _norm_header(value: str) -> str:
    value = str(value or "").strip().casefold()
    value = (
        value.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    return re.sub(r"[^a-z0-9]+", "", value)


def _pick(
    fieldnames: Iterable[str], aliases: Iterable[str], *, prefix: bool = True
) -> str | None:
    normalized = {_norm_header(name): name for name in fieldnames if name}
    wanted = [_norm_header(alias) for alias in aliases]
    for alias in wanted:
        if alias in normalized:
            return normalized[alias]
    if prefix:
        for alias in wanted:
            if len(alias) < 4:
                continue
            for key, original in normalized.items():
                if key.startswith(alias):
                    return original
    return None


def _matching_columns(fieldnames: Iterable[str], aliases: set[str]) -> list[str]:
    wanted = {_norm_header(alias) for alias in aliases}
    result: list[str] = []
    for original in fieldnames:
        key = _norm_header(original)
        if key in wanted or any(
            len(alias) >= 4 and key.startswith(alias) for alias in wanted
        ):
            result.append(original)
    return result


def _parse_date(raw: str) -> date:
    value = str(raw or "").replace("\u00a0", " ").strip().strip('"').strip("'")
    if not value:
        raise BankStatementError("Leeres Datum.")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    candidate = re.split(r"[ T]", value, maxsplit=1)[0].rstrip(",;")
    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%Y%m%d",
        "%d%m%Y",
    ):
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    raise BankStatementError(f"Unbekanntes Datumsformat: {value!r}")


def _parse_decimal(raw: str) -> Decimal:
    value = str(raw or "").strip()
    if not value:
        return Decimal("0")
    negative_parentheses = value.startswith("(") and value.endswith(")")
    value = value.strip("()")
    value = re.sub(r"[^0-9,.'+\-]", "", value).replace("'", "")
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        parts = value.split(",")
        value = (
            "".join(parts[:-1]) + "." + parts[-1]
            if len(parts[-1]) in {1, 2}
            else "".join(parts)
        )
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise BankStatementError(f"Ungültiger Betrag: {raw!r}") from exc
    return -result if negative_parentheses and result > 0 else result


def _decode_csv(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise BankStatementError("CSV-Zeichensatz konnte nicht erkannt werden.")


def _currency_from_columns(*columns: str | None) -> str | None:
    for column in columns:
        if not column:
            continue
        match = re.search(r"(?:^|\s)([A-Z]{3})(?:\s|$)", str(column).upper())
        if match:
            return match.group(1)
    return None


def _joined_text(row: dict[str, str], columns: list[str]) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for column in columns:
        value = str(row.get(column, "") or "").strip()
        key = value.casefold()
        if value and key not in seen:
            values.append(value)
            seen.add(key)
    return " | ".join(values)


class SemicolonExcel(csv.excel):
    """Fallback-Dialekt, wenn der Sniffer kein Trennzeichen erkennt.

    Vorher wurde dafuer ``csv.excel.delimiter`` selbst auf ";" gesetzt. Das
    ist eine Klasse, kein Objekt - die Zuweisung veraenderte den
    Standarddialekt fuer den gesamten Prozess, also auch fuer jeden spaeteren
    CSV-Leser ausserhalb des Bankimports.
    """

    delimiter = ";"


def load_csv(path: str | Path, default_currency: str = "CHF") -> list[BankTransaction]:
    source = Path(path)
    _validate_source(source)
    text = _decode_csv(source)
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = SemicolonExcel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    if not reader.fieldnames:
        raise BankStatementError("CSV enthält keine Kopfzeile.")

    # Buchungsdatum hat Vorrang. Valuta ist nur ein Fallback, wenn eine Bank
    # überhaupt kein Buchungsdatum exportiert. ZKB darf Valuta leer lassen.
    date_col = _pick(reader.fieldnames, _BOOKING_DATE_ALIASES)
    if not date_col:
        date_col = _pick(reader.fieldnames, _VALUE_DATE_ALIASES)

    amount_col = _pick(reader.fieldnames, _AMOUNT_ALIASES, prefix=False)
    debit_col = _pick(reader.fieldnames, _DEBIT_ALIASES)
    credit_col = _pick(reader.fieldnames, _CREDIT_ALIASES)
    currency_col = _pick(reader.fieldnames, _CURRENCY_ALIASES, prefix=False)
    party_col = _pick(reader.fieldnames, _PARTY_ALIASES)
    text_cols = _matching_columns(reader.fieldnames, _DESC_ALIASES)

    if not date_col or not (amount_col or debit_col or credit_col):
        raise BankStatementError(
            "CSV benötigt Datum und Betrag oder Belastung/Gutschrift. "
            "Gefundene Spalten: " + ", ".join(str(name) for name in reader.fieldnames)
        )

    # ZKB: Betrag Detail ist Fremdwährungs-Detail; Belastung/Gutschrift CHF
    # sind maßgeblich.
    if debit_col or credit_col:
        amount_col = None

    result: list[BankTransaction] = []
    for index, raw_row in enumerate(reader, start=1):
        if index > MAX_CSV_ROWS:
            raise BankStatementError(
                f"CSV enthält mehr als {MAX_CSV_ROWS:,} Datenzeilen."
            )
        row = {str(k): str(v or "") for k, v in raw_row.items()}
        if not any(value.strip() for value in row.values()):
            continue
        if amount_col:
            amount = _parse_decimal(row.get(amount_col, ""))
        else:
            debit = (
                _parse_decimal(row.get(debit_col, "")) if debit_col else Decimal("0")
            )
            credit = (
                _parse_decimal(row.get(credit_col, "")) if credit_col else Decimal("0")
            )
            amount = credit - abs(debit)
        if amount == 0:
            continue
        try:
            booking_date = _parse_date(row.get(date_col, ""))
        except BankStatementError as exc:
            raise BankStatementError(
                f"CSV-Zeile {index + 1}, Spalte {date_col!r}: {exc}"
            ) from exc

        if debit_col or credit_col:
            currency = _currency_from_columns(debit_col, credit_col) or default_currency
        else:
            currency = (
                row.get(currency_col, "") if currency_col else default_currency
            ) or default_currency
        currency = currency.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise BankStatementError(f"Ungültiger Währungscode: {currency!r}")

        description = _joined_text(row, text_cols)
        counterparty = row.get(party_col, "").strip() if party_col else ""
        result.append(
            BankTransaction(
                source_kind="csv",
                source_name=source.name,
                source_index=index,
                booking_date=booking_date,
                amount=amount,
                currency=currency,
                description=description or counterparty or "CSV-Import",
                counterparty=counterparty,
                raw=row,
            )
        )
    return result


@dataclass
class _ZkbPending:
    source_index: int
    booking_date: date
    amount: Decimal
    description: str
    valuta: str
    saldo: str
    line: str


_ZKB_LAYOUT_LABELS = (
    "datum",
    "buchungstext",
    "belastung chf",
    "gutschrift chf",
    "valuta",
    "saldo chf",
)
_PDF_DATE_TOKEN = r"(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{2}-\d{2})"
_PDF_AMOUNT_TOKEN = r"(?:[+\-(]?(?:\d{1,3}(?:[' ]\d{3})+|\d+)(?:[.,]\d{1,2})?[)]?)"
_PDF_LINE = re.compile(
    rf"^(?P<date>{_PDF_DATE_TOKEN})\s+"
    rf"(?P<text>.+?)\s+(?P<amount>{_PDF_AMOUNT_TOKEN})"
    r"\s*(?P<currency>[A-Z]{3})?$"
)
_ZKB_FLAT_TAIL = re.compile(
    rf"\s{_PDF_AMOUNT_TOKEN}\s+{_PDF_DATE_TOKEN}\s+{_PDF_AMOUNT_TOKEN}\s*$"
)


def _zkb_header_positions(line: str) -> dict[str, int] | None:
    lowered = line.casefold()
    positions = {label: lowered.find(label) for label in _ZKB_LAYOUT_LABELS}
    if any(position < 0 for position in positions.values()):
        return None
    ordered = [positions[label] for label in _ZKB_LAYOUT_LABELS]
    if ordered != sorted(ordered) or len(set(ordered)) != len(ordered):
        return None
    return positions


def _slice_layout_column(line: str, start: int, end: int | None = None) -> str:
    if start >= len(line):
        return ""
    return line[start:end].strip()


def _parse_zkb_layout_lines(
    lines: list[str],
    *,
    source_name: str,
    default_currency: str,
) -> list[BankTransaction]:
    """Parst ZKB-Text-PDFs anhand der sichtbaren Tabellenspalten.

    Entscheidend ist die Spaltenlage: Ein Tail wie
    ``19.85 21.08.2026 5'179.55`` bedeutet Betrag, Valuta und Saldo und darf
    niemals als einzelner Betrag interpretiert werden.
    """
    result: list[BankTransaction] = []
    positions: dict[str, int] | None = None
    pending: _ZkbPending | None = None

    def flush_pending() -> None:
        nonlocal pending
        if not pending:
            return
        if pending.amount == 0:
            pending = None
            return
        result.append(
            BankTransaction(
                source_kind="pdf",
                source_name=source_name,
                source_index=pending.source_index,
                booking_date=pending.booking_date,
                amount=pending.amount,
                currency=default_currency.upper(),
                description=pending.description.strip() or "ZKB PDF-Import",
                raw={
                    "line": pending.line,
                    "valuta": pending.valuta,
                    "saldo": pending.saldo,
                    "layout": "zkb",
                },
            )
        )
        pending = None

    for index, line in enumerate(lines, start=1):
        header = _zkb_header_positions(line)
        if header is not None:
            flush_pending()
            positions = header
            continue
        if positions is None:
            continue

        date_start = positions["datum"]
        text_start = positions["buchungstext"]
        debit_start = positions["belastung chf"]
        credit_start = positions["gutschrift chf"]
        value_start = positions["valuta"]
        balance_start = positions["saldo chf"]

        raw_date = _slice_layout_column(line, date_start, text_start)
        description = _slice_layout_column(line, text_start, debit_start)
        debit_raw = _slice_layout_column(line, debit_start, credit_start)
        credit_raw = _slice_layout_column(line, credit_start, value_start)
        valuta_raw = _slice_layout_column(line, value_start, balance_start)
        saldo_raw = _slice_layout_column(line, balance_start, None)

        is_transaction_start = bool(re.fullmatch(_PDF_DATE_TOKEN, raw_date))
        if not is_transaction_start:
            # Fortsetzungszeilen im Buchungstext gehören zur vorherigen
            # Transaktion. Kontakt-/Footertext außerhalb der Textspalte wird
            # ignoriert.
            if pending and description:
                pending.description = f"{pending.description} | {description}"
            continue

        flush_pending()

        debit = _parse_decimal(debit_raw) if debit_raw else Decimal("0")
        credit = _parse_decimal(credit_raw) if credit_raw else Decimal("0")
        if debit and credit:
            raise BankStatementError(
                f"ZKB-PDF-Zeile {index}: Belastung und Gutschrift sind "
                "gleichzeitig befüllt."
            )
        amount = credit - abs(debit)
        if amount == 0:
            # Zeilen mit Datum aber ohne Betrag sind z.B. reine
            # Saldo-/Hinweiszeilen und keine Buchung.
            continue

        if valuta_raw:
            try:
                _parse_date(valuta_raw)
            except BankStatementError as exc:
                raise BankStatementError(
                    f"ZKB-PDF-Zeile {index}, Spalte 'Valuta': {exc}"
                ) from exc
        if saldo_raw:
            _parse_decimal(saldo_raw)

        pending = _ZkbPending(
            source_index=index,
            booking_date=_parse_date(raw_date),
            amount=amount,
            description=description,
            valuta=valuta_raw,
            saldo=saldo_raw,
            line=line,
        )

    flush_pending()
    return result


def _extract_pdf_page_text(page: Any) -> str:
    extract_text = getattr(page, "extract_text", None)
    if not callable(extract_text):
        return ""
    try:
        return str(extract_text(extraction_mode="layout") or "")
    except TypeError:
        # Defensiver Rückfall für ältere pypdf-Versionen. Der gepinnte
        # BudgetManager-Build verwendet pypdf 6.x und nimmt den Layout-Pfad.
        return str(extract_text() or "")


def load_pdf(path: str | Path, default_currency: str = "CHF") -> list[BankTransaction]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise BankStatementError(
            "PDF-Unterstützung benötigt das Runtime-Paket 'pypdf'."
        ) from exc
    source = Path(path)
    _validate_source(source)
    reader = PdfReader(str(source))
    if len(reader.pages) > MAX_PDF_PAGES:
        raise BankStatementError(f"PDF enthält mehr als {MAX_PDF_PAGES} Seiten.")
    lines: list[str] = []
    text_chars = 0
    for page in reader.pages:
        text = _extract_pdf_page_text(page)
        text_chars += len(text)
        if text_chars > MAX_PDF_TEXT_CHARS:
            raise BankStatementError("PDF enthält zu viel extrahierten Text.")
        lines.extend(line.rstrip() for line in text.splitlines() if line.strip())
    if not lines:
        raise BankStatementError(
            "PDF enthält keinen extrahierbaren Text. " "Scan-PDFs benötigen lokale OCR."
        )

    zkb_rows = _parse_zkb_layout_lines(
        lines,
        source_name=source.name,
        default_currency=default_currency,
    )
    if zkb_rows:
        return zkb_rows

    result: list[BankTransaction] = []
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        # ZKB-Flachtext ohne Layout endet typischerweise mit
        # "<Betrag> <Valuta> <Saldo>". Die letzte Zahl ist der Kontosaldo und
        # darf niemals als Buchungsbetrag in den generischen Parser fallen.
        if _ZKB_FLAT_TAIL.search(stripped):
            continue
        match = _PDF_LINE.match(stripped)
        if not match:
            continue
        amount = _parse_decimal(match.group("amount"))
        if amount == 0:
            continue
        currency = (match.group("currency") or default_currency).upper()
        result.append(
            BankTransaction(
                source_kind="pdf",
                source_name=source.name,
                source_index=index,
                booking_date=_parse_date(match.group("date")),
                amount=amount,
                currency=currency,
                description=match.group("text").strip(),
                raw={"line": line},
            )
        )
    if not result:
        raise BankStatementError(
            "PDF-Text gelesen, aber kein unterstütztes Buchungsformat erkannt."
        )
    return result


def load_transactions(
    path: str | Path, default_currency: str = "CHF"
) -> list[BankTransaction]:
    source = Path(path)
    suffix = source.suffix.casefold()
    if suffix == ".csv":
        return load_csv(source, default_currency)
    if suffix == ".pdf":
        return load_pdf(source, default_currency)
    raise BankStatementError("Unterstützt werden aktuell PDF und CSV.")
