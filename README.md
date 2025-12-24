# Budgetmanager v0.16.0

Ein umfassender Budgetmanager mit erweiterten Features zur Verwaltung von Finanzen.

## Neue Features in Version 0.16.0

### 1. Typ-Filter "Alle"
- **Budget-Tab**: Anzeige aller Typen (Ausgaben, Einkommen, Ersparnisse) gleichzeitig
- **Kategorien-Tab**: Übersicht über alle Kategorien-Typen in einer Ansicht
- Gruppierte Darstellung mit Typ-Headern

### 2. Mehrfachauswahl für Kategorien
- **ExtendedSelection-Modus**: Mehrere Kategorien gleichzeitig auswählen (Strg+Klick, Shift+Klick)
- **Bulk-Edit Dialog**: Ausgewählte Kategorien gemeinsam bearbeiten
  - Fixkosten-Status für mehrere setzen
  - Wiederkehrend-Status für mehrere setzen
  - Tag für mehrere Kategorien gleichzeitig festlegen
- **Mehrfach-Löschen**: Mehrere Kategorien auf einmal entfernen

### 3. Tags/Labels System
- **Tags erstellen**: Eigene Labels für Kategorien definieren
- **Farbcodierung**: Jedem Tag eine Farbe zuweisen
- **Tag-Verwaltung**: Tags Kategorien zuordnen und entfernen
- **Filter nach Tags**: Kategorien nach Tags filtern (zukünftig)

### 4. Budgetwarnungen
- **Schwellenwerte**: Warnungen bei Überschreitung eines bestimmten Prozentsatzes (Standard: 90%)
- **Automatische Prüfung**: System prüft Budget vs. tatsächliche Ausgaben
- **Benachrichtigungen**: Warnmeldungen bei Überschreitung
- **Pro Kategorie**: Individuelle Warnungen für jede Budget-Kategorie

### 5. Favoriten-System
- **Kategorien pinnen**: Häufig genutzte Kategorien als Favoriten markieren
- **Sortierung**: Favoriten in eigener Reihenfolge
- **Schnellzugriff**: Bevorzugte Kategorien immer oben in Listen

### 6. Sparziele
- **Ziele definieren**: Namen, Zielbetrag, Frist
- **Fortschritt tracken**: Aktuellen Stand eingeben
- **Visualisierung**: Fortschrittsbalken für jedes Ziel
- **Kategorien-Verknüpfung**: Sparziele mit Budget-Kategorien verbinden
- **Automatische Synchronisation**: 
  - Bei Ersparnisse-Buchung in verknüpfter Kategorie → Sparziel wird automatisch erhöht
  - Bei Löschen der Buchung → Sparziel wird automatisch verringert
  - Bei Ändern der Buchung → Sparziel wird entsprechend angepasst
- **Manuelle Synchronisation**: Button "Mit Tracking synchronisieren" berechnet Stand neu
- **Notizen**: Zusätzliche Informationen zu jedem Ziel

### 7. Undo/Redo System
- **Operation-Stack**: Letzte 50 Aktionen werden gespeichert
- **Rückgängig**: Änderungen rückgängig machen
- **Unterstützte Operationen**: INSERT, UPDATE, DELETE auf allen Tabellen

### 8. Backup & Wiederherstellung
- **Automatische Backups**: Bei kritischen Operationen
- **Manuelles Backup**: Jederzeit Backup erstellen
- **Backup-Verwaltung**: Liste aller Backups mit Zeitstempel und Größe
- **Import/Export**: Backups exportieren und importieren
- **Restore**: Datenbank aus Backup wiederherstellen
- **Sicherheits-Backup**: Vor Restore automatisches Backup

### 9. Datenbank-Reset
- **Kompletter Reset**: Alle Daten auf Standardwerte zurücksetzen
- **Sicherheits-Backup**: Automatisches Backup vor Reset
- **Doppelte Bestätigung**: Versehentliches Löschen verhindern
- **Tabellen betroffen**: 
  - tracking
  - budget
  - categories
  - favorites
  - savings_goals
  - budget_warnings
  - undo_stack
  - tags
  - category_tags
  - theme_profiles

