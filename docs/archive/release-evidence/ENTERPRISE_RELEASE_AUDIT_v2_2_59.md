# BudgetManager v2.2.59 – selektiver LifePlanner-Baseline-Merge

**Datum:** 3. August 2026  
**Status:** Zielsystem-Test erforderlich  
**Verbindliche Basis:** `BudgetManager_Source_2_2_56_LIFEPLANNER_FIXED_2026-08-02.zip`  
**Quellversion für selektive Verbesserungen:** v2.2.58

## 1. Merge-Strategie

v2.2.56 LIFEPLANNER_FIXED blieb führend. v2.2.58 wurde nicht vollständig darüberkopiert. Übernommen wurden nur die zuvor vereinbarten Verbesserungen:

- Lohnzyklus für den Cockpit-Monatsstatus,
- gehärtete LifePlanner-/FPM-Import-Inbox,
- offener Importzähler und Review-Dialog,
- zusätzliche LifePlanner-Vertragsprüfung,
- SHA256-Erzeugung für `.lpmodule`-Pakete.

## 2. Aus der Basis unverändert erhalten

- `BUDGETMANAGER_DATA_DIR`
- `LIFEPLANNER_MODULE_DATA_DIR`
- `LIFEPLANNER_BRIDGE_DIR`
- `LIFEPLANNER_CENTRAL_UPDATER=1`
- Windows-x86_64- und Linux-x86_64-Modulbuild
- FPM-Ausgaben-Outbox
- Sparziel-Outbox
- Standalone-Start und eigener Updater außerhalb des LifePlanner-Modus
- unabhängige Cockpit-Spalten mit sichtbarer Drop-Vorschau
- QtCharts-Lebensdauer-Härtung
- Sparziel-Flussbestand mit Bezug, Korrektur und Teilfreigabe
- verschlüsselte Datenbank, Backups und Datenbankschema 18

## 3. Neue sichere Import-Inbox

- Keine automatische Finanzbuchung.
- Neue, geänderte, abgelehnte und verwaiste Vorschläge werden getrennt behandelt.
- Stabile externe IDs und Payload-Hashes verhindern Dubletten.
- Geänderte Upserts aktualisieren die bestehende Zielbuchung.
- Benutzerkategorien bleiben bei späteren Aktualisierungen erhalten.
- Datum, Typ, Kategorie, Betrag und Beschreibung sind vor Übernahme editierbar.
- Fremdwährungen benötigen eine ausdrückliche Umrechnungsbestätigung.
- Dateigröße, Zeilenlänge, Datensatzanzahl, ID, Datum und Betrag werden begrenzt und validiert.
- Offene Vorschläge werden in der Seitenleiste angezeigt.

## 4. Lohnzyklus-Monatsstatus

Der Monatsstatus läuft vom tatsächlichen beziehungsweise hinterlegten Lohneingang bis zum Tag vor dem nächsten Lohntag. Beispiel: Lohneingang am 25. Januar ergibt den Zeitraum 25. Januar bis 24. Februar. Die Trendwerte vergleichen den vorherigen Lohnzyklus. Ohne erkennbare Lohnkategorie bleibt der Kalendermonat als sicherer Fallback.

## 5. Modulpaket und GitHub-Release

Der bestehende Dual-Plattform-Workflow bleibt erhalten. Der Builder:

- erstellt signierte `.lpmodule`-Pakete für Windows x86_64 und Linux x86_64,
- prüft das erzeugte ZIP-Archiv,
- erzeugt zusätzlich eine gleichnamige `.sha256`-Datei,
- veröffentlicht Paket und Prüfsumme gemeinsam im GitHub-Release.

## 6. Prüfergebnisse

| Gate | Ergebnis |
|---|---:|
| Vollständige Pytest-Suite in drei Gruppen | **815 bestanden, 13 übersprungen, 0 fehlgeschlagen** |
| Selektive LifePlanner-/Lohnzyklus-Tests | **26 bestanden** |
| Final Release Audit | **1'000 Schleifen / 19'755 Prüfungen / 0 Warnungen / 0 Fehler** |
| Release-Logik-Audit | **100 Schleifen / 0 Findings** |
| i18n-Audit DE/EN/FR | **PASS** |
| Handbuch-Vollständigkeit | **PASS** |
| Versions- und Dokumentationsabgleich | **PASS – 2.2.59** |
| Release-Lint und Bereinigung | **PASS** |
| Python-Syntax-/Bytecodeprüfung | **PASS** |
| Bandit | **Nicht ausgeführt: Werkzeug nicht installiert** |
| Echte Qt-/PySide6-Laufzeitprüfung | **Nicht möglich: PySide6 in der Audit-Umgebung nicht installiert** |

## 7. Änderungsumfang gegen die Basis

- Geänderte bestehende Dateien: **45**
- Neu hinzugefügte Dateien: **9**
- Entfernte Dateien: **0**

Die Änderungen konzentrieren sich auf LifePlanner-Vertrag, Import-Inbox, Lohnzyklus, Cockpit-Anbindung, Übersetzungen, Dokumentation, Tests und Modul-Releaseprozess.

## 8. Noch nötiger Zielsystemtest

1. Standalone-Start unter Fedora.
2. Start als Modul aus LifePlanner 0.5.0.
3. Getrennte Datenordner für mindestens zwei LifePlanner-Profile.
4. Echte FPM-Bridge-Datei: bearbeiten, übernehmen, ändern und ablehnen.
5. FPM-Ausgaben- und Sparziel-Outbox über „An FPM bereitstellen“ erzeugen.
6. Monatsstatus mit echtem Lohneingang prüfen.
7. Windows- und Linux-`.lpmodule` im GitHub-Workflow bauen und installieren.

## 9. LifePlanner-Folgeänderung

Der bereitgestellte LifePlanner 0.5.0 pinnt BudgetManager weiterhin auf **2.2.49**. Nach Veröffentlichung muss in `dependencies/modules.lock.json` die Version und `default_ref` auf **2.2.59 / v2.2.59** angehoben werden.
