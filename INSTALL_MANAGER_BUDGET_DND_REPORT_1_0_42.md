# BudgetManager v1.0.42 – Install-Manager, Dropdowns, Budget-Drag&Drop

## Zusammenführung

Basis: `BudgetManager_Source_1_0_41_complete.zip`.
Zusätzlich wurden die sinnvollen Install-Manager-/Release-Pipeline-Fixes aus `1.0.41_install_manager_fix` wieder integriert, weil sie in `1.0.41_complete` teilweise fehlten.

## Änderungen

### Install-/Erststart-Manager

- Sprachdialog fragt jetzt zusätzlich Währung und bevorzugten Monatstag ab.
- Sprachwahl setzt sinnvolle Defaults, überschreibt aber manuell geänderte Werte nicht:
  - Deutsch: CHF, 25. des Monats
  - Englisch: USD, 1. des Monats
  - Französisch: CHF, 25. des Monats
- Option „Kein bevorzugter Tag“ ergänzt.
- Setup-Assistent zeigt Budget-Schnellbeträge mit der gewählten Währung statt fest CHF.

### Einstellungen → Verhalten

- „Bevorzugter Tag (wiederkehrend)“ ist jetzt ein Dropdown inklusive „Kein bevorzugter Tag“.
- „Überschuss-/Defizit-Vorschlag ab“ ist jetzt ein Dropdown statt SpinBox.
- Neue Option: „Drag & Drop in der Budgetübersicht aktivieren“.

### Kategorien-Manager

- Fälligkeitstag im rechten Bearbeitungsbereich ist jetzt ein Dropdown statt SpinBox.
- Kontextmenü „Fälligkeitstag setzen“ nutzt ebenfalls eine Dropdown-Auswahl.
- Vorhandene Drag-&-Drop-/Kontextmenü-Funktionen für Parent/Child bleiben erhalten.

### Budgetübersicht

- Kategorien können direkt in der Budgettabelle per Drag & Drop umgehängt werden:
  - auf Kategorie ziehen → wird Unterkategorie
  - auf Typ-Überschrift ziehen → wird Hauptkategorie dieses Typs
- Drag & Drop kann in den Einstellungen deaktiviert werden.
- Schutz gegen falschen Typ, Selbstverschiebung und Zyklen nutzt `CategoryModel.can_reparent()`.

### Release/Updater-Pipeline

- GitHub-Build erzeugt weiterhin versionierte Release-Dateien:
  - `BudgetManager-v<version>-windows.exe`
  - `BudgetManager-v<version>-linux`
  - `BudgetManager-v<version>-portable.zip`
- `latest.json.template` und `docs/latest.json.template` auf v1.0.42-Schema aktualisiert.

## Checks

- `python tools/sync_version.py --check`
- `python -m compileall -q . -x '(^|/)(\.git|\.venv|__pycache__|build|dist|_attic)(/|$)'`
- `python tools/i18n_audit.py --lang de --lang en --lang fr`

Ergebnis: Version synchron, Syntax OK, i18n de/en/fr vollständig. GUI-Livetest im Container nicht durchgeführt.
