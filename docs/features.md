# Budgetmanager v0.4.8.0 — Vollständige Feature-Dokumentation

## Übersicht

Der Budgetmanager ist eine umfassende Desktop-Anwendung zur Verwaltung persönlicher Finanzen mit erweiterten Features für Budget-Planung, Tracking und Analyse. Entwickelt mit Python, PySide6 (Qt 6) und SQLite.

**Aktuelle Version:** 1.0.0 (19. Februar 2026)  
**Codebase:** ~28'500 Zeilen Python, 139+ Dateien, MVC-Architektur

---

## Implementierte Features

### 1. Budget-Verwaltung ⭐
- **17-Spalten Budget-Tabelle**: Monatlich oder jährlich planen
- **Hierarchische Kategorien**: Haupt- und Unterkategorien mit Baumansicht
- **Multi-Typ-Support**: Einkommen, Ausgaben, Ersparnisse
- **Budget-Saldo**: Automatische Berechnung (Einkommen − Ausgaben − Ersparnisse)
- **Jahr kopieren**: Budget von Jahr zu Jahr übernehmen (mit/ohne Beträge)
- **Budget-Vorschläge**: Dynamische Anpassungsempfehlungen basierend auf historischen Daten
- **Schutz**: Verhindert System-Kategorien wie "BUDGET-SALDO"

### 2. Tracking (Buchungen) 📊
- **Transaktionsverwaltung**: Erfassen, bearbeiten, löschen
- **Filtern & Suchen**: Nach Datum, Typ, Kategorie, Betrag, Tags
- **Schnelleingabe**: Dialog für häufige Buchungen (Strg+N)
- **Batch-Import**: Excel/CSV-Import für Massenbuchungen
- **Kontextmenü**: Rechtsklick für schnelle Aktionen
- **Sortierung**: Alle Spalten sortierbar

### 3. Wiederkehrende Transaktionen 🔄
- **Automatische Buchungen**: Mit Soll-Buchungsdatum je Eintrag
- **Flexibles Intervall**: Monatlich, quartalsweise, jährlich
- **Fälligkeitsmanagement**: Status-Anzeige (überfällig/heute/bevorstehend)
- **Direkt buchen**: Aus Übersicht heraus mit einem Klick

### 4. Fixkosten-Management ⚡
- **Monatsprüfung**: Automatische Prüfung ob in dem Monat schon gebucht
- **Fehlende Buchungen**: Optionale Liste zum Anzeigen und Auswählen
- **Schätzung**: Basierend auf Durchschnitt und Vorjahr
- **Direktes Buchen**: Aus Liste heraus buchen mit einem Klick
- **Auto-Erkennung**: Erkennt potenzielle Fixkosten automatisch

### 5. Budgetwarnungen ⚠️
- **Überschreitungs-Alerts**: Warnung bei Budget-Überschreitung
- **Prozentuale Schwellwerte**: Konfigurierbare Warnstufen (80%, 100%)
- **Chronische Überschreiter**: Erkennung bei ≥3 Monaten
- **Budget-Anpassungsvorschläge**: Detaillierte Empfehlungen mit Einkommens-Check
- **Kategorien-spezifisch**: Individuelle Warnungen pro Kategorie

### 6. Tags & Labels 🏷️
- **Flexible Kategorisierung**: Zusätzlich zu Hauptkategorien
- **Multi-Tag-Support**: Mehrere Tags pro Buchung
- **Farbige Tags**: Individuelle Farben wählbar
- **Tag-Verwaltung**: Erstellen, umbenennen, löschen, zusammenführen
- **Tag-Statistiken**: Auswertung nach Tags mit Nutzungszählung

### 7. Undo/Redo ↩️
- **Änderungen rückgängig**: Strg+Z für Undo
- **Wiederherstellen**: Strg+Shift+Z für Redo
- **Persistenter Stack**: Überlebt Neustart (SQLite-basiert)
- **Gruppen-Undo**: Zusammengehörige Operationen als Einheit

### 8. Favoriten ⭐
- **Häufige Kategorien pinnen**: Rechtsklick → "Als Favorit markieren"
- **Dashboard**: Eigener Dialog mit Budget-Auslastung und Fortschrittsbalken
- **Schnellzugriff**: Favoriten prominent in der Übersicht
- **Typ-übergreifend**: Für Einkommen, Ausgaben und Ersparnisse

### 9. Sparziele 💰
- **Ziel definieren**: Name, Zielbetrag, Zieldatum, Priorität
- **Fortschritt tracken**: Automatische Berechnung aus Ersparnisse-Buchungen
- **Visualisierung**: Fortschrittsbalken mit Farbabstufung
- **Entnahme/Freigabe**: Sparziel-Beträge teilweise freigeben
- **Synchronisation**: Automatisch mit Tracking-Buchungen

### 10. Backup & Wiederherstellung 💾
- **Manuelles Backup**: Jederzeit als ZIP-Archiv sichern
- **Auto-Backup**: Vor kritischen Operationen (Reset, Restore)
- **Wiederherstellung**: Aus Backup-Liste auswählen und restaurieren
- **Backup-Verwaltung**: Liste mit Datum, Größe und Version
- **Restore-Key**: Für Konto-Wiederherstellung

