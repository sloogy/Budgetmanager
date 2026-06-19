# BudgetManager

## Neu in v2.0.31

- Final-Release-Härtung für Update-Dialog, Frozen-CLI und portable ZIP-Struktur.
- Stabile Startdateien im Portable-ZIP: `BudgetManager.exe` und `BudgetManager`.
- Doku-/Help-/Manifest-Versionen synchron auf v2.0.31.
- Zusätzliche dynamische Dialogtexte über i18n statt harter deutscher Strings.
- Konto-Hub für Konto, Speicherort, Backup/Wiederherstellung und Datenbank-Wartung.
- Frei wählbarer Datenordner mit optionaler sicherer Datenübernahme.
- PBKDF2-Härtung mit automatischem Legacy-Upgrade für Vorab-Konten.
- Autobuchungs-Artfilter, optionale Budgetposten und Deckungswarnungen.
- Schnelleingabe mit Suche/Dropdown und validierter Kategorieauflösung.

## Cockpit-Startseite

Das Cockpit fasst die wichtigsten Punkte zusammen: Monatsstatus, Favoriten, aktive Sparziele, Budget-Ampel, offene Monatsbuchungen und letzte 10 Buchungen. Es ist bewusst kompakt und frei gestaltbar: Bereiche lassen sich im Cockpit oder unter `Ansicht → Anzeigen` ein-/ausblenden. Auch Hauptreiter können ausgeblendet werden, damit Einsteiger nicht von zu vielen Tabs erschlagen werden.
## v2.0.31 — Feature-Übersicht

BudgetManager ist eine lokale Desktop-App für Budgetplanung, Buchungen, Kategorien, Fixkosten, wiederkehrende Zahlungen, Sparziele und Auswertungen.

## Kernfunktionen

### Budgetplanung

- Jahresbudget mit 12 Monatswerten und Totalspalte.
- Typen: Einkommen, Ausgaben, Ersparnisse.
- Haupt- und Unterkategorien.
- Fixkosten- und Wiederkehrend-Markierung.
- Fälligkeitstag je Kategorie.
- Budget-Saldo und Monats-/Jahresübersichten.
- Budgetvorschläge auf Basis historischer Buchungen.
- Optionales Drag & Drop in der Budgetübersicht zum Umhängen von Kategorien.

### Kategorien

- Kategorien-Manager mit Baumansicht.
- Drag & Drop für Parent/Child-Ebenen.
- Kontextmenü zum Verschieben, Umbenennen, Löschen und Zur-Hauptkategorie-Machen.
- Schutz gegen Self-Parenting, Typ-Mischung und Zyklen.
- Bulk-Bearbeitung für Fixkosten, Wiederkehrend und Fälligkeitstag.
- Import/Export von Kategorien über Excel/CSV.

### Tracking / Buchungen

- Buchungen erfassen, bearbeiten und löschen.
- Filter nach Jahr, Monat, Zeitraum, Typ und Kategorie.
- Schnellfilter für letzte 14/30 Tage.
- Tags und Detailtexte.
- Import/Export für Buchungen.
- Direkte Buchung wiederkehrender Einträge.

### Wiederkehrende Buchungen und Fixkosten

- Fällige Buchungen erkennen.
- Fixkosten aus Budgetwerten übernehmen.
- Monatliches Fälligkeitsdatum inklusive Monatsende.
- Optionaler bevorzugter Standard-Buchungstag.
- Einstellung „kein bevorzugter Tag“ für manuelle Pflege.

### Sparziele und Auswertungen

- Sparziele als eigener Bereich.
- Übersicht über Budget vs. Ist-Buchungen.
- Diagramme und Tabellen im Übersichtstab.
- Verschiebbare/skalierbare Panels.

### Einstellungen und Komfort

- Mehrsprachig: Deutsch, Englisch, Französisch.
- Währung: CHF, EUR, USD, GBP.
- Themes und Designprofile.
- Tab-Layout und Fensterzustand werden gespeichert.
- Backup/Restore inklusive Einstellungen.
- Persistentes Undo/Redo.
- Multi-Account-System mit Quick/PIN/Passwort-Modus.

