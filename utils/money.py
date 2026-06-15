"""Zentrale Geld-Formatierung & Parsing für den Budgetmanager.

Unterstützt CHF, EUR, USD und GBP.  Die aktive Währung wird über
``set_currency()`` gesetzt (typischerweise beim App-Start aus den Settings)
und von allen ``format_*``-Funktionen verwendet.

NEU (v2.0.1): Das **Zahlenformat** (Dezimal- und Tausender-Trennzeichen) ist
jetzt konfigurierbar und unabhängig von der Währung.  Es wird über
``set_number_format()`` gesetzt – typischerweise beim Start aus den Settings
und im Erststart-Assistenten gewählt.

Vordefinierte Formate (siehe ``NUMBER_FORMATS``):

    swiss   1'234.56   (Apostroph / Punkt)   – Default, Schweiz
    german  1.234,56   (Punkt / Komma)       – DE/AT
    french  1 234,56   (schmales Leerz./Komma) – FR/BE
    anglo   1,234.56   (Komma / Punkt)       – US/UK
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


# ── Zahlenformate ─────────────────────────────────────────────────────
# decimal   = Dezimaltrennzeichen
# thousands = Tausender-Trennzeichen ("" = keines)
# label_key = i18n-Schlüssel für die Anzeige in ComboBoxen (Fallback: label)

NUMBER_FORMATS: dict[str, dict] = {
    "swiss":  {"decimal": ".", "thousands": "'",      "label": "1'234.56  (Schweiz)"},
    "german": {"decimal": ",", "thousands": ".",      "label": "1.234,56  (Deutschland/Österreich)"},
    "french": {"decimal": ",", "thousands": "\u202f", "label": "1\u202f234,56  (Frankreich)"},  # schmales geschütztes Leerzeichen
    "anglo":  {"decimal": ".", "thousands": ",",      "label": "1,234.56  (US/UK)"},
}

NUMBER_FORMAT_CODES: list[str] = ["swiss", "german", "french", "anglo"]

# Sinnvolle Vorauswahl je Sprache (nur Vorschlag im Assistenten)
LANGUAGE_NUMBER_FORMAT_DEFAULTS: dict[str, str] = {
    "de": "swiss",   # Schweizer Default-Markt; DE-User wählen ggf. "german"
    "en": "anglo",
    "fr": "french",
}

# ── Globaler State – wird beim Start aus den Settings gesetzt ─────────
_active_currency: str = "CHF"
_active_number_format: str = "swiss"


def set_currency(code: str) -> None:
    """Setzt die aktive Währung.  Unbekannte Codes fallen auf CHF zurück."""
    global _active_currency
    _active_currency = code if code in CURRENCIES else "CHF"


def get_currency() -> str:
    """Gibt den aktiven Währungscode zurück."""
    return _active_currency


# Alias-/Legacy-Mapping: toleriert alte oder abweichende Codes und mappt sie
# auf die kanonischen Keys. So fallen bestehende Einstellungen NICHT still auf
# 'swiss' zurück, sondern werden korrekt migriert.
_NUMBER_FORMAT_ALIASES: dict[str, str] = {
    "ch": "swiss", "de_ch": "swiss", "chf": "swiss",
    "de": "german", "at": "german", "eu": "german", "eur": "german",
    "fr": "french", "be": "french",
    "us": "anglo", "uk": "anglo", "gb": "anglo", "en": "anglo", "usd": "anglo",
}


def normalize_number_format(key: str | None) -> str:
    """Mappt beliebige (auch veraltete) Format-Codes auf einen kanonischen Key."""
    if not key:
        return "swiss"
    k = str(key).strip().lower()
    if k in NUMBER_FORMATS:
        return k
    return _NUMBER_FORMAT_ALIASES.get(k, "swiss")


def set_number_format(key: str) -> None:
    """Setzt das aktive Zahlenformat.  Unbekannte/alte Keys werden migriert."""
    global _active_number_format
    _active_number_format = normalize_number_format(key)


def get_number_format() -> str:
    """Gibt den aktiven Zahlenformat-Key zurück ('swiss', 'german', ...)."""
    return _active_number_format


def set_money_locale(*, currency: str | None = None, number_format: str | None = None) -> None:
    """Setzt Währung und Zahlenformat zusammen.

    Rückwärtskompatibler Helfer für alte Aufrufer/Tests. ``number_format``
    darf neue Keys (swiss/german/french/anglo) oder alte Keys (ch/eu/us) sein.
    """
    if currency is not None:
        set_currency(currency)
    if number_format is not None:
        set_number_format(number_format)


def preferred_number_format_for_currency(currency: str | None) -> str:
    """Sinnvoller Vorschlag für neue Installationen.

    CHF -> swiss, EUR -> german, USD/GBP -> anglo.
    """
    code = currency if currency in CURRENCIES else "CHF"
    if code == "EUR":
        return "german"
    if code in {"USD", "GBP"}:
        return "anglo"
    return "swiss"


def _fmt_cfg() -> dict:
    return NUMBER_FORMATS.get(_active_number_format, NUMBER_FORMATS["swiss"])


def get_decimal_separator() -> str:
    """Aktives Dezimaltrennzeichen ('.' oder ',')."""
    return _fmt_cfg()["decimal"]


def get_thousands_separator() -> str:
    """Aktives Tausender-Trennzeichen ('', \"'\", '.', ',', schmales Leerz.)."""
    return _fmt_cfg()["thousands"]


def get_symbol(code: str | None = None) -> str:
    """Gibt das Symbol der (aktiven) Währung zurück."""
    c = CURRENCIES.get(code or _active_currency, CURRENCIES["CHF"])
    return c["symbol"]


# ── Formatierung ──────────────────────────────────────────────────────

def _group_thousands(int_part: str, sep: str) -> str:
    """Fügt ``sep`` als Tausender-Trenner in den Ganzzahl-String ein."""
    if not sep:
        return int_part
    # Von rechts in 3er-Gruppen
    rev = int_part[::-1]
    chunks = [rev[i:i + 3] for i in range(0, len(rev), 3)]
    return sep.join(chunks)[::-1]


def format_money(
    value: float,
    *,
    currency: str | None = None,
    with_symbol: bool = True,
    force_sign: bool = False,
) -> str:
    """Formatiert einen Betrag im aktiven Zahlenformat.

    Beispiele (Format 'german'): ``"1.234,56 €"``.
    Beispiele (Format 'swiss'):  ``"1'234.56 CHF"``.

    Args:
        value:       Der zu formatierende Betrag.
        currency:    Währungscode-Override (``None`` = aktive Währung).
        with_symbol: Symbol anhängen/voranstellen?
        force_sign:  ``+`` bei positiven Werten voranstellen?
    """
    code = currency or _active_currency
    cfg = CURRENCIES.get(code, CURRENCIES["CHF"])
    fmt = _fmt_cfg()

    abs_val = abs(value)
    # Immer mit Punkt-Dezimal rendern, dann auf Zielformat mappen
    raw = f"{abs_val:.2f}"          # z. B. "1234.56"
    int_part, dec_part = raw.split(".")
    int_grouped = _group_thousands(int_part, fmt["thousands"])
    s = f"{int_grouped}{fmt['decimal']}{dec_part}"

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

    Robust gegenüber gemischten Eingaben.  Wenn das aktive Format ein
    eindeutiges Dezimalzeichen hat und nur dieses vorkommt, wird es bevorzugt
    interpretiert – so wird ``"1.234"`` im Format 'german' korrekt als 1234
    (nicht 1.234) gelesen.
    """
    s = (text or "").strip()

    # Alle bekannten Währungssymbole entfernen
    for cfg in CURRENCIES.values():
        s = s.replace(cfg["symbol"], "")

    # Apostrophe, (schmale) Leerzeichen, Non-Breaking-Spaces als Tausender entfernen
    for ch in ("'", "\u00a0", "\u202f", " "):
        s = s.replace(ch, "")

    if not s:
        return 0.0

    has_comma = "," in s
    has_dot = "." in s

    if has_comma and has_dot:
        # Letztes Trennzeichen = Dezimalzeichen
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")   # europäisch 1.234,56
        else:
            s = s.replace(",", "")                       # angelsächsisch 1,234.56
    elif has_comma:
        # Nur Komma: Dezimaltrenner ODER Tausender?  Aktives Format entscheidet.
        if get_decimal_separator() == ",":
            s = s.replace(",", ".")                      # Dezimaltrenner
        else:
            # Komma ist hier Tausendertrenner – nur entfernen, wenn es so aussieht
            if _looks_like_thousands(s, ","):
                s = s.replace(",", "")
            else:
                s = s.replace(",", ".")
    elif has_dot:
        # Nur Punkt: Dezimaltrenner ODER Tausender?
        if get_decimal_separator() == "." :
            pass                                         # Punkt ist Dezimaltrenner
        else:
            if _looks_like_thousands(s, "."):
                s = s.replace(".", "")                   # Tausendertrenner (z. B. "1.234")
            # sonst Punkt als Dezimaltrenner stehen lassen

    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _looks_like_thousands(s: str, sep: str) -> bool:
    """Heuristik: Sieht ``sep`` in ``s`` nach einem Tausendertrenner aus?

    True, wenn nach dem letzten ``sep`` genau 3 Ziffern folgen und es
    mindestens eine Ziffer davor gibt (z. B. '1.234', '12.345.678').
    """
    last = s.rfind(sep)
    if last <= 0:
        return False
    after = s[last + 1:]
    return after.isdigit() and len(after) == 3
