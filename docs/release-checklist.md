# Release-Checkliste — BudgetManager v2.2.6

## Lokal prüfen

```bash
python tools/sync_version.py --check
python -m compileall -q . -x '(^|/)(\.git|\.venv|__pycache__|build|dist)(/|$)'
python tools/i18n_audit.py
python tools/dau_first_run_check.py
python -m black --check model/
python -m mypy model/
python -m pytest tests/ -v -ra --tb=short
python tools/clean_release_tree.py
python tools/lint_procedure_check.py
```

## Manuell prüfen

- Start unter Linux/Wayland: Log zeigt standardmäßig `QT_QPA_PLATFORM=xcb`.
- Start unter Windows: App öffnet ohne Konsole/Crash.
- Cockpit: Rechtsklick öffnet Cockpit-Aktionen.
- Cockpit: Budgetwarnungen sind sichtbar.
- Budgetwarnung: Doppelklick öffnet die Warnungsprüfung.
- Tracking: Buchung erfassen, bearbeiten, löschen.
- Backup: Backup erstellen und Import/Restore testen.
- Restore: falscher Wiederherstellungscode führt zurück zum Start, ohne defekten Benutzer zu behalten.
- Start: defektes Konto bietet Selbstheilung an statt die App zu blockieren.

## Release erstellen

```bash
git status
git add .
git commit -m "Release v2.2.6"
git push origin main
git tag -a v2.2.6 -m "BudgetManager v2.2.6"
git push origin v2.2.6
```

## Nach GitHub Actions

- Windows-EXE herunterladen und starten.
- Linux-Binary herunterladen und starten.
- Von GitHub Actions erzeugte `latest.json` prüfen: Version, URLs und SHA256-Werte müssen zum Tag passen.
- Release-Beschreibung aus `CHANGELOG.md` übernehmen.
