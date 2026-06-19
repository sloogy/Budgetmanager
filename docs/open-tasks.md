# Open Tasks — BudgetManager v2.0.32

Stand: 19. Juni 2026

## Vor Release prüfen

- Windows-EXE über GitHub Actions bauen lassen.
- Linux-Binary über GitHub Actions bauen lassen.
- Portable-ZIP unter Windows testen.
- Portable-ZIP unter Linux testen.
- Start unter GNOME/Wayland prüfen: Standard-Fallback auf `xcb` im Log sichtbar.
- Cockpit prüfen: Rechtsklick-Menü öffnet echte Cockpit-Aktionen.
- Cockpit prüfen: Budget-Ampel und Budgetwarnungen werden angezeigt.
- Update-Manifest nach dem GitHub-Release mit echten SHA256-Werten füllen.

## Funktionale Smoke-Tests

- Erster Start: Sprache, Währung und Zahlenformat übernehmen.
- Konto anlegen und Datenbank erstellen.
- Budgetwert erfassen und speichern.
- Buchung erfassen, bearbeiten und löschen.
- Fixkosten/Wiederkehrend-Buchungen buchen.
- Budgetwarnungen öffnen und Doppelklick-Aktion prüfen.
- Kategorien-Manager: Kategorie verschieben, umbenennen und löschen.
- Backup erstellen und Restore testen.
- Backup-Restore mit falschem Restore-Key testen.
- Defektes Konto/Selbstheilung testen.

## Technische Checks

```bash
python tools/sync_version.py --check
python -m compileall -q . -x '(^|/)(\.git|\.venv|__pycache__|build|dist)(/|$)'
python tools/i18n_audit.py
python tools/dau_first_run_check.py
black --check model/
mypy model/
pytest tests/ -v
```

## Nach Release

- GitHub-Tag eindeutig setzen: `v2.0.32`.
- Nicht mehrere Release-Tags auf denselben alten Commit zeigen lassen.
- Release-Assets prüfen:
  - `BudgetManager-v2.0.32-portable.zip`
  - `BudgetManager-v2.0.32-windows.exe`
  - `BudgetManager-v2.0.32-linux`
  - `latest.json`
