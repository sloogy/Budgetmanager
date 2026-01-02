# Theme-System Dokumentation - Budgetmanager v0.18.1

## Übersicht

Das Theme-System erlaubt vollständige Anpassung der Benutzeroberfläche mit:
- ✅ 15 vordefinierte Themes (alle editierbar!)
- ✅ Unbegrenzt eigene Themes erstellen
- ✅ Import/Export von Themes
- ✅ Echtzeit-Vorschau
- ✅ Standard-Themes auf Original zurücksetzen

## Wichtige Änderung: Standard-Themes sind jetzt editierbar!

### Vorher (v0.18.0):
- Standard-Themes konnten **nicht** bearbeitet werden
- Nur duplizieren und dann bearbeiten möglich
- Änderungen gingen beim Update verloren

### Jetzt (v0.18.1):
- ✨ **Standard-Themes können direkt bearbeitet werden**
- Änderungen werden in `~/.budgetmanager/themes/` gespeichert
- Bei Updates bleiben Ihre Anpassungen erhalten
- "Auf Standard zurücksetzen" Button zum Wiederherstellen der Originalwerte

## Verwendung

### Theme auswählen
1. **Einstellungen** öffnen (Menü → Einstellungen oder Strg+,)
2. **Darstellung** Tab auswählen
3. **Design-Profil** im Dropdown wählen
4. **Apply** für Vorschau oder **OK** zum Speichern

### Standard-Theme anpassen
1. In Einstellungen → Darstellung → **"Profile verwalten..."**
2. Standard-Theme aus der Liste wählen (z.B. "Solarized - Dunkel")
3. Farben nach Belieben ändern
4. **Änderungen sofort anwenden** ist aktiv → Vorschau in Echtzeit
5. Fenster schließen → Änderungen werden automatisch gespeichert

### Standard-Theme zurücksetzen
1. In Einstellungen → Darstellung → **"Profile verwalten..."**
2. Standard-Theme wählen
3. **"Auf Standard zurücksetzen"** Button klicken
4. Bestätigen → Theme wird auf Originalwerte zurückgesetzt

### Eigenes Theme erstellen
1. In Einstellungen → Darstellung → **"Profile verwalten..."**
2. **"Neu..."** klicken
3. Namen eingeben
4. Farben anpassen
5. **"Profil anwenden"** zum Testen

### Theme duplizieren
1. Bestehendes Theme wählen
2. **"Duplizieren"** klicken
3. Neuen Namen eingeben
4. Kopie anpassen

## Datei-Struktur

### Theme-Dateien
```
~/.budgetmanager/themes/
├── standard_hell.json          # Standard Hell (editierbar!)
├── standard_dunkel.json        # Standard Dunkel (editierbar!)
├── solarized_hell.json         # Solarized Hell (editierbar!)
├── nord_dunkel.json            # Nord Dunkel (editierbar!)
├── mein_eigenes_theme.json     # Eigenes Theme
└── ...
```

### Theme-Datei Format (JSON)
```json
{
  "name": "Mein Theme",
  "modus": "dunkel",
  "hintergrund_app": "#1e1e1e",
  "hintergrund_panel": "#2d2d2d",
  "hintergrund_seitenleiste": "#252525",
  "sidebar_panel_bg": "#2a2a2a",
  "filter_panel_bg": "#2d2d2d",
  "text": "#e0e0e0",
  "text_gedimmt": "#aaaaaa",
  "akzent": "#0078d4",
  "tabelle_hintergrund": "#1e1e1e",
  "tabelle_alt": "#252525",
  "tabelle_header": "#2d2d2d",
  "tabelle_gitter": "#3d3d3d",
  "auswahl_hintergrund": "#0078d4",
  "auswahl_text": "#ffffff",
  "negativ_text": "#ff6b6b",
  "typ_einnahmen": "#4caf50",
  "typ_ausgaben": "#f44336",
  "typ_ersparnisse": "#2196f3",
  "schriftgroesse": 10,
  "dropdown_bg": "#2d2d2d",
  "dropdown_text": "#e0e0e0",
  "dropdown_selection": "#0078d4",
  "dropdown_selection_text": "#ffffff",
  "dropdown_border": "#3d3d3d"
}
```

## Farb-Definitionen

### Pflicht-Felder (müssen vorhanden sein):

