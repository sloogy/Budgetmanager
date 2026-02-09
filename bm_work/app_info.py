"""Zentrale App-Metadaten (Name/Version/Release-Datum).

Best Practice:
- Version nur hier ändern.
- GUI (Fenstertitel, Über-Dialog), Updater, Logs usw. lesen diese Werte.

Hinweis:
Die Codebasis hieß historisch "v2.2.0 ... fix2" – für Releases verwenden wir aber 0.x.x.x,
solange das Projekt noch nicht "fertig" ist.
"""

APP_NAME = "Budgetmanager"

# SemVer-ähnlich, aber mit 4 Stellen wie von dir gewünscht: 0.MAJOR.MINOR.PATCH
APP_VERSION = "0.3.0.0"

# Nur Anzeige (About-Dialog). Kannst du jederzeit anpassen.
APP_RELEASE_DATE = "9. Februar 2026"


def app_window_title() -> str:
    """Fenstertitel der App."""
    return f"{APP_NAME} v{APP_VERSION}"


def app_about_title() -> str:
    """Titel des Über-Dialogs."""
    return f"Über {APP_NAME} v{APP_VERSION}"


def app_version_label() -> str:
    """Version-String für Anzeigen in der UI."""
    return f"{APP_VERSION} ({APP_RELEASE_DATE})"
