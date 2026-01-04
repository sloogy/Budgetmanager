# 💰 Budgetmanager v0.2.3.0.0

Ein umfassender, persönlicher Budgetmanager für Windows/Linux/macOS – entwickelt mit Python und PySide6.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PySide6](https://img.shields.io/badge/PySide6-6.6+-green.svg)
![SQLite](https://img.shields.io/badge/SQLite-3-lightgrey.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## 🌟 Features

### Kernfunktionen

- **📊 Budget-Planung** – Monatsbudgets nach Kategorien verwalten
- **📈 Tracking** – Einnahmen und Ausgaben erfassen
- **📁 Hierarchische Kategorien** – Baumstruktur (z.B. Gesundheit › Krankenkasse › Prämie)
- **🎯 Sparziele** – Ziele setzen und Fortschritt tracken
- **📉 Dashboard** – Budget vs. Gebucht Übersicht

### NEU in v0.2.3.0.0

- **🧭 Einführungsassistent** – Schritt-für-Schritt Setup für neue Benutzer
- **📊 Excel-Import/Export** – Kategorien via Excel-Vorlage verwalten
- **💰 Budget-Ausfüll-Dialog** – Fokussiertes Budget-Eintragen
- **🐛 Undo/Redo Fix** – Datenbank-Kompatibilitätsprobleme behoben

### Weitere Features

- ⭐ **Fixkosten** markieren und automatisch buchen
- ∞ **Wiederkehrende Transaktionen** mit Soll-Buchungsdatum
- 🏷️ **Tags** für zusätzliche Kategorisierung
- ⚠️ **Budgetwarnungen** bei Überschreitung
- ↩️ **Undo/Redo** für alle Aktionen (Strg+Z / Strg+Y)
- 🔍 **Globale Suche** (Strg+F)
- ⚡ **Schnelleingabe** (Strg+N)
- 💾 **Backup & Wiederherstellung**
- 🎨 **Theme-Profile** (Hell/Dunkel + viele Varianten)

---

## 🚀 Schnellstart

### Voraussetzungen

- Python 3.10 oder höher
- pip (Python Package Manager)

### Installation

```bash
# Repository klonen oder ZIP entpacken
cd Budgetmanager_v0_2_3_0_0

# Abhängigkeiten installieren
pip install -r requirements.txt

# Starten
python main.py
```

### Erster Start

Beim ersten Start öffnet sich automatisch der **Einführungsassistent**, der dich durch das Setup führt:

1. Kategorien anlegen (Manager oder Excel-Import)
2. Budget ausfüllen
3. Erste Buchung erstellen
4. Fixkosten verstehen

Der Assistent kann jederzeit über **Hilfe → 🧭 Erste Schritte...** erneut gestartet werden.

---

## ⌨️ Tastenkürzel

| Kürzel | Funktion |
|--------|----------|
| `Strg+S` | Speichern |
| `Strg+N` | Schnelleingabe |
| `Strg+F` | Globale Suche |
| `Strg+K` | Kategorien-Manager |
| `Strg+E` | Export |
| `Strg+Z` | Rückgängig (Undo) |
| `Strg+Y` | Wiederholen (Redo) |
| `Strg+1-4` | Zu Tab wechseln |
| `F1` | Tastenkürzel-Hilfe |
| `F5` | Aktualisieren |
| `F10` | Maximieren |
| `F11` | Vollbild |

---

## 🎨 Themes

Der Budgetmanager bietet zahlreiche Theme-Profile:

### Hell
- Standard Hell
- V2 Hell – Neon Cyan
- V2 Hell – Pastel Mint
- V2 Hell – Warm Sand
- Gruvbox Hell
- Solarized Hell
- Pastell Sanft

### Dunkel
- Standard Dunkel
- V2 Dunkel – Graphite Cyan
- V2 Dunkel – Purple Night
- Dracula, Nord, Monokai, Ocean
- Gruvbox Dunkel, OLED Kontrastarm

Zugriff: **Datei → Einstellungen → Darstellung**

---

## 📊 Excel-Import für Kategorien

### Vorlage ausfüllen

| Typ | Pfad | Fix (0/1) | Wiederkehrend (0/1) | Tag (1-31) |
|-----|------|-----------|---------------------|------------|
| Ausgaben | Wohnen › Miete | 1 | 1 | 1 |
| Ausgaben | Gesundheit › Krankenkasse › Prämie | 1 | 1 | 1 |
| Einkommen | Lohn | 0 | 1 | 25 |
| Ersparnisse | Notgroschen | 0 | 1 | 1 |

### Pfad-Syntax

- Trennzeichen: `›`, `»`, `>`, `/`, `\`
- Beispiel: `Gesundheit › Krankenkasse › Prämie`
- Eltern-Kategorien werden automatisch erstellt

---

## 🔧 Konfiguration

### Settings-Datei

`budgetmanager_settings.json` im Programmverzeichnis.

### Wichtige Einstellungen

| Einstellung | Beschreibung | Standard |
|-------------|--------------|----------|
| `show_onboarding` | Einführung beim Start | `true` |
| `setup_completed` | Setup abgeschlossen | `false` |
| `auto_save` | Automatisches Speichern | `false` |
| `show_categories_tab` | Kategorien-Tab (Experten) | `false` |

---

## 🗄️ Datenbank

- **Format**: SQLite 3
- **Datei**: `budgetmanager.db`
- **Schema-Version**: 8
- **Backup**: Automatisch vor Migrationen

---

## 📜 Lizenz

MIT License

---

*Entwickelt mit ❤️ und ☕ in der Schweiz*
