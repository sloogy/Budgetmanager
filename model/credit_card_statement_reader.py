"""Strukturierter CSV-Reader für Kreditkartenexporte.

Er ergänzt den generischen Bank-Reader um das Kartenformat mit Spalten wie
TransactionId, CardId, Date, ValutaDate, Amount, Currency, OriginalAmount,
OriginalCurrency, MerchantName, MerchantPlace und MerchantCountry.

Das Vorzeichen von ``Amount`` wird absichtlich unverändert übernommen. Der
Importdialog schlägt daraus einen BudgetManager-Typ vor, der Nutzer kann ihn
vor dem Import jedoch ändern.
"""
from __future__ import annotations

import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from model.bank_statement_reader import BankStatementError, BankTransaction

_REQUIRED_HEADERS = frozenset(
    {
        "transactionid",
        "cardid",
        "date",
        "amount",
        "currency",
        "merchantname",
    }
)
_MAX_SOURCE_BYTES = 50 * 1024 * 1024
_MAX_ROWS = 50_000


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().casefold())


def _decode(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise BankStatementError("CSV-Zeichensatz konnte nicht erkannt werden.")


def _dialect(text: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
        return dialect


def _header_map(fieldnames: list[str] | None) -> dict[str, str]:
    return {_norm(name): str(name) for name in (fieldnames or []) if name is not None}


def is_credit_card_csv(path: str | Path) -> bool:
    source = Path(path)
    if source.suffix.casefold() != ".csv" or not source.is_file():
        return False
    try:
        text = _decode(source)
        reader = csv.reader(text.splitlines(), dialect=_dialect(text))
        header = next(reader, [])
    except (OSError, csv.Error, BankStatementError):
        return False
    normalized = {_norm(name) for name in header}
    return _REQUIRED_HEADERS.issubset(normalized)


def _parse_date(raw: str):
    from datetime import datetime

    value = str(raw or "").strip().strip('"').strip("'")
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
        pieces = value.split(",")
        value = (
            "".join(pieces[:-1]) + "." + pieces[-1]
            if len(pieces[-1]) in {1, 2}
            else "".join(pieces)
        )
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise BankStatementError(f"Ungültiger Betrag: {raw!r}") from exc
    return -result if negative_parentheses and result > 0 else result


def _value(row: dict[str, str], headers: dict[str, str], key: str) -> str:
    column = headers.get(key)
    return str(row.get(column, "") or "").strip() if column else ""


def _description(row: dict[str, str], headers: dict[str, str]) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for key in ("merchantname", "merchantplace", "merchantcountry", "details", "type"):
        value = _value(row, headers, key)
        folded = value.casefold()
        if value and folded not in seen:
            values.append(value)
            seen.add(folded)
    return " | ".join(values)


def load_credit_card_csv(
    path: str | Path,
    default_currency: str = "CHF",
) -> list[BankTransaction]:
    source = Path(path)
    if not source.exists() or not source.is_file():
        raise BankStatementError(f"Datei nicht gefunden: {source}")
    if source.stat().st_size > _MAX_SOURCE_BYTES:
        raise BankStatementError("Datei ist größer als 50 MB.")

    text = _decode(source)
    reader = csv.DictReader(text.splitlines(), dialect=_dialect(text))
    headers = _header_map(reader.fieldnames)
    missing = sorted(_REQUIRED_HEADERS - set(headers))
    if missing:
        raise BankStatementError(
            "Kreditkarten-CSV: Pflichtspalten fehlen: " + ", ".join(missing)
        )

    result: list[BankTransaction] = []
    for index, raw_row in enumerate(reader, start=1):
        if index > _MAX_ROWS:
            raise BankStatementError(f"CSV enthält mehr als {_MAX_ROWS:,} Datenzeilen.")
        row = {str(key): str(value or "") for key, value in raw_row.items() if key is not None}
        if not any(value.strip() for value in row.values()):
            continue

        amount = _parse_decimal(_value(row, headers, "amount"))
        if amount == 0:
            continue
        try:
            booking_date = _parse_date(_value(row, headers, "date"))
        except BankStatementError as exc:
            date_column = headers.get("date", "Date")
            raise BankStatementError(
                f"CSV-Zeile {index + 1}, Spalte {date_column!r}: {exc}"
            ) from exc

        currency = (_value(row, headers, "currency") or default_currency).upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise BankStatementError(f"Ungültiger Währungscode: {currency!r}")

        merchant = _value(row, headers, "merchantname")
        description = _description(row, headers) or merchant or "Kreditkarten-Import"
        result.append(
            BankTransaction(
                source_kind="credit_card_csv",
                source_name=source.name,
                source_index=index,
                booking_date=booking_date,
                amount=amount,
                currency=currency,
                description=description,
                counterparty=merchant,
                raw=row,
            )
        )
    return result
