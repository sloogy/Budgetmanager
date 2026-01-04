# 📦 Budgetmanager v0.2.3.0 BETA - Installation & Start

## 🚀 Schnellstart

1. **ZIP entpacken**
   ```bash
   unzip Budgetmanager_v0_2_3_0_BETA.zip
   cd Budgetmanager_0.2.2.1_fix2_patched
   ```

2. **Programm starten**
   ```bash
   python main.py
   ```

   **Oder auf Windows:**
   - Doppelklick auf `main.py`
   - Oder: `python.exe main.py` in der Eingabeaufforderung

## 📋 Voraussetzungen

- **Python 3.8 oder höher** ([Download](https://www.python.org/downloads/))
- **PySide6** (wird automatisch installiert)

### Installation der Abhängigkeiten

Wenn das Programm nicht startet (Fehler: "ModuleNotFoundError: No module named 'PySide6'"):

```bash
pip install PySide6
```

**Oder mit den mitgelieferten Requirements:**
```bash
pip install -r requirements.txt
```

## 🆕 Was ist neu in v0.2.3.0?

### Budget-Tab komplett überarbeitet!

- ✅ **17 Spalten** (statt 14)
  - Bezeichnung (hierarchisch: Wohnen › Miete)
  - ⭐ Fix-Status (klickbar)
  - ∞ Wiederkehrend (klickbar)
  - Tag (1-31, editierbar)
  - Jan-Dez
  - Total

- ✅ **Total-Zeile zu oberst**
  - Zeigt Saldo: Einnahmen - Ausgaben - Ersparnisse
  - Farbcodiert: Grün (positiv), Rot (negativ), Grau (ausgeglichen)

- ✅ **Feste Reihenfolge**
  - Total-Zeile (Zeile 0)
  - Einnahmen
  - Ausgaben
  - Ersparnisse

- ✅ **Klickbare Symbole**
  - ⭐ Fix: Klick = umschalten
  - ∞ Wiederkehrend: Klick = umschalten
  - Tag: Editierbar (nur wenn Wiederkehrend aktiv)

## 📁 Projektstruktur

```
Budgetmanager_0.2.2.1_fix2_patched/
├── main.py                          # Hauptprogramm START HIER!
├── VERSION_INFO.txt                 # Änderungslog
├── README.md                        # Projekt-Dokumentation
├── CHANGELOG.md                     # Vollständiger Changelog
├── requirements.txt                 # Python-Abhängigkeiten
├── settings.py                      # Einstellungen
├── theme_manager.py                 # Theme-Verwaltung
├── model/                           # Datenmodelle
│   ├── budget_model.py
│   ├── category_model.py
│   ├── tracking_model.py
│   └── ...
├── views/                           # UI-Komponenten
│   ├── main_window.py
│   ├── tabs/
│   │   ├── budget_tab.py           # ⭐ NEU v2.3.0!
│   │   ├── budget_tab_ORIGINAL_v0.2.2.1.py  # Backup
│   │   ├── tracking_tab.py
│   │   ├── overview_tab.py
│   │   └── categories_tab.py
│   └── ...
└── docs/                            # Dokumentation

```

## 🔧 Konfiguration

### Datenbank-Speicherort

Standardmäßig: `~/.budgetmanager/budget.db`

Ändern in `settings.py`:
```python
DB_PATH = "dein/pfad/zur/datenbank.db"
```

### Themes

30+ Themes verfügbar! Wechsel über: **Ansicht → Erscheinungsmanager**

## ⚠️ Wichtige Hinweise (BETA)

Diese Version ist **BETA**. Bitte:

1. **Backup der Datenbank erstellen** (automatisch beim ersten Start)
2. **Gründlich testen** vor produktivem Einsatz
3. **Fehler melden** mit Fehlermeldung

### Bei Problemen

**Option 1:** Alte budget_tab.py wiederherstellen
```bash
cd views/tabs
cp budget_tab_ORIGINAL_v0.2.2.1.py budget_tab.py
```

**Option 2:** Backup der Datenbank wiederherstellen
```bash
cp ~/.budgetmanager/budget_backup_DATUM.db ~/.budgetmanager/budget.db
```

## 🆘 Support

Bei Fragen oder Problemen:

1. `VERSION_INFO.txt` lesen
2. `Open Tasks.md` prüfen (bekannte Probleme)
3. Fehler dokumentieren (Fehlermeldung + Schritte zur Reproduktion)

## 📝 Lizenz

Siehe `README.md` im Projekt-Verzeichnis.

## 🙏 Credits

- **Original:** Christian (Projekt-Autor)
- **Budget-Tab v2.3.0:** Claude (Anthropic)
- **Framework:** PySide6 (Qt for Python)

---

**Viel Erfolg mit dem Budgetmanager! 💰📊**
