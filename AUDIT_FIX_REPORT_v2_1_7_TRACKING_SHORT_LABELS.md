# Audit-Fix v2.1.7 – Tracking-Kurzlabels (RC2)

## Geprüft und bestätigt

- Kurzlabels sind datenseitig eindeutig: `UNIQUE(typ, name)` auf `categories`, keine Ambiguität möglich.
- 3-Ebenen-Bäume: auch mittlere Parents (Ebene 2 mit Kind) werden korrekt gefiltert, Blätter bleiben buchbar.
- Parent-Kategorien als Favoriten werden im Picker korrekt ausgeblendet.
- Waisen-Kategorien (parent_id auf gelöschte ID) landen via `build_tree` als Roots und bleiben buchbar.
- Resolver-Kette (`resolve_combo_category` → `resolve_name`) validiert Freitext gegen die DB, case-insensitive.
- i18n: alle sechs `picker.group_*`-Keys in de/en/fr vorhanden (nested JSON).
- Quick-Add ist reine Neuanlage und vom Blocker nicht betroffen.

## Blocker gefunden und behoben

**Stiller Kategorienwechsel beim Bearbeiten alter Parent-Buchungen.**
`TrackerDialog._set_combo_by_data()` fand für eine Preset-Kategorie wie `Wohnen`
(Parent mit Kindern, seit 2.1.7 nicht mehr im Picker gelistet) weder itemData-
noch Text-Match und kehrte still zurück. Die Auswahl blieb auf dem ersten
Picker-Eintrag; beim Speichern wäre die Buchung ungewollt umgehängt worden –
im Widerspruch zum Release-Ziel „bestehende Parent-Buchungen werden nicht
automatisch umgehängt“.

**Fix:** Editable-Fallback in `_set_combo_by_data` – ungelistete Preset-Werte
werden mit `setCurrentIndex(-1)` + `setEditText(value)` sichtbar als Freitext
gesetzt. Die bestehende Resolver-Kette liefert daraus wieder exakt die
Parent-Kategorie (End-to-End verifiziert). Für gelistete Kategorien ändert
sich nichts (itemData-Match greift weiterhin zuerst).

## Neue Regressionen

- `tests/test_category_combo_resolution.py::test_parent_category_preset_survives_short_label_picker`
  (funktional: Freitext-Zustand → Resolver liefert Parent-Namen)
- `tests/test_picker_and_budget_reached.py::test_tracker_dialog_keeps_unlisted_preset_category_editable_fallback`
  (statisch: Fallback darf nicht zurückgebaut werden)

## Validierung (Audit-Umgebung, ohne PySide6/pytest)

```text
python -m compileall -q .        → OK
tools/sync_version.py --check    → Alle Versionsdateien synchron: 2.1.7
tools/i18n_audit.py de/en/fr     → OK, keine hardcoded UI-Strings
Qt-freie Tests (6 Dateien)       → 27 passed, 0 failed
End-to-End Edit-Simulation       → Buchung bleibt auf 'Wohnen'
```

In der Build-Umgebung bitte wie üblich zusätzlich: `python -m pytest -q`
(voller Lauf mit PySide6), GUI-Smoke Bearbeiten einer alten Parent-Buchung.
