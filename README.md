# 💰 BudgetManager v1.0.27

Eine umfassende Personal-Finance-Anwendung zur Verwaltung von Budget, Buchungen und Sparzielen.

![Version](https://img.shields.io/badge/version-1.0.27-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-orange)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)

---

## 🚀 Download & Start

### Windows

1. **Download**: `BudgetManager.exe` herunterladen
2. **Starten**: Doppelklick auf `BudgetManager.exe` — fertig!

Kein Installer notwendig, keine Admin-Rechte erforderlich. Daten liegen im Unterordner `./data/` neben der EXE.

### Linux (Quellcode)

```bash
# Abhängigkeiten installieren (empfohlen: venv)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Starten (empfohlen)
./run.sh

# Alternativ direkt
python3 main.py
```

---

## 🎯 Was ist neu in v1.0.26?

### ✨ Vollständiger Funktionsumfang
- **🔒 Multi-Account-System**: Quick-Modus, PIN und Passwort-Schutz mit PBKDF2 (200.000 Iterationen)
- **📅 Wiederkehrende Buchungen**: Automatisch mit Soll-Datum und Direktbuchung
- **💾 Backup inkl. Einstellungen**: Backup und Restore inklusive app-Einstellungen
- **🌍 Mehrsprachig**: Vollständige DE / EN / FR Lokalisierung (758 Keys)
- **🎨 25 Themes**: Hell, Dunkel, Gruvbox, Nord, Dracula, Solarized und mehr
- **↩️ Persistentes Undo/Redo**: Überlebt Neustart (SQLite-basiert)
- **🗂️ Sparziele-Tab**: Sparziele als eigenständiger Tab neben der Übersicht
- **📊 Verschiebbare Diagramme**: Panels im Übersichts-Tab per Splitter frei anpassbar
- **🖼️ Emoji → QIcon Migration**: Alle Buttons und Tabs nutzen native Qt-Icons (stabilere Darstellung)

Siehe [CHANGELOG.md](CHANGELOG.md) für alle Änderungen.

---

## 📋 Features

### Kern-Funktionen
- ✅ **Budget-Planung**: Hierarchische Kategorien, monatlich/jährlich
- ✅ **Buchungen (Tracking)**: Erfassen, bearbeiten, filtern, suchen
- ✅ **Wiederkehrende Transaktionen**: Automatische Buchungen mit Intervallen
- ✅ **Fixkosten-Management**: Automatische Prüfung und Erinnerungen
- ✅ **Budgetwarnungen**: Alerts bei Überschreitungen
- ✅ **Tags & Labels**: Flexible zusätzliche Kategorisierung
- ✅ **Undo/Redo**: Änderungen rückgängig machen (Strg+Z)
- ✅ **Favoriten**: Häufige Kategorien schnell erreichen
- ✅ **Sparziele**: Definieren, tracken, visualisieren

### Verwaltung & Tools
- ✅ **Backup & Restore**: Automatisch und manuell
- ✅ **Database-Management**: Statistiken, Bereinigung, Reset
- ✅ **Excel-Import/Export**: Massendaten verarbeiten
- ✅ **Globale Suche**: Alle Buchungen durchsuchen (Strg+F)
- ✅ **Shortcuts**: Umfangreiche Tastaturkürzel

### Visualisierung & Analyse
- ✅ **Diagramme**: Pie-Charts, Balkendiagramme, Trends
- ✅ **Übersichts-Tab**: Budget vs. Ist, Saldo, Statistiken
- ✅ **Kategorie-Analyse**: Ausgaben nach Kategorie
- ✅ **Multi-Jahr-Ansicht**: Jahresübergreifende Vergleiche
- ✅ **Sparziele-Tab**: Eigener Tab mit Übersicht aller Sparziele
- ✅ **Verschiebbare Panels**: Diagramme per Splitter im Übersichts-Tab anpassen

### Personalisierung
- ✅ **25 Themes**: Hell, Dunkel, Solarized, Gruvbox, Nord, Dracula, etc.
- ✅ **Theme-Editor**: Eigene Themes erstellen und speichern
- ✅ **Anpassbare UI**: Spaltenbreiten, Schriftgrößen, etc.

### Windows-Features
- ✅ **Direkt startbare EXE**: Kein Installer nötig
- ✅ **Auto-Updates**: Update-Check und Download (optional)
- ✅ **Native Qt-Icons**: Stabile Darstellung aller Buttons und Tabs

Siehe [FEATURES.md](FEATURES.md) für vollständige Liste.

---

## 🛠️ Installation

### Option 1: Windows — Direkt starten (Empfohlen)

1. **Download**: `BudgetManager.exe` herunterladen
2. **Starten**: Doppelklick auf `BudgetManager.exe` — fertig!

Kein Installer notwendig, keine Admin-Rechte erforderlich.

### Option 2: Linux / Quellcode

```bash
# Repository klonen
git clone <repo-url>
cd BudgetManager

# Abhängigkeiten installieren
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Starten
./run.sh
```

### Voraussetzungen (Quellcode)
- Python 3.11 oder höher
- PySide6 (automatisch via requirements.txt)
- SQLite (inkludiert in Python)

---

## 📖 Schnellstart

### 1. Erste Schritte

Nach dem Start:
1. **Kategorien einrichten**: Standard-Kategorien werden automatisch erstellt — unter "Budget" > "Kategorie-Manager" anpassen
2. **Budget planen**: "Budget"-Tab > Jahr wählen > monatliche Budgets eintragen
3. **Erste Buchung**: `Strg+N` für Schnelleingabe oder "Tracking"-Tab > "Neu"

### 2. Fixkosten einrichten

1. Budget-Tab > Rechtsklick auf Kategorie > "Eigenschaften" > Haken bei "Fixkosten"
2. Monatliche Prüfung: Extras > Fixkosten-Prüfung

### 3. Sparziele setzen

1. Tab "Sparziele" öffnen
2. "Neues Ziel" > Name, Betrag, Zieldatum eingeben
3. Fortschritt wird automatisch via Ersparnisse-Buchungen getrackt

### 4. Theme wählen

Ansicht > Erscheinungsmanager > aus 25 Themes wählen oder eigenes erstellen

---

## 💡 Tipps & Best Practices

- **Regelmäßig buchen**: Täglich oder wöchentlich (nicht monatlich)
- **Puffer einplanen**: 10-20% für unerwartete Ausgaben
- **Backups**: Wöchentlich, vor größeren Änderungen
- **Bereinigung**: Monatlich Database-Management nutzen

---

## 🔧 Konfiguration

### Datei-Speicherorte

| Datei | Pfad |
|-------|------|
| Datenbank | `./data/c.enc` |
| Einstellungen | `./data/budgetmanager_settings.json` |
| Backups | `./data/backups/*.bmr` |
| Theme-Profile | `./data/profiles/` |

---

## 📚 Dokumentation

- **[FEATURES.md](FEATURES.md)**: Vollständige Feature-Liste
- **[CHANGELOG.md](CHANGELOG.md)**: Versionshistorie
- **[MIGRATION.md](MIGRATION.md)**: Migrations-Hinweise

---

## 🤝 Support

### Häufige Probleme

**Q: BUDGET-SALDO zeigt falsche Werte**
A: Database-Management > Bereinigung durchführen.

**Q: Fixkosten werden nicht erkannt**
A: Kategorie muss als "Fixkosten" markiert sein (Rechtsklick > Eigenschaften).

**Q: Datenbank ist zu groß**
A: Database-Management > Bereinigung + VACUUM.

---

## 📄 Lizenz

MIT License — siehe [LICENSE.txt](LICENSE.txt)

---

**Version**: 1.0.26 | **Datum**: 04.03.2026 | **Status**: Stable ✅
