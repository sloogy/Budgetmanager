# LifePlanner-Integrationsgrenze – BudgetManager

BudgetManager bleibt ein eigenständiges Git-Repository und eine eigenständig startbare Anwendung. LifePlanner übernimmt keinen BudgetManager-Quellcode und veröffentlicht keine Artefakte im BudgetManager-Release.

## Vom BudgetManager-Repository bereitgestellt

- `module.json` als Laufzeitvertrag
- `BUDGETMANAGER_DATA_DIR` für profilbezogene Daten
- `LIFEPLANNER_BRIDGE_DIR` für die kontrollierte Bridge
- `LIFEPLANNER_CENTRAL_UPDATER` zur Deaktivierung des internen Updaters im Hostbetrieb
- Review-first Import-Inbox für `budgetmanager.import.v1`
- eigener PyInstaller-Build über `BudgetManager.spec`

## Git-Regel

Alle Änderungen an Budgetfachlogik, Import-Inbox, Datenbank oder UI werden hier committet und getestet. LifePlanner pinnt nur eine veröffentlichte Version oder einen Git-Ref.

## Veröffentlichungsgrenze

Ein BudgetManager-Versionstag veröffentlicht ausschließlich BudgetManager-Artefakte: portable Pakete für Windows und Linux, Windows-Setup, Updater-Metadaten und die von GitHub automatisch erzeugten Quellcodearchive.

LifePlanner prüft und bezieht seinen Online-Stand über den eigenen Update- und Veröffentlichungsweg. Deshalb gibt es in diesem Repository weder einen LifePlanner-GitHub-Check noch einen Tag-Workflow, der `.lpmodule`-Dateien in ein BudgetManager-Release hochlädt.

`module.json` und die lokalen Paketwerkzeuge bleiben als technischer Laufzeit- und Entwicklungsvertrag erhalten. Sie gehören nicht zum automatischen BudgetManager-GitHub-Release.
