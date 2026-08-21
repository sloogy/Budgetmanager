# Paketübersicht — BudgetManager v2.2.64

Diese Übersicht beschreibt den aktuellen Release-Quellbaum. Alte Arbeits-, Analyse- und Zwischenstandsberichte sind nicht Bestandteil des Release-Pakets.

## Root

```text
main.py                         App-Start
app_info.py                     zentrale Version
settings.py                     persistente Einstellungen
settings_dialog.py              Einstellungsdialog
theme_manager.py                Theme-Anwendung
version.json                    lokale Versionsinfo
latest.json.template            Release-/Updater-Template
README.md                       Hauptdokumentation
README_INSTALLATION.md          Installation und Start
CHANGELOG.md                    Versionshistorie
FEATURES.md                     Funktionsübersicht
```

## Ordner

```text
.github/workflows/              GitHub-Actions-Build
model/                          Datenbank, Migrationen, Geschäftslogik
views/                          PySide6-UI
views/tabs/                     Hauptbereiche Budget/Kategorien/Tracking/Übersicht
utils/                          i18n, Geldformatierung, Hilfsfunktionen
locales/                        de/en/fr Übersetzungen
data/                           Standard-Kategorien und Platzhalter
installer/                      Inno-Setup-Skript
updater/                        Update-Logik und Manifest-Helfer
tools/                          Release-/Audit-Skripte
tests/                          Core- und GUI-Smoke-Tests
docs/                           aktive technische Dokumentation und Hilfe
```

## Bereinigt in diesem Paket

- Keine AI-Arbeitsordner.
- Keine lokalen Nutzer-Settings.
- Keine Python-Cache-Ordner.
- Historische Merge-, Analyse- und Bugfix-Berichte liegen ausschließlich unter `docs/archive/release-evidence/`.
- Release-Dateien, aktive Dokumentation und Manifest-Beispiele sind auf `v2.2.63` synchronisiert.
- Der Tag-Workflow veröffentlicht unsigned Windows-/Linux-`.lpmodule` samt SHA-256-Dateien für den lokalen Import mit Vertrauensbestätigung.
