"""Zentraler UI-Farb-Helper für Theme-Integration.

Stellt allen Views eine einheitliche API bereit, um Farben aus dem
aktiven Theme-Profil zu beziehen, ohne den ThemeManager direkt kennen
zu müssen. Fallback-Werte garantieren Funktionsfähigkeit auch ohne
Theme-Manager (z.B. in Tests oder Standalone-Dialogen).

Nutzung:
    from views.ui_colors import ui_colors
    c = ui_colors(self)          # self = beliebiges QWidget
    label.setStyleSheet(f"color: {c.negative};")
    item.setForeground(QColor(c.type_colors.get(_TE, "#e74c3c")))
"""
from __future__ import annotations

import logging
from utils.i18n import tr, trf
from dataclasses import dataclass, field
from typing import Dict, Optional

from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

# ── Standard-Farben (Hell-Modus Fallback) ──────────────────────────

# TYP_* Konstanten als Schlüssel (DB-Werte = immer Deutsch, sprachunabhängig)
try:
    from model.typ_constants import TYP_INCOME as _TI, TYP_EXPENSES as _TE, TYP_SAVINGS as _TS
except Exception:
    _TI, _TE, _TS = "Einkommen", "Ausgaben", "Ersparnisse"

_DEFAULT_TYPE_COLORS: Dict[str, str] = {
    _TI: "#2ecc71",
    _TE: "#e74c3c",
    _TS: "#3498db",
}

_DEFAULTS = {
    "type_colors": dict(_DEFAULT_TYPE_COLORS),
    "negative": "#e74c3c",
    "ok": "#27ae60",
    "warning": "#f39c12",
    "danger": "#e74c3c",
    "text": "#111111",
    "text_dim": "#444444",
    "bg_app": "#ffffff",
    "bg_panel": "#f6f7f9",
    "bg_sidebar": "#f0f2f5",
    "table_bg": "#ffffff",
    "table_alt": "#f7f9fc",
    "table_header": "#eef2f7",
    "table_grid": "#d6dbe3",
    "selection_bg": "#2f80ed",
    "selection_text": "#ffffff",
    "accent": "#2f80ed",
    "border": "#d6dbe3",
    "info_bg": "#e3f2fd",
    "info_text": "#1565c0",
    "warning_bg": "#fff3cd",
    "warning_text": "#856404",
    "error_bg": "#ffebee",
    "error_text": "#c62828",
    "success_bg": "#e8f5e9",
    "success_text": "#2e7d32",
    "neutral": "#95a5a6",
}


