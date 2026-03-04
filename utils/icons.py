"""
Icon-Helper: Rendert Emoji-basierte QIcons plattformunabhaengig.

Strategie:
1) Theme-Icon via QIcon.fromTheme anhand Emoji-Mapping.
2) Falls nicht verfuegbar: Emoji auf transparentes QPixmap zeichnen.
3) Falls Emoji nicht sichtbar renderbar: farbiger Buchstaben-Fallback.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QIcon, QPixmap, QPainter, QFont, QColor, QFontMetrics

logger = logging.getLogger(__name__)

# Mapping: Emoji -> Freedesktop Theme-Icon-Name
_EMOJI_THEME: dict[str, str] = {
    "★": "rating",
    "☆": "rating-unrated",
    "⚙": "preferences-system",
    "⚠": "dialog-warning",
    "⚡": "flash",
    "✅": "emblem-default",
    "✏": "document-edit",
    "✓": "emblem-default",
    "✗": "process-stop",
    "❌": "window-close",
    "➕": "list-add",
    "🌍": "applications-internet",
    "🌱": "emblem-favorite",
    "🌳": "folder",
    "🎨": "applications-graphics",
    "🎯": "preferences-desktop",
    "🏠": "go-home",
    "🏦": "office-chart-pie",
    "🏷": "tag",
    "👤": "user-identity",
    "💡": "dialog-information",
    "💬": "mail-message-new",
    "💰": "wallet",
    "💳": "wallet",
    "💸": "wallet",
    "💾": "document-save",
    "📁": "folder",
    "📂": "folder-open",
    "📄": "text-x-generic",
    "📅": "x-office-calendar",
    "📈": "view-statistics",
    "📉": "view-statistics",
    "📊": "view-statistics",
    "📋": "view-list-details",
    "📌": "emblem-important",
    "📝": "document-edit",
    "📤": "document-export",
    "📥": "document-import",
    "📦": "package-x-generic",
    "🔁": "view-refresh",
    "🔄": "view-refresh",
    "🔍": "edit-find",
    "🔑": "dialog-password",
    "🔒": "object-locked",
    "🔓": "object-unlocked",
    "🔔": "preferences-desktop-notification-bell",
    "🔢": "accessories-calculator",
    "🔧": "applications-system",
    "🔨": "applications-engineering",
    "🔴": "media-record",
    "🗄": "folder-saved-search",
    "🗑": "edit-delete",
    "🛠": "applications-engineering",
    "🛡": "security-high",
    "🟠": "dialog-warning",
    "🟡": "dialog-warning",
    "🟢": "emblem-default",
    "🧹": "edit-clear",
}

# Mapping: Emoji -> (Fallback-Buchstabe, Farbe)
_EMOJI_FALLBACK: dict[str, tuple[str, str]] = {
    "🏠": ("H", "#4CAF50"),
    "💰": ("$", "#FFC107"),
    "📊": ("G", "#2196F3"),
    "🔧": ("W", "#795548"),
    "⚙": ("S", "#607D8B"),
    "📁": ("F", "#FF9800"),
    "💾": ("D", "#9C27B0"),
    "🔑": ("K", "#F44336"),
    "📅": ("C", "#00BCD4"),
    "📋": ("L", "#3F51B5"),
    "❌": ("X", "#F44336"),
    "✅": ("V", "#4CAF50"),
    "⚠": ("!", "#FF9800"),
    "🗑": ("D", "#9E9E9E"),
    "➕": ("+", "#4CAF50"),
    "✏": ("E", "#FF9800"),
    "🔄": ("R", "#2196F3"),
    "📤": ("U", "#673AB7"),
    "📥": ("I", "#009688"),
    "🎯": ("T", "#E91E63"),
    "💡": ("I", "#FFEB3B"),
    "🔔": ("N", "#FF5722"),
    "🏷": ("T", "#00BCD4"),
    "📌": ("P", "#F44336"),
    "🔒": ("L", "#F44336"),
    "🔓": ("U", "#4CAF50"),
    "👤": ("U", "#607D8B"),
    "💬": ("M", "#2196F3"),
    "🌍": ("W", "#4CAF50"),
    "🎨": ("T", "#E91E63"),
    "📈": ("A", "#4CAF50"),
    "📉": ("D", "#F44336"),
    "🏦": ("B", "#3F51B5"),
    "💳": ("C", "#9C27B0"),
    "🛡": ("S", "#2196F3"),
}

_DEFAULT_SIZE = 32


def _normalize_emoji(emoji: str) -> str:
    return emoji.replace("\ufe0f", "") if emoji else emoji


@lru_cache(maxsize=128)
def get_icon(emoji: str, size: int = _DEFAULT_SIZE) -> QIcon:
    """Erzeuge ein QIcon aus einem Emoji-String.

    Zuerst wird versucht, ein Theme-Icon zu laden. Falls nicht verfuegbar,
    wird das Emoji direkt auf ein QPixmap gezeichnet. Wenn auch das
    nicht robust sichtbar ist, greift ein farbiger Buchstaben-Fallback.
    """
    emoji_norm = _normalize_emoji(emoji)

    theme_name = _EMOJI_THEME.get(emoji_norm)
    if theme_name:
        themed = QIcon.fromTheme(theme_name)
        if not themed.isNull():
            return themed

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)

    rect = QRect(0, 0, size, size)

    # Versuche Emoji direkt zu zeichnen
    font = QFont()
    font.setPixelSize(int(size * 0.75))
    painter.setFont(font)

    fm = QFontMetrics(font)
    emoji_width = fm.horizontalAdvance(emoji_norm)

    if emoji_width > 0 and _emoji_renders_visible(emoji_norm, font, size):
        painter.drawText(rect, Qt.AlignCenter, emoji_norm)
    else:
        # Fallback: Farbiger Buchstabe auf rundem Hintergrund
        fb_char, fb_color = _EMOJI_FALLBACK.get(
            emoji_norm, (emoji_norm[0] if emoji_norm else "?", "#9E9E9E")
        )
        color = QColor(fb_color)

        # Runder Hintergrund
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        margin = int(size * 0.05)
        painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)

        # Weisser Buchstabe
        painter.setPen(QColor("#FFFFFF"))
        bold_font = QFont()
        bold_font.setPixelSize(int(size * 0.55))
        bold_font.setBold(True)
        painter.setFont(bold_font)
        painter.drawText(rect, Qt.AlignCenter, fb_char)

    painter.end()
    return QIcon(pixmap)


def _emoji_renders_visible(emoji: str, font: QFont, size: int) -> bool:
    """Prueft heuristisch ob ein Emoji sichtbar gerendert wird."""
    try:
        test_pm = QPixmap(size, size)
        test_pm.fill(Qt.transparent)
        p = QPainter(test_pm)
        p.setFont(font)
        p.setPen(QColor("#000000"))
        p.drawText(QRect(0, 0, size, size), Qt.AlignCenter, emoji)
        p.end()

        img = test_pm.toImage()
        cx, cy = size // 2, size // 2
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                x, y = cx + dx, cy + dy
                if 0 <= x < size and 0 <= y < size:
                    if img.pixelColor(x, y).alpha() > 10:
                        return True
        return False
    except Exception:
        return False
