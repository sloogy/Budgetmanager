# Budgetmanager (Pre-Release) — v0.2.2.1

Ein **Desktop-Budgettool** (Python + PySide6, SQLite), um dein **Jahresbudget** zu planen und deine **Buchungen** (Einnahmen/Ausgaben/Ersparnisse) zu tracken – inklusive Kategorien-Baum, Fixkosten/Wiederkehrend, Tags, Sparzielen und Dashboard.

> **Status:** Pre-Release (**0.x.x.x**). Die App ist nutzbar, aber UI/Logik wird noch konsolidiert und das Datenmodell wird voraussichtlich nochmals „groß“ umgebaut (siehe **0.3.0.0 / DB-Ziel V8**).

---

## Was ist in v0.2.2.1 neu?

- **Dashboard / Übersicht → Subtab „Tabellarisch“**: Budget / Gebucht / Rest über mehrere Monate
  - Auswahl: *nur aktueller Monat*, *aktueller + nächster*, *letzte 2 + aktueller*, *letzte 3 + aktueller*
- Diese Funktion kommt als **gezielter Patch** aus `v2.2.1_tree_overview`:
  - übernommen wurde **nur** `views/tabs/overview_tab.py`
  - **nicht** übernommen wurde der Budget-Tab aus dieser Quelle (Regression: Badges/Path-Mode)

---

## Funktionen (Stand v0.2.2.1)

### 1) Budget-Tab (Planung)
- **Budget erfassen / bearbeiten** (Jahr/Monat)
- **Kategorien als Baumstruktur** (Haupt-/Unterkategorien)
- **Copy-Year**: Budget-Kategorien und (optional) Beträge von Jahr A → Jahr B kopieren
- **Rechtsklick-Kontextmenü** für Kategorien/Budgetzeilen (z. B. Eigenschaften, Fix/Wiederkehrend, Tag setzen)
- **Kategoriepfad anzeigen** (z. B. `Gesundheit › Krankenkasse › Prämie`) – hilft enorm gegen „DAU-Fragezeichen“

### 2) Kategorien-Tab (optional / Expertenmodus)
- Kategorien verwalten: **Hinzufügen / Entfernen / Bearbeiten**
- **Mehrfachauswahl** + **Bulk-Edit** (Fixkosten / Wiederkehrend / Tag)
- Tab kann per Einstellung ausgeblendet werden (wenn man nur im Budget-Dialog arbeiten will)

### 3) Buchungen-Tab (Tracking)
- Buchung erfassen/bearbeiten/löschen mit:
  - Datum, Betrag, Typ/Konto (Einnahmen/Ausgaben/Ersparnisse), Kategorie, Bemerkung
- **Quick Add** (schnell viele Buchungen erfassen)
- **Fixkosten / Monatsanfang**: kann wiederkehrende „Start-of-month“ Buchungen erleichtern
- **Filter** (Datum/Monat/Jahr, Typ/Konto, Kategorie, Bemerkung, etc.)
- Dialoge/Tools rund ums Wiederholen:
  - **Wiederkehrende Buchungen verwalten**
  - **Fixkosten-Check** / fehlende Buchungen prüfen (je nach Nutzung)

### 4) Dashboard / Übersicht
- Gegenüberstellung **Budget vs. Gebucht vs. Rest**
- Grafiken/KPIs (je nach Datenbestand)
- **NEU:** Subtab **„Tabellarisch“** (Monatsvergleich, siehe oben)

### 5) Extras (je nach Menü/Build aktiv)
- **Sparziele** (mit Tracking-Anbindung)
- **Favoriten** (Schnellzugriff)
- **Tags/Labels** (für Kategorien)
- **Budgetwarnungen** (Schwellwerte)
- **Undo/Redo** (Stack für Datenbank-Operationen)
- **Backup & Wiederherstellung**
- **Export** (CSV/Excel je nach Dialog)

---

## Installation & Start

### Voraussetzungen
- Python **3.10+** (Fedora / Windows)
- PySide6 + Abhängigkeiten aus `requirements.txt` (falls vorhanden)

### Start (Linux / Fedora)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Start (Windows)
- Analog mit venv (oder portable Build).  
- Hinweis: Windows-Paketierung/Updater ist **noch nicht final** (siehe Open Tasks).

---

## Datenbank (SQLite) & Migrationen

- Die App nutzt eine **SQLite**-Datenbank (Datei).
- Migrationen passieren beim Start automatisch (falls im Code vorgesehen).
- **Wichtig für die Zukunft:** Aktuell sind einige Beziehungen noch string-basiert (Kategorie-Strings).  
  Das ist praktisch, aber anfällig bei Umbenennungen.

---

## Versionierung (Wichtig)

- **Alle Releases bleiben bei 0.x.x.x**, solange „noch nicht fertig“.
- Historisch existieren Ordner-/Code-Labels wie `v2.2.0`.  
  Inhaltlich entspricht das der **0.2.x** Linie.

### Nächster „echter“ Major-Kandidat: 0.3.0.0 (Breaking)
> Der nächste „echte“ Major-Kandidat wäre **0.3.0.0**, wenn du das **V8 DB-Ziel** (ID-basierte Budget/Tracking-Relations) umsetzt – das ist eine **Breaking-Änderung**, die sich wie „neue Generation“ anfühlt.

---

## Bekannte Baustellen (ehrlich, ohne Drama)
- UI/Flows (Budget ↔ Kategorie-Management) sind teilweise historisch gewachsen → wird weiter vereinheitlicht.
- DB-Modell V7 ist „praktisch“, aber Umbenennen/Tree/Relations werden erst mit V8 wirklich robust.
- Wiederkehrende Buchungen/Fixkosten-Checks sind funktional, aber UX kann noch klarer werden.

---

## Mitmachen / Dev-Workflow (empfohlen)
- Entwicklung auf `dev`, Releases auf `main`.
- Kleine, klare Commits (z. B. `fix: ...`, `feat: ...`).
- Vor Release: Changelog pflegen, Version in `app_info.py` bumpen (ein Ort).

---

## Lizenz
Derzeit: intern/privat (anpassen, sobald du es public/OSS machst).
