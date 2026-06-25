from __future__ import annotations

from PySide6.QtGui import QColor, QBrush
from utils.money import parse_money, CURRENCIES


import logging
from utils.i18n import tr, trf, db_typ_from_display
logger = logging.getLogger(__name__)

def apply_tracking_type_colors(table, type_colors: dict[str, str], negative_color: str | None = None) -> None:
    """
    Erwartet QTableWidget mit Spalten:
      Datum | Typ | Kategorie | <Währung> | Details | _id
    Färbt:
      - Typ-Zelle: Vordergrund nach type_colors (Einnahmen/Ausgaben/Ersparnisse)
      - Betrags-Zelle: negativ => negative_color (wenn Betrag < 0 oder Text beginnt mit '-')
    """
    if table is None or table.columnCount() < 4:
        return

    # Alle bekannten Währungssymbole (lowercase) für Header-Erkennung
    _currency_headers = {"betrag", "amount"}
    for cfg in CURRENCIES.values():
        _currency_headers.add(cfg["symbol"].lower())

    # Spaltenindex suchen
    typ_col = None
    chf_col = None
    for c in range(table.columnCount()):
        header_item = table.horizontalHeaderItem(c)
        if not header_item:
            continue
        t = header_item.text().strip().lower()
        if t == "typ":
            typ_col = c
        if t in _currency_headers:
            chf_col = c

    if typ_col is None:
        typ_col = 1
    if chf_col is None:
        chf_col = 3

    neg_brush = QBrush(QColor(negative_color)) if negative_color else None

    for r in range(table.rowCount()):
        typ_item = table.item(r, typ_col)
        chf_item = table.item(r, chf_col)

        # Typ-Farbe
        if typ_item:
            typ_txt = typ_item.text().strip()
            # 1) Direkt (wenn cell-text schon DB-Key ist, z.B. DE)
            col_hex = type_colors.get(typ_txt)
            if not col_hex:
                # 2) Display-Text → DB-Key (für EN/FR: "Income"→"Einkommen")
                col_hex = type_colors.get(db_typ_from_display(typ_txt))
            if col_hex:
                typ_item.setForeground(QBrush(QColor(col_hex)))
                typ_item.setFont(typ_item.font())  # keep

        # Negativ-Farbe
        if chf_item and neg_brush:
            txt = chf_item.text().strip()
            is_neg = txt.startswith("-")
            if not is_neg:
                try:
                    val = parse_money(txt)
                    is_neg = val < 0
                except Exception:
                    is_neg = False
            if is_neg:
                chf_item.setForeground(neg_brush)
