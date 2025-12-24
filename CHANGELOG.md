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

--# Budgetmanager Version 0.18.0 - Theme Manager Rework

## 🎨 Hauptänderungen

### Verbesserter Theme Manager
- **JSON-basierte Profile**: Jedes Theme wird als separate JSON-Datei gespeichert
- **Speicherort**: `~/.budgetmanager/themes/`
- **Persistenz**: Einstellungen gehen nicht mehr verloren
- **7 vordefinierte Themes**: Standard Hell/Dunkel, Grün, Blau, Kontrast, Pastell

### 🐛 Behobene Probleme

#### 1. Dropdown-Problem behoben
**Problem**: Schwarze Schrift auf schwarzem Hintergrund in Dropdowns
**Lösung**: 
- Neue separate Dropdown-Farben in jedem Theme-Profil
- Explizite Styles für `QComboBox` und `QAbstractItemView`
- Farben werden pro Theme korrekt angewendet

```css
/* Neue Dropdown-Farb-Keys */
"dropdown_bg": "#ffffff",
"dropdown_text": "#111111", 
"dropdown_selection": "#2f80ed",
"dropdown_selection_text": "#ffffff",
"dropdown_border": "#d6dbe3",
```

#### 2. Typ-Colorierung beibehalten
- Einnahmen, Ausgaben, Ersparnisse werden weiterhin farblich hervorgehoben
- `type_color_helper.py` funktioniert unverändert
- Neue Methode `get_type_colors()` im ThemeManager

### 🎯 Neue Features

#### Theme-Profil Struktur
Jedes Profil enthält jetzt:
```json
{
  "name": "Standard Hell",
  "modus": "hell",
  "hintergrund_app": "#ffffff",
  "hintergrund_panel": "#f6f7f9",
  "text": "#111111",
  "akzent": "#2f80ed",
  "typ_einnahmen": "#2ecc71",
  "typ_ausgaben": "#e74c3c",
  "typ_ersparnisse": "#3498db",
  "dropdown_bg": "#ffffff",
  "dropdown_text": "#111111",
  // ... weitere Farben
}
```

#### Anpassbare Farben
Alle Farben können pro Profil individuell angepasst werden:
- Hintergrundfarben (App, Panel, Sidebar)
- Textfarben (Normal, Gedimmt)
- Akzentfarbe
- Tabellenfarben
- Auswahl-Farben
- **NEU**: Dropdown-Farben
- Typ-Farben (Einnahmen/Ausgaben/Ersparnisse)
- Negative Zahlen Farbe

### 📦 Vordefinierte Themes

1. **Standard Hell** - Klassisches helles Design, Blau
2. **Standard Dunkel** - Modernes dunkles Design, Blau
3. **Hell - Grün** - Beruhigendes Grün
4. **Dunkel - Blau** - Tiefblauer Dunkel-Modus
5. **Dunkel - Grün** - Waldgrüner Dunkel-Modus
6. **Kontrast - Schwarz/Weiß** - Maximaler Kontrast für Barrierefreiheit
7. **Pastell - Sanft** - Weiche Pastelltöne

### 🔧 API-Änderungen

#### Theme Manager Methoden
```python
# Neuer Theme Manager (vereinfachte API)
theme_manager = ThemeManager(settings)

# Profile verwalten
profiles = theme_manager.get_all_profiles()  # Liste aller Profile
profile = theme_manager.get_profile("Standard Hell")  # Einzelnes Profil
current = theme_manager.get_current_profile()  # Aktuelles Profil

# Theme anwenden
theme_manager.apply_theme(app, "Standard Dunkel")

# Typ-Farben für Tabellen
type_colors = theme_manager.get_type_colors()
negative_color = theme_manager.get_negative_color()

# Profile erstellen/bearbeiten/löschen
theme_manager.create_profile("Mein Theme", base_profile="Standard Hell")
theme_manager.update_profile("Mein Theme", updated_data)
theme_manager.delete_profile("Mein Theme")

# Export/Import
theme_manager.export_profile("Mein Theme", "mein_theme.json")
imported_name = theme_manager.import_profile("mein_theme.json")
```

