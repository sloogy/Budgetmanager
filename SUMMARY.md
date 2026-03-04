# codex2 – Übersicht-Charts/Widgets Fix (Ist-Zustand + Umsetzung)

## Umgesetzt
1. Hardcodierte UI-Strings in den Overview/Favorites-Bereichen auf `tr()`/`trf()` umgestellt und fehlende Locale-Keys in `de/en/fr` ergänzt (verschachtelte Struktur beibehalten).
2. Chart-/Typ-Zuordnung auf stabile Typ-Keys (`TYP_INCOME`, `TYP_EXPENSES`, `TYP_SAVINGS`) ausgerichtet, statt Display-Text-Matching.
3. EN/FR-Aufrufproblem in der Übersicht gefixt: KPI-Klickpfad nutzt nun key-basierte Typ-Normalisierung statt Sprachstring-Vergleich.
4. Reviewer-Findings nachgezogen:
   - Placeholder-Mismatch in Budget-Tooltip korrigiert (`actual` statt `booked`).
   - Falschen Dialogtitel-i18n-Key korrigiert (`msg.budget_suggestions`).
   - Typ-Chart farbstabil key-basiert gemacht (`color_map` für Pie-Chart + feste TYP-Farbzuordnung).

## Geänderte Dateien
- `views/tabs/overview_tab.py`
- `views/tabs/overview_kpi_panel.py`
- `views/tabs/overview_budget_panel.py`
- `views/tabs/overview_right_panel.py`
- `views/tabs/overview_savings_panel.py`
- `views/tabs/overview_widgets.py`
- `views/favorites_dashboard_dialog.py`
- `locales/de.json`
- `locales/en.json`
- `locales/fr.json`

## Checks
- `python -m compileall .` -> OK
- `python ai/i18n_check.py` -> OK
  - de.json: total=1121 missing=0 extra=0
  - en.json: total=1121 missing=0 extra=0
  - fr.json: total=1121 missing=0 extra=0

## Multi-Agent Ablauf
- Explorer: betroffene Stellen + Minimalplan identifiziert.
- Worker: minimale Patches implementiert.
- Reviewer: 3 Risiken gefunden; alle behoben.
