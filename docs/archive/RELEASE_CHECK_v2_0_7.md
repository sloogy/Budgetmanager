# BudgetManager v2.0.7 — Release-Check nach Fix-Loop

Stand: 2026-06-13

## Entscheidung

**v2.0.7 ist der neue Release-Kandidat.**

Basis ist **v2.0.2**, weil diese Version die stabilere Kategorie-/Rename-/Undo-Logik enthält. Aus **v2.0.6** wurden nur die sinnvollen Verbesserungen übernommen, ohne die dort gefundenen Regressionen mitzunehmen.

## Plausibilitätsprüfung des Berichts v2.0.2 vs. v2.0.6

Der Bericht ist plausibel:

| Punkt | Bewertung |
|---|---|
| v2.0.2 als stabilere Basis | bestätigt |
| v2.0.6 nicht direkt releasefähig | bestätigt |
| Versionschaos in v2.0.6 | bestätigt |
| User-/Testdaten in v2.0.6 | bestätigt |
| Kategorie-Reassign/Undo-Regression in v2.0.6 | bestätigt |
| v2.0.6-Erststart-/Update-Ideen sinnvoll | bestätigt, selektiv übernommen |

## Umgesetzte Fixes in v2.0.7

### Release-Hygiene

- Version zentral auf `2.0.7` gesetzt.
- Synchronisiert:
  - `app_info.py`
  - `version.json`
  - `latest.json.template`
  - `docs/latest.json.template`
  - `installer/budgetmanager_setup.iss`
  - README/Installation/Features/Package-Doku
- Testuser und Userdaten entfernt:
  - kein `data/users.json`
  - keine `data/*.enc`
- Cache-/Buildreste werden vor dem ZIP entfernt:
  - keine `.pytest_cache`
  - keine `__pycache__`

### Kategorien / Datenintegrität

Aus v2.0.2 beibehalten:

- zentrale sichere Kategorie-Löschung per ID,
- Reassign mit additivem Budget-Merge,
- Parent-Löschung hebt Kinder eine Ebene hoch,
- zentraler Kategorie-Löschdialog,
- `BudgetModel.rename_category()` delegiert an `CategoryModel.rename_and_cascade()`,
- Undo/Redo-Rename-Cascade über die bekannten Referenztabellen.

Nicht übernommen aus v2.0.6:

- kaputte Mehrfachlöschung per Unterbaum-Cascade,
- Reassign ohne Budget-Merge,
- vereinfachte/inkonsistente Kategorie-Dialoglogik.

### Erststart / DAU-Führung

- Zahlenformat ist bereits beim ersten Sprach-/Regionsdialog wählbar.
- Setup-Assistent prüft strenger:
  - Budget-Schritt wird erst grün, wenn mindestens ein Budgetwert `> 0` existiert.
  - Tracking-Schritt wird erst grün, wenn mindestens eine Buchung existiert.
- QLocale wird passend zum Zahlenformat gesetzt, damit Qt-Eingabefelder konsistent mit der Geldanzeige arbeiten.
- Quick-Account-Warnung klarer formuliert.

### Update-Logik

- Neuer geführter Update-Dialog:
  - Prüfung startet automatisch beim Öffnen.
  - Ergebnis wird strukturiert in `updates/last_check.json` geschrieben.
  - Kein fragiles Parsen von Konsolentext.
  - Ein klarer Button: „Jetzt aktualisieren & neu starten“.
- Windows-Apply bleibt bewusst beim sichtbaren externen Helfer:
  - `CREATE_NEW_CONSOLE` bleibt erhalten.
  - `DETACHED_PROCESS` wird nicht mit `CREATE_NEW_CONSOLE` kombiniert.
  - Nutzer sieht ein Update-Fenster, während die EXE ersetzt wird.

### Tools

- `tools/dau_first_run_check.py` integriert und an die stabile v2.0.2-Kategorie-API angepasst.
- `tools/verify_qt_translations.py` integriert für Build-/Release-Checks.
- `BudgetManager.spec` warnt beim Build, falls Qt-Übersetzungskataloge fehlen.

## Teststand

Im Container ausgeführt:

```text
python -m compileall -q .
pytest -q
25 passed, 1 skipped

python tools/dau_first_run_check.py
ERGEBNIS: ALLE CHECKS BESTANDEN ✅
```

Zusätzliche Release-Integritätschecks in `tests/test_release_integrity.py`:

- keine ausgelieferten Userdaten,
- Version/Manifest/Installer synchron,
- Update-Dialog nutzt strukturiertes Ergebnis,
- Windows-Helfer bleibt sichtbar.

## Einschränkung

Der Container enthält keine installierte PySide6/Qt-Translations-Umgebung. Deshalb kann `tools/verify_qt_translations.py` hier nur melden, dass die Qt-Übersetzungskataloge in dieser Umgebung fehlen. Das ist kein Codefehler, muss aber beim echten Windows-/Linux-Build geprüft werden.

## Finales Urteil

**v2.0.7 ist als Source-Release-Kandidat releasefähig.**

Vor Veröffentlichung als EXE/ZIP-Binary bleibt nur der reale Windows-Smoke-Test:

1. App startet frisch.
2. Erststart mit Sprache, Währung, Zahlenformat funktioniert.
3. Budgetwert erfassen.
4. Tracking-Buchung erfassen.
5. Kategorie umbenennen/löschen mit Reassign testen.
6. Update-Dialog öffnen und prüfen, dass der Ablauf verständlich ist.
