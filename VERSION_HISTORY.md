# Budgetmanager - Versions-Historie

## Version 0.18.1 (24.12.2024) - Theme-System Overhaul

### 🎨 Neue Features
- **Standard-Themes editierbar:** Alle 15 vordefinierten Themes können jetzt direkt bearbeitet werden
- **"Auf Standard zurücksetzen" Funktion:** Standard-Themes können auf Originalwerte zurückgesetzt werden
- **8 neue augenfreundliche Themes:**
  - Solarized (Hell & Dunkel)
  - Nord Dunkel
  - Gruvbox (Hell & Dunkel)
  - Monokai Dunkel
  - Dracula Dunkel
  - Warm Hell
  - Ocean Dunkel

### 🐛 Behobene Fehler
- **Dropdown-Styling:** Dropdowns hatten schwarzen Hintergrund/Text - jetzt vollständig styled
- **Theme-Speicherung:** OK-Button speichert jetzt auch das gewählte Theme (nicht nur Apply)
- **Profile-Anzeige:** Alle Profile werden korrekt im Dropdown angezeigt
- **Überschriften-Auswahl:** Überschriften im Dropdown sind nicht mehr auswählbar

### 🔧 Technische Verbesserungen
- Theme-Änderungen an Standard-Themes werden persistent in JSON gespeichert
- Verbesserte Profile-Verwaltung im Settings-Dialog
- Automatische Profilauswahl beim Öffnen der Einstellungen
- Dropdown-spezifische Farben für alle Themes definiert

---

## Version 0.18.0 (Dezember 2024) - Design-System

### 🎨 Neue Features
- **Erscheinungsmanager (Theme-System):**
  - 7 vordefinierte Themes (Hell & Dunkel Varianten)
  - Unbegrenzt eigene Themes erstellen
  - Vollständige Farb-Kontrolle
  - Export/Import von Themes
  - Echtzeit-Vorschau

### 🔧 Technische Features
- JSON-basiertes Theme-System
- Zentrale Theme-Verwaltung (`theme_manager.py`)
- Profile-Manager Dialog
- Stylesheet-Generator

---

## Version 0.17.0 (November 2024) - Automatisierung

### ⚡ Neue Features
- **Wiederkehrende Transaktionen:**
  - Automatische Buchungen konfigurierbar
  - Soll-Buchungsdatum je Eintrag
  - Flexible Wiederholungsintervalle

- **Fixkosten-Check:**
  - Prüfung ob Fixkosten gebucht wurden
  - Optional: Liste fehlender Buchungen
  - Quick-Booking für fehlende Fixkosten

- **Sparziele:**
  - Sparziele definieren
  - Fortschritt tracken
  - Automatische Synchronisation

- **Backup/Wiederherstellung:**
  - Automatisches Backup
  - Manuelle Backups
  - Wiederherstellungsfunktion
  - Backup-Metadaten

### 🔧 Technische Features
- Models für alle neuen Features
- Datenbank-Migrations-System
- Erweiterte Budget-Warnungen (Model)
- Tags/Labels (Model vorhanden)
- Undo/Redo (Model vorhanden)
- Favoriten (Model vorhanden)

---

## Version 0.16.0 (Oktober 2024) - Performance

### ⚡ Performance-Verbesserungen
- Optimierte Datenbankabfragen
- Lazy-Loading für große Datensätze
- Caching-System für häufige Abfragen
- Schnellere Tabellen-Aktualisierung

### 🐛 Behobene Fehler
- Speicherlecks bei langen Sessions
- Tabellen-Sortierung korrigiert
- Export-Fehler bei großen Datenmengen

---

## Version 0.15.2 (September 2024) - Bugfixes

### 🐛 Behobene Fehler
- Absturz beim Bearbeiten von Kategorien
- Falsche Summenberechnung in Übersicht
- Fehler beim Jahreswechsel
- Import-Dialog Probleme

### 🔧 Verbesserungen
- Verbesserte Fehlerbehandlung
- Bessere Log-Ausgaben
- Stabilere Datenbankoperationen

---

## Version 0.15.0 (August 2024) - UI Redesign

### 🎨 UI-Verbesserungen
- Modernisiertes Design
- Verbesserte Navigation
- Überarbeitete Icons
- Responsive Dialoge

### 🔧 Neue Features
- Quick-Add Dialog
- Global Search
- Keyboard Shortcuts
- Status Bar mit Informationen

---

## Version 0.14.0 (Juli 2024) - Export/Import

### 📊 Neue Features
- Excel-Export erweitert
- CSV-Import
- PDF-Berichte
- Datenbank-Export

### 🔧 Verbesserungen
- Bessere Excel-Formatierung
- Flexible Import-Optionen
- Konfigurierbare Berichte

