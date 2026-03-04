# BudgetManager — Agent-Regeln (Source of Truth)

## Ziel
Claude ist **Owner/Lead/Checker**. Codex implementiert, Gemini schreibt/übersetzt.

## Token-Sparen
- **Keine Repo-Vollscans**: zuerst `rg`/`glob`, dann gezielt Dateien lesen.
- **Ergebnisse in Dateien**: Worker schreiben nach `.ai/dispatch/latest/`.
- **Kleine Steps**: lieber 3 kleine Worker-Läufe als 1 riesiger.

## i18n (WICHTIG)
- Locale-Dateien sind **verschachtelte dicts** (JSON). Keys werden im Code typischerweise **geflattet** (z.B. `btn.save`).
- Niemals die Struktur (flach ↔ verschachtelt) ändern, außer die i18n-Lade-Logik unterstützt es explizit.
- Platzhalter in allen Sprachen identisch halten.

## Qualität
- Nach Änderungen immer:
  - `python -m compileall .`
  - `python ai/i18n_check.py` (Key-Sync de/en/fr)