| Feld | Beschreibung | Beispiel |
|------|--------------|----------|
| `modus` | Theme-Modus | "hell" oder "dunkel" |
| `hintergrund_app` | Hauptfenster-Hintergrund | "#ffffff" |
| `hintergrund_panel` | Panel-Hintergrund | "#f6f7f9" |
| `hintergrund_seitenleiste` | Seitenleiste-Hintergrund | "#f0f2f5" |
| `text` | Haupttext-Farbe | "#111111" |
| `text_gedimmt` | Sekundärtext-Farbe | "#444444" |
| `akzent` | Akzent-Farbe (Buttons, Links) | "#2f80ed" |
| `tabelle_hintergrund` | Tabellen-Hintergrund | "#ffffff" |
| `tabelle_alt` | Alternating Rows | "#f7f9fc" |
| `tabelle_header` | Tabellen-Kopf | "#eef2f7" |
| `tabelle_gitter` | Tabellen-Linien | "#d6dbe3" |
| `auswahl_hintergrund` | Auswahl-Hintergrund | "#2f80ed" |
| `auswahl_text` | Auswahl-Text | "#ffffff" |
| `negativ_text` | Negative Zahlen | "#e74c3c" |
| `typ_einnahmen` | Einnahmen-Farbe | "#2ecc71" |
| `typ_ausgaben` | Ausgaben-Farbe | "#e74c3c" |
| `typ_ersparnisse` | Ersparnisse-Farbe | "#3498db" |
| `schriftgroesse` | Schriftgröße (pt) | 10 |

### Optional-Felder (mit Fallback):

| Feld | Beschreibung | Fallback |
|------|--------------|----------|
| `sidebar_panel_bg` | Sidebar-Panel-BG | hintergrund_seitenleiste |
| `filter_panel_bg` | Filter-Panel-BG | hintergrund_panel |
| `dropdown_bg` | Dropdown-Hintergrund | hintergrund_panel |
| `dropdown_text` | Dropdown-Text | text |
| `dropdown_selection` | Dropdown-Auswahl-BG | akzent |
| `dropdown_selection_text` | Dropdown-Auswahl-Text | "#ffffff" |
| `dropdown_border` | Dropdown-Rahmen | tabelle_gitter |

## Verfügbare Standard-Themes

### Helle Themes
1. **Standard Hell** - Modernes, helles Design
2. **Solarized Hell** - Augenfreundlich, warme Töne
3. **Gruvbox Hell** - Retro, erdige Farben
4. **Hell - Grün** - Frisch, natürlich
5. **Kontrast Schwarz/Weiß** - Maximale Lesbarkeit
6. **Pastell - Sanft** - Weich, dezente Farben
7. **Warm Hell** - Gemütlich, orange Akzente

### Dunkle Themes
1. **Standard Dunkel** - Klassisch, ausgewogen
2. **Solarized Dunkel** - Augenfreundlich, reduzierter Kontrast
3. **Nord Dunkel** - Kühle, nordische Töne
4. **Gruvbox Dunkel** - Warm, erdige Farben
5. **Dunkel - Blau** - Tief, ozeanisch
6. **Dunkel - Grün** - Beruhigend, natürlich
7. **Monokai Dunkel** - Editor-klassisch
8. **Dracula Dunkel** - Modern, lebendige Farben
9. **Ocean Dunkel** - Tief, meeresblau

## Technische Details

### Theme Manager (theme_manager.py)

#### Initialisierung
```python
from theme_manager import ThemeManager
from settings import Settings

settings = Settings()
theme_manager = ThemeManager(settings)
```

#### Theme anwenden
```python
# Nach Profilname
theme_manager.apply_theme(profile_name="Solarized - Dunkel")

# Oder automatisch aktuelles Profil
theme_manager.apply_theme()
```

#### Profil laden
```python
profile = theme_manager.get_current_profile()
colors = theme_manager.get_type_colors(profile)
```

#### Alle Profile abrufen
```python
all_profiles = theme_manager.get_all_profiles()
# Gibt Liste von Profilnamen zurück
```

#### Standard-Profile
```python
predefined = ThemeManager.get_predefined_profiles()
# Gibt Liste der vordefinierten Profilnamen zurück
```

### Settings Dialog Integration

```python
from settings_dialog import SettingsDialog

dlg = SettingsDialog(settings, parent=self, app_version="0.18.1")
if dlg.exec():
    new_settings = dlg.get_settings()
    # Settings anwenden
```

### Appearance Profiles Dialog

```python
from views.appearance_profiles_dialog import AppearanceProfilesDialog

dlg = AppearanceProfilesDialog(parent=self, settings=settings)
if dlg.exec():
    # Profile wurden evtl. geändert
    self._reload_themes()
```

## Häufige Anwendungsfälle

### 1. Standard-Theme leicht anpassen
**Szenario:** Solarized Dunkel gefällt, aber Akzentfarbe soll grün sein

