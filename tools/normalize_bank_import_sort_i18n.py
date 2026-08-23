#!/usr/bin/env python3
"""Normalisiert die neuen Sortierlabels des Bankimports auf i18n-sichere UI.

3.0.1 wurde mit zehn neuen deutsch hartcodierten Sortierbeschriftungen getaggt.
Der Release-i18n-Audit blockiert solche neuen UI-Literale absichtlich. Dieses
kleine, idempotente Werkzeug ersetzt nur genau diese zehn bekannten Stellen:
vorhandene übersetzte Header-Begriffe werden wiederverwendet, die Richtung
bleibt sprachneutral als Pfeil. Der unveränderliche Tag v3.0.1 bleibt dabei
unangetastet; die Korrektur gehört in den nächsten Release-Commit.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "views" / "bank_import_dialog.py"

REPLACEMENTS = {
    'tools.addWidget(QLabel("Sortierung:"))': 'tools.addWidget(QLabel("↕"))',
    'self.cmb_sort.addItem("Originalreihenfolge", "original")': 'self.cmb_sort.addItem("↺", "original")',
    'self.cmb_sort.addItem("Datum: neu → alt", "date_desc")': 'self.cmb_sort.addItem(f"{tr(\'header.date\')} ↓", "date_desc")',
    'self.cmb_sort.addItem("Datum: alt → neu", "date_asc")': 'self.cmb_sort.addItem(f"{tr(\'header.date\')} ↑", "date_asc")',
    'self.cmb_sort.addItem("Betrag: hoch → tief", "amount_desc")': 'self.cmb_sort.addItem(f"{tr(\'header.amount\')} ↓", "amount_desc")',
    'self.cmb_sort.addItem("Betrag: tief → hoch", "amount_asc")': 'self.cmb_sort.addItem(f"{tr(\'header.amount\')} ↑", "amount_asc")',
    'self.cmb_sort.addItem("Buchungstext: A → Z", "text_asc")': 'self.cmb_sort.addItem(f"{tr(\'header.details\')} A → Z", "text_asc")',
    'self.cmb_sort.addItem("Kategorie: A → Z", "category_asc")': 'self.cmb_sort.addItem(f"{tr(\'header.category\')} A → Z", "category_asc")',
    'self.cmb_sort.addItem("Tags: A → Z", "tags_asc")': 'self.cmb_sort.addItem(f"{tr(\'header.tags\')} A → Z", "tags_asc")',
    'self.cmb_sort.addItem("Quelldatei: A → Z", "source_asc")': 'self.cmb_sort.addItem(f"{tr(\'header.source\')} A → Z", "source_asc")',
}


def normalized(source: str) -> str:
    result = source
    for old, new in REPLACEMENTS.items():
        result = result.replace(old, new)
    return result


def main() -> int:
    check = "--check" in sys.argv
    source = TARGET.read_text(encoding="utf-8")
    result = normalized(source)

    remaining = [old for old in REPLACEMENTS if old in result]
    if remaining:
        print("Bankimport-Sortierlabels konnten nicht vollständig normalisiert werden:")
        for value in remaining:
            print(f"  - {value}")
        return 1

    if check:
        if result != source:
            print("Bankimport-Sortierlabels sind noch nicht normalisiert.")
            return 1
        print("Bankimport-Sortierlabels sind i18n-normalisiert.")
        return 0

    if result != source:
        TARGET.write_text(result, encoding="utf-8")
        print("Bankimport-Sortierlabels i18n-normalisiert.")
    else:
        print("Bankimport-Sortierlabels bereits i18n-normalisiert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
