# 📦 BudgetManager v2.1.1 — Installation, Start & Update


## Hinweis zu v2.1.1

Diese README gehört zu v2.1.1. Enthalten sind der final gehärtete Portable-Updater mit stabilen Startdateien, synchronisierte Release-Dokumentation, i18n-Härtungen sowie Konto-Hub, frei wählbarer Datenordner mit optionaler Datenübernahme, PBKDF2-Härtung mit Legacy-Upgrade, Autobuchungs-Artfilter, Deckungswarnungen, Schnelleingabe-Suche und Budget-Mehrfachauswahl. Die zentrale Versionsquelle ist `app_info.py`.

## Windows: empfohlener Download

Für Windows gibt es im GitHub Release mehrere Dateien:

- `BudgetManager_Setup_2.1.0.zip` — empfohlen, wenn Browser oder Windows den direkten EXE-Download blockieren.
- `BudgetManager_Setup_2.1.0.exe` — direkter Installer.
- `BudgetManager-v2.1.0-portable-windows.zip` — portable Windows-Version ohne Installation.
- `BudgetManager-v2.1.0-windows.exe` — direkte Einzel-EXE für Standalone-Nutzung.
- `SHA256SUMS.txt` — Prüfsummen zur Kontrolle.

Windows SmartScreen kann neue, unsignierte Open-Source-Installer blockieren, weil der Herausgeber noch keine ausreichende Reputation hat. Deshalb wird der Installer zusätzlich als ZIP bereitgestellt.

### Prüfsumme unter Windows prüfen

PowerShell im Download-Ordner öffnen:

```powershell
Get-FileHash .\BudgetManager_Setup_2.1.0.exe -Algorithm SHA256
```

Den angezeigten Hash mit `SHA256SUMS.txt` vergleichen.

Falls Windows die Datei nach dem Download blockiert:

```powershell
Unblock-File .\BudgetManager_Setup_2.1.0.exe
```

## Windows Installer

1. `BudgetManager_Setup_2.1.0.zip` herunterladen.
2. ZIP entpacken.
3. Optional: SHA256 gegen `SHA256SUMS.txt` prüfen.
4. `BudgetManager_Setup_2.1.0.exe` starten.
5. Datenverzeichnis wählen.
6. Sprache, Währung und bevorzugten Buchungstag auswählen.
7. BudgetManager starten.

Der Installer schreibt `installation.json` in den Programmordner und nutzt den gewählten Datenordner für Nutzerdaten und Update-Staging. Bestehende Einstellungen werden nicht überschrieben.

## Windows Portable

1. `BudgetManager-v2.1.0-portable-windows.zip` herunterladen.
2. ZIP in einen normalen Benutzerordner entpacken, zum Beispiel `Dokumente\BudgetManager` oder auf einen USB-Stick.
3. `start-windows.cmd` oder `BudgetManager.exe` starten.

Standardmäßig liegen die Nutzerdaten im Ordner `data/` neben der Anwendung. Über den Reiter `Konto` → Speicherort kann ein anderer Datenordner gewählt werden; bei einem Wechsel bietet BudgetManager eine sichere Datenübernahme mit Sicherheits-ZIP an.

Wichtig für den Updater: In der portablen Windows-ZIP heißt die App bewusst stabil `BudgetManager.exe`. Nicht in einen versionierten Namen umbenennen.

## Linux Portable / Entwicklung

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

Für Releases gibt es zusätzlich `BudgetManager-v2.1.0-portable-linux.zip`. Darin startet Linux über `./start-linux.sh`; die Binary heißt stabil `BudgetManager`.

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
