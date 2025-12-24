# Changelog - Budgetmanager

## Version 0.16.0 (Dezember 2024)

### Neue Features

#### Typ-Filter "Alle"
- Budget-Tab und Kategorien-Tab unterstützen jetzt Filter "Alle"
- Zeigt alle Typen (Ausgaben, Einkommen, Ersparnisse) gleichzeitig an
- Gruppierte Darstellung mit Typ-Headern
- Typ-Information wird in Zellen gespeichert (UserRole+10)

#### Mehrfachauswahl für Kategorien
- ExtendedSelection-Modus aktiviert (Strg+Klick, Shift+Klick)
- Neuer Button "Mehrfach bearbeiten..."
- Bulk-Edit Dialog:
  - Fixkosten für mehrere Kategorien setzen
  - Wiederkehrend für mehrere Kategorien setzen
  - Tag für alle ausgewählten Kategorien festlegen
- Mehrfach-Löschen mit Bestätigungsdialog

#### Tags/Labels System
- Neue Tabelle `tags` für Label-Verwaltung
- Neue Tabelle `category_tags` für Zuordnung
- TagsModel mit CRUD-Operationen
- Farbcodierung für Tags
- Grundlage für zukünftiges Tag-Filtering

#### Budgetwarnungen
- Neue Tabelle `budget_warnings`
- BudgetWarningsModel zum Verwalten von Warnungen
- Schwellenwerte pro Kategorie (Standard: 90%)
- Automatische Prüfung: Budget vs. Ist-Ausgaben
- `check_warnings()` Methode gibt überschrittene Budgets zurück

#### Favoriten-System
- Neue Tabelle `favorites`
- FavoritesModel mit Sortierung
- Kategorien als Favoriten markieren
- Reihenfolge über `sort_order` anpassbar
- Methoden: `move_up()`, `move_down()`

#### Sparziele
- Neue Tabelle `savings_goals`
- SavingsGoalsModel zum Verwalten
- SavingsGoalsDialog mit:
  - Tabelle aller Ziele
  - Progressbars für Fortschritt
  - EditGoalDialog zum Erstellen/Bearbeiten
  - AddProgressDialog zum Hinzufügen von Fortschritt
  - **NEU: Sync-Button** für manuelle Synchronisation
- Verknüpfung mit Budget-Kategorien möglich
- **Automatische Synchronisation mit Tracking:**
  - Bei Ersparnisse-Buchung: Sparziel wird automatisch erhöht
  - Bei Löschen: Sparziel wird automatisch verringert
  - Bei Ändern: Sparziel wird entsprechend angepasst
  - Methoden: `_sync_savings_goals_add()`, `_sync_savings_goals_remove()`
- Methode `sync_with_tracking()` zur manuellen Neuberechnung
- Methode `recalculate_all()` zur Neuberechnung aller Ziele
- Deadline und Notizen

#### Undo/Redo System
- Neue Tabelle `undo_stack`
- UndoRedoModel zum Aufzeichnen von Operationen
- Stack-Größe: 50 Operationen
- `record_operation()` für INSERT, UPDATE, DELETE
- `undo_last()` macht letzte Operation rückgängig
- Speichert alte und neue Daten als JSON

#### Backup & Wiederherstellung
- BackupRestoreDialog mit vollständiger Backup-Verwaltung
- Backup-Ordner: `~/BudgetManager_Backups/`
- Features:
  - Backup erstellen
  - Backup wiederherstellen (mit Auto-Backup vorher)
  - Backup exportieren
  - Backup importieren
  - Backup löschen
  - Backup-Liste mit Größe und Datum

#### Datenbank-Reset
- Funktion zum Zurücksetzen der Datenbank
- Löscht alle Daten aus allen Tabellen
- Doppelte Sicherheitsabfrage
- Automatisches Backup vor Reset
- Betroffen: tracking, budget, categories, favorites, savings_goals, 
  budget_warnings, undo_stack, tags, category_tags, theme_profiles

