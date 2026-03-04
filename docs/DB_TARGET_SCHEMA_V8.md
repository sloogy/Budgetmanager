# Ziel-DB-Struktur (SQLite) – Budgetmanager V2.x → V8 (Plan)

Dieses Dokument skizziert ein **Ziel-Schema** (V8) und einen **Migration-Plan**, passend zu deinen Tabs:

- **Budget** (Jahr/Monat, Parent-Summen, Eigenbetrag/Puffer, Copy-Year)
- **Kategorien** (Tree, Fixkosten/Wiederkehrend, Konti/Farben)
- **Tracking** (Buchungen + Filter, Fixkosten/Monatsanfang Button)
- **Übersicht** (KPIs, Charts, Ranking, Verlauf)

## Warum überhaupt V8?

V2.0 speichert viele Beziehungen über **Strings** (`typ` + `category`). Das ist schnell gebaut, aber wird bei echten Features schmerzhaft:

- Umbenennen einer Kategorie zerbricht Budget/Tracking-Verknüpfungen.
- Tree-Kategorien (Parent/Child) lassen sich nur halb sauber filtern/summieren.
- Copy-Year und Fixkosten werden kompliziert, sobald du mehr Logik willst.

V8 löst das mit **IDs** und klaren Tabellen.


## Grundprinzipien (Best Practices)

1. **Alles referenziert IDs**
   - `tracking.category_id` zeigt auf `categories.id`
   - `budget_lines.category_id` zeigt auf `categories.id`
   - Umbenennen einer Kategorie ändert **nur** `categories.name`, sonst nichts.

2. **Konti (Accounts) sind eigene Tabelle**
   - Einnahmen / Ausgaben / Ersparnisse sind Default-Accounts
   - weitere Accounts möglich (mit Farbe)

3. **Kategorien sind ein Tree**
   - `categories.parent_id` bildet Parent/Child
   - Parent-Summen werden in der UI berechnet (kein redundantes Speichern)

4. **Fixkosten/Wiederkehrend über Flags + optional Rule**
   - simplest: Flags in `categories` (fix, recurring, due_day)
   - optional: `recurring_rules` für komplexere Muster

5. **Copy-Year ist ein Copy von Budget-Lines**
   - Kategorien bleiben die gleichen IDs
   - kopiert nur Budget-Daten, Kategorien werden nicht dupliziert

## Ziel-Schema (SQLite)

### 1) Meta / Versioning

```sql
CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
-- meta('schema_version') = '8'
```

### 2) Accounts (Konti)

```sql
CREATE TABLE IF NOT EXISTS accounts (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL UNIQUE,
  color_hex  TEXT NOT NULL DEFAULT '#4C8BF5',
  is_default INTEGER NOT NULL DEFAULT 0, -- 1 für die 3 Standardkonti
  is_active  INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 3) Categories (Tree + Flags)

```sql
CREATE TABLE IF NOT EXISTS categories (
  id           INTEGER PRIMARY KEY,
  account_id   INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
  name         TEXT NOT NULL,
  parent_id    INTEGER NULL REFERENCES categories(id) ON DELETE SET NULL,

  -- Flags für deinen Workflow
  is_fixed_cost   INTEGER NOT NULL DEFAULT 0,  -- Fixkosten/Monatsanfang
  is_recurring    INTEGER NOT NULL DEFAULT 0,  -- wiederkehrend (monatlich)
  due_day         INTEGER NULL,               -- 1..31 optional

  is_active    INTEGER NOT NULL DEFAULT 1,
  sort_order   INTEGER NOT NULL DEFAULT 0,

  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at   TEXT NOT NULL DEFAULT (datetime('now')),

  -- keine doppelten Namen innerhalb eines Kontos
  UNIQUE(account_id, name)
);

CREATE INDEX IF NOT EXISTS idx_categories_account ON categories(account_id);
CREATE INDEX IF NOT EXISTS idx_categories_parent  ON categories(parent_id);
```

> Optional (Performance): Closure-Table für superschnelle Subtree-Queries

```sql
CREATE TABLE IF NOT EXISTS category_closure (
  ancestor_id   INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
  descendant_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
  depth         INTEGER NOT NULL,
  PRIMARY KEY (ancestor_id, descendant_id)
);
CREATE INDEX IF NOT EXISTS idx_closure_desc ON category_closure(descendant_id);
```

### 4) Budget

Best Practice: Budget ist immer **pro Jahr + Monat + Kategorie**.

```sql
CREATE TABLE IF NOT EXISTS budget_lines (
  id          INTEGER PRIMARY KEY,
  year        INTEGER NOT NULL,
  month       INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
  category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,

  amount      REAL NOT NULL DEFAULT 0.0,

  -- wenn du später mehrere Budget-Sets willst (z.B. "Plan", "Forecast")
  scenario    TEXT NOT NULL DEFAULT 'default',

  UNIQUE(year, month, category_id, scenario)
);