## Release-Härtungen

- Cockpit-Rechtsklick-Menüs, Budgetwarnungen, Wayland/xcb-Fallback und Keine-Daten-Hinweise sind enthalten.
- Restore-/Selbstheilungslogik verhindert Sackgassen nach falschem Restore-Key oder defektem Konto.
- Reproduzierbarkeit ist über `requirements.lock`, Versions-Sync, i18n-Audit und Regressionstests abgesichert.

## Wichtige Grundfunktionen

- Fixkosten/Wiederkehrend sauber getrennt:
  - Fix + Wiederkehrend = echter fixer Monatsbetrag.
  - Fix ohne Wiederholung = variable Rückstellung/Kostenblock, Betrag editierbar.
  - Wiederkehrend ohne Fix = variable wiederkehrende Buchung, Betrag editierbar.
- Fix-only und recurring-only werden erst abgeschlossen, wenn der Monatsbudgetbetrag erreicht ist.
- Tracker-Picker gruppiert Kategorien übersichtlicher: Favoriten, häufig manuell gebucht, normale Buchungen, variable Fix-/Wiederkehrend-Gruppen und echte Fixkosten.
- Fixkosten-Forecast geschützt: 0-Monate senken Fixkosten nicht allein; echte wiederholte Buchungen bleiben auswertbar.
- Installer-/Erststart-Abfrage für Sprache, Währung und bevorzugten Buchungstag bleibt korrekt verdrahtet.
- Robustes Settings-Laden mit Default-Merge für Teil-JSONs.
- Budgetübersicht: Drag & Drop optional ein-/ausschaltbar.
- Einstellungen → Verhalten: Dropdown für Budgetvorschlags-Fenster.
- Kategorien-Manager: Dropdown für Fälligkeitstage.
- Release-Paket bereinigt: keine AI-Arbeitsordner, keine lokalen Settings, keine veralteten Merge-/Analyseberichte.

## Technik

- Python 3.11+
- PySide6 / Qt 6
- SQLite mit automatischen Migrationen
- JSON-basierte i18n-Dateien unter `locales/`
- Zentrale App-Version in `app_info.py`
- GitHub-Actions-Build für Windows/Linux/Portable-ZIP

## Tests

```bash
python tools/sync_version.py --check
python -m compileall -q . -x '(^|/)(\.git|\.venv|__pycache__|build|dist)(/|$)'
pytest tests/ -v
```


## Übersicht: zusätzliche sinnvolle Graphen

- Monatsverlauf: Ausgaben Budget vs. gebucht.
- Monatsbilanz: echte Bilanz vs. geplante Bilanz.
- Top-Buchungen: größte Buchungen im gewählten Zeitraum.

Ziel: Ausreißer und Trends erkennen, ohne die Übersicht zu überladen.

### Sparziele im Workflow

Sparziele sind jetzt klarer eingebettet: im Budget gibt es einen kleinen 🎯-Einstieg, im Tracking erscheint bei aktiven Zielen ein ausblendbares Panel mit Fortschrittsbalken und Doppelklick zum Ziel, und die Übersicht bleibt die Kontrollstelle.

### Sparziel-Entnahme / Geld herausbuchen

Geld aus einem Sparziel wird als **negative Ersparnisse-Buchung** auf die mit dem Sparziel verknüpfte Kategorie gebucht, z. B. `-500 CHF` auf `Ersparnisse → Hochzeit`. Negative Beträge sind dafür bei `Ersparnisse` erlaubt; bei `Ausgaben` bleiben negative Beträge bewusst gesperrt.

Sparziele haben jetzt echte Grenzen: Eine Entnahme darf den Stand nicht unter `0 CHF` ziehen, und eine Einzahlung darf das Ziel nicht über `100 %` füllen. Bei beiden Fällen wird die Buchung blockiert und eine Meldung angezeigt.

Best Practice: Sparziel zuerst **freigeben**, dann die Entnahme buchen und das Ziel abschließen, wenn es erledigt ist.

### Sicherer Start

Auto-Speichern und Auto-Backup sind beim ersten Start aktiv.
