# Release-Bericht v2.1.7 – RC gegen INTEGRATED, Wiki nachgezogen

Datum: 2026-07-02

## Ergebnis

Die Version **BudgetManager Source 2 1 7 RC** ist die bessere Release-Basis gegenüber **BudgetManager_Source_2_1_7_INTEGRATED**.

Grund: Die RC enthält alle Integrationspunkte der vorherigen v2.1.7-Zusammenführung und zusätzlich mehrere konkrete Release-Blocker-Fixes inklusive Regressionstest. Deshalb wurde die RC als Basis behalten und die Anleitung/Wiki-Dokumentation auf den Stand der besseren RC-Funktionalität nachgezogen.

## Technischer Vergleich

| Bereich | INTEGRATED | RC | Bewertung |
|---|---:|---:|---|
| Dateien gesamt | 269 | 270 | RC enthält einen zusätzlichen Regressionstest. |
| Unterschiedliche Dateien | 7 | 7 | Unterschiede liegen gezielt in Changelog, Version Info, i18n und zwei UI-Dateien. |
| Zusätzliche Tests | – | `tests/test_release_217_blocker_fixes_static.py` | RC besser. |
| Schema-Migration Lernstatus | vorhanden | vorhanden + statisch abgesichert | RC besser. |
| Erststart mit Lernmodus | Budget-Schritt konnte weiterhin blockieren | Budget-Schritt akzeptiert aktiven Lernmodus | RC besser. |
| Übersichts-Banner | `initial` fiel in Defizit-Symbol | `initial` zeigt 🆕 | RC besser. |
| Changelog-Historie | 2.1.7 in falschem/verkürztem Kontext | 2.1.7, 2.1.5 und 2.1.4 sauber wiederhergestellt | RC besser. |
| Wiki/Anleitung | Lernmodus erklärt, aber RC-Blocker nicht vollständig dokumentiert | jetzt ergänzt | behoben. |

## Relevante Dateiunterschiede

### 1. `views/setup_assistant_dialog.py`

Die RC verbindet die Lernmodus-Checkbox mit `_recompute_budget_done()` und erlaubt den Budget-Schritt, wenn entweder ein Budgetwert vorhanden ist **oder** der Lernmodus aktiv ist.

Best Practice für deinen Workflow:

- Lernmodus aktiv: Nutzer darf zuerst nur tracken.
- Lernmodus aus: klassische Mindestdaten-Prüfung bleibt hart.

Das ist fachlich korrekt, weil der Lernmodus genau für den Einstieg ohne vollständiges Budget gedacht ist.

### 2. `views/tabs/overview_budget_panel.py`

Die RC unterscheidet Banner-Symbole sauber:

- 🆕 = neues Startbudget aus Lernmodus
- 📉 = echtes Defizit / Erhöhungsbedarf
- 📈 = Überschuss / Senkungsvorschlag

Damit wird ein neues Budget nicht fälschlich als Problem dargestellt.

### 3. `locales/de.json`, `locales/en.json`, `locales/fr.json`

Die RC ergänzt den i18n-Key:

- `setup.budget_learning_skip_ok`

Die Key-Parität bleibt erhalten.

### 4. `tests/test_release_217_blocker_fixes_static.py`

Neue statische Regressionen sichern ab:

- Erststart-Freigabe über Lernmodus
- Banner-Symbol für `initial`
- i18n-Key-Parität
- Schema-Version `CURRENT_VERSION >= 15`

## Wiki-/Anleitungs-Fix in dieser Ausgabe

Folgende Dokumente wurden ergänzt, damit die Anleitung zur besseren RC-Funktion passt:

- `README.md`
- `FEATURES.md`
- `docs/USER_GUIDE.de.md`
- `docs/USER_GUIDE.en.md`
- `docs/USER_GUIDE.fr.md`
- `docs/help/README.md`
- `docs/help/index.html`
- `VERSION_INFO.txt`

Ergänzt wurden:

1. Erststart-Verhalten bei aktivem Lernmodus.
2. Klare Abgrenzung: Lernmodus aktiv = Budget-Schritt darf ohne Budgetwert weiter; Lernmodus deaktiviert = Mindestprüfung bleibt hart.
3. Banner-Symbolik für Lernbudgets, Defizite und Überschüsse.
4. Entscheidungspfad für neue Nutzer im Wiki.

## Release-Readiness

Status: **Releasefähig als v2.1.7 RC Wiki Fixed**.

Die Version ist stärker als die vorherige INTEGRATED-Version, weil sie nicht nur die Lernmodus-Integration enthält, sondern auch die sichtbaren Erststart-/Banner-Blocker behebt und absichert.

Noch extern zu prüfen, weil in dieser Umgebung nicht sinnvoll ausführbar:

- PyInstaller-Build
- Inno-Setup-Installer
- echter Windows-Updater-Lauf
- manueller GUI-Klicktest auf Windows

## Validierung

Ausgeführt in der Quellumgebung:

```bash
python -m compileall -q .
python tools/sync_version.py --check
python tools/i18n_audit.py
python -m pytest -q
```

Ergebnis:

```text
Alle Versionsdateien synchron: 2.1.7
[OK] Keine verdächtigen hardcoded UI-Strings gefunden
277 passed, 2 skipped
```

## Fazit

Die RC ist die korrekte technische Basis. Die Wiki-/Anleitungsunterschiede wurden behoben, indem die zusätzlichen RC-Fixes in README, Features, User-Guides und Help-Wiki aufgenommen wurden.
