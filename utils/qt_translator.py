"""Installiert Qt-eigene Übersetzungen (qtbase_<lang>.qm).

Hintergrund
-----------
Das native Kontextmenü von Eingabefeldern (QLineEdit/QTextEdit/QSpinBox …) –
also *Rückgängig / Ausschneiden / Kopieren / Einfügen / Löschen / Alles
auswählen* – stammt NICHT aus unserem JSON-i18n, sondern aus Qt selbst.
Diese Strings werden nur übersetzt, wenn ein ``QTranslator`` mit der passenden
``qtbase_<lang>.qm``-Datei in die ``QApplication`` installiert wird.

Ohne diesen Schritt bleiben die Menüs **immer englisch** – unabhängig von der
in der App gewählten Sprache.

Verwendung
----------
Einmal beim Start (nach dem Erzeugen der ``QApplication``) und erneut bei jedem
Sprachwechsel::

    from utils.qt_translator import install_qt_translations
    install_qt_translations(app, "de")
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Aktive Translator-Instanzen merken, damit wir sie bei einem Sprachwechsel
# sauber wieder entfernen können (sonst stapeln sie sich).
_installed: list = []


def _candidate_translation_dirs() -> list[Path]:
    """Mögliche Verzeichnisse mit ``qtbase_*.qm`` – inkl. PyInstaller-Layouts."""
    dirs: list[Path] = []

    # 1) Offizieller Weg über Qt
    try:
        from PySide6.QtCore import QLibraryInfo

        try:
            # Qt6-API
            p = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        except Exception:
            # Ältere Bindings
            p = QLibraryInfo.location(QLibraryInfo.TranslationsPath)  # type: ignore[attr-defined]
        if p:
            dirs.append(Path(p))
    except Exception as e:  # pragma: no cover - nur Logging
        logger.debug("QLibraryInfo nicht verfügbar: %s", e)

    # 2) PySide6-Paketverzeichnis (…/site-packages/PySide6/translations)
    try:
        import PySide6

        base = Path(PySide6.__file__).resolve().parent
        dirs.append(base / "translations")
        dirs.append(base / "Qt" / "translations")
    except Exception as e:  # pragma: no cover
        logger.debug("PySide6-Paketpfad nicht ermittelbar: %s", e)

    # 3) PyInstaller (eingefrorene App): _MEIPASS/PySide6/translations
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        mp = Path(meipass)
        dirs.append(mp / "PySide6" / "translations")
        dirs.append(mp / "translations")

    # Duplikate entfernen, Reihenfolge erhalten
    seen: set[str] = set()
    uniq: list[Path] = []
    for d in dirs:
        key = str(d)
        if key not in seen:
            seen.add(key)
            uniq.append(d)
    return uniq


def _normalize_lang(code: str) -> str:
    """'Deutsch'/'de_CH'/'DE' -> 'de'.  Gibt 2-Buchstaben-Code zurück."""
    name_map = {
        "deutsch": "de",
        "german": "de",
        "englisch": "en",
        "english": "en",
        "französisch": "fr",
        "french": "fr",
        "italiano": "it",
        "italian": "it",
    }
    low = (code or "").lower().strip()
    low = name_map.get(low, low)
    # 'de_ch' / 'de-CH' -> 'de'
    for sep in ("_", "-"):
        if sep in low:
            low = low.split(sep, 1)[0]
    return low or "en"


def install_qt_translations(app, lang_code: str) -> bool:
    """Installiert ``qtbase_<lang>.qm`` (und ``qt_<lang>.qm``) in die App.

    Entfernt zuvor installierte Translator-Instanzen, damit ein Sprachwechsel
    zur Laufzeit sauber funktioniert.

    Returns:
        True, wenn mindestens eine .qm-Datei geladen und installiert wurde.
    """
    try:
        from PySide6.QtCore import QTranslator
    except Exception as e:  # pragma: no cover
        logger.debug("QTranslator nicht verfügbar: %s", e)
        return False

    lang = _normalize_lang(lang_code)

    # Alte Translator entfernen
    global _installed
    for tr in _installed:
        try:
            app.removeTranslator(tr)
        except Exception as e:  # pragma: no cover
            logger.debug("removeTranslator fehlgeschlagen: %s", e)
    _installed = []

    # Englisch ist die Qt-Default-Sprache -> nichts zu laden, aber kein Fehler.
    if lang == "en":
        return True

    dirs = _candidate_translation_dirs()
    loaded_any = False

    # qtbase deckt die Standard-Widgets/Kontextmenüs ab; qt_ ist der Sammel-Katalog.
    for prefix in ("qtbase", "qt"):
        for d in dirs:
            qm = d / f"{prefix}_{lang}.qm"
            if not qm.exists():
                continue
            translator = QTranslator(app)
            # load(filename, directory) ist am robustesten
            if translator.load(f"{prefix}_{lang}", str(d)) and app.installTranslator(
                translator
            ):
                _installed.append(translator)
                loaded_any = True
                logger.debug("Qt-Übersetzung installiert: %s", qm)
                break  # diesen prefix erledigt, nächsten prefix probieren

    if not loaded_any:
        logger.info(
            "Keine qtbase_%s.qm gefunden – native Kontextmenüs bleiben englisch. "
            "Geprüfte Pfade: %s",
            lang,
            [str(d) for d in dirs],
        )
    else:
        logger.info(
            "Qt-Übersetzungen für '%s' aktiv (native Kontextmenüs lokalisiert).", lang
        )
    return loaded_any


# ──────────────────────────────────────────────────────────────────────────
# QLocale an das gewählte Zahlenformat koppeln
# ──────────────────────────────────────────────────────────────────────────
def apply_number_locale(number_format: str) -> bool:
    """Setzt die Qt-Standard-QLocale passend zum BudgetManager-Zahlenformat.

    Wichtig für QDoubleSpinBox & Co.: Diese Widgets parsen/formatieren nach
    QLocale, nicht nach utils.money. Ohne Kopplung müsste ein EU-Nutzer im
    Spin-Feld weiterhin Punkt statt Komma eingeben.

    Mapping der kanonischen BudgetManager-Formate:
      swiss/ch  -> de_CH   german/eu/french -> de_DE   anglo/us -> en_US
    """
    try:
        from PySide6.QtCore import QLocale
    except Exception as e:  # pragma: no cover
        logger.debug("QLocale nicht verfügbar: %s", e)
        return False

    code = (number_format or "swiss").strip().lower()
    locale_name = {
        "swiss": "de_CH",
        "ch": "de_CH",
        "de_ch": "de_CH",
        "german": "de_DE",
        "eu": "de_DE",
        "de": "de_DE",
        "french": "fr_FR",
        "fr": "fr_FR",
        "anglo": "en_US",
        "us": "en_US",
        "en": "en_US",
        "uk": "en_US",
    }.get(code, "de_CH")
    try:
        QLocale.setDefault(QLocale(locale_name))
        logger.debug("QLocale gesetzt: %s (Zahlenformat %s)", locale_name, code)
        return True
    except Exception as e:  # pragma: no cover
        logger.debug("QLocale.setDefault fehlgeschlagen: %s", e)
        return False
