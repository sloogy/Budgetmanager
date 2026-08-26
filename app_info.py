"""Zentrale App-Metadaten (Name/Version/Release-Datum).

Best Practice:
- Version nur hier ändern.
- GUI (Fenstertitel, Über-Dialog), Updater, Logs usw. lesen diese Werte.

Hinweis:
Die Versionsnummer ist die zentrale Release-Nummer für App, Installer, Updater und Anzeige.
"""

from __future__ import annotations

APP_NAME = "Budgetmanager"

# SemVer-Release-Version
APP_VERSION = "3.0.7"

# Nur Anzeige (About-Dialog). Kannst du jederzeit anpassen.
APP_RELEASE_DATE = "25. August 2026"


def app_window_title() -> str:
    """Fenstertitel der App."""
    return f"{APP_NAME} v{APP_VERSION}"


def app_about_title() -> str:
    """Titel des Über-Dialogs."""
    return f"Über {APP_NAME} v{APP_VERSION}"


def app_version_label() -> str:
    """Version-String für Anzeigen in der UI."""
    return f"{APP_VERSION} ({APP_RELEASE_DATE})"
