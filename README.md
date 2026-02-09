<<<<<<< Updated upstream
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
=======
# 💰 Budgetmanager v2.3.0.1

Eine umfassende Personal-Finance-Anwendung zur Verwaltung von Budget, Buchungen und Sparzielen.

![Version](https://img.shields.io/badge/version-2.3.0.1-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-orange)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)

---

## 🎯 Was ist neu in 2.3.0.1?

### 🐛 Kritischer Bugfix: BUDGET-SALDO Kumulierung behoben
Das Problem, bei dem sich der BUDGET-SALDO über Monate kumulierte statt den korrekten monatlichen Saldo anzuzeigen, wurde behoben. Die fehlerhaften Einträge werden automatisch beim Start entfernt.

### ✨ Neue Features
- **🗄️ Database-Management**: Statistiken, Bereinigung, Reset-Funktionen
- **💰 Erweiterter Fixkosten-Check**: Monatliche Prüfung mit intelligenter Schätzung und Batch-Buchung
- **📚 Vollständige Dokumentation**: Detaillierte Feature-Übersicht und Anleitungen

Siehe [CHANGELOG.md](CHANGELOG.md) für Details.

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
- ✅ **PDF-Reports**: Professionelle Berichte generieren
- ✅ **Globale Suche**: Alle Buchungen durchsuchen (Strg+F)
- ✅ **Shortcuts**: Umfangreiche Tastaturkürzel

### Visualisierung & Analyse
- ✅ **Diagramme**: Pie-Charts, Balkendiagramme, Trends
- ✅ **Übersichts-Tab**: Budget vs. Ist, Saldo, Statistiken
- ✅ **Kategorie-Analyse**: Ausgaben nach Kategorie
- ✅ **Multi-Jahr-Ansicht**: Jahresübergreifende Vergleiche

### Personalisierung
- ✅ **24 Themes**: Hell, Dunkel, Solarized, Gruvbox, Nord, Dracula, etc.
- ✅ **Theme-Editor**: Eigene Themes erstellen und speichern
- ✅ **Anpassbare UI**: Spaltenbreiten, Schriftgrößen, etc.

### Windows-Features
- ✅ **Installer**: Professioneller Inno Setup Installer
- ✅ **Auto-Updates**: Update-Check und Download (optional)
- ✅ **Startmenü-Integration**: Shortcuts und Deinstallation

Siehe [FEATURES.md](FEATURES.md) für vollständige Liste.

---

## 🚀 Installation

### Option 1: Windows-Installer (Empfohlen)

1. **Download**: `Budgetmanager_Setup_v2.3.0.1.exe`
2. **Installieren**: Doppelklick auf Installer
3. **Fertig**: Programm über Startmenü starten

### Option 2: Python (Development)

```bash
# Repository klonen oder ZIP herunterladen
cd Budgetmanager_v0_2_3_0_1

# Virtuelle Umgebung erstellen (optional aber empfohlen)
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
>>>>>>> Stashed changes

# Abhängigkeiten installieren
pip install -r requirements.txt

# Starten
python main.py
```

<<<<<<< Updated upstream
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
=======
### Voraussetzungen (für Python-Installation)
- Python 3.11 oder höher
- PySide6 (automatisch via requirements.txt)
- SQLite (inkludiert in Python)

---

## 📖 Schnellstart

### 1. Erste Schritte

#### Nach Installation:
1. **Kategorien einrichten**: 
   - Die Anwendung erstellt automatisch Standard-Kategorien
   - Passe diese unter "Budget" > "Kategorie-Manager" an

2. **Budget planen**:
   - Gehe zum "Budget"-Tab
   - Wähle Jahr und trage monatliche Budgets ein
   - Nutze "Jahr kopieren" für wiederkehrende Budgets

3. **Erste Buchung**:
   - Drücke `Strg+N` für Schnelleingabe
   - Oder: "Tracking"-Tab > "Neu"
   - Datum, Typ, Kategorie, Betrag eingeben

### 2. Fixkosten einrichten

1. **Kategorien als Fixkosten markieren**:
   - Budget-Tab > Rechtsklick auf Kategorie > "Eigenschaften"
   - Haken bei "Fixkosten" setzen
   - Wiederkehrend-Tag eintragen (z.B. 1 für Monatsanfang)

2. **Monatliche Prüfung**:
   - Extras > Fixkosten-Prüfung
   - Zeigt fehlende Buchungen
   - Wähle aus und buche direkt

### 3. Sparziele setzen

1. **Ziel erstellen**:
   - Tools > Sparziele
   - "Neues Ziel"
   - Name, Betrag, Zieldatum eingeben

2. **Fortschritt tracken**:
   - Automatisch via Ersparnisse-Buchungen
   - Oder manuell zuweisen

### 4. Theme wählen

1. **Theme ändern**:
   - Ansicht > Erscheinungsmanager
   - Wähle aus 24 vordefinierten Themes
   - Oder erstelle eigenes Theme

---

## 💡 Tipps & Best Practices

### Budget-Verwaltung
- **Realistische Budgets**: Start mit tatsächlichen Ausgaben, dann optimieren
- **Puffer einplanen**: 10-20% Puffer für unerwartete Ausgaben
- **Regelmäßig reviewen**: Monatlich Budget vs. Ist vergleichen

### Buchungen
- **Konsistenz**: Täglich oder wöchentlich buchen (nicht monatlich)
- **Beschreibungen**: Aussagekräftige Beschreibungen verwenden
- **Tags nutzen**: Für detailliertere Analysen

### Kategorien
- **Hierarchie nutzen**: Hauptkategorien + Unterkategorien
- **Nicht zu viele**: 15-25 Kategorien sind optimal
- **Fixkosten markieren**: Für automatische Erinnerungen

### Datensicherheit
- **Regelmäßige Backups**: Wöchentlich oder monatlich
- **Vor großen Änderungen**: Immer Backup erstellen
- **Backup-Speicherort**: Sicherer Ort (externe Festplatte, Cloud)

### Performance
- **Bereinigung**: Monatlich Database-Bereinigung durchführen
- **Alte Daten**: Jahresweise archivieren bei >5 Jahren Daten
- **VACUUM**: Regelmäßig für Größenreduktion

---

## 🎨 Screenshots

### Budget-Ansicht
```
┌─────────────────────────────────────────────────────────────┐
│ Budgetmanager - Budget 2026                                 │
├─────────────────────────────────────────────────────────────┤
│ Bezeichnung      │Fix│∞│Tag│ Jan │ Feb │ ... │ Dez │ Total │
├──────────────────┼───┼─┼───┼─────┼─────┼─────┼─────┼───────┤
│📊 BUDGET-SALDO   │   │ │   │8434 │8434 │ ... │8434 │101208 │
│ Einkommen        │   │ │   │     │     │     │     │       │
│  • Lohn (Netto)  │★ │∞│25 │6950 │6950 │ ... │6950 │ 83400 │
│ Ausgaben         │   │ │   │     │     │     │     │       │
│  • Miete         │★ │∞│ 1 │1500 │1500 │ ... │1500 │ 18000 │
│  • Lebensmittel  │   │ │   │ 600 │ 600 │ ... │ 600 │  7200 │
└─────────────────────────────────────────────────────────────┘
```

### Fixkosten-Prüfung
```
┌─────────────────────────────────────────────────────────────┐
│ 💰 Fixkosten-Prüfung - Februar 2026                         │
├─────────────────────────────────────────────────────────────┤
│ ⚠️ 3 Fixkosten fehlen noch! (5/8 gebucht, 62%)             │
├───┬─────────────────┬─────────┬───────────┬──────────┬─────┤
│☑ │ Miete           │Ausgaben │  1'500.00 │ 1'500.00 │01.02│
│☑ │ Strom & Gas     │Ausgaben │    150.00 │   145.00 │15.02│
│☑ │ Netflix         │Ausgaben │     15.90 │    15.90 │01.02│
└───┴─────────────────┴─────────┴───────────┴──────────┴─────┘
│ [Alle auswählen] [Alle abwählen]     [✅ Ausgewählte buchen]│
└─────────────────────────────────────────────────────────────┘
```
>>>>>>> Stashed changes

---

## 🔧 Konfiguration

<<<<<<< Updated upstream
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
=======
### Datenbank-Speicherort
```
Windows: %USERPROFILE%\.budgetmanager\budgetmanager.db
Linux:   ~/.budgetmanager/budgetmanager.db
```

### Settings
```
Windows: %USERPROFILE%\.budgetmanager\budgetmanager_settings.json
Linux:   ~/.budgetmanager/budgetmanager_settings.json
```

### Theme-Profile
```
Windows: %USERPROFILE%\.budgetmanager\profiles\
Linux:   ~/.budgetmanager/profiles/
```

---

## 📚 Dokumentation

- **[FEATURES.md](FEATURES.md)**: Vollständige Feature-Liste mit technischen Details
- **[CHANGELOG.md](CHANGELOG.md)**: Versionshistorie und Änderungen
- **docs/**: Weitere Dokumentation
  - `CHANGES_TREE_BUDGET.md`: Änderungen an Budget-Struktur
  - `DB_TARGET_SCHEMA_V8.md`: Datenbank-Schema

---

## 🤝 Support

### Bei Problemen
1. **Dokumentation prüfen**: Siehe FEATURES.md
2. **Backup erstellen**: Vor Experimenten
3. **Database-Management**: Statistiken und Bereinigung prüfen
4. **Log-Datei**: `budgetmanager.log` im Anwendungsordner

### Häufige Probleme

**Q: BUDGET-SALDO zeigt falsche Werte**
A: In v2.3.0.1 behoben. Update installieren oder Database-Bereinigung durchführen.

**Q: Fixkosten werden nicht erkannt**
A: Kategorie muss als "Fixkosten" markiert sein (Rechtsklick > Eigenschaften).

**Q: Theme ändert sich nicht**
A: Neustart der Anwendung erforderlich (wird in Zukunft behoben).

**Q: Datenbank ist zu groß**
A: Database-Management > Bereinigung durchführen, dann VACUUM.

---

## 🔜 Roadmap

### Geplant für v2.4
- Mobile App (Android/iOS)
- Cloud-Synchronisation (optional)
- Mehr Report-Templates
- Budget-Vorschläge basierend auf Historie

### Langfristig
- Multi-Währung-Support
- API für Drittanbieter
- Verschlüsselung der Datenbank
- Web-Version

---

## 📄 Lizenz

MIT License - siehe LICENSE Datei

---

## 👨‍💻 Entwickler

**Christian**

---

## 🙏 Danksagungen

- PySide6/Qt Team für das UI-Framework
- SQLite Team für die robuste Datenbank
- Community für Feedback und Testing

---

## 🎉 Zusammenfassung

**Budgetmanager v2.3.0.1** ist bereit für den produktiven Einsatz mit:

- ✅ Alle angeforderten Features implementiert
- ✅ Kritischer BUDGET-SALDO Bug behoben
- ✅ Database-Management mit Reset-Funktionalität
- ✅ Erweiterter Fixkosten-Check mit Monatsprüfung
- ✅ 24 professionelle Themes
- ✅ Windows-Installer verfügbar
- ✅ Umfangreiche Dokumentation
- ✅ Aktive Entwicklung

**Download jetzt und starte deine finanzielle Reise! 🚀**

---

**Version**: 2.3.0.1  
**Datum**: 08.02.2026  
**Status**: Stable ✅
>>>>>>> Stashed changes
