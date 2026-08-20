# 📦 BudgetManager v2.2.63 — Installation, Start & Update


## Diagramm-Hinweis v2.2.63

Für eine eigene Kachelanordnung oben im Cockpit **Kacheln frei anordnen** aktivieren. Danach die Kachel an ihrer gesamten Kopfzeile oder am Griff `≡` nach oben, unten oder in die andere Spalte ziehen. Die Anordnung wird automatisch gespeichert.

Der Cockpit-Verlauf bleibt zusätzlich gegen den nativen QtCharts-Absturz aus v2.2.54 gehärtet. Falls ein bestimmter Linux-/Grafiktreiber trotzdem Probleme mit QtCharts verursacht, startet dieser Befehl die Anwendung ohne die beiden Cockpit-Diagramme:

```bash
BM_DISABLE_COCKPIT_CHARTS=1 ./run.sh
```

Budget, Buchungen, Kategorien, Übersicht und Backups bleiben dabei nutzbar. Der Schalter verändert keine Daten und kann beim nächsten normalen Start einfach weggelassen werden.

Auch die Übersichtsdiagramme werden beim Aktualisieren atomar ausgetauscht und
verzögert freigegeben. Das verhindert eine native QtCharts-/Shiboken-Freigabe
während laufender Paint- oder Layout-Ereignisse.

## Hinweis zu v2.2.63

Diese README gehört zur gehärteten Vorab-Release-Version v2.2.63. Sie enthält zusätzlich unsigned LifePlanner-/LiveManager-Modulpakete, den Einfach-/Erweitert-Modus, XLSX-/PDF-Berichte, erweiterte Diagnose- und visuelle Plattformprüfungen sowie die atomare Restore-Kopie. Designprofile bleiben vollständig über den DesignManager steuerbar. Die zentrale Versionsquelle ist `app_info.py`.

## Windows: empfohlener Download

Für Windows gibt es im GitHub Release mehrere Dateien:

- `BudgetManager_Setup_2.2.63.zip` — empfohlen, wenn Browser oder Windows den direkten EXE-Download blockieren.
- `BudgetManager_Setup_2.2.63.exe` — direkter Installer.
- `BudgetManager-v2.2.63-portable-windows.zip` — portable Windows-Version ohne Installation.
- `BudgetManager-v2.2.63-portable-linux.zip` — portable Linux-Version.
- `budgetmanager_2.2.63_Windows_x86_64.lpmodule` / `budgetmanager_2.2.63_Linux_x86_64.lpmodule` — unsigned LifePlanner-/LiveManager-Module; beim lokalen Import ist die Vertrauenswarnung zu bestätigen.
- `latest.json` — Manifest für die veröffentlichten Pakete.
- `SHA256SUMS.txt` — Prüfsummen zur Kontrolle.

Dieser nicht-kommerzielle Vorab-Release ist noch nicht mit Authenticode oder
einer `latest.json.sig` signiert. Windows SmartScreen kann deshalb warnen; die
SHA-256-Prüfsummen müssen vor dem Start kontrolliert werden. Der
signaturpflichtige In-App-Updater bleibt bis zur regulär signierten
Veröffentlichung bewusst deaktiviert, die Pakete können manuell installiert
oder gestartet werden.

### Prüfsumme unter Windows prüfen

PowerShell im Download-Ordner öffnen:

```powershell
Get-FileHash .\BudgetManager_Setup_2.2.63.exe -Algorithm SHA256
```

Den angezeigten Hash mit `SHA256SUMS.txt` vergleichen.

Falls Windows die Datei nach dem Download blockiert:

```powershell
Unblock-File .\BudgetManager_Setup_2.2.63.exe
```

## Windows Installer

1. `BudgetManager_Setup_2.2.63.zip` herunterladen.
2. ZIP entpacken.
3. Optional: SHA256 gegen `SHA256SUMS.txt` prüfen.
4. `BudgetManager_Setup_2.2.63.exe` starten.
5. Datenverzeichnis wählen.
6. Sprache, Währung und bevorzugten Buchungstag auswählen.
7. BudgetManager starten.

Der Installer schreibt `installation.json` in den Programmordner und nutzt den gewählten Datenordner für Nutzerdaten und Update-Staging. Bestehende Einstellungen werden nicht überschrieben.

## Windows Portable

1. `BudgetManager-v2.2.63-portable-windows.zip` herunterladen.
2. ZIP in einen normalen Benutzerordner entpacken, zum Beispiel `Dokumente\BudgetManager` oder auf einen USB-Stick.
3. `start-windows.cmd` oder `BudgetManager.exe` starten.

Standardmäßig liegen die Nutzerdaten im Ordner `data/` neben der Anwendung. Über den Reiter `Konto` → Speicherort kann ein anderer Datenordner gewählt werden; bei einem Wechsel bietet BudgetManager eine sichere Datenübernahme mit Sicherheits-ZIP an.

