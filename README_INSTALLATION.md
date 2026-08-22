# 📦 BudgetManager v2.2.72 — Installation, Start & Update

Diese Anleitung beschreibt Installation, Start, Update und Notstart für Windows, Linux und den Betrieb aus dem Quellcode. Die Kurzfassung steht in [README.md](README.md), die Bedienung im [Benutzerhandbuch](docs/USER_GUIDE.de.md).

Die zentrale Versionsquelle ist `app_info.py`; alle hier genannten Dateinamen beziehen sich auf die aktuelle Version.

---

## Inhalt

- [Windows: welche Datei ist die richtige?](#windows-welche-datei-ist-die-richtige)
- [Prüfsummen kontrollieren](#prüfsummen-kontrollieren)
- [Windows Installer](#windows-installer)
- [Windows Portable](#windows-portable)
- [Linux](#linux)
- [macOS](#macos)
- [Update](#update)
- [Notstart und Diagnose](#notstart-und-diagnose)
- [LifePlanner-/LiveManager-Modul](#lifeplanner--livemanager-modul)
- [Hilfe und Restore-Key](#hilfe-und-restore-key)
- [Für Entwickler](#für-entwickler)

---

## Windows: welche Datei ist die richtige?

Im GitHub-Release liegen mehrere Dateien:

| Datei | Wofür |
| --- | --- |
| `BudgetManager_Setup_2.2.71.zip` | Empfohlen, wenn Browser oder Windows den direkten EXE-Download blockieren. |
| `BudgetManager_Setup_2.2.71.exe` | Direkter Installer. |
| `BudgetManager-v2.2.71-portable-windows.zip` | Portable Windows-Version ohne Installation. |
| `BudgetManager-v2.2.71-portable-linux.zip` | Portable Linux-Version. |
| `budgetmanager_2.2.71_Windows_x86_64.lpmodule` | Unsigned LifePlanner-/LiveManager-Modul für Windows. |
| `budgetmanager_2.2.71_Linux_x86_64.lpmodule` | Unsigned LifePlanner-/LiveManager-Modul für Linux. |
| `latest.json` / `latest.json.sig` | Update-Manifest und Ed25519-Signatur. |
| `SHA256SUMS.txt` | Prüfsummen aller Artefakte. |
| `BudgetManager-v<Version>.cdx.json` | CycloneDX-SBOM. |

Faustregel: Installer, wenn BudgetManager fest auf dem Rechner bleiben soll — portable ZIP, wenn der komplette Ordner mitwandern soll, zum Beispiel auf einem USB-Stick.

**Hinweis zur Signatur.** Die Authenticode-Signierung der Windows-Binaries hängt am Code-Signing-Zertifikat des Projekts. Solange sie fehlt, warnt Windows SmartScreen beim Start; die Prüfsummen aus `SHA256SUMS.txt` sind dann der verlässliche Nachweis. Davon unabhängig ist die Manifest-Signatur: Seit v2.2.65 trägt jedes Build einen eingebetteten Ed25519-Vertrauensanker, und ein Release ohne `latest.json.sig` kommt gar nicht erst durch das Gate. Der In-App-Updater prüft die Signatur immer und verwirft ein Update ohne gültige Signatur.

---

## Prüfsummen kontrollieren

PowerShell im Download-Ordner öffnen:

```powershell
Get-FileHash .\BudgetManager_Setup_2.2.71.exe -Algorithm SHA256
```

Den angezeigten Hash mit der passenden Zeile in `SHA256SUMS.txt` vergleichen.

Falls Windows die Datei nach dem Download blockiert:

```powershell
Unblock-File .\BudgetManager_Setup_2.2.71.exe
```

Unter Linux:

```bash
sha256sum -c SHA256SUMS.txt --ignore-missing
```

---

## Windows Installer

1. `BudgetManager_Setup_2.2.71.zip` herunterladen.
2. ZIP entpacken.
3. Optional, aber empfohlen: SHA-256 gegen `SHA256SUMS.txt` prüfen.
4. `BudgetManager_Setup_2.2.71.exe` starten.
5. Datenverzeichnis wählen.
6. Sprache, Währung und bevorzugten Buchungstag auswählen.
7. BudgetManager starten.

Der Installer schreibt `installation.json` in den Programmordner und nutzt den gewählten Datenordner für Nutzerdaten und Update-Staging. Bestehende Einstellungen werden nicht überschrieben.

Für eine unbeaufsichtigte Installation unterstützt das Setup die üblichen Inno-Setup-Schalter:

```powershell
.\BudgetManager_Setup_2.2.71.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR="C:\Programme\BudgetManager" /DATA_DIR="D:\BudgetManagerDaten" /LANG=german
```

Genau dieser Ablauf — Silent-Install, Start der installierten App, Selbsttest, Silent-Uninstall — wird im Release-Workflow automatisch geprüft.

---

## Windows Portable

1. `BudgetManager-v2.2.71-portable-windows.zip` herunterladen.
2. ZIP in einen normalen Benutzerordner entpacken, zum Beispiel `Dokumente\BudgetManager`, oder auf einen USB-Stick.
3. `start-windows.cmd` oder `BudgetManager.exe` starten.

Standardmässig liegen die Nutzerdaten im Ordner `data/` neben der Anwendung. Über den Reiter `Konto` → Speicherort kann ein anderer Datenordner gewählt werden; bei einem Wechsel bietet BudgetManager eine sichere Datenübernahme mit Sicherheits-ZIP an.

Wichtig für den Updater: In der portablen Windows-ZIP heisst die App bewusst stabil `BudgetManager.exe`. Bitte nicht in einen versionierten Namen umbenennen — sonst findet das Update die zu ersetzende Datei nicht.

Nicht in `C:\Program Files` entpacken. Dort fehlen die Schreibrechte für Daten und Update-Staging.

---

## Linux

### Portable Paket

1. `BudgetManager-v2.2.71-portable-linux.zip` herunterladen und entpacken.
2. Starten:

```bash
./start-linux.sh
```

Die Binary heisst darin stabil `BudgetManager` und darf ebenfalls nicht umbenannt werden.

Fehlen Qt-Systembibliotheken, meldet der Start einen Plugin-Fehler. Nachinstallieren:

```bash
# Fedora
sudo dnf install mesa-libEGL libglvnd-glx libxkbcommon-x11 xcb-util-cursor dbus-libs fontconfig

# Debian/Ubuntu
sudo apt install libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 libdbus-1-3 libfontconfig1
```

### Aus dem Quellcode

```bash
git clone https://github.com/sloogy/Budgetmanager.git
cd Budgetmanager
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

`./run.sh` erledigt dasselbe automatisch: Es startet eine vorhandene Binary, legt sonst `.venv` an, installiert die Abhängigkeiten und startet den Quellcode. Voraussetzung ist Python 3.11 oder neuer.

### Wayland

Unter einer Wayland-Sitzung wechselt BudgetManager automatisch auf das XCB-/XWayland-Backend, weil Qt beim Schliessen kleiner Dialoge oder Kontextmenüs sonst nativ abstürzen kann. Wer natives Wayland ausprobieren möchte, startet mit `BM_ALLOW_WAYLAND=1`; umgekehrt erzwingt `BM_FORCE_XCB=1` das XCB-Backend auch ausserhalb einer Wayland-Sitzung.

---

## macOS

Für macOS gibt es kein fertiges Release-Paket und keinen automatischen Update-Weg. Der Start aus dem Quellcode funktioniert:

```bash
./start-macos.sh
```

Das Skript benötigt Python 3.12 oder neuer, legt `.venv` an, installiert die Abhängigkeiten und startet `main.py`.

---

## Update

### Aus der App heraus

1. BudgetManager öffnen.
2. Menü `Extras → Updates…` öffnen oder im Über-Dialog auf `Updates…` klicken.
3. Im Update-Fenster `Update jetzt ausführen` klicken.
4. Die App prüft online, lädt das Paket, verifiziert Signatur und Prüfsumme und startet die Installation. Jeder Schritt steht im Log des Fensters.
5. Unter Windows schliesst sich BudgetManager, danach übernimmt ein kleines Update-Helferfenster — die laufende EXE kann sich nicht selbst überschreiben.
6. Portable/Standalone: Die Programmdateien werden ersetzt. Installer-Version: Die neue `BudgetManager_Setup_*.exe` wird im Update-Modus gestartet, damit Uninstaller, Startmenü und Installationspfad sauber bleiben.

Datenbank, Einstellungen, Backups, Exporte und der Update-Cache bleiben im gewählten Datenordner erhalten.

### Alte Installationen

Den eingebetteten Vertrauensanker für Update-Signaturen gibt es erst ab v2.2.65. Ältere Installationen melden beim Update „Kein eingebetteter Update-Public-Key gefunden“ und müssen einmal von Hand auf die aktuelle Version gebracht werden — danach läuft das In-App-Update wieder von selbst.

Für v2.2.61 liegt dem Release zusätzlich `BudgetManager-v2.2.61-Trust-Bridge.ps1` bei. Das Skript hinterlegt ausschliesslich den öffentlichen Ed25519-Schlüssel in der bestehenden Installation und startet danach den unveränderten, signaturprüfenden Updater. Ein vorhandener abweichender Key wird nicht überschrieben, der private Signierschlüssel ist nie Bestandteil des Skripts, und eine Neuinstallation ist nicht nötig.

### Manuelle Prüfung für Entwickler

```bash
python main.py --check-update
python main.py --apply-update
```

Im normalen Betrieb sind diese Befehle nicht nötig; die GUI erledigt den Ablauf.

---

## Notstart und Diagnose

Alle Schalter sind Umgebungsvariablen. Sie verändern keine Daten und gelten nur für den jeweiligen Start.

| Variable | Wirkung |
| --- | --- |
| `BM_DISABLE_COCKPIT_CHARTS=1` | Startet ohne die beiden Cockpit-Diagramme. |
| `BM_SKIP_STARTUP_AUTO_BACKUP=1` | Überspringt nur die automatische Backup-Prüfung beim Start. |
| `BM_ALLOW_WAYLAND=1` | Natives Wayland statt XCB-Fallback. |
| `BM_FORCE_XCB=1` | Erzwingt das XCB-Backend. |
| `BUDGETMANAGER_DATA_DIR=…` | Setzt den Datenordner explizit. |

### Absturz im Cockpit

Falls ein bestimmter Grafiktreiber Probleme mit QtCharts macht:

```bash
BM_DISABLE_COCKPIT_CHARTS=1 ./run.sh
```

Budget, Buchungen, Kategorien, Übersicht und Backups bleiben dabei voll nutzbar. Der Cockpit-Verlauf ist zusätzlich gegen den nativen QtCharts-Absturz aus v2.2.54 gehärtet: Serien und Achsen werden in-place aktualisiert statt bei jedem Refresh zerstört, und ersetzte Diagramme werden erst nach dem nativen Qt-`destroyed`-Signal freigegeben — nie während laufender Paint- oder Layout-Ereignisse.

### Absturz beim Start-Backup

```bash
BM_SKIP_STARTUP_AUTO_BACKUP=1 ./run.sh
```

Manuelle Backups bleiben dabei aktiv; der Schalter betrifft ausschliesslich die automatische Backup-Prüfung beim Programmstart.

### Kacheln im Cockpit anordnen

Für eine eigene Anordnung oben im Cockpit **Kacheln frei anordnen** aktivieren. Danach die Kachel an ihrer gesamten Kopfzeile oder am Griff `≡` nach oben, unten oder in die andere Spalte ziehen. Ab 720 px Breite stehen zwei gleich breite Zielspalten zur Verfügung. Reihenfolge und Spaltenzuordnung werden nach jedem Drop gespeichert; Tabellen, Buttons und Diagramme innerhalb der Kacheln bleiben normal bedienbar.

### Mehrere Python-Programme parallel

Der Single-Instance-Schutz ist absichtlich datenordnerspezifisch. Er verhindert nur, dass zwei BudgetManager-Fenster dieselbe Datenbank gleichzeitig öffnen. Ein anderes Programm mit eigenem Ordner wird nicht blockiert.

Bei Tests deshalb bitte keine globalen Befehle wie `pkill -f "python main.py"` verwenden, wenn andere Python-Programme laufen. Besser gezielt die PID aus `data/budgetmanager.instance.lock/pid` prüfen. In der Source-Version startet der Update-Dialog für interne Prüfungen keine zweite `main.py`, sondern Updater-Module.

---

## LifePlanner-/LiveManager-Modul

Die `.lpmodule`-Pakete im Release sind bewusst **unsigned**; beim lokalen Import ist die Vertrauenswarnung des Hosts ausdrücklich zu bestätigen. Jedes Paket hat eine eigene SHA-256-Datei und wird vor dem Upload strukturell geprüft.

Als Modul nutzt BudgetManager die vom Host vorgegebenen, getrennten Daten- und Bridge-Ordner (`BUDGETMANAGER_DATA_DIR`, `LIFEPLANNER_BRIDGE_DIR`) und übernimmt beim Start dessen Designprofil (`LIFEPLANNER_THEME_FILE`, Format `lifeplanner.theme.v1`), ohne die lokal gespeicherte Profilwahl zu überschreiben. Standalone gestartet gilt weiterhin die eigene Wahl. Die Brücke zu FountainPen Manager wird nach jeder Datenänderung, beim Schliessen und einmal beim Start nachgezogen; Ordner und Dateien liegen mit `0700`/`0600` im Benutzerverzeichnis.

---

## Hilfe und Restore-Key

Die Hilfe ist lokal gebündelt und benötigt kein Internet:

- **F1** — durchsuchbares In-App-Handbuch
- **Ctrl+F1** — Tastenkürzel
- **Hilfe → HTML-Wissensdatenbank öffnen…** — [`docs/help/index.html`](docs/help/index.html) im Browser
- **Hilfe → Informations-Laufplan / Mindmap anzeigen…** — [`docs/help/mindmap.html`](docs/help/mindmap.html) im Browser
- **Hilfe → Restore-Key anzeigen…** — Datenbank-/Restore-Key erneut anzeigen und kopieren

Der Restore-Key wird beim ersten Start angezeigt und muss ausserhalb des Programmordners gesichert werden. Er wird bei einer Wiederherstellung gebraucht, besonders wenn `users.json` fehlt oder eine verschlüsselte Datenbank aus einem Backup wieder geöffnet werden soll.

---

## Für Entwickler

### Release-Prüfung vor dem Tag

```bash
python tools/sync_version.py --check
python tools/verify_hashed_lock.py
python -m compileall -q . -x '(^|/)(\.git|\.venv|__pycache__|build|dist)(/|$)'
python tools/exception_audit.py
python -m ruff check . --select E9,F63,F7,F82
python -m black --check model/
python -m mypy model/
python tools/i18n_audit.py
python -m pytest tests/ -q
python tools/clean_release_tree.py
python tools/lint_procedure_check.py
```

Die vollständige Liste inklusive Coverage-, Bandit- und Audit-Gates steht in [docs/open-tasks.md](docs/open-tasks.md), der Release-Ablauf in [docs/release-checklist.md](docs/release-checklist.md) und die Signaturkette in [docs/release-signing.md](docs/release-signing.md).

### Abnahme vor dem Final Release

- App startet auf Windows und auf Linux/Fedora.
- Erststart-Assistent fragt Sprache, Region, Währung und Zahlenformat ab.
- Kategorie löschen fragt nach der Daten-Aktion; eine Parent-Kategorie hebt ihre Children hoch.
- Kategorie-Rename aktualisiert Budget, Tracking, Favoriten, Warnungen, wiederkehrende Buchungen und Sparziele.
- Update-Fenster zeigt den Ablauf und startet die Installation nach erfolgreichem Download automatisch.
- Windows-Update ersetzt die EXE erst nach dem Schliessen der App und startet anschliessend neu.
- `latest.json` und `latest.json.sig` werden gemeinsam geprüft.
- Portable Windows- und Linux-Pakete starten auf einem sauberen System.
