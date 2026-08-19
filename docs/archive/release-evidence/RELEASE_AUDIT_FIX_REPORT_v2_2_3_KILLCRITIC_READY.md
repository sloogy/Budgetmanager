# Release Audit & Fix Report – BudgetManager v2.2.3 KILLCRITIC READY

Datum: 5. Juli 2026  
Basis: `BudgetManager Source 2 2 3 RELEASE.zip`  
Verglichen mit: `BudgetManager_Source_2_2_2_RECURRING_DAY_DEFAULT_FIXED.zip`

## Ergebnis

v2.2.3 übernimmt den v2.2.2-Stand inklusive Fälligkeitstag-Fix und ergänzt das geführte Cockpit mit „Nächste Schritte“. Nach KILLCRITIC-Prüfung wurden zwei Release-Blocker/UX-Fehler behoben. Der Source-Release ist headless releasefähig.

Einschränkung der lokalen Prüfung: In dieser Umgebung ist PySide6/Qt nicht installiert. Darum wurden echte GUI-Smoke-Tests, Qt-Translation-Verify gegen installierte Qt-Kataloge, PyInstaller und Inno Setup nicht lokal ausgeführt. Diese Gates bleiben für die Build-/CI-Umgebung vorgesehen.

## Vergleich v2.2.2 fixed → v2.2.3

Übernommen aus v2.2.2 KILLCRITIC/Recurring-Day-Fix:

- Tag-Filter in der Übersicht bleibt zentralisiert über `TrackingModel.get_entries_in_range(..., tag_id=...)`.
- Favorit/Tag/Fälligkeitstag sind in Hilfe und UI klarer getrennt.
- Standard-Fälligkeitstag aus den Einstellungen wird bei wiederkehrenden Kategorien respektiert.

Neu in v2.2.3:

- Cockpit zeigt unter dem Monatsstatus eine dynamische Zeile „Nächste Schritte“.
- Vorschläge basieren auf echten Daten: keine Buchung im Monat, offene Fix-/wiederkehrende Buchungen, Monatsabschluss ab Tag 25.
- Neue i18n-Keys für de/en/fr.

## Gefundene Fehler

### 1. Release-Blocker: `trf` wurde verwendet, aber nicht importiert

In `views/tabs/cockpit_tab.py` nutzte `_refresh_next_steps()` `trf("cockpit.next_missing_fix", n=n_missing)`. Importiert war aber nur `tr`. Sobald offene Fixkosten/wiederkehrende Buchungen vorhanden waren, konnte das Cockpit beim Refresh in einen `NameError` laufen.

Fix:

- Import korrigiert auf `from utils.i18n import display_typ, tr, trf`.
- Regressionstest erweitert, damit dieser Fehler nicht wieder unbemerkt bleibt.

### 2. UX/Logik: Anzahl offener Monatsbuchungen war nur Tabellen-Anzahl

`_missing_count` wurde bisher auf `len(rows)` gesetzt. Die Tabelle zeigt maximal 10 Einträge. Bei mehr als 10 offenen Fix-/wiederkehrenden Buchungen hätte „Nächste Schritte“ trotzdem nur 10 angezeigt.

Fix:

- Offene Positionen werden jetzt vollständig gezählt (`open_count`).
- Die Tabelle zeigt weiter maximal 10 Zeilen, die Hinweiszeile nutzt aber die echte Gesamtanzahl.

### 3. Text stimmte nicht mit echtem Button überein

Der Empty-State-Hinweis sprach von „＋ Schnell erfassen“, der sichtbare Cockpit-Button heisst aber „➕ Buchung erfassen“.

Fix:

- de/en/fr-Hinweise auf den sichtbaren Buttontext angepasst.
- Changelog-Text korrigiert.

## Validierte Checks

Bestanden:

- `python tools/sync_version.py --check`
- `python -m compileall -q .`
- `python -m pytest -q -ra` → 312 passed, 2 skipped
- `python -m pytest tests/test_recurring_preferred_day_defaults.py -q` → 4 passed
- `python -m pytest tests/test_release_221_reset_and_ux.py -q` → 13 passed
- `python tools/i18n_audit.py` → OK, keine verdächtigen hardcoded UI-Strings
- `python tools/dau_first_run_check.py` → OK
- `python tools/release_logic_audit_100.py` → PASS, 100 Loops, 0 Findings
- `python tools/deep_logic_release_audit.py` → PASS, 500 Loops / 3500 Checks, 0 Findings
- `python tools/lint_procedure_check.py` → PASS nach Release-Clean
- Release-Baum bereinigt: keine `.bmr`, `.log`, `.pyc`, `__pycache__`, `.pytest_cache`

Lokal nicht ausführbar wegen fehlender PySide6/Qt-Buildumgebung:

- GUI-Smoke-Tests
- `tools/verify_qt_translations.py`
- PyInstaller-Build
- Inno-Setup-Installer-Build

## Release-Einschätzung

Der Source-Stand ist releasefähig als:

`BudgetManager v2.2.3 KILLCRITIC RELEASE READY`

Vor öffentlichem Upload sollten in GitHub Actions/Buildumgebung noch Windows/Linux-Build, GUI-Smoke, Qt-Translation-Verify und Installer-Build laufen.
