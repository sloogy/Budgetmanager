# CHANGELOG — Budgetmanager (Pre-Release)

> Versionierung: **0.x.x.x** (Solange das Projekt noch nicht „fertig“ ist)  
> Historisch existieren Ordner-/Code-Labels wie `v2.2.0`. Diese entsprechen **inhaltlich** der 0.2.x Linie.

## 0.2.2.1 — 03.01.2026

### Added
- **Dashboard → Subtab „Tabellarisch“** (Budget / Gebucht / Rest über mehrere Monate)
  - Auswahl: aktueller Monat, aktueller+nächster, letzte 2/3 + aktueller Monat
  - Quelle: Patch aus `v2.2.1_tree_overview` (nur `views/tabs/overview_tab.py`)

### Notes
- **Wichtig:** Budget-Tab NICHT aus `v2.2.1_tree_overview` übernehmen (Regression: Badges/Path-Mode).

---

## 0.2.2.0-fix2 — 02.01.2026

### Added
- **Integrierte Kategorie-Verwaltung im Budget-Dialog**
  - Kategorien direkt beim Budget-Erfassen anlegen
  - CategoryManagementWidget mit Management-Menü (Neu/Unterkategorie/Umbenennen/Löschen/Fix/Wiederkehrend/Tag)
  - Auto-Dialog bei unbekannter Kategorie (NewCategoryDialog)

- **Kategorien-Manager-Dialog** (Extras → Kategorien-Manager, Strg+K)
  - Mehrfachauswahl + Bulk-Edit für Fixkosten/Wiederkehrend/Tag
  - Filter (Alle/Fix/Wiederkehrend/Typ)
  - Farbkodierung (Fix rot, Wiederkehrend grün, beides orange)

- **Rechtsklick-Kontextmenü im Budget-Tab**
  - Eigenschaften/Umbenennen/Fix/Wiederkehrend/Tag
  - Neue Kategorie/Unterkategorie
  - Budget-Zeile entfernen (nur dieses Jahr) / Kategorie löschen (global)

- **Kategorien-Tab-Toggle (Expertenmodus)**
  - Ansicht-Menü + Settings: `show_categories_tab`
  - Tab kann ohne Neustart ein-/ausgeblendet werden

### Changed
- Tab-Handling stabilisiert (Einfügen an richtiger Position)
- Kategorie-Logik besser gekapselt (eigene Widgets/Dialogs)

### Technical
- DB-Schema bleibt V7 (Strings für Budget/Tracking, Tree via `parent_id` in `categories`)

---

## 0.2.1.0 — 01.01.2026

### Added / Merged
- Theme-Manager (JSON-Profile) + User-Overrides (`~/.budgetmanager/profiles/`)
- Fenster-State-Persistenz (Position/Größe/Max/Fullscreen)
- Budget-Tab Tree-Ansicht + Puffer-System (Parent/Child)

---

## 0.2.0.3 — 12.2025

- Theme-Manager + 26 vordefinierte Profile
- Fenster-State-Persistenz

## 0.2.0.0 — 12.2025

- Tree-Kategorien (Haupt-/Unterkategorien)
- Budget-Tab hierarchisch + Puffer-System

---

## Nächster großer Meilenstein (Breaking)

### 0.3.0.0 (Kandidat)
- **DB Ziel V8**: ID-basierte Beziehungen für Budget/Tracking (Breaking Change)
- Macht Umbenennen/Tree/Filter/Copy-Year deutlich robuster
- Siehe: `docs/DB_TARGET_SCHEMA_V8.md`