@dataclass(frozen=True)
class UIColors:
    """Immutable Container für die aktiven Theme-Farben."""

    # Typ-Farben
    type_colors: Dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_TYPE_COLORS))

    # Semantische Farben
    negative: str = "#e74c3c"
    ok: str = "#27ae60"
    warning: str = "#f39c12"
    danger: str = "#e74c3c"
    neutral: str = "#95a5a6"

    # Text
    text: str = "#111111"
    text_dim: str = "#444444"

    # Hintergründe
    bg_app: str = "#ffffff"
    bg_panel: str = "#f6f7f9"
    bg_sidebar: str = "#f0f2f5"

    # Tabelle
    table_bg: str = "#ffffff"
    table_alt: str = "#f7f9fc"
    table_header: str = "#eef2f7"
    table_grid: str = "#d6dbe3"

    # Auswahl
    selection_bg: str = "#2f80ed"
    selection_text: str = "#ffffff"
    accent: str = "#2f80ed"

    # Rahmen
    border: str = "#d6dbe3"

    # Semantische Hintergründe (Info/Warning/Error/Success)
    info_bg: str = "#e3f2fd"
    info_text: str = "#1565c0"
    warning_bg: str = "#fff3cd"
    warning_text: str = "#856404"
    error_bg: str = "#ffebee"
    error_text: str = "#c62828"
    success_bg: str = "#e8f5e9"
    success_text: str = "#2e7d32"

    # ── Hilfsmethoden ──────────────────────────────────────────

    def type_color(self, typ: str) -> str:
        """Farbe für einen Budgettyp (Einnahmen/Ausgaben/Ersparnisse)."""
        # typ kann DB-Key (TYP_*) oder Display-Name sein - DB-Key zuerst versuchen
        if typ in self.type_colors:
            return self.type_colors[typ]
        # Fallback: normalisieren
        try:
            from model.typ_constants import normalize_typ as _nt
            normed = _nt(typ)
            if normed in self.type_colors:
                return self.type_colors[normed]
        except Exception:
            pass
        return self.text_dim

    def type_qcolor(self, typ: str) -> QColor:
        """QColor für einen Budgettyp."""
        return QColor(self.type_color(typ))

    def type_brush(self, typ: str) -> QBrush:
        """QBrush für einen Budgettyp."""
        return QBrush(self.type_qcolor(typ))

    def severity_color(self, level: str) -> str:
        """Farbe für ok/warning/danger."""
        return {"ok": self.ok, "warning": self.warning, "danger": self.danger}.get(level, self.text)

    def amount_color(self, value: float) -> str:
        """Farbe für Beträge: negativ=rot, positiv=grün, null=neutral."""
        if value < -0.01:
            return self.negative
        elif value > 0.01:
            return self.ok
        return self.neutral

    def amount_qcolor(self, value: float) -> QColor:
        """QColor für Beträge."""
        return QColor(self.amount_color(value))

    def progress_color(self, percent: float) -> str:
        """Farbe für Fortschrittsbalken: >100%=rot, >80%=orange, sonst grün."""
        if percent > 100:
            return self.danger
        elif percent > 80:
            return self.warning
        return self.ok

    def chart_palette(self, n: int = 10) -> list[str]:
        """n Farben für Diagramme, basierend auf Theme-Akzentfarbe."""
        base = [
            self.type_colors.get(_TS, "#3498db"),
            self.type_colors.get(_TE, "#e74c3c"),
            self.type_colors.get(_TI, "#27ae60"),
            self.warning,
            "#9b59b6",
            "#1abc9c",
            "#e67e22",
            "#34495e",
            "#16a085",
            "#c0392b",
        ]
        # Erweitern falls n > len(base) benötigt wird
        while len(base) < n:
            base.extend(base)
        return base[:n]

    def budget_chart_colors(self, typ: str) -> dict[str, str]:
        """3 Farbvarianten (gebucht/budget/offen) für Budget-Balkendiagramme."""
        base = self.type_color(typ)
        return {
            "gebucht": _darken(base, 0.7),
            "budget": _lighten(base, 0.4),
            "offen": _lighten(base, 0.65),
        }


# ── Cache ──────────────────────────────────────────────────────────
# Einfacher Cache pro ThemeManager-Instanz (wird bei Theme-Wechsel
# durch neuen Aufruf überschrieben).
_cache: dict[int, UIColors] = {}


