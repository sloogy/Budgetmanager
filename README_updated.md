# BudgetManager 0.17.0

Ein umfassender Budget-Manager mit erweiterten Features für wiederkehrende Transaktionen, intelligente Budget-Warnungen und vieles mehr.

## ✨ Neue Features in Version 0.17.0

### 🔄 Wiederkehrende Transaktionen mit Soll-Buchungsdatum
- Automatische Buchung von Fixkosten und wiederkehrenden Ausgaben/Einnahmen
- Flexibles Soll-Buchungsdatum (beliebiger Tag im Monat)
- Automatische Erkennung von fälligen Buchungen
- Start- und Enddatum für zeitlich begrenzte Transaktionen
- Aktivieren/Deaktivieren von Transaktionen ohne Löschen

### 📊 Intelligente Budget-Warnungen
- Automatische Erkennung von Budget-Überschreitungen
- Historische Analyse (letzte 6 Monate)
- **Intelligente Budget-Vorschläge** basierend auf tatsächlichen Ausgaben
- Automatischer Vorschlag zur Budget-Anpassung bei häufigen Überschreitungen
- Gewichteter Durchschnitt für realistischere Prognosen

### 🗄️ Datenbank-Management
- **Datenbank-Reset auf Standardwerte**
  - Optional: Kategorien behalten
  - Optional: Budgets behalten
  - Automatisches Backup vor Reset
- **Backup & Restore**
  - Manuelle und automatische Backups
  - Wiederherstellung aus Backup
  - Backup-Verwaltung mit Übersicht
- **Datenbank-Statistiken**
  - Dateigröße, Anzahl Einträge
  - Zeitraum der Daten
  - Summen nach Typ
- **Datenbank-Optimierung** (VACUUM)
- **JSON-Export** für externe Verwendung

### 🎨 Erscheinungs-Manager (Theme Profiles)
- Erstellen und Speichern von Farbprofilen
- Schnelles Wechseln zwischen Themes
- Export/Import von Theme-Profilen
- Vorschau vor Anwendung

### 🔧 Weitere Features
- **Tags/Labels** für zusätzliche Kategorisierung
- **Undo/Redo-Funktion** für alle Änderungen
- **Favoriten** - Häufig verwendete Kategorien pinnen
- **Sparziele** setzen und verfolgen
- **Budget-Warnungen** mit konfigurierbaren Schwellenwerten

### 🪟 Windows-Spezifisch
- **Windows Installer** mit Inno Setup
- **Portable Version** (ZIP)
- **Automatisches Update-Tool**
  - Prüfung auf neue Versionen
  - Download und Installation
  - Stable/Beta-Kanäle

## 📋 Voraussetzungen

### Allgemein
- Python 3.10 oder höher
- PySide6 (Qt für Python)
- SQLite3
- openpyxl (Excel-Export)
- matplotlib (Diagramme)

### Für Windows-Build
- PyInstaller
- Inno Setup 6.x (für Installer)

## 🚀 Installation

### Aus Quellcode
```bash
# Repository klonen
git clone https://github.com/yourusername/budgetmanager.git
cd budgetmanager

# Dependencies installieren
pip install -r requirements.txt

# Anwendung starten
python main.py
```

