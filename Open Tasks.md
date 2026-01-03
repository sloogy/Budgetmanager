# Open Tasks — Budgetmanager (Stand 0.2.2.1)

> Ziel: „Wildwuchs“ eindämmen, UX vereinfachen, Release-Prozess stabilisieren.  
> Prioritäten: **P0 (Must)** / **P1 (Should)** / **P2 (Nice)**

---

## P0 — Must-haves (nächste Releases)

- [ ] **Welcome / Setup-Assistent (1. Start)**
  - [ ] Schritt 1: Kategorien anlegen (Beispiel-Struktur)
  - [ ] Schritt 2: Budget setzen (Copy-Year anbieten)
  - [ ] Schritt 3: Buchungen importieren oder „Quick Add“
  - [ ] Schritt 4: Fertig → Dashboard erklärt (Drilldown Hinweise)
  - [ ] Checkbox „Nicht mehr anzeigen“ + Setting

- [ ] **Kategorie-Pfad überall anzeigen**
  - Budget-Tabelle, Tracking-Tabelle, Dropdowns, Exporte  
  Beispiel: `Gesundheit › Krankenkasse › Prämie`

- [ ] **Empty-States statt leere Flächen**
  - „Noch keine Buchungen – klicke auf + …“
  - „Noch kein Budget – Budget aus Vorjahr kopieren“ (Button)

- [ ] **Tooltips / „?“ Hilfe an kritischen Stellen**
  - Jahrwechsel, Copy-Year, Fixkosten/Monatsanfang, Filterlogik, Sparziele

- [ ] **Tracking: Button „Fixkosten / Monatsanfang“**
  - Fügt alle als Fixkosten markierten Kategorien als Buchungen ein
  - Übernimmt Monat als Bemerkung + Kategorienbezeichnung

- [ ] **Globale Suche: Navigation bei Doppelklick**
  - `views/global_search_dialog.py` hat TODO: „Navigation implementieren“

---

## P1 — Should-haves (nach Stabilisierung)

- [ ] **Begriffe entschärfen**
  - „Tracking“ → „Buchungen“
  - „Übersicht“ → „Dashboard“

- [ ] **Kontextmenüs konsistent**
  - Rechtsklick überall: zeigt nur Aktionen, die aktuell sinnvoll sind
  - Massenbearbeitung (Kategorien/Tracking) UX aufräumen

- [ ] **Filter weniger, dafür mehr Klick-/Doppelklick-Drilldowns**
  - Klick auf Diagramm-Slice setzt automatisch Kategorie-Filter
  - Doppelklick auf Tabellenzeile springt in Tracking-Tab und markiert Buchung

- [ ] **Recurring / Wiederkehrend-Logik verbessern**
  - Monatstag editierbar (pro Kategorie) + Default aus Settings (`recurring_preferred_day`)
  - UI „Wiederkehrend verwalten“ prüfen: macht es Sinn? Vereinheitlichen.

- [ ] **Build/Release-Version konsolidieren**
  - `build_windows.py` nutzt noch `VERSION = "0.17.0"` → auf 0.2.2.x umstellen
  - Version aus EINER Quelle (z.B. `__version__` Datei)

- [ ] **Update-Manager entweder richtig verdrahten oder entfernen**
  - `tools/update_manager.py` benötigt `requests` + `packaging`
  - Klare Strategie: GitHub Releases + Installer/Portable + Self-Update Flow

---

## P2 — Nice-to-haves

- [ ] **Filter-Presets speichern** („Arbeit“, „Haushalt“, „Fixkosten“…)
- [ ] **Mehr Konti (Accounts)**
  - Mindestens 3 Standard: Einnahmen/Ausgaben/Ersparnisse
  - Farben pro Konto + Kategorien je Konto
- [ ] **Import/Export verbessern**
  - CSV/Excel Import-Assistent + Mapping
  - Export mit Kategoriepfad & Filtern
- [ ] **Undo/Redo UX**
  - Aktionen klar benennen (z.B. „Kategorie umbenannt“, „Budget kopiert“)

