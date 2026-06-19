# BudgetManager v2.0.29 – Hotfix Forecast & Shortcut-i18n

Datum: 19. Juni 2026

## Gefixte Punkte

### 1. Forecast-Logik: inkrementelle Fixkosten

**Problem:** Bei fixkostenähnlichen Kategorien (`is_fix=1` oder `is_recurring=1`) wurden 0-Monate für die Analyse ignoriert. Dadurch konnte ein Muster wie `250, 250, 250, 0, 0, 0` bei 200 CHF Monatsbudget fälschlich als dauerhafte Unterdeckung gewertet werden.

**Fix:** Wenn eine Fixkosten-/wiederkehrende Kategorie im Analysefenster 0-Monate enthält, gilt jetzt:

- keine Senkung aufgrund von 0-Monaten,
- keine Erhöhung aufgrund einzelner aktiver Zahlungsmonate,
- Erhöhung nur dann, wenn **Summe Ist > Summe Budget** im gesamten Analysefenster,
- die Anpassung wird konservativ aus der durchschnittlichen Gesamtunterdeckung pro Monat berechnet.

**Regression:**

- Budget 200 CHF, Ist `250, 250, 250, 0, 0, 0` → **kein Vorschlag**.
- Budget 200 CHF, Ist `450, 450, 450, 0, 0, 0` → Vorschlag aus Fensterdurchschnitt, nicht aus Einzelzahlung.
- Monatlich echte Überschreitung, z. B. 100 Budget / 160 Ist über 6 Monate → Erhöhung bleibt erlaubt.

### 2. Tastenkürzel-/Shortcut-Texte vollständig i18n-fähig

**Problem:** Shortcut-Beschreibungen und Gruppen waren in `model/shortcuts_config.py` deutsch hardcodiert. Auch `Ctrl` wurde immer zu `Strg` und `Shift` zu `Umschalt`, wodurch EN/FR falsche Texte anzeigen konnten.

**Fix:**

- Shortcut-Katalog verwendet jetzt i18n-Keys statt sichtbarer deutscher Texte.
- `label_for()` und `group_for()` liefern lokalisierte Texte.
- `shortcut_display_name()` übersetzt Tastennamen sprachabhängig:
  - DE: `Strg+Umschalt+Z`
  - EN: `Ctrl+Shift+Z`
  - FR: `Ctrl+Maj+Z`
- Shortcut-Dialog und Settings-Dialog verwenden die lokalisierten Werte.

## Geänderte Dateien

- `model/budget_suggestion_engine.py`
- `model/shortcuts_config.py`
- `views/shortcuts_dialog.py`
- `settings_dialog.py`
- `locales/de.json`
- `locales/en.json`
- `locales/fr.json`
- `tests/test_fixed_cost_suggestion.py`
- `tests/test_shortcuts_i18n.py`
- `tools/release_logic_audit_100.py`

## Validierung

```text
python -m compileall -q .
PASS

python tools/i18n_audit.py --lang de --lang en --lang fr --max-hardcoded 120
PASS: alle referenzierten Keys vorhanden, keine verdächtigen hardcoded UI-Strings

python tools/release_logic_audit_100.py
PASS: 100 Loops, findings=0

python -m pytest -q
157 passed, 2 skipped
```

## Release-Urteil

Die beiden zuvor gemeldeten NO-GO-Punkte sind behoben und durch Regressionstests abgesichert. Lokal nicht ersetzt werden weiterhin echte Windows-/Installer-/PyInstaller-Build-Smokes, weil sie eine entsprechende Build-Umgebung benötigen.
