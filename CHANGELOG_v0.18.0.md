# Budgetmanager Version 0.18.0 - Theme Manager Rework

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
**Status**: Stabil, Produktionsreif