### 11. Datenbank-Verwaltung 🗄️
- **Statistiken**: DB-Größe, Anzahl Einträge, Schema-Version
- **Bereinigung**: Entfernt verwaiste Einträge
- **Reset**: Komplett oder partiell (Budget/Kategorien ohne Buchungen)
- **Integritätsprüfung**: Validiert Datenbank-Konsistenz
- **Optimierung**: VACUUM für Größenreduktion

### 12. Erscheinungsmanager (Themes) 🎨
- **24+ vordefinierte Themes**: Hell, Dunkel, Solarized, Nord, Dracula u.v.m.
- **Theme-Editor**: Eigene Themes erstellen und bearbeiten
- **JSON-Farbprofile**: Import/Export zum Teilen
- **Live-Preview**: Sofortige Vorschau bei Änderungen
- **Zentrales Farbsystem**: `ui_colors.py` für konsistente Darstellung
- **Dark-Mode**: Vollständige Unterstützung über alle Dialoge

### 13. Windows-Installer 📦
- **PyInstaller**: Standalone .exe
- **Inno Setup**: Professioneller Installer mit Startmenü-Integration
- **Build-Script**: `build_windows.py` für einfaches Packaging
- **Deinstallation**: Saubere Entfernung

### 14. Update-Tool 🔄
- **Version-Check**: Prüft auf neue Versionen (GitHub)
- **Changelog**: Zeigt Änderungen der neuen Version
- **Update-Benachrichtigung**: Optional beim Start
- **Manifest-basiert**: Intelligentes Delta-Update

### 15. Weitere Features
- **Excel-Export**: Daten als .xlsx exportieren
- **Diagramme**: Donut-Charts, Balkendiagramme, Fortschrittsbalken
- **Globale Suche**: Durchsucht Buchungen, Kategorien, Budget (Strg+F)
- **Tastenkürzel**: Umfangreiche Shortcuts (F1 für Übersicht)
- **Multi-Jahr-Ansicht**: Jahresübergreifende Analysen
- **Kategorie-Manager**: Umbenennen, Verschieben, Zusammenführen, Massenbearbeitung
- **Setup-Assistent**: Geführte Ersteinrichtung
- **Multi-User**: Benutzerverwaltung mit Quick/PIN/Passwort-Sicherheit

---

## Technische Details

### Architektur (MVC)
- **Model**: `model/` — Datenbank-Zugriff, Business-Logik (14 Module)
- **View**: `views/` — Qt-Dialoge und Tabs (30+ Dateien)
- **Utils**: `utils/` — Hilfsfunktionen (Geldformatierung, i18n, Tabellen)
- **Theme**: `theme_manager.py` + `views/ui_colors.py` — Zentrales Farbsystem

### Datenbank
- **SQLite** mit automatischen Migrationen (aktuell Schema v8)
- **Backup vor Migration**: Sicherheit bei Updates
- **Foreign Keys, Unique Constraints**: Datenintegrität

### Code-Qualität (v0.4.6.0)
- **0 hardcoded setStyleSheet-Farben** (von ~30) — alle Theme-aware
- **4 absichtliche QColor("#")** (von ~50) — Kontrast/ColorPicker/Spezial
- **Einheitliche PySide6-Enums**: Vollqualifiziert durchgängig
- **Logger in allen View-Dateien**: Kein silent `except: pass`
- **format_money()**: Konsistente Geldformatierung

### Tastenkürzel (Auszug)
| Kürzel | Aktion |
|--------|--------|
| Strg+N | Schnelleingabe |
| F2 | Budget bearbeiten |
| Insert | Neue Budget-Zeile |
| Strg+F | Globale Suche |
| Strg+E | Export |
| Strg+Z | Undo |
| Strg+Shift+Z | Redo |
| F1 | Shortcut-Übersicht |

---

## Installation

### Voraussetzungen
- Python 3.11+
- PySide6

### Entwicklung
```bash
pip install PySide6
python main.py
```

### Windows
1. Installer herunterladen
2. Installer ausführen
3. Installationsverzeichnis wählen

---

## Datenschutz & Sicherheit
- **Lokal**: Alle Daten bleiben auf dem eigenen Gerät
- **Keine Cloud**: Kein automatisches Hochladen
- **Verschlüsselung**: Optionale Konto-Sicherheit (PIN/Passwort)
- **Backup**: Empfohlen in sicheren Ordner

---

## Versionsverlauf

| Version | Datum | Highlights |
|---------|-------|------------|
| 0.4.6.0 | 19.02.2026 | Architektur-Feinschliffe, MVC-Bereinigung, Import-Ordnung |
| 0.4.5.0 | 17.02.2026 | UI-Konsistenz, Theme-Integration, Dark-Mode, Code-Qualität |
| 0.4.4.0 | 16.02.2026 | Forecast/Suggestion-System (8 Bug-Fixes, 15/15 Tests) |
| 0.3.7.1 | — | Hotfixes, Stabilitätsverbesserungen |
| 0.3.6.x | — | Tags, Favoriten, Sparziele |
| 0.2.x | — | Grundgerüst, Budget, Tracking |
