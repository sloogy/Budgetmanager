# BudgetManager v2.2.12 – Release-Fixbericht

**Datum:** 11. Juli 2026  
**Ausgangsversion:** 2.2.11 Security Hardening  
**Zielversion:** 2.2.12 Update & Restore Transaction Hardening

## Umgesetzte Release-Blocker

### 1. Vorhandenes Update-Staging wird nicht mehr wiederverwendet
Nach jedem erfolgreich heruntergeladenen und per SHA256 geprüften Asset wird der komplette Staging-Ordner gelöscht und neu aufgebaut. Alte, manipulierte oder unvollständige Dateien können dadurch nicht mehr in ein neues Update gelangen.

### 2. Portable ZIPs werden strukturell validiert
Ein ZIP gilt nicht mehr allein deshalb als gültig, weil irgendeine Datei enthalten ist. Erforderlich ist nun mindestens ein erkennbarer BudgetManager-Startpunkt:

- `BudgetManager` beziehungsweise `BudgetManager.exe`, oder
- Source-Paket mit `main.py` plus `app_info.py` beziehungsweise `version.json`.

Ein ZIP mit nur einer README wird abgelehnt.

### 3. Schutz beim Entpacken erweitert
Der Updater blockiert jetzt:

- Pfad-Traversal und ZipSlip
- Symlinks im Archiv
- leere Archive
- mehr als 20.000 Archiveinträge
- Einzeldateien über 512 MB
- mehr als 2 GB entpackte Gesamtdaten
- auffällige Kompressionsraten als Zip-Bomb-Indikator

### 4. Staging wird unmittelbar vor Installation erneut geprüft
Nach dem Entpacken wird ein deterministischer SHA256 über Dateipfade, Größen und Inhalte des gesamten Staging-Baums erstellt und im Update-Marker gespeichert. `apply_update` berechnet diesen Hash vor der Installation erneut und bricht bei jeder Veränderung ab.

### 5. Full-Tree-Update mit Rollback
Programmkomponenten werden nicht mehr zuerst gelöscht und danach einzeln kopiert. Neue Komponenten werden vorbereitet, alte Komponenten in einen Transaktionsordner verschoben und neue Komponenten per Rename aktiviert. Scheitert ein Schritt, werden alle bereits ausgetauschten Komponenten zurückgerollt.

### 6. Vollständiger Konto-Restore transaktional
Datenbank und `users.json` werden jetzt als zusammengehörige Einheit behandelt:

- beide neuen Dateien werden zuerst vollständig vorbereitet,
- beide bisherigen Dateien werden als Rollback gesichert,
- schlägt der zweite Austausch fehl, wird auch der erste rückgängig gemacht,
- DB und Benutzer-Schlüssel können dadurch nicht mehr in einem gemischten Zustand verbleiben.

### 7. Restriktive Dateirechte nach Backup-Import
Importierte `.bmr`-Dateien erhalten nach dem Kopieren sofort die sicheren Dateirechte des BudgetManagers.

## Zusätzliche Release-Bereinigung

- Version auf **2.2.12** synchronisiert
- Releasedatum auf **11. Juli 2026** synchronisiert
- öffentliche Dokumentation und Benutzerhandbücher aktualisiert
- `requirements.lock`-Header aktualisiert
- PyInstaller für reproduzierbare Builds auf **6.16.0** fixiert
- automatisch erzeugte Backup- und Cache-Artefakte vor dem Verpacken entfernt

## Neue Regressionstests

Sechs neue Tests prüfen:

1. README-only-Update wird abgelehnt
2. Pfad-Traversal im ZIP wird abgelehnt
3. manipuliertes Staging wird vor Anwendung erkannt
4. bestehendes Staging wird vollständig neu aufgebaut
5. fehlgeschlagener Programmtausch wird zurückgerollt
6. Backup-Import und Full-Account-Restore enthalten die neuen Sicherheitsmechanismen

## Prüfergebnisse

- **403 Tests bestanden**
- **2 Tests übersprungen** – echte Qt-GUI-Smokes in der nicht vollständigen GUI-Testumgebung
- Python-Kompilierung: bestanden
- Versionssynchronisierung: bestanden
- Lint-/Release-Prozedur: bestanden
- Release-Baum bereinigt: bestanden

## Release-Urteil

**Code-seitig releasefähig mit Vorbehalt.**

Die zuvor bestätigten Update- und Restore-Blocker sind behoben und durch Regressionstests abgesichert. Vor dem öffentlichen Release bleiben die normalen plattformspezifischen manuellen Smoke-Tests erforderlich:

- Fedora: Start, Update-Simulation, Backup/Restore, Tracking und Cockpit
- Windows: Installer-Update beziehungsweise externer Update-Helfer mit realer gebuildeter EXE
- Sichtprüfung der wichtigsten Dialoge in Deutsch, Englisch und Französisch
