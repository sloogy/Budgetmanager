# LifePlanner-Repositoryvertrag – BudgetManager

BudgetManager 2.2.58 bleibt ein eigenständiges Git-Repository und eine eigenständig startbare Anwendung. LifePlanner übernimmt keinen BudgetManager-Quellcode.

## Vom BudgetManager-Repository bereitgestellt

- `module.json` als Laufzeitvertrag
- `BUDGETMANAGER_DATA_DIR` für profilbezogene Daten
- `LIFEPLANNER_BRIDGE_DIR` für die kontrollierte Bridge
- `LIFEPLANNER_CENTRAL_UPDATER` zur Deaktivierung des internen Updaters im Hostbetrieb
- Review-first Import-Inbox für `budgetmanager.import.v1`
- eigener PyInstaller-Build über `BudgetManager.spec`

## Git-Regel

Alle Änderungen an Budgetfachlogik, Import-Inbox, Datenbank oder UI werden hier committet und getestet. LifePlanner pinnt nur eine veröffentlichte Version oder einen Git-Ref.

## Eigenständiges Installer-Asset

Dieses Repository veröffentlicht bei einem Versionstag zusätzlich ein eigenes, signiertes LifePlanner-Modulpaket:

```text
budgetmanager_<version>_Windows_x86_64.lpmodule
```

Der Workflow `.github/workflows/lifeplanner-module-release.yml` baut das Windows-Programm aus diesem Repository, verpackt `module.json` und die PyInstaller-Ausgabe und lädt das `.lpmodule` in genau dieses GitHub-Release hoch. Der LifePlanner-Windows-Installer fragt dieses Repository zur Installationszeit direkt ab.

Das Secret `LIFEPLANNER_UPDATE_PRIVATE_KEY_B64` muss mit dem Vertrauensanker des LifePlanner-Core übereinstimmen. Unsignierte Pakete werden vom Online-Installer abgelehnt.

