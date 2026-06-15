# Paketübersicht — BudgetManager v2.0.8

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
docs/                           technische Dokumentation
```

## Bereinigt in diesem Paket

- Keine AI-Arbeitsordner.
- Keine lokalen Nutzer-Settings im Root.
- Keine alten Merge-/Analyse-Berichte.
- Kein `_attic`-Ordner mit totem Code.
- Release-Dateien sind auf `v2.0.8` synchronisiert.
