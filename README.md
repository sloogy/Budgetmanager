# Budgetmanager (Pre-Release) — 0.2.2.1

> **Hinweis zur Versionierung:** Im Code/Ordnernamen steht teils noch `v2.x` (historisch).  
> Für Releases verwenden wir ab jetzt **`0.x.x.x`**, solange das Produkt noch im Aufbau ist.

## Was ist das?

**Budgetmanager** ist ein Desktop-Tool (Python + **PySide6** + **SQLite**) zum:

- **Budget planen** (jährlich, mit 12-Monats-Sicht)
- **Buchungen/Tracking erfassen** (Einnahmen, Ausgaben, Ersparnisse)
- **Kategorien als Baum** (Parent/Child, Pfad-Anzeige)
- **Dashboard/Übersicht** (KPIs, Charts, Ranking, Verlauf)
- **Themes/Designprofile** (JSON, hell/dunkel) + Settings-Persistenz

---

## Die „beste“ Basis für 0.2.2.x

**Master-Basis:** `0.2.2.0-fix2` (Codebase: „v2.2.0 … fix2“)  
**+ empfohlenes Mini-Patch:** `0.2.2.1` (nur 1 Datei) → bringt die gewünschte **Tabellarisch-Ansicht** im Dashboard.

### ✅ 0.2.2.1 Patch (empfohlen)
Du übernimmst **nur** diese Datei aus `v2.2.1_tree_overview`:

- `views/tabs/overview_tab.py`

**Wichtig:** **Nicht** den Budget-Tab aus `v2.2.1_tree_overview` übernehmen – der wirft dir **Badges/Path-Mode** wieder raus.

**Patch anwenden (Beispiel):**
```bash
# im Repo-Root
cp -v path/zur/v2.2.1_tree_overview/Budgetmanager_v2.2.0/views/tabs/overview_tab.py \
      views/tabs/overview_tab.py
```

Danach:
```bash
python main.py
```

---

## Quickstart (Fedora / Linux)

### 1) Virtuelle Umgebung (empfohlen)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
```

### 2) Abhängigkeiten installieren
Minimal:
```bash
pip install -r requirements.txt
```

Wenn du auch Update-Tool / Charts nutzt:
```bash
pip install -r requirements_updated.txt
```

### 3) Starten
```bash
python main.py
```

---

## Tabs im Programm

### 1) Budget
- Jahresbudget (Jan–Dez + Total)
- **Tree-Kategorien** (Parent/Child)
- Parent-Kategorien können **Puffer/Eigenbetrag** haben (siehe `docs/CHANGES_TREE_BUDGET.md`)
- **Copy-Year** (Budget von Jahr A → Jahr B)

### 2) Kategorien (Experten-Tab, optional)
Standard: Kategorien werden über Budget-Dialog verwaltet.  
Optional: separater Tab für Massenpflege.

Aktivieren:
- Menü **Ansicht** → „Kategorien-Tab anzeigen (Experten)“
- oder **Einstellungen → Verhalten → show_categories_tab**

### 3) Tracking (Buchungen)
- Erfassen nach Datum, Betrag, Konto/Typ, Kategorie, Bemerkung
- Filter nach Typ/Kategorie/Text/Datum/Monat/Jahr
- Fixkosten-/Wiederkehrend-Logik über Kategorie-Flags

### 4) Übersicht / Dashboard
- KPIs, Charts (Kreisdiagramme), Rankings
- **Neu in 0.2.2.1:** Subtab **„Tabellarisch“**
  - zeigt **Budgetiert / Gebucht / Rest** für mehrere Monate
  - Auswahl: aktueller Monat, aktueller+nächster, letzte 2/3 + aktuell

---

## Daten & Speicherorte

- **Datenbank:** standardmäßig `budgetmanager.db` (Pfad in Settings konfigurierbar)
- **Einstellungen:** `budgetmanager_settings.json`
- **Migration-Backups:** Standard `~/BudgetManager_Backups/`
  - Beim Start werden DB-Migrations ausgeführt und bei Bedarf ein Backup erstellt.

---

## Tastenkürzel (Stand fix2)

| Taste | Funktion |
|---|---|
| F1 | Hilfe / Shortcuts |
| F5 | Aktualisieren |
| Strg+N | Schnelleingabe |
| Strg+F | Globale Suche |
| Strg+S | Speichern |
| Strg+, | Einstellungen |
| Strg+1–4 | Tab wechseln |

---

## Datenbank-Version (aktuell)

- Aktuelles Schema: **V7** (siehe `model/migrations.py`)
- Nächster „echter“ Major-Kandidat: **0.3.0.0**, wenn du das **V8 DB-Ziel** umsetzt  
  (ID-basierte Budget/Tracking-Relations → Breaking Change, fühlt sich an wie „neue Generation“).

Siehe Plan: `docs/DB_TARGET_SCHEMA_V8.md`

---

## Entwicklung & Release-Flow (empfohlen)

- Entwicklung auf `dev`
- Release auf `main`
- Release-Check: nur releasen, wenn `dev` **ahead of** `main`

(Release-Skripte/Automatisierung sind als Open Tasks geführt.)

---

## Lizenz

Aktuell „Personal use“ (siehe `LICENSE.txt` / Build-Skript).  
Wenn du irgendwann veröffentlichen willst: Lizenz sauber entscheiden (MIT/GPL/…).

