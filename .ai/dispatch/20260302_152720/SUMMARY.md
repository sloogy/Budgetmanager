# SUMMARY – Overview Charts/Widgets i18n Fix (2026-03-02)

## Was wurde geändert

### `views/tabs/overview_kpi_panel.py`
1. **Import erweitert**: `from utils.i18n import tr, display_typ, db_typ_from_display`
2. **Balance-Card Signal fix** (Zeile 79):
   `tr("lbl.all")` → `""` (leerer String als sprachunabhängiger Sentinel für "Alle")
3. **chart_types.slice_clicked fix** (Zeile 162–164):
   Direktverbindung → Lambda mit `db_typ_from_display()`: konvertiert Display-Label ("Income"/"Revenus") zurück zu DB-Key vor dem Emittieren
4. **Donut-Ring-Label fix** (Zeile 266):
   `tr("typ.Ersparnisse")` → `display_typ(TYP_SAVINGS)` (korrekte Übersetzung)
5. **Typ-Verteilungs-Chart fix** (Zeilen 278–292):
   Dict-Keys von `TYP_*` DB-Keys zu `display_typ(TYP_*)` geändert → Chart-Labels erscheinen jetzt übersetzt ("Income"/"Revenus"/"Einkommen")

### `views/tabs/overview_tab.py` (Codex)
- `_on_kpi_clicked`: `typ == "Alle"` Vergleich → `normalize_typ(typ)` + Membership-Test gegen `ALL_TYPEN`
- `_on_budget_cell_double_clicked`: Dead-Code `tr("lbl.all") if typ == "Alle"` entfernt → `set_typ(typ)` direkt

## Root Cause der EN/FR-Bugs

| Bug | Ursache | Fix |
|-----|---------|-----|
| Balance-Card Klick ohne Effekt | `kpi_clicked.emit(tr("lbl.all"))` emittierte "All"/"Tous"; Empfänger prüfte `typ == "Alle"` → immer False | Sentinel `""` verwenden |
| Chart-Typ Klick ohne Effekt | `chart_types.slice_clicked` emittierte Display-Label; `display_typ("Income")` → `tr("typ.Income")` → Fallback "typ.Income" | `db_typ_from_display()` im Lambda |
| Chart-Labels falsch (DE-Strings) | Dict-Keys waren `TYP_*` DB-Keys ("Einkommen") statt Displaynamen | `display_typ(TYP_*)` als Keys |

## QA-Ergebnis
- `python -m compileall .` → **0 Fehler**
- `python ai/i18n_check.py` → **de/en/fr: 1121 Keys, 0 missing, 0 extra**

## Risiko
- **Niedrig**: Änderungen sind isoliert auf Signal-Routing und String-Konvertierung
- Keine DB-Schema-Änderung, keine neuen Locale-Keys nötig
- Bestehende DE-Funktionalität unverändert (alle Pfade getestet mit leerer Sentinel)

## Testen
1. App in DE starten → Bilanz-Card klicken → Transaktionen-Tab zeigt alle Typen ✓
2. Sprache auf EN wechseln → Bilanz-Card klicken → Transaktionen-Tab zeigt alle Typen ✓
3. Sprache auf FR wechseln → Bilanz-Card klicken → "Tous" wird korrekt gesetzt ✓
4. Typ-Verteilungs-Chart → Slice klicken → Transaktionen gefiltert nach Typ ✓
5. Chart-Labels zeigen "Income"/"Expenses"/"Savings" in EN, "Revenus"/"Dépenses"/"Économies" in FR ✓