CREATE INDEX IF NOT EXISTS idx_budget_y_m ON budget_lines(year, month);
CREATE INDEX IF NOT EXISTS idx_budget_cat ON budget_lines(category_id);
```

**Parent-Summe + Puffer**:
- der **Eigenbetrag/Puffer** ist einfach `budget_lines.amount` für die Parent-Kategorie.
- die Anzeige im Budget-Tab berechnet: `parent_total = parent_amount + SUM(child_subtree)`

### 5) Tracking (Buchungen)

```sql
CREATE TABLE IF NOT EXISTS tracking_entries (
  id          INTEGER PRIMARY KEY,
  date        TEXT NOT NULL, -- ISO yyyy-mm-dd

  account_id  INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
  category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,

  amount      REAL NOT NULL,
  description TEXT NOT NULL DEFAULT '',

  -- optional: Flags, die aus Kategorie übernommen werden (Snapshot)
  is_fixed_cost_snapshot INTEGER NOT NULL DEFAULT 0,

  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tracking_date ON tracking_entries(date);
CREATE INDEX IF NOT EXISTS idx_tracking_cat  ON tracking_entries(category_id);
CREATE INDEX IF NOT EXISTS idx_tracking_acc  ON tracking_entries(account_id);
```

### 6) Tags (für Filter)

```sql
CREATE TABLE IF NOT EXISTS tags (
  id   INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS entry_tags (
  entry_id INTEGER NOT NULL REFERENCES tracking_entries(id) ON DELETE CASCADE,
  tag_id   INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY (entry_id, tag_id)
);
```

### 7) Sparziele

```sql
CREATE TABLE IF NOT EXISTS savings_goals (
  id          INTEGER PRIMARY KEY,
  name        TEXT NOT NULL,
  target_amount REAL NOT NULL,

  -- optionaler Zeitraum
  start_date  TEXT NULL,
  end_date    TEXT NULL,

  -- wo wird gemessen?
  account_id  INTEGER NULL REFERENCES accounts(id) ON DELETE SET NULL,
  category_id INTEGER NULL REFERENCES categories(id) ON DELETE SET NULL,

  is_active   INTEGER NOT NULL DEFAULT 1,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Auswertung** (Übersicht):
- Ziel kann an **Account** oder **Kategorie** hängen
- Ist-Wert = SUM(Tracking) im Zeitraum, gefiltert auf account/category


## Migration-Plan (V2 → V8) – sicher & rückwärtskompatibel

### Phase 0 – Vorbereitung

- **DB-Backup** vor jeder Migration (dein `migrations.py` macht das bereits)
- `meta.schema_version` einführen (falls noch nicht vorhanden)

### Phase 1 – Neue Tabellen parallel anlegen

1. Neue Tabellen `accounts`, `categories` (neu), `budget_lines`, `tracking_entries` (neu), `tags`, `entry_tags`, `savings_goals` erstellen.
2. Standardkonti anlegen:
   - `Einnahmen`, `Ausgaben`, `Ersparnisse` (mit Default-Farbe)

### Phase 2 – Daten aus V2 backfillen

> V2 Tabellen (Beispiele):
> - `categories(typ,name,is_fixed_cost,is_recurring,due_day,parent_id_text?)`
> - `budget(year,month,typ,category,amount)`
> - `tracking(date,typ,category,amount,details)`

Backfill-Schritte:

1. **categories:**
   - Map `typ` → `account_id`
   - Erzeuge neue `categories` mit gleicher `name`
   - Parent/Child: über bestehende Parent-Beziehung (falls vorhanden) setzen

2. **budget:**
   - Für jede Zeile: finde `category_id` über (account_id,name)
   - Insert in `budget_lines(year,month,category_id,amount)`

3. **tracking:**
   - Für jede Buchung: finde `account_id` + `category_id`
   - Insert in `tracking_entries(date,account_id,category_id,amount,description)`

### Phase 3 – App-Code auf IDs umstellen

- Modelle arbeiten nur noch mit IDs.
- UI zeigt weiter Namen (und Tree), speichert intern aber `category_id`.
- Filter/Übersicht werden deutlich zuverlässiger:
  - Parent-Kategorie filtert Subtree via `category_closure` oder BFS.

### Phase 4 – Cleanup (optional)

- Alte V2 Tabellen als `*_legacy` umbenennen oder entfernen, sobald alles stabil läuft.

## Copy-Year (Budget)

Copy-Year kopiert nur `budget_lines`:

- Quelle: `(src_year, scenario)`
- Ziel: `(dst_year, scenario)`
- Für jede Kategorie bleibt die **gleiche category_id**.
- Option **carry_amounts**:
  - `true` → amounts werden 1:1 kopiert
  - `false` → amounts werden auf 0 gesetzt, Struktur bleibt