#### Erscheinungsprofile (Theme-Manager)
- Neue Tabelle `theme_profiles`
- ThemeProfilesDialog zur Verwaltung
- Vordefinierte Profile:
  - Standard
  - Hell
  - Dunkel
  - Blau
  - Grün
- CreateProfileDialog für eigene Farbschemata
- Farbeinstellungen:
  - Primärfarbe
  - Sekundärfarbe
  - Hintergrundfarbe
  - Textfarbe
  - Akzentfarbe
- Live-Vorschau der Farben
- Import/Export vorbereitet

### Datenbank-Änderungen

#### Neue Tabellen
```sql
tags
category_tags
budget_warnings
favorites
savings_goals
undo_stack
theme_profiles
```

#### Neue Indizes
```sql
idx_undo_timestamp ON undo_stack(timestamp)
```

### UI-Verbesserungen

#### Budget-Tab
- ComboBox erweitert: ["Alle", "Ausgaben", "Einkommen", "Ersparnisse"]
- `load()` Methode überarbeitet für Typ-Filter
- Typ-Header beim "Alle"-Filter
- Einrückung bei Kategorien im "Alle"-Modus

#### Kategorien-Tab
- SelectionMode auf ExtendedSelection geändert
- Neuer Button "Mehrfach bearbeiten..."
- `refresh()` Methode für "Alle"-Filter
- `delete_selected()` für Mehrfachauswahl angepasst
- `bulk_edit_dialog()` Methode hinzugefügt

#### Main Window
- Version auf 0.16.0 aktualisiert
- Neue Menüpunkte:
  - Extras → Sparziele...
  - Extras → Backup & Wiederherstellung...
  - Ansicht → Theme → Erscheinungsprofile...
- Neue Methoden:
  - `_show_savings_goals()`
  - `_show_backup_restore()`
  - `_show_theme_profiles()`

### Neue Dateien

#### Models
- `model/tags_model.py`
- `model/favorites_model.py`
- `model/savings_goals_model.py`
- `model/budget_warnings_model.py`
- `model/undo_redo_model.py`

#### Views
- `views/savings_goals_dialog.py`
- `views/backup_restore_dialog.py`
- `views/theme_profiles_dialog.py`

#### Dokumentation
- `README.md` - Umfassende Dokumentation
- `CHANGELOG.md` - Diese Datei

### Technische Verbesserungen

- Typ-Information in UserRole+10 gespeichert für "Alle"-Filter
- JSON-Serialisierung für Undo-Stack
- Pfad-Handling mit pathlib
- Robuste Error-Handling bei Backup-Operationen
- Sicherheits-Backups bei kritischen Operationen
- **Tracking Model erweitert:**
  - `add()` ruft automatisch `_sync_savings_goals_add()` auf
  - `update()` synchronisiert alte und neue Werte
  - `delete()` ruft automatisch `_sync_savings_goals_remove()` auf
  - Hilfsmethoden für Sparziel-Synchronisation

### Bekannte Einschränkungen

- Tags sind implementiert, aber noch nicht in UI integriert
- Budgetwarnungen sind im Model, aber noch ohne automatische Benachrichtigung
- Undo/Redo ist vorbereitet, aber noch nicht an UI gebunden
- Wiederkehrende Transaktionen noch nicht implementiert
- Update-Tool noch nicht implementiert

### Migration

Die Datenbank wird automatisch beim Start aktualisiert.
Keine manuellen Schritte erforderlich.

Alte Datenbanken von v0.15.x sind kompatibel und werden automatisch erweitert.

### Kompatibilität

- Python 3.11+
- PySide6 6.5+
- SQLite 3

---

## Version 0.15.2 (November 2024)

### Features
- Fixkosten und wiederkehrende Buchungen
- Kategorien-Verwaltung mit Inline-Editing
- Tag-Feld für wiederkehrende Buchungen (1-31)

### Bekannte Probleme
- Keine Mehrfachauswahl für Kategorien
- Kein "Alle"-Filter

---

## Version 0.15.0 (November 2024)

### Initiale Features
- Budget-Planung
- Tracking
- Kategorien-Verwaltung
- Overview-Tab
- Themes (Hell/Dunkel)
- Export-Funktion
