from __future__ import annotations

from PySide6.QtGui import QColor, QBrush
from PySide6.QtCore import Qt


def apply_tracking_type_colors(table, type_colors: dict[str, str], negative_color: str | None = None) -> None:
    """
    Erwartet QTableWidget mit Spalten:
      Datum | Typ | Kategorie | CHF | Details | _id
    Färbt:
      - Typ-Zelle: Vordergrund nach type_colors (Einnahmen/Ausgaben/Ersparnisse)
      - CHF-Zelle: negativ => negative_color (wenn Betrag < 0 oder Text beginnt mit '-')
    """
    if table is None or table.columnCount() < 4:
        return

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
        if t in ("chf", "betrag", "amount"):
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
            col_hex = type_colors.get(typ_txt)
            if col_hex:
                typ_item.setForeground(QBrush(QColor(col_hex)))
                typ_item.setFont(typ_item.font())  # keep

        # Negativ-Farbe
        if chf_item and neg_brush:
            txt = chf_item.text().strip().replace("’", "'").replace(" ", "")
            is_neg = txt.startswith("-")
            if not is_neg:
                try:
                    val = float(txt.replace("CHF", "").replace(",", "."))
                    is_neg = val < 0
                except Exception:
                    is_neg = False
            if is_neg:
                chf_item.setForeground(neg_brush)
