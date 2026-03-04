# Datenbank-Struktur & Migration (BudgetManager)

## Aktuelles Schema (v10)
Die Anwendung nutzt SQLite mit folgenden Haupttabellen:
- `categories`: Baumstruktur (id, name, parent_id, account_id).
- `tracking`: Tatsächliche Buchungen (date, category_id, amount, description).
- `budget_lines`: Geplante Budgets pro Jahr/Monat.
- `recurring_transactions`: Automatisierte Buchungsregeln.
- `undo_stack` / `redo_stack`: Historie für Rückgängig-Funktion.

## Migrations-Konzept
- Migrationen werden in `model/migrations.py` definiert.
- Jede Migration erhöht die `schema_version` in der Tabelle `system_flags`.
- **Sicherheit**: Vor jeder Migration wird automatisch ein Backup der Datenbank im Ordner `data/backups/` erstellt.

## Ziel-Struktur (V8+ Plan)
Das Ziel ist eine vollständige ID-basierte Referenzierung (weg von String-basierten Typen/Kategorien):
1. **Accounts (Konti)**: Eigene Tabelle für Einnahmen, Ausgaben, Ersparnisse.
2. **Category Tree**: Saubere Parent-Child-Beziehung.
3. **Indizes**: Optimierte Suche nach Datum und Kategorien.

## Datenbank-Management
- **Backup**: Manuelle und automatische Sicherungen als `.bmr` (ZIP).
- **Reset**: Möglichkeit zum Zurücksetzen (komplett oder nur Daten unter Beibehaltung der Kategorien).
- **Optimierung**: Regelmäßiges `VACUUM` zur Reduzierung der Dateigröße.
- **Integrität**: Validierung von System-Kategorien (z. B. Schutz von "BUDGET-SALDO").