Wichtig für den Updater: In der portablen Windows-ZIP heißt die App bewusst stabil `BudgetManager.exe`. Nicht in einen versionierten Namen umbenennen.

## Linux-Notstart bei Absturz im automatischen Start-Backup

Falls BudgetManager direkt nach dem Setup oder beim automatischen Backup nativ abstürzt, kann die Startprüfung einmalig deaktiviert werden:

```bash
BM_SKIP_STARTUP_AUTO_BACKUP=1 ./run.sh
```

Dadurch werden **keine manuellen Backups deaktiviert**. Der Schalter betrifft nur die automatische Backup-Prüfung beim Programmstart und dient zur Diagnose beziehungsweise zum sicheren Zugriff auf die Anwendung.

## Linux Portable / Entwicklung

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

Für Releases gibt es zusätzlich `BudgetManager-v2.2.63-portable-linux.zip`. Darin startet Linux über `./start-linux.sh`; die Binary heißt stabil `BudgetManager`.

## Update aus der App

1. BudgetManager öffnen.
2. Menü `Extras → Updates...` öffnen oder im Über-Dialog `Updates...` klicken.
3. Im Update-Fenster `Update jetzt ausführen` klicken.
4. Die App prüft online, lädt das Update, prüft die Datei und startet die Installation automatisch.
5. Unter Windows schließt sich BudgetManager. Danach öffnet sich ein kleines Update-Helferfenster.
6. Portable/Standalone: Programmdateien werden ersetzt. Installer-Version: die neue `BudgetManager_Setup_*.exe` wird im Update-Modus gestartet.

Wichtig: Datenbank, Einstellungen, Backups, Exporte und Updates bleiben im gewählten Datenordner erhalten.

## Manuelle Update-Prüfung für Entwickler

```bash
python main.py --check-update
python main.py --apply-update
```

Im normalen Windows-Betrieb sollte der Nutzer nicht mit diesen Befehlen arbeiten müssen. Die GUI erledigt den Ablauf.

## Release-Prüfung

```bash
python tools/sync_version.py --check
python -m compileall -q . -x '(^|/)(\.git|\.venv|__pycache__|build|dist)(/|$)'
python tools/i18n_audit.py
black --check model/
mypy model/
pytest tests/ -v
```

## Abnahme vor Final Release

- App startet auf Windows.
- App startet auf Linux/Fedora.
- Erststart-Assistent fragt Sprache, Region, Währung und Zahlenformat ab.
- Kategorie löschen fragt nach Daten-Aktion.
- Parent-Kategorie löschen hebt Children hoch.
- Kategorie-Rename aktualisiert Budget, Tracking, Favoriten, Warnungen, wiederkehrende Buchungen und Sparziele.
- Update-Fenster zeigt den Ablauf und startet die Installation automatisch nach erfolgreichem Download.
- Windows-Update ersetzt die EXE erst nach Schließen der App und startet anschließend neu.

---

## Hilfe / Wissensdatenbank / Mindmap

Die Hilfe ist lokal gebündelt und benötigt kein Internet:

- **F1**: durchsuchbares In-App-Handbuch
- **Ctrl+F1**: Tastenkürzel
- **Hilfe → HTML-Wissensdatenbank öffnen…**: `docs/help/index.html` im Browser
- **Hilfe → Informations-Laufplan / Mindmap anzeigen…**: `docs/help/mindmap.html` im Browser
- **Hilfe → Restore-Key anzeigen…**: Datenbank-/Restore-Key erneut anzeigen und kopieren

Der Restore-Key wird beim ersten Start angezeigt und muss extern gesichert werden. Er kann bei einer Wiederherstellung nötig sein, besonders wenn `users.json` fehlt oder eine verschlüsselte Datenbank aus einem Backup wieder geöffnet werden muss.

## Hinweis zu parallelen Python-Programmen

Der Single-Instance-Schutz von BudgetManager ist absichtlich datenordnerspezifisch. Er soll nur verhindern, dass zwei BudgetManager-Fenster dieselbe Budget-Datenbank gleichzeitig öffnen. Ein anderes Programm, z. B. ein Füller-Sammelprogramm mit eigenem Ordner, wird dadurch nicht blockiert.

Bei Tests bitte keine globalen Befehle wie `pkill -f "python main.py"` verwenden, wenn andere Python-Programme laufen.

### Testhinweis: mehrere Python-Programme

BudgetManager blockiert nur einen zweiten BudgetManager mit demselben Datenordner. Andere Python-Programme bleiben parallel nutzbar. In der Source-Version startet der Update-Dialog für interne Prüfungen nicht mehr `main.py`, sondern Updater-Module, damit kein falscher Eindruck weiterer BudgetManager-Instanzen entsteht.
