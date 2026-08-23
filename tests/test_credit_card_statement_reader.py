from datetime import date
from decimal import Decimal

from model.bank_import_service import external_id
from model.credit_card_statement_reader import (
    is_credit_card_csv,
    load_credit_card_csv,
)


def test_credit_card_csv_header_from_real_export_is_detected(tmp_path):
    path = tmp_path / "credit-card.csv"
    path.write_text(
        "TransactionId;CardId;Date;ValutaDate;Amount;Currency;;OriginalAmount;"
        "OriginalCurrency;MerchantName;MerchantPlace;MerchantCountry;StateType;"
        "Details;Type;Exchange Rate\n"
        "TX-123;CARD-1;21.08.2026;22.08.2026;-19.85;CHF;;21.30;EUR;"
        "COOP;Winterthur;CH;BOOKED;Mittagessen;PURCHASE;0.9319\n",
        encoding="utf-8",
    )

    assert is_credit_card_csv(path) is True

    rows = load_credit_card_csv(path)
    assert len(rows) == 1
    tx = rows[0]
    assert tx.source_kind == "credit_card_csv"
    assert tx.booking_date == date(2026, 8, 21)
    assert tx.amount == Decimal("-19.85")
    assert tx.currency == "CHF"
    assert tx.counterparty == "COOP"
    assert "COOP" in tx.description
    assert "Winterthur" in tx.description
    assert "CH" in tx.description
    assert "Mittagessen" in tx.description
    assert tx.raw["TransactionId"] == "TX-123"
    assert tx.raw["OriginalAmount"] == "21.30"
    assert tx.raw["OriginalCurrency"] == "EUR"
    assert tx.raw["Exchange Rate"] == "0.9319"


def test_credit_card_amount_sign_is_preserved(tmp_path):
    path = tmp_path / "credit-card-refund.csv"
    path.write_text(
        "TransactionId;CardId;Date;ValutaDate;Amount;Currency;;OriginalAmount;"
        "OriginalCurrency;MerchantName;MerchantPlace;MerchantCountry;StateType;"
        "Details;Type;Exchange Rate\n"
        "TX-REFUND;CARD-1;22.08.2026;22.08.2026;12.50;CHF;;12.50;CHF;"
        "SHOP;Zürich;CH;BOOKED;Rückerstattung;REFUND;1.0\n",
        encoding="utf-8",
    )

    tx = load_credit_card_csv(path)[0]
    assert tx.amount == Decimal("12.50")


def test_transaction_id_deduplicates_across_different_export_files(tmp_path):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    header = (
        "TransactionId;CardId;Date;ValutaDate;Amount;Currency;;OriginalAmount;"
        "OriginalCurrency;MerchantName;MerchantPlace;MerchantCountry;StateType;"
        "Details;Type;Exchange Rate\n"
    )
    row = (
        "TX-STABLE;CARD-1;21.08.2026;22.08.2026;-19.85;CHF;;21.30;EUR;"
        "COOP;Winterthur;CH;BOOKED;Einkauf;PURCHASE;0.9319\n"
    )
    first.write_text(header + row, encoding="utf-8")
    second.write_text(header + row, encoding="utf-8")

    tx1 = load_credit_card_csv(first)[0]
    tx2 = load_credit_card_csv(second)[0]

    assert external_id(tx1, "digest-one") == external_id(tx2, "digest-two")