#### Integration in MainWindow
```python
# In main_window.py

from theme_manager import ThemeManager

class MainWindow(QMainWindow):
    def __init__(self, ...):
        # Theme Manager initialisieren
        self.theme_manager = ThemeManager(self.settings)
        
        # Theme laden
        self.theme_manager.apply_theme()
        
    def _apply_theme(self):
        """Theme auf Fenster anwenden"""
        self.theme_manager.apply_theme()
        
        # Tabellen-Farben anwenden
        self._update_table_colors()
    
    def _update_table_colors(self):
        """Typ-Farben in Tabellen anwenden"""
        from views.type_color_helper import apply_tracking_type_colors
        
        type_colors = self.theme_manager.get_type_colors()
        negative_color = self.theme_manager.get_negative_color()
        
        # Auf alle Tabellen anwenden
        if hasattr(self, 'tracking_tab'):
            table = self.tracking_tab.get_table()
            if table:
                apply_tracking_type_colors(table, type_colors, negative_color)
```

### 📋 Migration von alter Version

#### Automatische Migration
Bei erstem Start mit Version 0.18.0:
1. Alte Einstellung `appearance_profile` wird beibehalten
2. Neue vordefinierte Profile werden erstellt
3. Wenn altes Profil nicht existiert: Fallback auf "Standard Hell"

#### Manuelle Migration (falls nötig)
```python
# Alte Profile löschen (optional)
rm -rf ~/.budgetmanager/themes/*.json

# App neu starten -> Profile werden neu erstellt
```

### 🎨 Farb-Editor (in Planung)

Zukünftige Version wird einen visuellen Farb-Editor enthalten:
- Farbwahl-Dialog für jede Farbe
- Echtzeit-Vorschau
- Einfaches Erstellen eigener Themes
- Export/Import von Themes

### 🔬 Technische Details

#### Stylesheet-Generierung
Der Theme Manager generiert ein komplettes QSS-Stylesheet:
- ~700 Zeilen CSS pro Theme
- Alle Qt-Widgets werden gestylt
- Hover/Focus/Disabled States
- Dropdown-Fix integriert

#### Dropdown-Fix Details
```css
/* Problem: Schwarzer Hintergrund, schwarze Schrift */
QComboBox QAbstractItemView {
    background-color: {dropdown_bg};  /* Explizit gesetzt */
    color: {dropdown_text};            /* Explizit gesetzt */
}

/* Jedes Item einzeln */
QComboBox QAbstractItemView::item {
    background-color: {dropdown_bg};
    color: {dropdown_text};
}

/* Selection State */
QComboBox QAbstractItemView::item:selected {
    background-color: {dropdown_sel};
    color: {dropdown_sel_text};
}
```

### 📝 Bekannte Einschränkungen

1. **Profile-Editor**: Aktuell nur programmatisch, kein GUI
2. **Validierung**: Keine Validierung von Hex-Codes im JSON
3. **Backup**: Keine automatische Sicherung bei Profil-Änderungen

### 🚀 Roadmap

#### Version 0.18.1 (geplant)
- [ ] GUI Profile-Editor
- [ ] Farb-Picker Dialog
- [ ] Echtzeit-Vorschau
- [ ] Profile duplizieren

#### Version 0.19.0 (geplant)
- [ ] Theme-Gallery mit Community-Themes
- [ ] Theme-Import aus Datei (GUI)
- [ ] Validierung von Farbwerten
- [ ] Backup/Restore von Profilen

### 🐞 Bugfixes

- ✅ Dropdown schwarze Schrift behoben
- ✅ Dropdown schwarzer Hintergrund behoben  
- ✅ Einstellungen gehen nicht mehr verloren
- ✅ Typ-Colorierung funktioniert in allen Themes
- ✅ Schriftgröße wird korrekt angewendet
- ✅ Akzentfarbe wird überall verwendet

### 📖 Dokumentation

Siehe auch:
- `THEME_MIGRATION_GUIDE.md` - Detaillierte Migrations-Anleitung
- `THEME_README.md` - Vollständige Feature-Dokumentation
- `theme_manager.py` - API-Dokumentation im Code

### 🙏 Danksagung

Theme-System entwickelt für robuste, persistente Darstellungsverwaltung.

---

**Version**: 0.18.0  
**Datum**: 24. Dezember 2024  
**Status**: Stabil, Produktionsreif-

[0.17.0]: https://github.com/yourusername/budgetmanager/compare/v0.16.0...v0.17.0
[0.16.0]: https://github.com/yourusername/budgetmanager/compare/v0.15.0...v0.16.0