def _build_from_theme_manager(tm) -> UIColors:
    """Baut UIColors aus einem ThemeManager."""
    p = tm.get_current_profile()
    if not p:
        return UIColors()

    tc = tm.get_type_colors()  # Dict[str, str]
    neg = tm.get_negative_color()

    # Semantische Hintergründe aus dem Profil ableiten
    modus = p.get("modus", "hell")
    is_dark = modus == "dunkel"

    # Für Dunkel-Modus: Dunklere Varianten der semantischen Farben
    if is_dark:
        info_bg = _darken(p.get("typ_ersparnisse", "#3498db"), 0.2)
        warning_bg = _darken("#f39c12", 0.25)
        error_bg = _darken(neg, 0.2)
        success_bg = _darken(p.get("typ_einnahmen", "#27ae60"), 0.2)
        info_text = _lighten(p.get("typ_ersparnisse", "#3498db"), 0.6)
        warning_text = _lighten("#f39c12", 0.6)
        error_text = _lighten(neg, 0.6)
        success_text = _lighten(p.get("typ_einnahmen", "#27ae60"), 0.6)
    else:
        info_bg = "#e3f2fd"
        warning_bg = "#fff3cd"
        error_bg = "#ffebee"
        success_bg = "#e8f5e9"
        info_text = "#1565c0"
        warning_text = "#856404"
        error_text = "#c62828"
        success_text = "#2e7d32"

    return UIColors(
        type_colors=tc or dict(_DEFAULT_TYPE_COLORS),
        negative=neg,
        ok=tc.get(_TI, "#27ae60"),
        warning="#f39c12",
        danger=neg,
        neutral="#95a5a6",
        text=p.get("text", "#111111"),
        text_dim=p.get("text_gedimmt", "#444444"),
        bg_app=p.get("hintergrund_app", "#ffffff"),
        bg_panel=p.get("hintergrund_panel", "#f6f7f9"),
        bg_sidebar=p.get("hintergrund_seitenleiste", "#f0f2f5"),
        table_bg=p.get("tabelle_hintergrund", "#ffffff"),
        table_alt=p.get("tabelle_alt", "#f7f9fc"),
        table_header=p.get("tabelle_header", "#eef2f7"),
        table_grid=p.get("tabelle_gitter", "#d6dbe3"),
        selection_bg=p.get("auswahl_hintergrund", "#2f80ed"),
        selection_text=p.get("auswahl_text", "#ffffff"),
        accent=p.get("akzent", "#2f80ed"),
        border=p.get("tabelle_gitter", "#d6dbe3"),
        info_bg=info_bg,
        info_text=info_text,
        warning_bg=warning_bg,
        warning_text=warning_text,
        error_bg=error_bg,
        error_text=error_text,
        success_bg=success_bg,
        success_text=success_text,
    )


def _darken(hex_color: str, factor: float = 0.3) -> str:
    """Erzeugt eine dunklere Version einer Farbe (für dunkle Hintergründe)."""
    try:
        c = QColor(hex_color)
        r = int(c.red() * factor)
        g = int(c.green() * factor)
        b = int(c.blue() * factor)
        return QColor(r, g, b).name()
    except Exception:
        return "#2d2d30"


def _lighten(hex_color: str, factor: float = 0.6) -> str:
    """Erzeugt eine hellere Version einer Farbe (für Text auf dunklem BG)."""
    try:
        c = QColor(hex_color)
        r = min(255, int(c.red() + (255 - c.red()) * factor))
        g = min(255, int(c.green() + (255 - c.green()) * factor))
        b = min(255, int(c.blue() + (255 - c.blue()) * factor))
        return QColor(r, g, b).name()
    except Exception:
        return "#cccccc"


# ── Haupt-API ──────────────────────────────────────────────────────

def ui_colors(widget: Optional[QWidget] = None) -> UIColors:
    """Holt die aktuellen Theme-Farben.

    Durchsucht die Widget-Hierarchie nach dem MainWindow und dessen
    ThemeManager. Cached das Ergebnis pro ThemeManager-Instanz.

    Args:
        widget: Beliebiges QWidget. Wenn None, werden Defaults geliefert.

    Returns:
        UIColors-Instanz mit allen Farben.

    Beispiel::

        c = ui_colors(self)
        label.setStyleSheet(f"color: {c.negative};")
        item.setForeground(c.type_qcolor(tr("kpi.expenses")))
    """
    if widget is None:
        return UIColors()

    # Widget-Hierarchie hochgehen zum MainWindow
    try:
        main = widget.window()
        tm = getattr(main, "theme_manager", None)
        if tm is None:
            return UIColors()

        tm_id = id(tm)
        # Cache invalidieren wenn Profil gewechselt hat
        cached = _cache.get(tm_id)
        if cached is not None:
            return cached

        result = _build_from_theme_manager(tm)
        _cache[tm_id] = result
        return result
    except Exception as e:
        logger.debug("ui_colors fallback: %s", e)
        return UIColors()


def invalidate_color_cache() -> None:
    """Cache leeren (nach Theme-Wechsel aufrufen)."""
    _cache.clear()