---

## Architektur/DB (größerer Umbau)

- [ ] **0.3.0.0 — V8 Datenbank-Ziel (Breaking)**
  - ID-basierte Relations (Budget/Tracking → category_id)
  - Accounts Tabelle
  - Tree sauber (parent_id / optional closure table)
  - Migration/Upgrade-Strategie + Backup + Fallback

---

### V8 DB-Ziel: ID-Struktur (Details, damit der Umbau „richtig“ wird)

**Ziel:** Budget und Buchungen referenzieren Kategorien **nicht mehr über Namen/Strings**, sondern über **IDs** (`category_id`).  
Damit werden **Umbenennen**, **Baum-Refactor**, **Merge/Split** und **Exporte** robust.

#### Minimal-Schema (V8 — Vorschlag)
- `categories`:
  - `id` (PK, int)
  - `name` (text)
  - `parent_id` (FK → categories.id, NULL möglich)
  - `account_id` (FK → accounts.id) *(optional, wenn Kategorien je Konto getrennt sind)*
  - Flags: `is_fixed_cost` (bool), `is_recurring` (bool), `recurring_day` (int 1–31, NULL), `tag` (text, NULL)
  - Indexe: `(parent_id)`, ggf. `(account_id)`

- `accounts`:
  - `id` (PK)
  - `name` (z.B. Einnahmen/Ausgaben/Ersparnisse)
  - `color` (text, z.B. HEX)
  - `is_active` (bool)

- `budgets`:
  - `id` (PK)
  - `year` (int)
  - `month` (int 1–12 oder 0/NULL für „Gesamt“)
  - `category_id` (FK → categories.id)
  - `amount` (numeric)
  - Unique: `(year, month, category_id)`

- `transactions` (Tracking/Buchungen):
  - `id` (PK)
  - `date` (date)
  - `amount` (numeric)
  - `account_id` (FK → accounts.id)
  - `category_id` (FK → categories.id)
  - `note` (text, NULL)
  - Flags: `is_fixed_cost` (bool) *(optional redundant)*, `is_recurring_instance` (bool)
  - Indexe: `(date)`, `(category_id)`, `(account_id)`

#### Migrations-Plan (V7 → V8)
- [ ] **Backup erzwingen** vor Migration (automatisch + Hinweis im UI)
- [ ] Neue Tabellen/Spalten erstellen (`accounts`, `category_id` in budgets/transactions, etc.)
- [ ] **Mapping**: alte Kategorie-Strings → neue `categories.id`
  - Strategie: eindeutiger „Pfad-Key“ (z.B. `Gesundheit›Krankenkasse›Prämie`) als temporärer Matcher
- [ ] Daten umziehen (UPDATE budgets/transactions setzen `category_id`)
- [ ] Validieren: keine NULL `category_id` (außer „Unkategorisiert“ Fallback)
- [ ] Alte String-Spalten entfernen oder als Legacy behalten (nur falls unbedingt nötig)
- [ ] Foreign Keys aktivieren + Indizes setzen

#### Akzeptanzkriterien (damit 0.3.0.0 wirklich „Generation 2“ ist)
- [ ] Kategorie umbenennen → **Budget + Buchungen bleiben korrekt verknüpft**
- [ ] Kategorie verschieben im Tree → **Pfad ändert sich**, Relation bleibt korrekt
- [ ] Copy-Year funktioniert weiterhin (über IDs)
- [ ] Exporte enthalten weiterhin **Kategoriepfad** (aus Tree berechnet)
- [ ] Migration ist reproduzierbar (Test-DBs) + Fallback/Restore klappt

## Release-Kandidat-Definition

**0.2.2.x „fertig genug“ wenn:**
- Setup/Wizard vorhanden
- Pfad-Anzeige überall
- Fixkosten/Monatsanfang Button zuverlässig
- Empty states + Tooltips an den DAU-Stellen
- Keine bekannten Crash-/Loop-Bugs beim Tab-Toggle/Filter-Refresh

