#!/usr/bin/env python3
"""Misst, wie lange ein einzelner atomarer Importblock die Oberflaeche sperrt.

Warum es das gibt: P1.5 haelt den finalen Bankimport bewusst im Bedien-Thread
(Regel 1.4) und schreibt je Quelldatei genau **einen** atomaren Block (Regel
1.8). Waehrend dieses Blocks laeuft keine Ereignisschleife - die Oberflaeche
steht. P1.5 hat diese Dauer nie gemessen und die Frage ausdruecklich an das
PHASE-1-GATE uebergeben: Ist der eine Block bei einer sehr grossen Einzeldatei
noch tragbar, oder wirkt die Anwendung eingefroren?

Gemessen wird deshalb nicht ein Mikrobenchmark, sondern der echte Weg:

1. eine ZKB-artige CSV mit ``n`` Zeilen auf die Platte schreiben (echte
   Dateigroesse statt geschaetzter),
2. sie mit ``load_csv`` einlesen - das ist der Anteil, der seit P1.3 im
   Worker-Thread liegt und die Oberflaeche **nicht** sperrt,
3. ``BankImportService.import_items`` gegen eine echte Datei-Datenbank fahren -
   das ist der eine atomare Block, der sie sehr wohl sperrt.

Mit ``--verschluesselt`` laeuft derselbe Import gegen eine echte
``EncryptedSession``. Das ist der Modus, in dem die Anwendung normalerweise
arbeitet, und der Unterschied ist keine Nuance: Jeder ``commit()`` schreibt dort
ueber den Auto-Save-Rueckruf die **ganze** ``.enc``-Datei neu. Gezaehlt wird
deshalb zusaetzlich, wie oft das waehrend eines einzigen Imports passiert.

Aufruf::

    QT_QPA_PLATFORM=offscreen python tools/mess_import_blockdauer.py
    python tools/mess_import_blockdauer.py --zeilen 500 2000 10000
    python tools/mess_import_blockdauer.py --verschluesselt --zeilen 250 500
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model.bank_import_service import (
    BankImportItem,
    BankImportService,
)
from model.bank_statement_reader import load_csv
from model.category_model import CategoryModel
from model.migrations import migrate_all
from model.typ_constants import TYP_EXPENSES

KATEGORIE = "Messkategorie"

KOPF = (
    "Datum;Buchungstext;Whg;Betrag Detail;ZKB-Referenz;Referenznummer;"
    "Belastung CHF;Gutschrift CHF;Valuta;Saldo CHF;Zahlungszweck;Details\n"
)

HAENDLER = (
    "COOP Einkauf",
    "MIGROS Supermarkt",
    "SBB Billett",
    "Apotheke Zentral",
    "Restaurant Sonne",
    "Tankstelle Nord",
    "Buchhandlung Orell",
    "TWINT Zahlung",
)


def csv_schreiben(pfad: Path, zeilen: int) -> None:
    """Schreibt eine ZKB-artige Kontoauszugsdatei mit ``zeilen`` Buchungen."""
    teile = [KOPF]
    for index in range(zeilen):
        tag = index % 28 + 1
        monat = index // 28 % 12 + 1
        betrag = f"{index % 900 + 5},{index % 100:02d}"
        haendler = HAENDLER[index % len(HAENDLER)]
        teile.append(
            f"{tag:02d}.{monat:02d}.2026;Kartenzahlung;CHF;;ZKB-{index};"
            f"REF-{index};{betrag};;{tag:02d}.{monat:02d}.2026;1'000,00;"
            f"{haendler} {index};Filiale Winterthur\n"
        )
    pfad.write_text("".join(teile), encoding="utf-8")


def datenbank_vorbereiten(pfad: Path) -> sqlite3.Connection:
    """Echte Datei-DB statt ``:memory:`` - der Block soll Platten-I/O sehen."""
    conn = sqlite3.connect(str(pfad))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_all(conn)
    CategoryModel(conn).create(TYP_EXPENSES, KATEGORIE)
    return conn


def verschluesselte_sitzung(basis: Path):
    """Baut eine echte ``EncryptedSession`` - der Normalmodus der Anwendung.

    Wichtig fuer die Messung: Diese Sitzung haengt einen Auto-Save an jeden
    erfolgreichen Commit. Ein Import mit vielen kleinen Commits schreibt die
    verschluesselte Datei entsprechend oft komplett neu.
    """
    from cryptography.fernet import Fernet

    from model.crypto import encrypt_db_to_file
    from model.database import EncryptedSession

    vorlage = sqlite3.connect(":memory:")
    vorlage.row_factory = sqlite3.Row
    migrate_all(vorlage)
    CategoryModel(vorlage).create(TYP_EXPENSES, KATEGORIE)
    schluessel = Fernet.generate_key()
    salz = os.urandom(16)
    enc_pfad = basis / "user.enc"
    encrypt_db_to_file(vorlage, str(enc_pfad), schluessel, salz)
    vorlage.close()
    return EncryptedSession.open_with_key(str(enc_pfad), schluessel, salz), enc_pfad


def messen(zeilen: int, *, verschluesselt: bool = False) -> dict[str, float | int]:
    """Fuehrt einen vollstaendigen Durchgang aus und liefert die Zahlen."""
    with tempfile.TemporaryDirectory() as ordner:
        basis = Path(ordner)
        csv_pfad = basis / "kontoauszug.csv"
        csv_schreiben(csv_pfad, zeilen)
        groesse = csv_pfad.stat().st_size

        beginn = time.perf_counter()
        transaktionen = load_csv(csv_pfad)
        lesedauer = time.perf_counter() - beginn

        schreibvorgaenge = 0
        sitzung = None
        if verschluesselt:
            sitzung, _ = verschluesselte_sitzung(basis)
            conn = sitzung.conn
            echt_speichern = sitzung.save

            def gezaehlt(*args, **kwargs):
                nonlocal schreibvorgaenge
                schreibvorgaenge += 1
                return echt_speichern(*args, **kwargs)

            sitzung.save = gezaehlt  # type: ignore[method-assign]
        else:
            conn = datenbank_vorbereiten(basis / "mess.db")

        try:
            service = BankImportService(conn)
            posten = [
                BankImportItem(
                    transaction=tx,
                    typ=TYP_EXPENSES,
                    category=KATEGORIE,
                    tags=(),
                    amount=float(abs(Decimal(tx.amount))),
                    details=tx.description,
                )
                for tx in transaktionen
            ]
            digest = "c" * 64
            beginn = time.perf_counter()
            ergebnis = service.import_items(posten, document_digest=digest)
            blockdauer = time.perf_counter() - beginn
            offen = bool(conn.in_transaction)
        finally:
            if sitzung is not None:
                sitzung.freeze()
            conn.close()

        return {
            "zeilen": zeilen,
            "dateigroesse": groesse,
            "gelesen": len(transaktionen),
            "geschrieben": ergebnis.imported,
            "lesedauer": lesedauer,
            "blockdauer": blockdauer,
            "transaktion_offen": int(offen),
            "enc_schreibvorgaenge": schreibvorgaenge,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--zeilen",
        type=int,
        nargs="+",
        default=[100, 500, 1000, 2500, 5000],
        help="Buchungszahlen, die gemessen werden sollen",
    )
    parser.add_argument(
        "--verschluesselt",
        action="store_true",
        help="gegen eine echte EncryptedSession messen (Normalmodus der Anwendung)",
    )
    argumente = parser.parse_args()

    print(
        f"{'Zeilen':>7} {'CSV (KiB)':>10} {'Lesen (s)':>10} "
        f"{'Block (s)':>10} {'ms/Zeile':>9} {'Tx offen':>9} {'.enc-Writes':>12}"
    )
    for zeilen in argumente.zeilen:
        werte = messen(zeilen, verschluesselt=argumente.verschluesselt)
        assert werte["gelesen"] == zeilen, "CSV wurde nicht vollstaendig gelesen"
        assert werte["geschrieben"] == zeilen, "Block hat nicht alles geschrieben"
        print(
            f"{werte['zeilen']:>7} "
            f"{float(werte['dateigroesse']) / 1024:>10.1f} "
            f"{float(werte['lesedauer']):>10.3f} "
            f"{float(werte['blockdauer']):>10.3f} "
            f"{float(werte['blockdauer']) * 1000 / max(1, zeilen):>9.2f} "
            f"{'ja' if werte['transaktion_offen'] else 'nein':>9} "
            f"{werte['enc_schreibvorgaenge']:>12}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