**Lösung:**
1. Profile verwalten → "Solarized - Dunkel" wählen
2. "Akzent" Farbe auf Grün ändern (z.B. #27ae60)
3. Fertig! Änderung wird automatisch gespeichert

### 2. Eigene Farbpalette erstellen
**Szenario:** Firmen-CI mit spezifischen Farben

**Lösung:**
1. "Neu..." → Namen eingeben (z.B. "Firmen-Theme")
2. Alle Farben nach CI anpassen
3. Export → JSON-Datei für Kollegen

### 3. Themes zwischen Rechnern synchronisieren
**Szenario:** Gleiches Theme auf mehreren PCs

**Lösung:**
1. Theme exportieren (JSON)
2. JSON in Cloud (Dropbox, etc.)
3. Auf anderem PC importieren

### 4. Verschiedene Themes für Tag/Nacht
**Szenario:** Hell bei Tag, Dunkel bei Nacht

**Lösung:**
1. Zwei Themes erstellen/anpassen
2. In Einstellungen schnell wechseln
3. (Zukünftig: Automatischer Wechsel geplant)

## Best Practices

### Farb-Kontrast
- **Hell auf Hell vermeiden** - Text muss lesbar sein
- **WCAG 2.0** - Mindestens 4.5:1 Kontrast für normalen Text
- **Test-Tools** - [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)

### Theme-Namen
- **Beschreibend** - "Warm Orange Hell" statt "Theme 1"
- **Konsistent** - "Dunkel - X" für dunkle Themes
- **Keine Sonderzeichen** - Dateinamen-kompatibel

### Backup
- **Vor großen Änderungen** - Theme exportieren
- **Regelmäßig** - Eigene Themes sichern
- **Cloud-Sync** - Theme-Ordner in Cloud

## Fehlerbehebung

### Theme wird nicht angewendet
**Problem:** Nach Auswahl ändert sich nichts

**Lösung:**
1. "Apply" statt nur "OK" drücken
2. Cache leeren: `rm -rf ~/.budgetmanager/cache/`
3. Anwendung neu starten

### Dropdown ist schwarz/unleserlich
**Problem:** Dropdown-Hintergrund schwarz, Text schwarz

**Lösung:**
1. Theme-Manager öffnen
2. Dropdown-Farben prüfen:
   - `dropdown_bg` ≠ `dropdown_text`
   - `dropdown_selection` ≠ `dropdown_selection_text`
3. Falls fehlend: Theme auf Standard zurücksetzen

### Theme-Datei beschädigt
**Problem:** Theme lädt nicht, Fehler in Konsole

**Lösung:**
1. JSON-Datei mit Editor öffnen
2. Syntax prüfen (alle Kommata, Klammern)
3. Oder: Theme löschen und neu erstellen

### Standard-Theme versehentlich geändert
**Problem:** Standard-Theme sieht falsch aus

**Lösung:**
1. Profile verwalten
2. Standard-Theme wählen
3. "Auf Standard zurücksetzen" klicken

## Migration von v0.18.0

### Was ändert sich?
- **Nichts!** Bestehende Themes funktionieren weiter
- **Bonus:** Standard-Themes können jetzt bearbeitet werden
- **Backup:** Alte Themes bleiben erhalten

### Update-Prozess
1. Backup: `cp -r ~/.budgetmanager ~/.budgetmanager.backup`
2. Neue Dateien kopieren
3. Anwendung starten
4. Fertig!

### Rollback (falls nötig)
```bash
# Backup wiederherstellen
rm -rf ~/.budgetmanager
mv ~/.budgetmanager.backup ~/.budgetmanager
```

## Entwickler-Hinweise

### Neues Standard-Theme hinzufügen

**In `theme_manager.py`:**
```python
PREDEFINED_PROFILES = {
    # ... bestehende Themes ...
    
    "Mein Neues Theme": {
        "modus": "dunkel",
        "hintergrund_app": "#...",
        # ... alle erforderlichen Felder ...
        "dropdown_bg": "#...",
        "dropdown_text": "#...",
        "dropdown_selection": "#...",
        "dropdown_selection_text": "#...",
        "dropdown_border": "#...",
    },
}
```

### Theme programmatisch ändern
```python
# Profil laden
profile = theme_manager._load_profile_from_file("Standard Hell")

# Ändern
profile['akzent'] = "#ff0000"

# Speichern
theme_manager._save_profile_to_file("Standard Hell", profile)

# Anwenden
theme_manager.apply_theme(profile_name="Standard Hell")
```

### Stylesheet-Generierung erweitern
```python
# In theme_manager.py, build_stylesheet() Methode
def build_stylesheet(self, profile: ThemeProfile) -> str:
    # ... bestehender Code ...
    
    # Neue CSS-Regel hinzufügen
    stylesheet += f"""
    MeinWidget {{
        background-color: {custom_color};
    }}
    """
    
    return stylesheet
```

## Roadmap

### v0.19.0 (geplant)
- [ ] Automatischer Tag/Nacht-Wechsel
- [ ] Theme-Vorschau-Modus
- [ ] Gradient-Unterstützung
- [ ] Mehr vordefinierte Themes

### v0.20.0 (geplant)
- [ ] Theme-Marktplatz (Community-Themes)
- [ ] Live-Theme-Editor mit Vorschau
- [ ] Theme-Generator (aus Bild)
- [ ] Animationen zwischen Themes

## Support

### Hilfe benötigt?
- **GitHub Issues:** [Link einfügen]
- **E-Mail:** [E-Mail einfügen]
- **Discord:** [Discord-Link einfügen]

### Theme teilen?
Erstelle ein GitHub Issue mit:
- Theme-Name
- Screenshot
- JSON-Export
- Beschreibung

---

**Version:** 0.18.1  
**Autor:** Christian  
**Datum:** 24.12.2024  
**Lizenz:** [Lizenz einfügen]
