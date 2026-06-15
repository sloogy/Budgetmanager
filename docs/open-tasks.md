# Open Tasks — BudgetManager v2.0.8

Stand: 13. Juni 2026

## Vor Release prüfen

- Windows-Installer mit Inno Setup real bauen und starten.
- Installer-Seite für Sprache, Währung und bevorzugten Buchungstag testen.
- Portable-ZIP unter Windows testen: `start-windows.cmd` und direkte EXE.
- Portable-ZIP unter Linux testen: `./start-linux.sh` oder `./run.sh`.
- Update-Manifest nach dem GitHub-Release mit echten SHA256-Werten prüfen.

## Funktionale Smoke-Tests

- Kategorien-Manager: Kategorie auf Kategorie ziehen → wird Unterkategorie.
- Kategorien-Manager: Kategorie auf Typ-Header ziehen → wird Hauptkategorie.
- Budgetübersicht: Drag & Drop aktivieren/deaktivieren.
- Budgetübersicht: Kategorie per Drag & Drop umhängen und Budget neu laden.
- Einstellungen → Verhalten: Budgetvorschlag-Monate und Drag&Drop speichern.
- Erststart: Sprache/Währung/Tag übernehmen.

## Technische Checks

```bash
python tools/sync_version.py --check
python -m compileall -q . -x '(^|/)(\.git|\.venv|__pycache__|build|dist)(/|$)'
pytest tests/ -v
```

## Nach Release

- GitHub-Tag eindeutig setzen: `v2.0.8`.
- Nicht mehrere Release-Tags auf denselben alten Commit zeigen lassen.
- Release-Assets prüfen:
  - `BudgetManager-v2.0.8-portable.zip`
  - `BudgetManager-v2.0.8-windows.exe`
  - `BudgetManager-v2.0.8-linux`
  - `latest.json`
