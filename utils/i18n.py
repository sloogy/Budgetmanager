"""JSON-basiertes Übersetzungssystem für den Budgetmanager.

Locale-Dateien liegen als ``locales/<code>.json`` neben dem Projektroot.
Deutsch (``de.json``) ist die Fallback-Sprache – fehlende Schlüssel in
anderen Sprachen fallen automatisch auf Deutsch zurück.

Neue Sprache hinzufügen = neue JSON-Datei anlegen.  Fertig.

Verwendung in Views::

    from utils.i18n import tr, trf

    label.setText(tr("menu.file"))              # -> "Datei" / "File"
    label.setText(trf("lbl.last_n_days", n=14)) # -> "Nur letzte 14 Tage"

Sprache setzen (beim Start / in Einstellungen)::

    from utils.i18n import set_language, get_language
    set_language("en")
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Konfiguration ───────────────────────────────────────────────

_LOCALE_DIR = Path(__file__).resolve().parent.parent / "locales"
_FALLBACK_LANG = "de"

# ── Interner State ──────────────────────────────────────────────

_lang: str = _FALLBACK_LANG
_strings: dict[str, str] = {}       # aktive Sprache
_fallback: dict[str, str] = {}      # de.json (immer geladen)
_available: list[str] = []          # verfuegbare Sprachcodes

# Missing-Key Debug (optional)
_debug_missing_keys: bool = os.environ.get("BM_I18N_DEBUG", "").strip() not in ("", "0", "false", "False")


# ── Laden ───────────────────────────────────────────────────────

def _load_json(lang_code: str) -> dict[str, str]:
    """Laedt eine locale/<code>.json Datei.  Gibt {} bei Fehler zurueck."""
    path = _LOCALE_DIR / f"{lang_code}.json"
    if not path.exists():
        logger.warning("Locale-Datei nicht gefunden: %s", path)
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.error("Locale %s ist kein JSON-Objekt", path)
            return {}
        flat: dict[str, str] = {}
        _flatten(data, "", flat)
        return flat
    except Exception as e:
        logger.error("Fehler beim Laden von %s: %s", path, e)
        return {}


def _flatten(obj: dict, prefix: str, out: dict[str, str]) -> None:
    """Konvertiert verschachtelte Dicts in flache dot-notation Keys.

    {"menu": {"file": "Datei"}} -> {"menu.file": "Datei"}
    """
    for k, v in obj.items():
        full_key = k if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            _flatten(v, full_key, out)
        else:
            out[full_key] = str(v)


def _discover_languages() -> list[str]:
    """Findet alle verfuegbaren Sprachen anhand der JSON-Dateien."""
    if not _LOCALE_DIR.exists():
        return [_FALLBACK_LANG]
    codes = []
    for p in sorted(_LOCALE_DIR.glob("*.json")):
        codes.append(p.stem)
    return codes if codes else [_FALLBACK_LANG]


# ── Oeffentliche API ────────────────────────────────────────────

def init() -> None:
    """Initialisiert das Uebersetzungssystem.  Wird automatisch aufgerufen."""
    global _fallback, _strings, _available
    _available = _discover_languages()
    _fallback = _load_json(_FALLBACK_LANG)
    _strings = _fallback.copy()
    logger.debug("i18n initialisiert: %d Sprachen, %d Fallback-Strings",
                 len(_available), len(_fallback))


def set_language(code: str) -> None:
    """Setzt die aktive Sprache.

    Akzeptiert: 'de', 'Deutsch', 'en', 'Englisch', 'English', 'fr', etc.
    """
    global _lang, _strings

    name_map = {
        "deutsch": "de", "german": "de",
        "englisch": "en", "english": "en",
        "französisch": "fr", "french": "fr",
        "italiano": "it", "italian": "it",
    }
    low = code.lower().strip()
    resolved = name_map.get(low, low)

    if not _fallback:
        init()

    _lang = resolved

    if resolved == _FALLBACK_LANG:
        _strings = _fallback.copy()
    else:
        loaded = _load_json(resolved)
        _strings = {**_fallback, **loaded}

    logger.debug("Sprache gesetzt: %s (%d Strings)", _lang, len(_strings))


def get_language() -> str:
    """Gibt den aktiven Sprachcode zurueck ('de' oder 'en')."""
    return _lang


def available_languages() -> list[dict[str, str]]:
    """Gibt alle verfuegbaren Sprachen als [{code, name}] zurueck."""
    if not _available:
        init()
    result = []
    for code in _available:
        data = _load_json(code)
        name = data.get("meta.name", code.upper())
        result.append({"code": code, "name": name})
    return result


def tr(key: str) -> str:
    """Uebersetzt einen Schluessel in die aktive Sprache.

    Fallback-Kette: aktive Sprache -> Deutsch -> Schluessel selbst.
    """
    if not _strings and not _fallback:
        init()

    if key in _strings:
        return _strings[key]
    if key in _fallback:
        return _fallback[key]

    if _debug_missing_keys:
        logger.warning("[i18n] Missing key: %s", key)
    return key


def set_debug_missing(enabled: bool) -> None:
    """Aktiviert/Deaktiviert Missing-Key Warnungen im Log."""
    global _debug_missing_keys
    _debug_missing_keys = bool(enabled)


def trf(key: str, **kwargs) -> str:
    """Wie ``tr()``, aber mit ``str.format()``-Ersetzung.

    Beispiel::

        trf("lbl.last_n_days", n=14)  # -> "Nur letzte 14 Tage"
    """
    try:
        return tr(key).format(**kwargs)
    except (KeyError, IndexError):
        return tr(key)


def tr_msg(message) -> str:
    """Übersetzt eine Message aus Model/UI.

    Unterstützt:
    - ('key.path', {'var': 'x'})  -> trf
    - 'key.path'                  -> tr
    - alles andere                -> str(message)
    """
    if isinstance(message, tuple) and len(message) == 2 and isinstance(message[0], str) and isinstance(message[1], dict):
        return trf(message[0], **message[1])
    if isinstance(message, str):
        # Wenn es wie ein Key aussieht, versuchen wir tr().
        if "." in message and message.split(".", 1)[0] in {
            "msg", "dlg", "tab_ui", "account", "budget", "export", "update", "common", "database", "error", "info", "settings_ui",
        }:
            return tr(message)
        return message
    return str(message)


# ── Display-Helfer fuer DB-Werte ────────────────────────────────

def display_typ(db_typ: str) -> str:
    """Uebersetzt einen DB-Typwert ('Ausgaben') in die Anzeigesprache.

    Die DB speichert immer deutsche Schluessel.  Diese Funktion
    gibt den lokalisierten Anzeigenamen zurueck.
    """
    return tr(f"typ.{db_typ}")


def db_typ_from_display(display: str) -> str:
    """Inverse von display_typ(): Anzeigename -> DB-Schluessel.

    Wird fuer ComboBox-Auswahl benoetigt, wo der User den
    uebersetzten Namen sieht, aber der DB-Schluessel gebraucht wird.
    """
    db_types = ["Ausgaben", "Einkommen", "Ersparnisse"]
    for db_val in db_types:
        if tr(f"typ.{db_val}") == display:
            return db_val
    return display


def tr_category_name(name: str) -> str:
    """Übersetzt bekannte Default-Kategorien (ohne DB-Migration)."""
    try:
        from utils.category_i18n import DEFAULT_CATEGORY_NAME_TO_KEY
        key = DEFAULT_CATEGORY_NAME_TO_KEY.get(name)
        return tr(key) if key else name
    except Exception:
        return name


# ── Auto-Init beim Import ───────────────────────────────────────
init()
