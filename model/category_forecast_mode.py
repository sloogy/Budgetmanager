"""Sprachneutrale Forecast-Behandlung für Budget-Kategorien.

Die UI darf Begriffe wie "Pot" oder "inkrementell" übersetzen. Die Logik
arbeitet nur mit stabilen internen Werten.
"""

from __future__ import annotations

FORECAST_MODE_AUTO = "auto"
FORECAST_MODE_NORMAL = "normal"
FORECAST_MODE_POT = "pot"
FORECAST_MODE_INCREMENTAL = "incremental"

ALL_FORECAST_MODES = {
    FORECAST_MODE_AUTO,
    FORECAST_MODE_NORMAL,
    FORECAST_MODE_POT,
    FORECAST_MODE_INCREMENTAL,
}

_ALIASES = {
    "": FORECAST_MODE_AUTO,
    FORECAST_MODE_AUTO: FORECAST_MODE_AUTO,
    "standard": FORECAST_MODE_AUTO,
    "default": FORECAST_MODE_AUTO,
    FORECAST_MODE_NORMAL: FORECAST_MODE_NORMAL,
    "flex": FORECAST_MODE_NORMAL,
    "flexible": FORECAST_MODE_NORMAL,
    FORECAST_MODE_POT: FORECAST_MODE_POT,
    "pool": FORECAST_MODE_POT,
    "reserve": FORECAST_MODE_POT,
    "rueckstellung": FORECAST_MODE_POT,
    "rückstellung": FORECAST_MODE_POT,
    "franchise": FORECAST_MODE_POT,
    FORECAST_MODE_INCREMENTAL: FORECAST_MODE_INCREMENTAL,
    "inkrementell": FORECAST_MODE_INCREMENTAL,
    "lumpy": FORECAST_MODE_INCREMENTAL,
    "annual": FORECAST_MODE_INCREMENTAL,
    "yearly": FORECAST_MODE_INCREMENTAL,
}


def normalize_forecast_mode(value: object) -> str:
    """Normalisiert einen gespeicherten/gelieferten Modus robust."""
    key = str(value or "").strip().lower()
    return _ALIASES.get(key, FORECAST_MODE_AUTO)


def default_forecast_mode(is_fix: bool, is_recurring: bool) -> str:
    """Best-Practice-Default ohne zusätzliche Benutzereinstellung.

    - fix + nicht wiederkehrend = Pot/Rückstellung (z.B. Franchise/Selbstbehalt)
    - fix oder wiederkehrend = inkrementell/lumpy geschützt
    - sonst = normal/flexibel
    """
    if bool(is_fix) and not bool(is_recurring):
        return FORECAST_MODE_POT
    if bool(is_fix) or bool(is_recurring):
        return FORECAST_MODE_INCREMENTAL
    return FORECAST_MODE_NORMAL


def effective_forecast_mode(value: object, is_fix: bool, is_recurring: bool) -> str:
    mode = normalize_forecast_mode(value)
    if mode == FORECAST_MODE_AUTO:
        return default_forecast_mode(is_fix, is_recurring)
    return mode
