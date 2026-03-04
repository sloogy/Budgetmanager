"""Zentrale Geld-Formatierung & Parsing für den Budgetmanager.

Unterstützt CHF, EUR, USD und GBP.  Die aktive Währung wird über
``set_currency()`` gesetzt (typischerweise beim App-Start aus den Settings)
und von allen ``format_*``-Funktionen verwendet.

Zahlenformat ist immer Schweizer-Stil: **1'234.56** (Apostroph als
Tausender-Trenner, Punkt als Dezimalzeichen).
"""

from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

# ── Währungsdefinitionen ──────────────────────────────────────────────

CURRENCIES: dict[str, dict] = {
    "CHF": {"symbol": "CHF", "position": "suffix", "label": "CHF – Schweizer Franken"},
    "EUR": {"symbol": "€",   "position": "suffix", "label": "EUR – Euro"},
    "USD": {"symbol": "$",   "position": "prefix", "label": "USD – US-Dollar"},
    "GBP": {"symbol": "£",   "position": "prefix", "label": "GBP – Britisches Pfund"},
}

# Alle Codes in stabiler Reihenfolge (für ComboBoxen)
CURRENCY_CODES: list[str] = ["CHF", "EUR", "USD", "GBP"]

# Globale Einstellung – wird beim Start von Settings gesetzt
_active_currency: str = "CHF"


def set_currency(code: str) -> None:
    """Setzt die aktive Währung.  Unbekannte Codes fallen auf CHF zurück."""
    global _active_currency
    _active_currency = code if code in CURRENCIES else "CHF"


def get_currency() -> str:
    """Gibt den aktiven Währungscode zurück."""
    return _active_currency


def get_symbol(code: str | None = None) -> str:
    """Gibt das Symbol der (aktiven) Währung zurück."""
    c = CURRENCIES.get(code or _active_currency, CURRENCIES["CHF"])
    return c["symbol"]


# ── Formatierung ──────────────────────────────────────────────────────

def format_money(
    value: float,
    *,
    currency: str | None = None,
    with_symbol: bool = True,
    force_sign: bool = False,
) -> str:
    """Formatiert einen Betrag im Schweizer Stil (1'234.56).

    Args:
        value:       Der zu formatierende Betrag.
        currency:    Währungscode-Override (``None`` = aktive Währung).
        with_symbol: Symbol anhängen/voranstellen?
        force_sign:  ``+`` bei positiven Werten voranstellen?

    Returns:
        Formatierter String, z. B. ``"1'234.56 CHF"`` oder ``"$ 1'234.56"``.
    """
    code = currency or _active_currency
    cfg = CURRENCIES.get(code, CURRENCIES["CHF"])

    abs_val = abs(value)
    # Python's f-String mit Tausender-Komma → dann Komma durch Apostroph
    s = f"{abs_val:,.2f}".replace(",", "'")  # 1'234.56

    if value < 0:
        prefix = "-"
    elif force_sign:
        prefix = "+"
    else:
        prefix = ""

    if not with_symbol:
        return f"{prefix}{s}"

    sym = cfg["symbol"]
    if cfg["position"] == "prefix":
        return f"{prefix}{sym} {s}"
    else:
        return f"{prefix}{s} {sym}"


def format_short(value: float) -> str:
    """Nur Zahl, ohne Währungssymbol.  Für Tabellenzellen."""
    return format_money(value, with_symbol=False)


def currency_header() -> str:
    """Header-Text für Betrags-Spalten (z. B. ``'CHF'``, ``'€'``)."""
    return get_symbol()


# ── Parsing ───────────────────────────────────────────────────────────

def parse_money(text: str) -> float:
    """Parst einen Geld-String zurück zu ``float``.

    Erkennt diverse Formate:
    ``"1'234.56 CHF"``, ``"CHF 1234.56"``, ``"$1,234.56"``,
    ``"1234,56"``, ``"-42.00"`` usw.
    """
    s = (text or "").strip()

    # Alle bekannten Symbole entfernen
    for cfg in CURRENCIES.values():
        s = s.replace(cfg["symbol"], "")

    # Apostrophe, Leerzeichen, Non-Breaking-Spaces
    s = s.replace("'", "").replace("\u00a0", "").replace(" ", "")

    # Komma vs. Punkt: wenn beides vorkommt, letztes = Dezimalzeichen
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            # z. B. "1.234,56" → europäisch
            s = s.replace(".", "").replace(",", ".")
        else:
            # z. B. "1,234.56" → angelsächsisch
            s = s.replace(",", "")
    elif "," in s:
        # Nur Komma → als Dezimalzeichen interpretieren
        s = s.replace(",", ".")

    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0
