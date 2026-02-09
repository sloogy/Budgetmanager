# Changelog

Alle wichtigen Änderungen am BudgetManager-Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## [0.17.0] - 2024-12-23

### ✨ Hinzugefügt

#### Wiederkehrende Transaktionen mit Soll-Buchungsdatum
- **Neue Tabelle:** `recurring_transactions` für automatische Buchungen
- **Soll-Buchungsdatum:** Festlegung eines bestimmten Tags im Monat (1-31)
- **Automatische Erkennung:** System prüft täglich auf fällige Buchungen
- **Zeitliche Begrenzung:** Start- und Enddatum für wiederkehrende Transaktionen
- **Aktivierungsstatus:** Ein-/Ausschalten ohne Löschen
- **Letztes Buchungsdatum:** Tracking der letzten automatischen Buchung
- **Prüf-Dialog:** Manuelles Prüfen und Buchen fälliger Transaktionen
- **Model:** `RecurringTransactionsModel` mit allen CRUD-Operationen
- **UI:** `RecurringTransactionsDialogExtended` für Verwaltung

#### Intelligente Budget-Warnungen und Anpassungsvorschläge
- **Erweiterte Analyse:** Prüfung der letzten 6 Monate auf Budget-Überschreitungen
- **Häufigkeitszähler:** Tracking wie oft Budget überschritten wurde
- **Intelligente Vorschläge:** 
  - Gewichteter Durchschnitt der Ausgaben (neuere Monate stärker gewichtet)
  - 10% Sicherheitspuffer
  - Rundung auf praktische Werte
- **Automatischer Dialog:** Bei häufigen Überschreitungen (≥3 Monate)
- **Überschreitungs-Statistiken:**
  - Anzahl Überschreitungen
  - Durchschnittliche Überschreitung in %
  - Maximale Überschreitung
- **Model:** `BudgetWarningsModelExtended` mit erweiterten Funktionen
- **UI:** `BudgetAdjustmentDialog` mit visueller Darstellung und Empfehlungen

#### Datenbank-Management
- **Datenbank-Reset auf Standardwerte:**
  - Option: Kategorien behalten
  - Option: Budgets behalten
  - Automatisches Backup vor Reset
  - Wiederherstellung von Standard-Kategorien
- **Erweiterte Backup-Funktionen:**
  - Manuelle Backups mit eigenem Namen
  - Backup-Liste mit Metadaten (Größe, Datum)
  - Backup-Verwaltung (Anzeigen, Löschen)
- **Datenbank-Statistiken:**
  - Dateigröße in MB
  - Anzahl Einträge pro Tabelle
  - Zeitraum der Transaktionen (erste/letzte)
  - Summen nach Typ
  - Anzahl Jahre/Monate mit Daten
- **Datenbank-Optimierung:**
  - VACUUM-Funktion für Defragmentierung
  - Speicherplatz-Freigabe
- **JSON-Export:**
  - Export von Kategorien, Budgets, Transaktionen
  - Konfigurierbare Export-Optionen
- **Model:** `DatabaseManagementModel`

#### Windows-Spezifische Features
- **Inno Setup Installer-Skript:**
  - Professioneller Windows-Installer
  - Mehrsprachig (Deutsch/Englisch)
  - Konfigurierbare Datenverzeichnisse
  - Desktop- und Startmenü-Verknüpfungen
  - Saubere Deinstallation
- **Build-Skript:** `build_windows.py`
  - Automatisiertes Erstellen von EXE
  - Erstellung von Portable-ZIP
  - Erstellung von Installer
  - Bereinigung alter Builds
  - PyInstaller .spec Generierung
- **Automatisches Lizenz-Handling**
- **Icon-Integration**

#### Update-Tool
- **Automatische Update-Prüfung:**
  - Prüfung gegen GitHub Releases
  - Versionserkennung (Semantic Versioning)
  - Konfigurierbare Prüf-Intervalle
- **Update-Download:**
  - Fortschrittsanzeige
  - Temporärer Download-Speicher
- **Update-Installation:**
  - Silent-Installation möglich
  - Automatisches Backup vor Update
- **Update-Kanäle:**
  - Stable-Channel
  - Beta/Pre-Release-Channel
- **Checksum-Verifikation:**
  - SHA256-Hash-Prüfung
  - Größen-Validierung
- **Einstellungen:**
  - Auto-Check aktivieren/deaktivieren
  - Prüf-Intervall konfigurieren
  - Auto-Download/Install
  - Pre-Releases einschließen
- **Tool:** `tools/update_manager.py` mit CLI-Interface
- **Model:** `UpdateManager` Klasse

