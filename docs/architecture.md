# Architektur & Systemanalyse — BudgetManager v3.1.1

Stand: 30. Juli 2026

## Architekturmodell

BudgetManager ist eine lokale, schichtenorientierte PySide6-Anwendung:

- `main.py`: Prozessstart, Kontoauswahl, Datenbanköffnung und Hauptfenster.
- `model/`: SQLite-Zugriff, Migrationen und Geschäftslogik.
- `views/`: PySide6-Oberfläche und UI-Orchestrierung.
- `utils/`: gemeinsam genutzte Infrastruktur, Sicherheit und UI-Hilfen.
- `updater/`: signierter Update-Download, Staging, Integritätsprüfung und Rollback.
- `tools/`: reproduzierbare Release-, Audit- und Build-Werkzeuge.

Ein eigener `controllers/`-Ordner wird aktuell nicht verwendet. Die Views rufen klar abgegrenzte Model-APIs auf; neue SQL-Zugriffe gehören grundsätzlich in die Model-Schicht.

## Daten und Migrationen

- SQLite mit aktivierter Fremdschlüsselprüfung, WAL-Modus und Schema-Migrationen.
- Aktuelle Schema-Version: **17**.
- Persistentes Undo/Redo mit referenzieller Tag-Bereinigung.
- Automatische, begrenzte Backups vor Migrationen.
- Restore-Bundles besitzen SHA-256-Integritätsprüfung und ZIP-Grössenlimits. Die finale Installation erfolgt über eine verifizierte, atomare Kopie mit `fsync`.
- Legacy-Backups ohne Prüfsumme werden standardmässig abgelehnt und nur nach ausdrücklicher Bestätigung in eine neue, geprüfte Kopie konvertiert.

## Sicherheitsarchitektur

- PIN/Passwort: PBKDF2-HMAC-SHA256 mit automatischem Legacy-Upgrade.
- Verschlüsselte Kontodaten: Fernet, technisch AES-128-CBC plus HMAC-SHA256.
- Updates: HTTPS, SHA-256 pro Asset und verpflichtende Ed25519-Signatur des exakten Manifests.
- Windows-Releases: verpflichtende Authenticode-Signatur für Anwendung und Installer.
- Supply Chain: transitive, gehashte Lockfiles; CycloneDX-SBOM; GitHub Build-Provenance.
- Excel-Import: vorgelagerte Prüfung gegen Pfad-Traversal, Symlinks, DTD/ENTITY, ZIP-Bomben und übergrosse Inhalte.

## Bericht und Diagnose

- CSV/TXT-Export bleibt kompatibel; XLSX nutzt getrennte Tabellenblätter und PDF einen A4-Qt-Druckpfad.
- Diagnose-ZIPs enthalten nur technische, anonymisierte Laufzeit- und Datenbank-Gesundheitsdaten.
- Bedienmodi liegen in einer Qt-freien Policy und werden durch ein kleines UI-Menü angewendet.

## Qualitätsgrenzen

`tools/architecture_quality_gate.py` verhindert neue übergrosse Produktdateien oder Methoden:

- Produktdatei: maximal 3.500 Zeilen.
- Funktion/Methode: maximal 400 Zeilen.
- `AboutDialog` und `LogViewerDialog` wurden aus `views/main_window.py` ausgelagert.

Die grössten UI-Dateien bleiben wartungsintensiv. Sie sind kein Release-Blocker mehr, weil eine feste Obergrenze weiteres Wachstum verhindert. Neue Funktionen sollen bevorzugt in kleinere Panels, Dialoge oder Hilfsmodule ausgelagert werden.

## Verbindliche Release-Gates

- vollständiger Black-Check des Quellbaums
- Mypy für die Model-Schicht
- Bandit: Nulltoleranz für MEDIUM/HIGH
- Tests mit Branch-Coverage und kritischen Modulgrenzen
- i18n-Parität DE/EN/FR ohne unreferenzierte Schlüssel
- Fedora/Wayland- und Windows-Skalierungsgates
- 10.000 Enterprise- und KILLCRITIC-Loops
- signierter PyInstaller-/Installer-Build mit Attestierung