---

## Version 0.13.0 (Juni 2024) - Kategorien

### 📁 Kategorie-System
- Unbegrenzte Kategorien
- Kategorie-Icons
- Kategorie-Farben
- Unterkategorien (geplant)

### 🔧 Verbesserungen
- Drag & Drop für Kategorien
- Batch-Operationen
- Kategorie-Statistiken

---

## Version 0.12.0 (Mai 2024) - Tracking

### 📊 Tracking-Features
- Erweiterte Filter
- Zeitraum-Auswahl
- Typ-Filter (Einnahmen/Ausgaben)
- Summen-Anzeige

### 🔧 Verbesserungen
- Schnellere Suche
- Mehrfach-Auswahl
- Context-Menü

---

## Version 0.11.0 (April 2024) - Budget-Verwaltung

### 💰 Budget-Features
- Monatsbudgets pro Kategorie
- Jahresbudgets
- Budget-Vorschläge
- Budget-Kopier-Funktion

### 🔧 Verbesserungen
- Visuelle Budget-Anzeige
- Prozentualer Fortschritt
- Warnungen bei Überschreitung

---

## Version 0.10.0 (März 2024) - Erste Release

### 🎉 Initiale Features
- Tracking von Einnahmen/Ausgaben
- Kategorie-System
- Budget-Verwaltung
- Monatliche/Jährliche Übersichten
- SQLite-Datenbank
- PySide6 UI

---

## Geplante Versionen

### Version 0.19.0 (Q1 2025) - Warnungen & Tags
- [ ] Budgetwarnungen vervollständigen
- [ ] Tags/Labels UI
- [ ] Undo/Redo UI & Shortcuts
- [ ] Favoriten UI

### Version 0.20.0 (Q2 2025) - Tools
- [ ] Datenbank-Management Tools
- [ ] Windows Installer
- [ ] Update-System
- [ ] Automatische Backups verbessert

### Version 1.0.0 (Q4 2025) - Stable Release
- [ ] Alle geplanten Features
- [ ] Umfangreiche Tests
- [ ] Dokumentation vervollständigt
- [ ] Marketing & Release

---

## Entwicklungs-Statistiken

### Codebase
- **Python-Dateien:** ~40
- **Zeilen Code:** ~15,000
- **Tests:** In Entwicklung
- **Dokumentation:** Umfangreich

### Technologie-Stack
- **Framework:** PySide6 (Qt for Python)
- **Datenbank:** SQLite 3
- **Sprache:** Python 3.11+
- **Build:** PyInstaller / Inno Setup

### Community
- **Contributors:** 1 (Hauptentwickler)
- **Issues:** GitHub
- **License:** [Lizenz einfügen]

---

## Upgrade-Pfad

### Von 0.18.0 zu 0.18.1
```bash
# Backup erstellen
cp -r ~/.budgetmanager ~/.budgetmanager_backup

# Neue Dateien kopieren
cp theme_manager.py [APP_DIR]/
cp settings_dialog.py [APP_DIR]/
cp views/appearance_profiles_dialog.py [APP_DIR]/views/

# Fertig! Keine Datenbank-Migration nötig
```

### Von 0.17.0 zu 0.18.0
- Automatische Datenbank-Migration
- Themes werden automatisch initialisiert
- Settings werden migriert

### Von 0.16.0 zu 0.17.0
- Datenbank-Schema Update (automatisch)
- Neue Tabellen werden erstellt
- Bestehende Daten bleiben erhalten

---

## Breaking Changes

### Version 0.18.1
- **Keine** - Vollständig abwärtskompatibel

### Version 0.18.0
- Settings-Format erweitert (abwärtskompatibel)
- Theme-System hinzugefügt (optional)

### Version 0.17.0
- Datenbank-Schema erweitert (Migration automatisch)
- Settings-Keys erweitert (Defaults vorhanden)

---

## Deprecations

### Version 0.18.0
- ⚠️ Alte Settings-Keys werden noch unterstützt, aber deprecated
  - `theme` → Verwende `active_design_profile`

### Geplante Deprecations (v0.20.0)
- Alte Export-Formate (Excel 97)
- Legacy-Datenbank-Format

---

## Danksagungen

### Contributors
- Christian - Hauptentwickler
- Claude (Anthropic) - Code-Assistenz & Dokumentation

### Inspiration
- YNAB (You Need A Budget)
- GnuCash
- Mint

### Technologie
- Qt/PySide6 Team
- Python Community
- SQLite Team

---

**Stand:** 24.12.2024  
**Aktuell:** Version 0.18.1  
**Lizenz:** [Lizenz einfügen]