### 10. Erscheinungsprofile (Theme Manager)
- **Vordefinierte Profile**:
  - Standard
  - Hell
  - Dunkel
  - Blau
  - Grün
- **Eigene Profile**: Benutzerdefinierte Farbschemata erstellen
- **Farbauswahl**: 
  - Primärfarbe
  - Sekundärfarbe
  - Hintergrundfarbe
  - Textfarbe
  - Akzentfarbe
- **Live-Vorschau**: Farben vor dem Anwenden sehen
- **Profil-Verwaltung**: Speichern, Laden, Löschen von Profilen

## Technische Details

### Neue Datenbank-Tabellen

```sql
-- Tags
CREATE TABLE tags (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    color TEXT DEFAULT '#3498db'
);

-- Kategorie-Tags Zuordnung
CREATE TABLE category_tags (
    category_id INTEGER,
    tag_id INTEGER,
    PRIMARY KEY (category_id, tag_id)
);

-- Budgetwarnungen
CREATE TABLE budget_warnings (
    id INTEGER PRIMARY KEY,
    year INTEGER,
    month INTEGER,
    typ TEXT,
    category TEXT,
    threshold_percent INTEGER DEFAULT 90,
    enabled INTEGER DEFAULT 1,
    UNIQUE(year, month, typ, category)
);

-- Favoriten
CREATE TABLE favorites (
    id INTEGER PRIMARY KEY,
    typ TEXT,
    category TEXT,
    sort_order INTEGER DEFAULT 0,
    UNIQUE(typ, category)
);

-- Sparziele
CREATE TABLE savings_goals (
    id INTEGER PRIMARY KEY,
    name TEXT,
    target_amount REAL,
    current_amount REAL DEFAULT 0,
    deadline TEXT,
    category TEXT,
    notes TEXT,
    created_date TEXT
);

-- Undo/Redo Stack
CREATE TABLE undo_stack (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    table_name TEXT,
    operation TEXT,
    old_data TEXT,
    new_data TEXT
);

-- Theme-Profile
CREATE TABLE theme_profiles (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    settings TEXT
);
```

### Neue Model-Dateien
- `model/tags_model.py` - Tags-Verwaltung
- `model/favorites_model.py` - Favoriten-System
- `model/savings_goals_model.py` - Sparziele
- `model/budget_warnings_model.py` - Budgetwarnungen
- `model/undo_redo_model.py` - Undo/Redo System

### Neue Dialog-Dateien
- `views/savings_goals_dialog.py` - Sparziele-Verwaltung
- `views/backup_restore_dialog.py` - Backup & Restore
- `views/theme_profiles_dialog.py` - Theme-Manager

## Installation

### Voraussetzungen
```bash
pip install PySide6
```

### Start
```bash
python main.py
```

## Nutzung

### Mehrfachauswahl in Kategorien
1. Kategorien-Tab öffnen
2. Mehrere Kategorien auswählen:
   - **Strg+Klick**: Einzelne Kategorien hinzufügen/entfernen
   - **Shift+Klick**: Bereich auswählen
3. "Mehrfach bearbeiten..." klicken
4. Gewünschte Änderungen vornehmen

### Sparziele
1. Extras → Sparziele...
2. "Neues Ziel" klicken
3. Ziel definieren (Name, Betrag, Frist)
4. Fortschritt hinzufügen über "Fortschritt hinzufügen"

### Backup erstellen
1. Extras → Backup & Wiederherstellung...
2. "Backup erstellen" klicken
3. Backups werden in `~/BudgetManager_Backups/` gespeichert

### Theme-Profile
1. Ansicht → Theme → Erscheinungsprofile...
2. "Neues Profil" für eigenes Farbschema
3. Farben auswählen und speichern
4. "Anwenden" um Profil zu aktivieren

## Backup-Strategie

Das System erstellt automatisch Backups:
- Vor Datenbank-Wiederherstellung: `budgetmanager_before_restore_TIMESTAMP.db`
- Vor Datenbank-Reset: `budgetmanager_before_reset_TIMESTAMP.db`
- Manuelle Backups: `budgetmanager_backup_TIMESTAMP.db`

## Tastenkürzel (neu)

