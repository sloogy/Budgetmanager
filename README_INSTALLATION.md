# 📦 BudgetManager v2.0.30 — Installation, Start & Update


## Hinweis zu v2.0.30

Diese README gehört zu v2.0.30. Enthalten sind der final gehärtete Portable-Updater mit stabilen Startdateien, synchronisierte Release-Dokumentation, i18n-Härtungen sowie Konto-Hub, frei wählbarer Datenordner mit optionaler Datenübernahme, PBKDF2-Härtung mit Legacy-Upgrade, Autobuchungs-Artfilter, Deckungswarnungen, Schnelleingabe-Suche und Budget-Mehrfachauswahl. Die zentrale Versionsquelle ist `app_info.py`.

## Windows Portable

1. `BudgetManager-v2.0.30-portable.zip` herunterladen.
2. ZIP in einen eigenen Ordner entpacken, z. B. `C:\BudgetManager` oder auf einen USB-Stick.
3. `BudgetManager.exe` starten.

Standardmäßig liegen die Nutzerdaten im Ordner `data/` neben der Anwendung. Über den Reiter `Konto` → Speicherort kann ein anderer Datenordner gewählt werden; bei einem Wechsel bietet BudgetManager eine sichere Datenübernahme mit Sicherheits-ZIP an.

## Windows Installer

1. `BudgetManager_Setup_2.0.30.exe` starten, falls ein Installer-Asset gebaut wurde.
2. Installation abschließen.
3. BudgetManager über Startmenü/Desktop starten.

## Linux / Entwicklung

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

## Update aus der App

1. BudgetManager öffnen.
2. Menü `Extras → Updates...` öffnen oder im Über-Dialog `Updates...` klicken.
3. Im Update-Fenster `Update jetzt ausführen` klicken.
4. Die App prüft online, lädt das Update, prüft die Datei und startet die Installation automatisch.
5. Unter Windows schließt sich BudgetManager. Danach öffnet sich ein kleines Update-Helferfenster, kopiert die neuen Dateien und startet BudgetManager neu.

Wichtig: Die Datenbank und Einstellungen im Ordner `data/` werden beim Update nicht gelöscht.

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
- **Hilfe → Informations-Laufplan / Mindmap anzeigen…**: sprachabhängige lokale Mindmap im Browser (`mindmap.de.html`, `mindmap.en.html`, `mindmap.fr.html`; `mindmap.html` bleibt deutscher Fallback)
- **Hilfe → Restore-Key anzeigen…**: Datenbank-/Restore-Key erneut anzeigen und kopieren

Der Restore-Key wird beim ersten Start angezeigt und muss extern gesichert werden. Er kann bei einer Wiederherstellung nötig sein, besonders wenn `users.json` fehlt oder eine verschlüsselte Datenbank aus einem Backup wieder geöffnet werden muss.

## Hinweis zu parallelen Python-Programmen

Der Single-Instance-Schutz von BudgetManager ist absichtlich datenordnerspezifisch. Er soll nur verhindern, dass zwei BudgetManager-Fenster dieselbe Budget-Datenbank gleichzeitig öffnen. Ein anderes Programm, z. B. ein Füller-Sammelprogramm mit eigenem Ordner, wird dadurch nicht blockiert.

Bei Tests bitte keine globalen Befehle wie `pkill -f "python main.py"` verwenden, wenn andere Python-Programme laufen.

### Testhinweis: mehrere Python-Programme

BudgetManager blockiert nur einen zweiten BudgetManager mit demselben Datenordner. Andere Python-Programme bleiben parallel nutzbar. In der Source-Version startet der Update-Dialog für interne Prüfungen nicht mehr `main.py`, sondern Updater-Module, damit kein falscher Eindruck weiterer BudgetManager-Instanzen entsteht.
