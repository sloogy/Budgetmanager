from __future__ import annotations

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen, QBrush
from PySide6.QtWidgets import QStyledItemDelegate, QStyle


def _ideal_text_color(bg: QColor) -> QColor:
    # Relative luminance approximation
    r = bg.redF()
    g = bg.greenF()
    b = bg.blueF()
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return QColor("#111111") if lum > 0.62 else QColor("#ffffff")


class BadgeDelegate(QStyledItemDelegate):
    """
    Zeichnet eine Pillen-/Badge-Darstellung in einer Tabelle.
    Erwartet:
      - item text: z.B. "Einnahmen" / "Ausgaben" / "Ersparnisse"
      - color_map: dict[str, str] mit Hex-Farben (z.B. {"Einnahmen":"#2ecc71"})
    Optional:
      - border_color: str (Hex) oder None
    """
    def __init__(self, parent=None, color_map: dict[str, str] | None = None, border_color: str | None = None):
        super().__init__(parent)
        self.color_map = color_map or {}
        self.border_color = border_color

    def set_colors(self, color_map: dict[str, str]) -> None:
        self.color_map = color_map or {}

    def paint(self, painter: QPainter, option, index) -> None:
        text = str(index.data(Qt.DisplayRole) or "").strip()
        if not text:
            super().paint(painter, option, index)
            return

        bg_hex = self.color_map.get(text)
        if not bg_hex:
            # Fallback: verschiedene Bezeichnungen (Legacy/EN)
            aliases = {
                "Einkommen": ["Einnahmen", "Income"],
                "Einnahmen": ["Einkommen", "Income"],
                "Ausgaben": ["Expenses", "Expense"],
                "Ersparnisse": ["Sparen", "Savings"],
            }
            for alt in aliases.get(text, []):
                bg_hex = self.color_map.get(alt)
                if bg_hex:
                    break
        if not bg_hex:
            super().paint(painter, option, index)
            return

        bg = QColor(bg_hex)
        fg = _ideal_text_color(bg)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Hintergrund der Zelle bei Selection weiterhin sichtbar lassen:
        # wir zeichnen Badge "on top", aber lassen selection background durch.
        # Also erst default draw (ohne Text), dann Badge.
        # Trick: wir nutzen super, aber nullen Text durch Pen transparent nicht sauber -> daher minimal:
        # Wir füllen Selection selbst.
        # PySide6: Selection-State hängt an QStyle (nicht am option-Objekt).
        # (option.State_Selected existiert nicht → würde zu wiederholten Paint-Fehlern führen.)
        selected_flag = (
            QStyle.StateFlag.State_Selected
            if hasattr(QStyle, "StateFlag")
            else QStyle.State_Selected
        )
        if option.state & selected_flag:
            painter.fillRect(option.rect, option.palette.highlight())

        # Badge Größe abhängig vom Text
        fm = QFontMetrics(option.font)
        pad_x = 10
        pad_y = 4
        text_w = fm.horizontalAdvance(text)
        text_h = fm.height()

        badge_w = text_w + pad_x * 2
        badge_h = text_h + pad_y * 2

        # Zentrieren in Zelle
        x = option.rect.x() + (option.rect.width() - badge_w) // 2
        y = option.rect.y() + (option.rect.height() - badge_h) // 2

        radius = badge_h // 2
        badge_rect = QRect(x, y, badge_w, badge_h)

        painter.setBrush(QBrush(bg))
        if self.border_color:
            painter.setPen(QPen(QColor(self.border_color), 1))
        else:
            painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(badge_rect, radius, radius)

        painter.setPen(QPen(fg))
        painter.drawText(badge_rect, Qt.AlignCenter, text)

        painter.restore()

    def sizeHint(self, option, index):
        # Etwas höher, damit Badge nicht gequetscht wirkt
        s = super().sizeHint(option, index)
        return s
