from datetime import date
from decimal import Decimal

from model.bank_statement_reader import load_csv


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


def test_csv_accepts_timestamp_and_short_date(tmp_path):
    path = tmp_path / "bank.csv"
    path.write_text(
        "Buchungsdatum (TT.MM.JJJJ);Beschreibung;Betrag;Währung\n"
        "23.08.2026 00:00:00;Einkauf;-12,50;CHF\n"
        "24/08/26;Kaffee;-4,50;CHF\n",
        encoding="utf-8",
    )
    rows = load_csv(path)
    assert [row.booking_date for row in rows] == [date(2026, 8, 23), date(2026, 8, 24)]