- **Strg+N**: Schnelleingabe
- **Strg+F**: Globale Suche
- **Strg+E**: Export
- **Strg+S**: Speichern
- **F1**: Hilfe/Tastenkürzel
- **F5**: Aktualisieren

## Zukünftige Features (Roadmap)

Folgende Features sind geplant, aber noch nicht implementiert:

### Wiederkehrende Transaktionen (geplant)
- Automatische Buchungen mit Sollbuchungsdatum
- Fixkosten-Check: Prüfung ob Buchung bereits im Monat erfolgt
- Optional: Liste nicht gebuchter Fixkosten mit Auswahl

### Update-Tool (geplant)
- Automatische Update-Prüfung
- Download neuer Versionen
- Migrations-Assistent

### Windows Installer (geplant)
- MSI/EXE Installer
- Start-Menü Integration
- Auto-Start Option

## Lizenz

Freie Nutzung für private und kommerzielle Zwecke.

## Changelog

### Version 0.16.0 (Dezember 2024)
- ✅ Typ-Filter "Alle" in Budget und Kategorien
- ✅ Mehrfachauswahl für Kategorien
- ✅ Bulk-Edit Dialog
- ✅ Tags/Labels System (Grundlage)
- ✅ Budgetwarnungen
- ✅ Favoriten-System
- ✅ Sparziele mit Tracking
- ✅ Undo/Redo System
- ✅ Backup & Wiederherstellung
- ✅ Datenbank-Reset
- ✅ Erscheinungsprofile (Theme-Manager)

### Version 0.15.2 (vorherige Version)
- Fixkosten und wiederkehrende Buchungen
- Verbesserte Kategorien-Verwaltung
- Inline-Editing

## Automatische Datenbank-Migration

**Von älteren Versionen (v0.15.x) auf v0.16.0:**

Die Datenbank wird beim ersten Start **vollautomatisch** aktualisiert:

✅ **Automatisches Backup** vor Migration  
✅ **Schrittweise Migration** über alle Versionen (v0→v1→v2→v3→v4)  
✅ **Info-Dialog** zeigt durchgeführte Änderungen  
✅ **Alle Daten bleiben erhalten** - kein Datenverlust  
✅ **Keine manuellen Schritte** erforderlich  

**Backup-Speicherort:** `~/BudgetManager_Backups/budgetmanager_pre_migration_TIMESTAMP.db`

**Was wird aktualisiert:**
- Neue Tabellen: `tags`, `favorites`, `savings_goals`, `budget_warnings`, `undo_stack`, `theme_profiles`
- Schema-Version wird gesetzt (Version 4)
- Alle existierenden Kategorien, Budget-Einträge und Buchungen bleiben unverändert

**Sicherheitsmaßnahmen:**
- Versionskontrolle verhindert doppelte Migration
- Idempotente Operationen (können mehrfach ausgeführt werden)
- Detaillierte Fehlerbehandlung
- Migrations-Info im Menü: Datei → Datenbank-Info

**Bei Problemen:**
```bash
# Backup wiederherstellen
cp ~/BudgetManager_Backups/latest_backup.db budgetmanager.db
```

Siehe [MIGRATIONS.md](MIGRATIONS.md) für technische Details und Troubleshooting.

## Konfigurierbare Pfade (NEU)

**Datenbank-Speicherort und Backup-Ordner frei wählbar:**

- **Menü → Datei → Einstellungen → Dateipfade**
- Datenbank-Pfad konfigurieren (Standard: `budgetmanager.db`)
- Backup-Ordner konfigurieren (Standard: `~/BudgetManager_Backups`)

**Anwendungsfälle:**
- Mehrere Datenbanken verwalten (privat/geschäftlich)
- Cloud-Synchronisation (Dropbox, OneDrive, etc.)
- Externe Festplatte für Portabilität
- Netzlaufwerk für zentrale Speicherung
- Automatische Backups auf NAS

**Wichtig:** Neustart erforderlich nach Pfad-Änderung!

Siehe [PFAD_EINSTELLUNGEN.md](PFAD_EINSTELLUNGEN.md) für Details und Anwendungsbeispiele.
