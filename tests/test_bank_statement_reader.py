from datetime import date
from decimal import Decimal

import pypdf

from model.bank_statement_reader import load_csv, load_pdf


def test_zkb_csv_uses_chf_debit_credit_not_betrag_detail(tmp_path):
    path = tmp_path / "zkb.csv"
    path.write_text(
        "Datum;Buchungstext;Whg;Betrag Detail;ZKB-Referenz;Referenznummer;"
        "Belastung CHF;Gutschrift CHF;Valuta;Saldo CHF;Zahlungszweck;Details\n"
        "23.08.2026;Kartenzahlung;EUR;12,34;ZKB-1;REF-1;10,00;;24.08.2026;"
        "1'000,00;COOP Einkauf;Filiale Winterthur\n"
        "22.08.2026;Rückzahlung;CHF;25,00;ZKB-2;REF-2;;25,00;22.08.2026;"
        "1'025,00;TWINT erhalten;Geteilte Kosten\n",
        encoding="utf-8",
    )

    rows = load_csv(path)
    assert len(rows) == 2
    assert rows[0].booking_date == date(2026, 8, 23)
    assert rows[0].amount == Decimal("-10.00")
    assert rows[0].currency == "CHF"
    assert "Kartenzahlung" in rows[0].description
    assert "COOP Einkauf" in rows[0].description
    assert "Filiale Winterthur" in rows[0].description
    assert rows[0].raw["Whg"] == "EUR"
    assert rows[0].raw["Betrag Detail"] == "12,34"
    assert rows[1].amount == Decimal("25.00")


def test_zkb_csv_prefers_datum_when_valuta_is_empty(tmp_path):
    path = tmp_path / "zkb-empty-valuta.csv"
    path.write_text(
        "Datum;Buchungstext;Whg;Betrag Detail;ZKB-Referenz;Referenznummer;"
        "Belastung CHF;Gutschrift CHF;Valuta;Saldo CHF;Zahlungszweck;Details\n"
        "23.08.2026;Kartenzahlung;CHF;;ZKB-3;REF-3;19,85;;;5'179,55;"
        "COOP Einkauf;Filiale Winterthur\n",
        encoding="utf-8",
    )

    rows = load_csv(path)

    assert len(rows) == 1
    assert rows[0].booking_date == date(2026, 8, 23)
    assert rows[0].amount == Decimal("-19.85")
    assert rows[0].raw["Valuta"] == ""


def test_csv_uses_valuta_only_when_booking_date_column_is_missing(tmp_path):
    path = tmp_path / "valuta-only.csv"
    path.write_text(
        "Valuta;Beschreibung;Betrag;Währung\n"
        "23.08.2026;Kaffee;-4,50;CHF\n",
        encoding="utf-8",
    )

    rows = load_csv(path)

    assert len(rows) == 1
    assert rows[0].booking_date == date(2026, 8, 23)
    assert rows[0].amount == Decimal("-4.50")


def test_csv_accepts_timestamp_and_short_date(tmp_path):
    path = tmp_path / "bank.csv"
    path.write_text(
        "Buchungsdatum (TT.MM.JJJJ);Beschreibung;Betrag;Währung\n"
        "23.08.2026 00:00:00;Einkauf;-12,50;CHF\n"
        "24/08/26;Kaffee;-4,50;CHF\n",
        encoding="utf-8",
    )
    rows = load_csv(path)
    assert [row.booking_date for row in rows] == [
        date(2026, 8, 23),
        date(2026, 8, 24),
    ]


def test_pdf_reader_uses_pypdf_text_and_parses_booking_line(tmp_path, monkeypatch):
    path = tmp_path / "konto.pdf"
    path.write_bytes(b"%PDF-1.4 test placeholder")

    class FakePage:
        def extract_text(self):
            return "23.08.2026 COOP Einkauf -12,50 CHF\n"

    class FakeReader:
        def __init__(self, _path):
            self.pages = [FakePage()]

    monkeypatch.setattr(pypdf, "PdfReader", FakeReader)
    rows = load_pdf(path)

    assert len(rows) == 1
    assert rows[0].booking_date == date(2026, 8, 23)
    assert rows[0].amount == Decimal("-12.50")
    assert rows[0].currency == "CHF"
    assert rows[0].description == "COOP Einkauf"


def test_zkb_pdf_separates_amount_valuta_and_balance(tmp_path, monkeypatch):
    path = tmp_path / "zkb-konto.pdf"
    path.write_bytes(b"%PDF-1.4 test placeholder")
    balance_debit = "5'179.55"
    balance_credit = "5'219.55"

    header = (
        f"{'Datum':<12}{'Buchungstext':<42}{'Belastung CHF':<16}"
        f"{'Gutschrift CHF':<22}{'Valuta':<12}{'Saldo CHF'}"
    )
    debit_line = (
        f"{'21.08.2026':<12}{'Kartenzahlung COOP':<42}{'19.85':<16}"
        f"{'':<22}{'21.08.2026':<12}{balance_debit}"
    )
    credit_line = (
        f"{'22.08.2026':<12}{'TWINT Zahlung erhalten':<42}{'':<16}"
        f"{'40.00':<22}{'22.08.2026':<12}{balance_credit}"
    )

    class FakePage:
        def extract_text(self, *, extraction_mode=None):
            assert extraction_mode == "layout"
            return "\n".join((header, debit_line, credit_line))

    class FakeReader:
        def __init__(self, _path):
            self.pages = [FakePage()]

    monkeypatch.setattr(pypdf, "PdfReader", FakeReader)
    rows = load_pdf(path)

    assert len(rows) == 2
    assert rows[0].booking_date == date(2026, 8, 21)
    assert rows[0].amount == Decimal("-19.85")
    assert rows[0].raw["valuta"] == "21.08.2026"
    assert rows[0].raw["saldo"] == balance_debit
    assert rows[1].booking_date == date(2026, 8, 22)
    assert rows[1].amount == Decimal("40.00")
    assert rows[1].raw["saldo"] == balance_credit
