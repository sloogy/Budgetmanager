# BudgetManager v2.0.30 – Merge-, Skalierungs- und Crash-Hardening-Report

Datum: 19. Juni 2026

## Ausgangslage

Es lagen drei unterschiedliche Stände vor:

1. `Budgetmanager_release.zip`  
   Enthielt den neueren GitHub-Release-Workflow für Windows, Linux, Installer und Portable-ZIP, aber noch Version `2.0.28` und ohne alle Mindmap-/Shortcut-/Forecast-Fixes.

2. `BudgetManager_Source_2_0_29_MINDMAP_I18N_FIXED (1).zip`  
   Enthielt die Mindmap in DE/EN/FR, Shortcut-I18N-Fixes, Forecast-Fixkosten-Korrektur und zusätzliche Release-Tests.

3. `BudgetManager_v2_0_29_RELEASE (1).zip`  
   Enthielt den vorherigen v2.0.29-Release-Stand mit weiteren Release-Fixes.

## Merge-Entscheidung

Basis ist `Budgetmanager_release.zip`, weil dort die korrigierte Release-YAML für GitHub Actions enthalten war. Darauf wurden die Fixes aus dem Mindmap/I18N-Stand und die fehlenden v2.0.29-Test-/Release-Härtungen gelegt.

Bewusst entfernt aus dem finalen Paket:

- `.git/` aus dem hochgeladenen Release-ZIP
- Cache-/Testartefakte
- Python-Bytecode

## Übernommene Fixes

### Release / GitHub Actions

- `.github/workflows/build.yml` aus dem Release-ZIP übernommen.
- Workflow baut weiterhin:
  - Windows-EXE
  - Linux-Binary
  - Windows-Installer
  - gemeinsames Portable-ZIP
  - `latest.json`
- Testlauf im Workflow auf `QT_QPA_PLATFORM=offscreen`, UTF-8 und kurzen Traceback gehärtet.
- Portable-Starter setzen jetzt zusätzlich DPI/Scaling-Defaults:
  - `QT_ENABLE_HIGHDPI_SCALING=1`
  - `QT_AUTO_SCREEN_SCALE_FACTOR=1`
  - `QT_SCALE_FACTOR_ROUNDING_POLICY=PassThrough`

### Mindmap / Hilfe / Dokumentation

- Lokale Hilfe/Mindmap ist in DE/EN/FR enthalten:
  - `docs/help/mindmap.de.html/.mmd`
  - `docs/help/mindmap.en.html/.mmd`
  - `docs/help/mindmap.fr.html/.mmd`
- Benutzeranleitungen in DE/EN/FR übernommen:
  - `docs/USER_GUIDE.de.md`
  - `docs/USER_GUIDE.en.md`
  - `docs/USER_GUIDE.fr.md`

### Shortcut-I18N

- Shortcut-Texte sind nicht mehr hart auf Deutsch verdrahtet.
- `Ctrl`, `Shift`, `Meta` usw. werden lokalisiert:
  - DE: `Strg`, `Umschalt`
  - EN: `Ctrl`, `Shift`
  - FR: `Ctrl`, `Maj`
- Neue Regressionstests sichern die Shortcut-Übersetzung ab.

### Forecast / Fixkostenlogik

Korrigierte Logik für inkrementelle/fixkostenähnliche Kategorien:

- `0`-Monate lösen bei Fixkosten keine Senkung aus.
- Aktive Monate über Budget lösen keine Erhöhung aus, wenn das Gesamtbudget im Betrachtungsfenster reicht.
- Beispiel abgesichert: Budget 200 CHF, Ist 250/250/250/0/0/0 → keine Erhöhung.
- Erhöhung erfolgt bei Fixkosten mit Lücken nur bei echter Gesamtunterdeckung über das Fenster.

### Skalierung / Portable / Windows / Linux

Neue Datei:

- `utils/ui_scaling.py`

Neue Maßnahmen:

- Qt-DPI-Umgebung wird vor `QApplication` vorbereitet.
- Fractional Scaling wird nicht grob auf 100/200 % gerundet.
- Kein harter `QT_SCALE_FACTOR`, damit Windows/Linux/Wayland/X11 die Systemskalierung nutzen.
- Gespeicherte Fenstergeometrie wird auf den sichtbaren Bildschirm geklemmt, damit Portable-Wechsel zwischen Monitoren/DPI-Stufen keine abgeschnittenen Fenster erzeugen.
- Cockpit-KPI-Karten wurden von 4 nebeneinander auf 2×2 umgestellt.
- Cockpit-Schnellaktionen wurden von einer langen horizontalen Buttonleiste auf ein 3×2-Grid umgestellt.
- Übersicht-Header nutzt keine harte Maximalhöhe mehr.
- Mehrere feste Breiten/Höhen wurden auf Minimum-Werte entschärft.

## Version

Version wurde auf `2.0.30` erhöht und synchronisiert:

- `app_info.py`
- `version.json`
- `VERSION_INFO.txt`
- `latest.json.template`
- `docs/latest.json.template`
- `installer/budgetmanager_setup.iss`

## Durchgeführte Prüfungen

### Syntax / Compile

```text
python -m compileall -q . -x '__pycache__|.git'
PASS
```

### Versions-Sync

```text
python tools/sync_version.py --check
Alle Versionsdateien synchron: 2.0.30
```

### Pytest – headless / ohne PySide6

```text
95 passed in 1.17s
```

Abgedeckt u. a.:

- Forecast-Fixkostenlogik
- Shortcut-I18N DE/EN/FR
- Release-Integrität
- Workflow-/Installer-Härtung
- Datenordner-Logik
- PBKDF2-/Verschlüsselungs-Kompatibilität
- Start-/Restore-Recovery
- Skalierungs-Härtung
- Mindmap DE/EN/FR

### 100-Loop Release-Logik-Audit

```text
Loops: 100
Status: PASS
Findings: 0
```

### I18N-Audit

```text
[OK] Alle referenzierten Keys existieren in de.json
[OK] en.json hat alle Keys von de.json
[OK] Keine verdächtigen hardcoded UI-Strings gefunden
```

Zusätzlich sichern Pytests die vollständige Key-Parität für DE/EN/FR ab.

## Nicht ausführbar in dieser Umgebung

Diese Umgebung hat kein installiertes `PySide6`. Deshalb konnte ich hier keinen echten GUI-Smoke und keinen Frozen-Binary-Test unter Windows/Linux ausführen. Der GitHub-Workflow ist aber so vorbereitet, dass GitHub Actions die Builds erzeugt. Nach dem Action-Build sollten diese drei Smoke-Tests noch manuell gemacht werden:

1. Windows Portable-ZIP starten, bei 100 %, 125 % und 150 % Skalierung prüfen.
2. Windows Installer starten, Sprache DE/EN/FR prüfen.
3. Linux-Binary/Portable unter X11/Wayland prüfen.

## Einschätzung

Source-seitig ist dieser Stand ein sauberer Release Candidate. Die bekannten Merge-Konflikte zwischen Release-YAML, Mindmap/I18N, Forecast-Fix und Skalierungsproblem sind zusammengeführt und durch headless Tests abgesichert. Die endgültige Freigabe hängt noch am echten Windows-/Linux-Frozen-Smoke nach GitHub-Actions-Build.
