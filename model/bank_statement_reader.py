"""Lokaler CSV/PDF-Kontoauszug-Reader für BudgetManager.

Keine Netzwerkzugriffe. CSV unterstützt u.a. ZKB-Exporte; PDF nutzt pypdf
für Text-PDFs. Scan-PDFs werden bewusst abgelehnt, bis lokale OCR vorhanden ist.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

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


_DATE_ALIASES = {
    "date", "datum", "buchungsdatum", "buchungstag", "valutadatum", "valuta",
    "bookingdate", "transactiondate", "valuedate",
}
_DESC_ALIASES = {
    "description", "beschreibung", "buchungstext", "text", "details",
    "zahlungszweck", "verwendungszweck", "purpose", "memo",
}
_PARTY_ALIASES = {
    "counterparty", "gegenpartei", "empfaenger", "empfänger", "beguenstigter",
    "begünstigter", "auftraggeber", "merchant", "payee",
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
        raise BankStatementError(f"Dateigröße konnte nicht gelesen werden: {exc}") from exc
    if size > MAX_SOURCE_BYTES:
        raise BankStatementError("Datei ist größer als 50 MB.")


def _norm_header(value: str) -> str:
    value = str(value or "").strip().casefold()
    value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "", value)


def _pick(fieldnames: Iterable[str], aliases: set[str], *, prefix: bool = True) -> str | None:
    normalized = {_norm_header(name): name for name in fieldnames if name}
    wanted = {_norm_header(alias) for alias in aliases}
    for alias in wanted:
        if alias in normalized:
            return normalized[alias]
    if prefix:
        for key, original in normalized.items():
            for alias in wanted:
                if len(alias) >= 4 and key.startswith(alias):
                    return original
    return None


def _matching_columns(fieldnames: Iterable[str], aliases: set[str]) -> list[str]:
    wanted = {_norm_header(alias) for alias in aliases}
    result: list[str] = []
    for original in fieldnames:
        key = _norm_header(original)
        if key in wanted or any(len(alias) >= 4 and key.startswith(alias) for alias in wanted):
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
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%d.%m.%Y", "%d/%m/%Y",
        "%d-%m-%Y", "%d.%m.%y", "%d/%m/%y", "%d-%m-%y", "%Y%m%d", "%d%m%Y",
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
        value = "".join(parts[:-1]) + "." + parts[-1] if len(parts[-1]) in {1, 2} else "".join(parts)
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


def load_csv(path: str | Path, default_currency: str = "CHF") -> list[BankTransaction]:
    source = Path(path)
    _validate_source(source)
    text = _decode_csv(source)
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    if not reader.fieldnames:
        raise BankStatementError("CSV enthält keine Kopfzeile.")

    date_col = _pick(reader.fieldnames, _DATE_ALIASES)
    amount_col = _pick(reader.fieldnames, _AMOUNT_ALIASES, prefix=False)
    debit_col = _pick(reader.fieldnames, _DEBIT_ALIASES)
    credit_col = _pick(reader.fieldnames, _CREDIT_ALIASES)
    currency_col = _pick(reader.fieldnames, _CURRENCY_ALIASES, prefix=False)
    party_col = _pick(reader.fieldnames, _PARTY_ALIASES)
    text_cols = _matching_columns(reader.fieldnames, _DESC_ALIASES)

    if not date_col or not (amount_col or debit_col or credit_col):
        raise BankStatementError(
            "CSV benötigt Datum und Betrag oder Belastung/Gutschrift. Gefundene Spalten: "
            + ", ".join(str(name) for name in reader.fieldnames)
        )

    # ZKB: Betrag Detail ist Fremdwährungs-Detail; Belastung/Gutschrift CHF sind maßgeblich.
    if debit_col or credit_col:
        amount_col = None

    result: list[BankTransaction] = []
    for index, raw_row in enumerate(reader, start=1):
        if index > MAX_CSV_ROWS:
            raise BankStatementError(f"CSV enthält mehr als {MAX_CSV_ROWS:,} Datenzeilen.")
        row = {str(k): str(v or "") for k, v in raw_row.items()}
        if not any(value.strip() for value in row.values()):
            continue
        if amount_col:
            amount = _parse_decimal(row.get(amount_col, ""))
        else:
            debit = _parse_decimal(row.get(debit_col, "")) if debit_col else Decimal("0")
            credit = _parse_decimal(row.get(credit_col, "")) if credit_col else Decimal("0")
            amount = credit - abs(debit)
        if amount == 0:
            continue
        try:
            booking_date = _parse_date(row.get(date_col, ""))
        except BankStatementError as exc:
            raise BankStatementError(f"CSV-Zeile {index + 1}, Spalte {date_col!r}: {exc}") from exc

        if debit_col or credit_col:
            currency = _currency_from_columns(debit_col, credit_col) or default_currency
        else:
            currency = (row.get(currency_col, "") if currency_col else default_currency) or default_currency
        currency = currency.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise BankStatementError(f"Ungültiger Währungscode: {currency!r}")

        description = _joined_text(row, text_cols)
        counterparty = row.get(party_col, "").strip() if party_col else ""
        result.append(BankTransaction(
            source_kind="csv", source_name=source.name, source_index=index,
            booking_date=booking_date, amount=amount, currency=currency,
            description=description or counterparty or "CSV-Import",
            counterparty=counterparty, raw=row,
        ))
    return result


_PDF_LINE = re.compile(
    r"^(?P<date>\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{2}-\d{2})\s+"
    r"(?P<text>.+?)\s+(?P<amount>[+\-(]?[0-9][0-9'., ]*[)]?)\s*(?P<currency>[A-Z]{3})?$"
)


def load_pdf(path: str | Path, default_currency: str = "CHF") -> list[BankTransaction]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise BankStatementError("PDF-Unterstützung benötigt das Runtime-Paket 'pypdf'.") from exc
    source = Path(path)
    _validate_source(source)
    reader = PdfReader(str(source))
    if len(reader.pages) > MAX_PDF_PAGES:
        raise BankStatementError(f"PDF enthält mehr als {MAX_PDF_PAGES} Seiten.")
    lines: list[str] = []
    text_chars = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        text_chars += len(text)
        if text_chars > MAX_PDF_TEXT_CHARS:
            raise BankStatementError("PDF enthält zu viel extrahierten Text.")
        lines.extend(line.strip() for line in text.splitlines() if line.strip())
    if not lines:
        raise BankStatementError("PDF enthält keinen extrahierbaren Text. Scan-PDFs benötigen lokale OCR.")

    result: list[BankTransaction] = []
    for index, line in enumerate(lines, start=1):
        match = _PDF_LINE.match(line)
        if not match:
            continue
        amount = _parse_decimal(match.group("amount"))
        if amount == 0:
            continue
        currency = (match.group("currency") or default_currency).upper()
        result.append(BankTransaction(
            source_kind="pdf", source_name=source.name, source_index=index,
            booking_date=_parse_date(match.group("date")), amount=amount,
            currency=currency, description=match.group("text").strip(), raw={"line": line},
        ))
    if not result:
        raise BankStatementError("PDF-Text gelesen, aber kein generisches Buchungsformat erkannt.")
    return result


def load_transactions(path: str | Path, default_currency: str = "CHF") -> list[BankTransaction]:
    source = Path(path)
    suffix = source.suffix.casefold()
    if suffix == ".csv":
        return load_csv(source, default_currency)
    if suffix == ".pdf":
        return load_pdf(source, default_currency)
    raise BankStatementError("Unterstützt werden aktuell PDF und CSV.")
