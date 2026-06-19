# BudgetManager v2.0.32 – Crash- und Skalierungsfix

## Anlass

Aus dem Windows-Crashlog:

```text
Windows fatal exception: access violation
File "main.py", line 654 in main

Windows fatal exception: access violation
File "views\tabs\budget_tab.py", line 1613 in _handle_leaf_ask_due
File "views\tabs\budget_tab.py", line 1473 in _on_item_changed
File "main.py", line 654 in main
```

Das ist kein normaler Python-Fehler, sondern ein nativer Qt/PySide-Crash. Solche Fehler entstehen typischerweise durch Reentrancy, Fokuswechsel oder QObject-Lebensdauerprobleme.

## Fix 1 – Budget-Detaildialog aus itemChanged entkoppelt

Problemstelle:

- Budget-Zelle wird editiert.
- `QTableWidget.itemChanged` feuert.
- Im selben Signalpfad wurde direkt ein `BudgetEntryDialog` geöffnet.
- Unter Windows/PyInstaller kann Qt dabei noch den Zell-Editor schließen, während bereits ein neues Modal-Fenster erzeugt wird.
- Ergebnis: sporadische native `access violation`.

Änderung:

- `_handle_leaf_ask_due()` setzt die Zelle nur noch auf den Datenbankwert zurück.
- Der Dialog wird per `QTimer.singleShot(0, ...)` in den nächsten Event-Loop-Tick verschoben.
- Der Dialog wird nicht-blockierend mit `open()` statt `exec()` geöffnet.
- Eine Python-Referenz wird gehalten, bis der Dialog fertig ist.
- Vor dem Öffnen wird ein noch aktiver Zell-Editor sicher geschlossen.
- Mehrfachauslösung durch nachlaufende Qt-Events wird über `_ask_due_dialog_pending` abgefangen.

## Fix 2 – Startup-Timer parented und crashsicher

Problemstelle:

- Der Setup-Assistent wurde über einen statischen `QTimer.singleShot(..., lambda...)` gestartet.
- Bei Start/Shutdown oder schnellen Fensterwechseln kann ein unparented Callback auf ein bereits zerstörtes Fenster zeigen.

Änderung:

- Setup-Start läuft jetzt über einen `QTimer(win)` mit `MainWindow` als QObject-Parent.
- Callback prüft `QApplication.instance()` und `_is_closing`.
- `RuntimeError` durch bereits zerstörte Qt-Objekte wird abgefangen.
- Startup-Auto-Backup nutzt ebenfalls einen parented Timer.

## Fix 3 – Skalierung / Portable / Windows / Linux

Änderungen:

- Früherer Default `tab_position = west` wird einmalig nach `north` migriert, solange der Nutzer die Position nicht bewusst gewählt hat.
- Tabs oben verhindern abgeschnittene vertikale Beschriftungen bei Windows 125/150 %, RDP, Linux Wayland/X11 und portabler Nutzung an fremden Monitoren.
- Tabbar nutzt Scrollbuttons und deaktiviert Text-Eliding.
- Cockpit-Tabellen erhalten robuste Mindestbreiten, Expanding-Policies und stabilisierte Spaltenbreiten.
- Cockpit-Panel-Reihenfolge korrigiert: doppelte Panel-Einträge durch versehentliches doppeltes `append()` entfernt.
- Fenstergeometrie wird weiter DPI-sicher in den verfügbaren Bildschirmbereich geklemmt.

## Version

Zentrale Version wurde auf `2.0.32` synchronisiert:

- `app_info.py`
- `version.json`
- `VERSION_INFO.txt`
- `installer/budgetmanager_setup.iss`
- `latest.json.template`
- `docs/latest.json.template`
- README/Dokumentation

## Tests

```text
python -m compileall -q .                         PASS
python tools/sync_version.py --check              PASS
pytest -q                                         160 passed, 2 skipped
```

## Einschränkung

Der konkrete Windows-Frozen-Smoke-Test kann in dieser Linux-Containerumgebung nicht ausgeführt werden. Die gefixten Stellen entsprechen aber exakt den im Crashlog genannten Stackframes und den bekannten Qt/PySide-Reentrancy-/QObject-Lifetime-Problemen.