### Windows Installer
1. Neuesten Installer von [Releases](https://github.com/yourusername/budgetmanager/releases) herunterladen
2. `BudgetManager_Setup_0.17.0.exe` ausführen
3. Installationsanweisungen folgen

### Portable Version
1. `BudgetManager_Portable_0.17.0.zip` von [Releases](https://github.com/yourusername/budgetmanager/releases) herunterladen
2. ZIP entpacken
3. `BudgetManager.exe` ausführen

## 🔨 Für Entwickler

### Projekt bauen

#### Windows EXE erstellen
```bash
python build_windows.py
```

Dies erstellt:
- `dist/BudgetManager.exe` - Ausführbare Datei
- `installer_output/BudgetManager_Portable_0.17.0.zip` - Portable Version
- `installer_output/BudgetManager_Setup_0.17.0.exe` - Installer (wenn Inno Setup verfügbar)

#### Nur PyInstaller
```bash
pyinstaller BudgetManager.spec
```

### Datenbank-Schema

Die Anwendung verwendet SQLite mit folgenden Haupttabellen:
- `categories` - Kategorien für Einnahmen/Ausgaben
- `budget` - Geplante Budgets
- `tracking` - Tatsächliche Transaktionen
- `recurring_transactions` - Wiederkehrende Transaktionen (NEU in 0.17.0)
- `budget_warnings` - Budget-Warnungen
- `tags` - Tags für zusätzliche Kategorisierung
- `favorites` - Favorisierte Kategorien
- `savings_goals` - Sparziele
- `undo_stack` - Undo/Redo-Historie
- `theme_profiles` - Gespeicherte Themes

### Migrationen

Die Datenbank wird automatisch migriert beim Start. Aktuelle Schema-Version: **5**

## 📖 Verwendung

### Wiederkehrende Transaktionen einrichten

1. **Menü** → **Verwaltung** → **Wiederkehrende Transaktionen**
2. Auf **"Neu"** klicken
3. Details eingeben:
   - Typ (Einnahmen/Ausgaben)
   - Kategorie
   - Betrag
   - Buchungstag (1-31 des Monats)
   - Startdatum und optional Enddatum
4. **Speichern**

Die Transaktion wird nun automatisch zum festgelegten Tag gebucht.

### Fällige Buchungen prüfen

1. **Menü** → **Verwaltung** → **Wiederkehrende Transaktionen**
2. Auf **"Fällige Buchungen prüfen"** klicken
3. Auswahl treffen, welche Buchungen durchgeführt werden sollen
4. **"Buchen"** klicken

### Budget-Anpassungen bei Überschreitungen

Wenn Budgets häufig überschritten werden, erscheint automatisch ein Dialog mit:
- Liste der überschrittenen Kategorien
- Häufigkeit der Überschreitung (letzte 6 Monate)
- Intelligenter Vorschlag für neues Budget
- Option zur direkten Anwendung

**Oder manuell:**
1. **Budget-Tab** → **Warnungen**-Button
2. Vorgeschlagene Anpassungen prüfen
3. Gewünschte Budgets auswählen
4. **"Anwenden"** klicken

### Datenbank zurücksetzen

1. **Menü** → **Datei** → **Datenbank-Management**
2. **"Auf Standard zurücksetzen"** wählen
3. Optionen auswählen:
   - ☑️ Kategorien behalten
   - ☑️ Budgets behalten
   - ☑️ Backup erstellen
4. Bestätigen

## 🔄 Updates

### Automatisch (Windows)
Die Anwendung prüft automatisch auf Updates und benachrichtigt Sie.

### Manuell
1. **Menü** → **Hilfe** → **Nach Updates suchen**
2. Falls verfügbar: **"Download"** → **"Installieren"**

### Kommandozeile
```bash
python tools/update_manager.py --version 0.17.0 --check
```

## 🛠️ Konfiguration

### Einstellungen
Einstellungen werden in `budgetmanager_settings.json` gespeichert:

```json
{
  "data_directory": "C:/Users/Username/Documents/BudgetManager",
  "backup_directory": "C:/Users/Username/Documents/BudgetManager/Backups",
  "theme": "modern",
  "language": "de",
  "auto_backup": true,
  "auto_backup_interval_days": 7,
  "check_recurring_on_startup": true
}
```

## 📊 Features-Übersicht

| Feature | Status | Version |
|---------|--------|---------|
| Budgetverwaltung | ✅ | 0.1.0 |
| Tracking von Transaktionen | ✅ | 0.1.0 |
| Excel-Export | ✅ | 0.8.0 |
| Diagramme | ✅ | 0.10.0 |
| Fixkosten | ✅ | 0.12.0 |
| Tags | ✅ | 0.16.0 |
| Favoriten | ✅ | 0.16.0 |
| Undo/Redo | ✅ | 0.16.0 |
| Sparziele | ✅ | 0.16.0 |
| Backup/Restore | ✅ | 0.16.0 |
| Theme Profiles | ✅ | 0.16.0 |
| Wiederkehrende Transaktionen | ✅ | **0.17.0** |
| Intelligente Budget-Vorschläge | ✅ | **0.17.0** |
| Datenbank-Reset | ✅ | **0.17.0** |
| Windows Installer | ✅ | **0.17.0** |
| Update-Tool | ✅ | **0.17.0** |

## 🐛 Bekannte Probleme

- Theme-Wechsel erfordert Neustart der Anwendung
- Excel-Export: Sehr große Datenmengen (>10.000 Zeilen) können langsam sein

## 🤝 Mitwirken

Beiträge sind willkommen! Bitte:
1. Fork des Repositories erstellen
2. Feature-Branch erstellen (`git checkout -b feature/AmazingFeature`)
3. Änderungen committen (`git commit -m 'Add some AmazingFeature'`)
4. Branch pushen (`git push origin feature/AmazingFeature`)
5. Pull Request erstellen

## 📝 Lizenz

MIT License - siehe [LICENSE.txt](LICENSE.txt)

## 👥 Autoren

- Hauptentwickler - [Ihr Name]
- Contributors - Siehe [CONTRIBUTORS.md](CONTRIBUTORS.md)

## 🙏 Danksagungen

- PySide6/Qt Team für das UI-Framework
- Alle Contributors und Beta-Tester
- Community für Feedback und Feature-Vorschläge

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/yourusername/budgetmanager/issues)
- **Diskussionen:** [GitHub Discussions](https://github.com/yourusername/budgetmanager/discussions)
- **E-Mail:** support@budgetmanager.example.com

## 🗺️ Roadmap

### Version 0.18.0 (geplant)
- [ ] Cloud-Synchronisation
- [ ] Mobile App (iOS/Android)
- [ ] Kategorien-Import aus Bank-Statements
- [ ] Multi-User Support
- [ ] Budget-Vorlagen

### Version 0.19.0 (geplant)
- [ ] KI-basierte Ausgaben-Prognose
- [ ] Automatische Kategorisierung
- [ ] Budget-Optimierungsvorschläge
- [ ] Erweiterte Statistiken

---

**Version:** 0.17.0  
**Letztes Update:** Dezember 2024  
**Status:** Stabil
