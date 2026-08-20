# LifePlanner-Integrationsgrenze – BudgetManager

BudgetManager bleibt ein eigenständiges Git-Repository und eine eigenständig startbare Anwendung. LifePlanner übernimmt keinen BudgetManager-Quellcode. Das BudgetManager-Repository veröffentlicht seine eigenen installierbaren Modulbinärdateien.

## Vom BudgetManager-Repository bereitgestellt

- `module.json` als Laufzeitvertrag
- `BUDGETMANAGER_DATA_DIR` für profilbezogene Daten
- `LIFEPLANNER_BRIDGE_DIR` für die kontrollierte Bridge
- `LIFEPLANNER_CENTRAL_UPDATER` zur Deaktivierung des internen Updaters im Hostbetrieb
- Review-first Import-Inbox für `budgetmanager.import.v1`
- eigener PyInstaller-Build über `BudgetManager.spec`
- unsigned `.lpmodule`-Pakete für Windows x86_64 und Linux x86_64

## Git-Regel

Alle Änderungen an Budgetfachlogik, Import-Inbox, Datenbank oder UI werden hier committet und getestet. LifePlanner pinnt nur eine veröffentlichte Version oder einen Git-Ref.

## Veröffentlichungsgrenze

Ein BudgetManager-Versionstag veröffentlicht ausschließlich BudgetManager-Artefakte: portable Pakete für Windows und Linux, Windows-Setup, Updater-Metadaten, unsigned Windows-/Linux-`.lpmodule`-Pakete und die von GitHub automatisch erzeugten Quellcodearchive.

LifePlanner bezieht BudgetManager als versioniertes Binärmodul aus dem BudgetManager-Release. Der einzige Tag-Workflow baut und prüft die plattformspezifischen Pakete; ein separater LifePlanner-Workflow ist nicht erforderlich.

`module.json` und die Paketwerkzeuge bilden den technischen Laufzeit- und Veröffentlichungsvertrag. Die v2.2.62-Modulpakete werden bewusst unsigned veröffentlicht. LifePlanner/LiveManager kennzeichnet sie entsprechend und verlangt vor der lokalen Installation eine manuelle Vertrauensbestätigung.