#### Weitere Verbesserungen
- **Migration v4 → v5:** Neue Tabelle für wiederkehrende Transaktionen
- **Erweiterte Validierung:** Sicherstellung gültiger Buchungsdaten
- **Performance-Indizes:** Optimierte Datenbankabfragen
- **Fehlerbehandlung:** Verbesserte Fehlerbehandlung in allen neuen Features

### 🔧 Geändert
- **Schema-Version:** Von 4 auf 5 erhöht
- **Budget-Warnings-Model:** Erweitert um historische Analyse
- **Migrations:** Unterstützung für neue Tabellen hinzugefügt
- **Settings:** Neue Einstellungen für Updates und wiederkehrende Transaktionen

### 🐛 Behoben
- Edge-Cases bei Monatsenden (z.B. 31. Februar wird auf letzten Tag des Monats gesetzt)
- Zeitzone-Probleme bei Datumsberechnungen
- Memory-Leaks in langen Sessions

### 📖 Dokumentation
- README komplett überarbeitet
- Neue Abschnitte für alle Features
- Build-Anleitung für Windows
- Update-Anleitung
- Entwickler-Dokumentation erweitert

### 🔒 Sicherheit
- Checksum-Verifikation für Downloads
- Backup vor kritischen Operationen
- Validierung von Benutzereingaben
- Schutz vor SQL-Injection (Parameterized Queries)

---

## [0.16.0] - 2024-11-XX

### ✨ Hinzugefügt
- **Tags/Labels** für zusätzliche Kategorisierung
- **Undo/Redo-Funktion** für alle Änderungen
- **Favoriten** für häufig verwendete Kategorien
- **Sparziele** setzen und verfolgen
- **Budget-Warnungen** mit konfigurierbaren Schwellenwerten
- **Theme Profiles** - Speichern und Laden von Farbschemata
- **Backup & Restore** Funktionalität
- **Globale Suche** über alle Transaktionen

### 🔧 Geändert
- UI-Verbesserungen in allen Dialogen
- Performance-Optimierungen bei großen Datenmengen
- Schema-Version auf 4 erhöht

### 🐛 Behoben
- Absturz bei leerem Budget
- Sortierung in Kategorie-Tabelle
- Excel-Export mit Sonderzeichen

---

## [0.15.0] - 2024-10-XX

### ✨ Hinzugefügt
- **Fixkosten-Management**
- **Monatliche Übersicht** mit Visualisierungen
- **Quick-Add Dialog** für schnelle Buchungen
- **Tastaturkürzel** für häufige Aktionen

### 🔧 Geändert
- Modernisiertes UI-Design
- Verbesserte Navigation
- Schnellere Ladezeiten

---

## [0.14.0] - 2024-09-XX

### ✨ Hinzugefügt
- **Kategorien-Verwaltung** verbessert
- **Budget-Tracking** mit monatlicher Ansicht
- **Export nach Excel** (.xlsx)

### 🐛 Behoben
- Datum-Sortierung in Tracking-Tabelle
- Rundungsfehler bei Währungen

---

## [0.13.0] - 2024-08-XX

### ✨ Hinzugefügt
- **Diagramme** für Ausgaben-Visualisierung
- **PDF-Export** von Reports
- **Filtern** nach Kategorien und Zeitraum

---

## [0.12.0] - 2024-07-XX

### ✨ Hinzugefügt
- **Fixkosten-Funktionalität**
- **Wiederkehrende Buchungen** (Basis-Version)
- **Notizen** zu Transaktionen

### 🔧 Geändert
- Datenbank-Schema optimiert
- UI für bessere Übersichtlichkeit

---

## [0.10.0] - 2024-05-XX

### ✨ Hinzugefügt
- **Jahresübersicht**
- **Budget vs. Ist-Vergleich**
- **Kategorien-Analyse**

---

## [0.8.0] - 2024-03-XX

### ✨ Hinzugefügt
- **Export-Funktionen** (CSV, Excel)
- **Suchfunktion** für Transaktionen
- **Mehrjahres-Support**

---

## [0.5.0] - 2024-01-XX

### ✨ Hinzugefügt
- **Basis-Tracking** von Einnahmen und Ausgaben
- **Budget-Planung** nach Kategorien
- **SQLite-Datenbank**
- **Kategorien-Verwaltung**

---

## Legende

- ✨ **Hinzugefügt** - Neue Features
- 🔧 **Geändert** - Änderungen an existierenden Features
- 🐛 **Behoben** - Bug-Fixes
- 🗑️ **Entfernt** - Entfernte Features
- 🔒 **Sicherheit** - Sicherheitsverbesserungen
- 📖 **Dokumentation** - Dokumentations-Änderungen
- ⚡ **Performance** - Performance-Verbesserungen

---

[0.17.0]: https://github.com/yourusername/budgetmanager/compare/v0.16.0...v0.17.0
[0.16.0]: https://github.com/yourusername/budgetmanager/compare/v0.15.0...v0.16.0
