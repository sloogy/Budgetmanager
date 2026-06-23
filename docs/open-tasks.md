# Open Tasks — BudgetManager v2.1.0

Stand: 22. Juni 2026

Diese Liste enthält nur noch Aufgaben, die außerhalb des Source-Pakets durch GitHub Actions oder manuelle Plattform-Smokes bestätigt werden müssen. Lokale Release-Gates sind im Source-Paket grün.

## Vor finalem Public Release prüfen

- GitHub Actions für Tag `v2.1.0` vollständig grün laufen lassen.
- Windows-EXE starten und ersten Dialog prüfen.
- Linux-Binary starten und ersten Dialog prüfen.
- Windows-Installer `BudgetManager_Setup_2.1.0.exe` installieren und Update-Modus prüfen.
- Portable-ZIP unter Windows testen: `start-windows.cmd`, stabile `BudgetManager.exe`, Daten in `./data/`.
- Portable-ZIP unter Linux testen: `start-linux.sh`, stabile `BudgetManager`, Daten in `./data/`.
- `latest.json` im GitHub Release prüfen: alle Assets vorhanden, SHA256-Werte gefüllt, keine `PUT_SHA256_HERE`.

## Funktionale Smoke-Tests

- Erster Start: Sprache, Währung und Zahlenformat übernehmen.
- Konto anlegen und Datenbank erstellen.
- Budgetwert erfassen und speichern.
- 13. Monatslohn mit Auszahlungsmonat und Betrag anlegen.
- Jahreskopie mit Review-Liste öffnen, Betrag ändern, eine Position abwählen.
- Buchung erfassen, bearbeiten und löschen.
- Fixkosten/Wiederkehrend-Buchungen buchen.
- Budgetwarnungen öffnen und Doppelklick-Aktion prüfen.
- Kategorien-Manager: Kategorie verschieben, umbenennen und löschen.
- Backup erstellen und Restore testen.
- Backup-Restore mit falschem Restore-Key testen.

## Technische Checks

```bash
python tools/sync_version.py --check
python -m compileall -q . -x '(^|/)(\.git|\.venv|__pycache__|build|dist)(/|$)'
python tools/i18n_audit.py
python tools/dau_first_run_check.py
python tools/release_logic_audit_100.py
python tools/verify_qt_translations.py
black --check model/
mypy model/
pytest tests/ -v
```

## Nach Release

- GitHub-Tag eindeutig setzen: `v2.1.0`.
- Nicht mehrere Release-Tags auf denselben alten Commit zeigen lassen.
- Release-Assets prüfen:
  - `BudgetManager-v2.1.0-portable.zip`
  - `BudgetManager-v2.1.0-windows.exe`
  - `BudgetManager-v2.1.0-linux`
  - `BudgetManager_Setup_2.1.0.exe`
  - `latest.json`
