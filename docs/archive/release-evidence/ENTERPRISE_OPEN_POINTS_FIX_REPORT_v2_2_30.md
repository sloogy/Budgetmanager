# BudgetManager v2.2.30 – Enterprise Open Points Fix Report

Datum: 24. Juli 2026

## Umgesetzte Korrekturen

### 1. GitHub-Actions Supply-Chain-Härtung

- Workflowweite Schreibrechte entfernt; global gilt nur noch `contents: read`.
- `contents: write`, `id-token: write` und `attestations: write` sind ausschließlich dem finalen Manifest-/Release-Job zugeordnet.
- Externe Actions in allen Workflows auf vollständige Commit-SHAs gepinnt.
- Regressionstest verhindert künftig bewegliche `@vN`-Referenzen und zu breite globale Rechte.

### 2. Manifest-Verifikation fail-closed

- Bei angeforderter Signaturprüfung ist ein vertrauenswürdiger Public Key zwingend erforderlich.
- Fehlt der Schlüssel, beendet sich das Release-Gate mit Fehler statt die kryptografische Prüfung auf den Client zu verschieben.
- Bestehende Ed25519-, Struktur- und Asset-Vertragsprüfungen bleiben erhalten.

### 3. DPI- und Kleinbildschirm-Härtung

- Neue zentrale Hilfsfunktion `utils/responsive_dialog.py`.
- Große Dialoge begrenzen Mindest- und Startgröße auf die tatsächlich verfügbare Bildschirmfläche.
- Die Anpassung erfolgt sofort und nochmals nach Abschluss des Qt-Layouts.
- Gehärtet wurden Einstellungen, wiederkehrende Buchungen, Kategorienverwaltung, Hilfe, Tastenkürzel, Setup-Assistent, Budget-Erfassung, globale Suche, Favoriten und Tag-Verwaltung.

### 4. Architektur-Gate korrigiert

- Die große `main()`-Funktion wird nicht mehr still von der Prüfung ausgenommen.
- Historische Altlasten besitzen jetzt eine explizite, begrenzte Legacy-Obergrenze.
- Neue und normale Funktionen bleiben auf 400 Zeilen begrenzt.
- Die Erfolgsmeldung beschreibt den tatsächlichen Prüfvertrag korrekt.

### 5. Regressionstests

Neue Datei: `tests/test_release_2231_enterprise_release_fixes.py`

Abgedeckt werden:

- Least-Privilege-Rechte im Release-Workflow
- vollständige SHA-Pins für externe Actions
- fail-closed Manifestprüfung ohne Public Key
- responsive Härtung aller großen Dialoge
- explizite und begrenzte Architektur-Legacy-Ausnahme

## Verifikation

- Python-Kompilierung: PASS
- Release-Logik-Audit: 100/100 Loops, 0 Findings
- Enterprise UI/ADHS Audit: 1.000 Loops, 4.300 Checks, 0 Fehler
- Architektur-Gate: PASS
- Lint-/Release-Prozedur: PASS
- Versionssynchronität: PASS
- Gesamtsuite: 580 bestanden, 9 übersprungen

Zwei Tests konnten in der bereitgestellten Prüfungsumgebung nicht ausgeführt werden:

- Bandit-Gate: Bandit nicht installiert
- isolierter KILLCRITIC-Qt-Worker: PySide6 nicht installiert

Dies sind Umgebungsfehler und keine festgestellten Programmregressionen.

## Release-Einschätzung

Die zuvor offenen Enterprise-Punkte wurden im Quellstand behoben. Für die finale öffentliche Freigabe sollte die CI einmal in der vorgesehenen vollständigen Build-Umgebung mit den gelockten Development-Abhängigkeiten, Bandit und PySide6 durchlaufen.
