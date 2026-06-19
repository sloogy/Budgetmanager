# Release-Checkliste — BudgetManager v2.0.30

## Lokal prüfen

```bash
python tools/sync_version.py --check
python -m compileall -q . -x '(^|/)(\.git|\.venv|__pycache__|build|dist)(/|$)'
python tools/i18n_audit.py
python tools/dau_first_run_check.py
black --check model/
mypy model/
pytest tests/ -v
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
git commit -m "Release v2.0.30 audit hardening"
git push origin main
git tag -a v2.0.30 -m "BudgetManager v2.0.30"
git push origin v2.0.30
```

## Nach GitHub Actions

- Windows-EXE herunterladen und starten.
- Linux-Binary herunterladen und starten.
- SHA256-Werte in `latest.json` eintragen.
- Release-Beschreibung aus `CHANGELOG.md` übernehmen.
