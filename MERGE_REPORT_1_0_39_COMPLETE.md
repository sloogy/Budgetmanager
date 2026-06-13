# BudgetManager 1.0.39 Complete Merge - Kurzbericht

Basis: `BudgetManager_Source_1_0_38_merged_settings_fix.zip`

Übernommen aus 1.0.39:
- Versionen/Installer auf 1.0.39
- globale Scrollbereiche für Einstellungsseiten
- Theme min-height / SpinBox-Pfeil-Fix

Behalten aus 1.0.38, weil kompletter:
- Kategorie-Manager mit Drag & Drop plus Kontextmenü „Verschieben unter…“
- `get_by_id()` und `can_reparent()` im CategoryModel
- vollständigere i18n-Keys de/en/fr
- Verhalten-Seite mit WrapLongRows, Mindestbreiten und i18n-Labels

Checks:
- `python3 tools/sync_version.py --check`: OK
- `python3 -m compileall .`: OK
- `tools/i18n_audit.py --lang de --lang en --lang fr`: OK
