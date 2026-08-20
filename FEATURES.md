## Neu in v2.2.62

- Unsigned LifePlanner-/LiveManager-`.lpmodule`-Pakete für Windows x86_64 und Linux x86_64 mit manueller Vertrauensbestätigung beim lokalen Import.
- Eigene SHA-256-Datei und Paketstrukturprüfung für jedes Modulrelease.
- Gemeinsamer taggesteuerter Releaseweg für Desktop-, Installer- und Modulpakete.

## Neu in v2.2.61

- Sicherer QtCharts-Lebenszyklus beim Aktualisieren aller Übersichtsdiagramme.
- Geprüfter Windows-Installer mit Silent-Install, App-Start und Silent-Uninstall.
- Versionssynchrone Hash-Lockfiles für PySide6 6.11.1 und die Releasewerkzeuge.

- Kacheln im Cockpit lassen sich im manuellen Modus über die gesamte Kopfzeile oder den Griff `≡` verschieben.
- Zwei gleich breite Zielspalten bleiben bereits ab 720 px verfügbar; dadurch funktioniert das Umordnen auch in normalen Fenstergrössen.
- Spaltenwechsel und Reihenfolge werden nach jedem Drop dauerhaft gespeichert.
- Interaktive Inhalte in der Kachel bleiben von der Drag-Zone getrennt.

## Neu in v2.2.54

- Cockpit-Flächenverlauf gegen native QtCharts-Segfaults gehärtet.
- `QLineSeries`, `QAreaSeries` und beide Achsen bleiben über die gesamte Widget-Lebensdauer erhalten.
- Neue Buchungen ersetzen nur noch atomar die Datenpunkte; kein `removeAllSeries()` und kein Achsen-Neuaufbau mehr.
- Optionaler Rettungsstart mit `BM_DISABLE_COCKPIT_CHARTS=1 ./run.sh`.

## Neu in v2.2.53

- Kritischen nativen Qt-/PySide6-Segfault nach Abschluss des Setup-Assistenten behoben.
- Dialogabbau und verschobenes Auto-Backup laufen in getrennten, am Hauptfenster gebundenen Timer-Schritten.
- Die Setup-Dialogreferenz bleibt bis nach dem nativen Schliesspfad erhalten; ein Abschluss-Guard verhindert Doppelaufrufe.
- Drei neue Regressionstests schützen den Ablauf dauerhaft.
- Notstart über `BM_SKIP_STARTUP_AUTO_BACKUP=1 ./run.sh`, ohne manuelle Backups abzuschalten.

## Neu in v2.2.52

- Cockpit-Modul startet wieder zuverlässig; `DEFAULT_PANEL_COLUMNS` greift nicht mehr aus einer Klassen-Comprehension auf Klassenattribute zu.
- Statischer Regressionstest schützt diese Python-Scope-Falle dauerhaft.

## Neu in v2.2.51

- Einfach-/Erweitert-Modus für eine ruhige, ADHS-freundliche Startoberfläche ohne Funktionsverlust.
- XLSX- und A4-PDF-Berichte zusätzlich zu CSV/TXT.
- Anonymisierte Diagnose-ZIP mit Qt-, Skalierungs- und Datenbank-Gesundheitsdaten.
- Atomare, verifizierte Restore-Kopie bei Schreib-, Rechte- und Datenträgerfehlern.
- Voll-Coverage-Gate, kritische Modulgrenzen, 50’000-Buchungen-Benchmark und visuelle Plattform-Screenshots.
- Progressive strengere Typprüfung der sicherheitskritischen Module.

## Neu in v2.2.49

- Vollständige Integritätsprüfung für Datenbank, Einstellungen und das zum Backup gehörende Benutzerkonto.
- Selbstkonsistente Konto-Backups: Bei mehreren lokalen Konten wird nur der Eintrag der gesicherten Datenbank aufgenommen.
- Speicherstabile Konto-Wiederherstellung durch gestreamtes Entpacken mit Größenlimit.
- Wichtig: Die eingebetteten SHA-256-Werte erkennen Beschädigungen und unveränderte Manipulationen, beweisen aber nicht die Herkunft eines Backups. Importiere vollständige Konto-Backups nur aus vertrauenswürdiger Quelle.

## Neu in v2.2.47

- Vollständiges Cockpit-Kapitel in DE/EN/FR und als eigenes Thema in der In-App-Hilfe.
- Verständliche Erklärung von KPI-Trends, Ring-/Flächendiagramm, Automatikmodus, fixiertem Drag-and-drop und responsiven Spalten.
- Atomare Layout-Persistenz aus v2.2.44 bleibt erhalten.
- Enterprise-DAU-Theme-Audit erkennt drei- und sechsstellige fest codierte Hexfarben.
- Release-Dokumentation, Installer- und Manifest-Beispiele synchronisiert.

## Neu in v2.2.44

- Beste Ansätze beider v2.2.43-Zweige konsolidiert, ohne den DesignManager zu umgehen.
- Cockpit-Hilfe in DE/EN/FR erklärt Automatik, Fixierung, Drag-and-drop, Responsive-Spalten und Reset vollständig.
- Atomare Persistenz zusammengehöriger Layoutwerte über `Settings.set_many()`.
- Eigenes Regression-Gate für historische Versionsreferenzen und ein kombiniertes Dashboard-/DesignManager-Gate.
- Diagramm-Kachel, Theme-Neuaufbau und beide Layout-Settings-Schemata bleiben erhalten.

## Neu in v2.2.43

- Zusammenführung von Dashboard-Optik und intelligentem Kachellayout.
- Automatikmodus: leere Kacheln schrumpfen und sinken innerhalb ihrer Spalte.
- Fixierter Modus: Drag-and-drop über einen eigenen Griff, inklusive Spaltenwechsel und Persistenz.
- Neuer Auswertungsbereich mit Ringdiagramm und kumuliertem Monatsverlauf.
- KPI-Karten mit Unicode-Symbolen und Vormonats-Trends.
- Sämtliche Dashboard-Farben und Zustände folgen dem DesignManager; keine festen Farben in Cockpit, Kacheln oder Diagrammen.
- Kompatibilitätsmigration für Layout-Einstellungen aus v2.2.41 und v2.2.42.

## Neu in v2.2.42

- Neues Designprofil „Mitternacht – Violett“.
- Kartenoptik, KPI-Trends, Ringdiagramm und Flächenverlauf.
- Diagramme ohne Animation als Wayland-Absturzschutz.

## Neu in v2.2.32

- Fehleingabe-Härtung: unsinnige Beträge wie „inf" oder „nan" werden in jedem Eingabefeld abgewiesen, statt Summen und Auswertungen unbemerkt zu verfälschen.
- Sparziele weisen nicht-endliche Zielbeträge klar mit Meldung ab (de/en/fr).

## Neu in v2.2.31

- Release-Gate schärft die Artefaktprüfung: generierte Ordner werden jetzt zuverlässig erkannt, das Auslieferungs-ZIP bleibt frei von `__pycache__`/`.pytest_cache`.
- Einheitlicher Tags-Rückgabetyp: alle Lesemethoden liefern `Tag`-Objekte, die zusätzlich Wörterbuch-Zugriff unterstützen.

## Neu in v2.2.30

- 10.000-Loop Enterprise-Release-Audit mit reproduzierbaren Seeds.
- Korrekte feste Tags nach Kategorienwechsel.
- Vollständige Tag-Wiederherstellung bei Undo/Redo von Buchungen.
- Echte Buchungsquelle bleibt in Listen, Filtern und Auswertungen erhalten.

## Neu in v2.2.24

- **Lesbarkeit:** Alle 25 integrierten Designs erfüllen für UI-Text mindestens WCAG-AA-Kontrast 4,5:1.
- **Sichere Eingabe:** Vorbefüllte Felder werden beim automatischen Fokus nicht mehr komplett markiert.
- **Screenreader:** Formularbeschriftungen werden als zugängliche Namen erkannt; Icon-Aktionen nutzen Tooltip-Metadaten für den Enter-Schutz.
- **Konsistente Sprache:** Ein Sprachwechsel wird vollständig beim nächsten Start angewendet statt teilweise in der laufenden Oberfläche.
- **Release-Sauberkeit:** Der Cleaner entfernt testweise erzeugte Settings, Datenbanken, Nutzerdateien und private Theme-Profile.
- **Prüfwerkzeuge überall lauffähig:** Enterprise-UI-Audit und Regressionstests laufen auch ohne Qt-Umgebung: Qt-unabhängige Tests bleiben aktiv, Qt-Fallbacks werden transparent als reduzierte WARN-Prüfung ausgewiesen; auf dem Zielsystem läuft die volle Tiefe.

## Neu in v2.2.22

- **Fokus-Modus wirkt jetzt wirklich:** Neuinstallationen starten mit dem reduzierten Cockpit; die Modus-Anzeige stimmt mit dem Sichtbaren ueberein. Bestehende Layouts bleiben unveraendert.
- **Ruhigeres Umschalten:** Ein Panel ein- oder ausblenden aendert genau dieses Panel.
- **Sichere Enter-Taste in drei Sprachen:** Auch franzoesische und englische Loesch-/Reset-Knoepfe werden nie zur Standardaktion.
- **Screenreader:** Tabellen-Hinweise sind jetzt lokalisiert (Deutsch, Englisch, Franzoesisch).
- **Fluessigere Oberflaeche:** Die UI-Haertung laeuft pro Fenster nur noch einmal statt bei jedem Oeffnen.

## Neu in v2.2.22

- **Sicherheit:** Der Notfall-Reset, der die Code-Abfrage umging, ist entfernt. Das Zuruecksetzen der Datenbank ist nur noch an einer Stelle moeglich und immer durch die Sicherheitsabfrage geschuetzt.
- **Qualitaet:** Neues 1000-Schleifen-Stresstest-Werkzeug ist Teil der Release-Pruefung; saubere Release-Pakete ohne Laufzeitdateien.

## Neu in v2.2.22

- **Fixkosten-Dialog immer erreichbar:** Auch wenn der aktuelle Monat schon komplett gebucht ist, oeffnet der Dialog und der Monat laesst sich direkt wechseln.
- **Sauberes Bearbeiten:** Das Korrigieren einer Buchung veraendert nicht mehr die Vorschlagsliste der zuletzt gebuchten Kategorien und meldet nicht mehr faelschlich "gebucht".
- **Korrekte Zusammenfassung:** Die Meldung nach dem Buchen bezieht sich auf den tatsaechlich gewaehlten Monat.

## Neu in v2.2.22

- **Buchen und Bearbeiten identisch:** Bearbeiten nutzt jetzt dasselbe, vollstaendige Formular wie das Anlegen (mit Tags und Aktionstexten).
- **Fixkosten in einem Dialog:** Monatsauswahl und faellige Buchungen sind zusammengefuehrt; der Monat laesst sich direkt im Dialog wechseln.
- **Zuruecksetzen sicherer:** Der Datenbank-Reset ist nur noch an einer Stelle erreichbar und immer durch die Code-Abfrage geschuetzt.
- **Aufgeraeumtes Menue:** Navigations-Doppelungen zur Seitenleiste sind entfernt.
- **Kategorien einheitlich:** Seite und Verwaltungs-Fenster nutzen dieselbe Oberflaeche.

## Neu in v2.2.22

- **Updates nur mit Rettungsweg:** Kann vor einem Update kein Rollback-Backup erstellt werden, wird das Update nicht angewendet.
- **Strengere Update-Pruefung:** Portable-Updates muessen ein vollstaendiges, startfaehiges Programmpaket sein.
- **Staerkere neue Zugangscodes:** Neue PIN mindestens 6 Ziffern, neues Passwort mindestens 10 Zeichen. Bestehende Konten bleiben unveraendert nutzbar.

## Neu in v2.2.22

- **Schluesselmaterial geschuetzt:** `users.json`, die verschluesselte Datenbank und Backups werden jetzt nur noch fuer den eigenen Benutzer lesbar abgelegt (0600 statt 0644).
- **Backups werden geprueft:** Beim Wiederherstellen wird die Pruefsumme aus dem Backup verifiziert. Beschaedigte oder veraenderte Backups werden abgewiesen, statt die Datenbank zu ueberschreiben.

## Neu in v2.2.10

- **Sicherheitsabfrage fuer Backups:** Export, Import und Wiederherstellen fragen jetzt den Benutzercode ab, bevor die Datenbank nach aussen geschrieben oder ersetzt wird.
- **Schnellzugang bleibt schnell:** Konten ohne PIN/Passwort (Quick) werden bewusst nicht gefragt – dort gibt es keinen Code.

## Neu in v2.2.9

- **Restore-Code-Härtung:** Normale Backups enthalten keine `users.json` mehr. Dadurch kann ein Backup die lokale Anmeldung bzw. den Wiederherstellungscode nicht mehr umgehen.
- **Sicherer Erststart-Import:** Alte `.bmr`-Backups mit eingebetteter `users.json` werden nicht mehr automatisch über Quick-User-Schlüssel geöffnet; fremde verschlüsselte Backups verlangen den Restore-Key.
- **Sicherer Restore-Dialog:** Benutzerkonten werden über den normalen Backup-Dialog nicht mehr aus Backups übernommen. Datenbank und sichere App-Einstellungen bleiben wiederherstellbar.

## Neu in v2.2.6

- **Konsistente Umbenennung:** Beim Umbenennen oder Umhaengen einer Kategorie folgt jetzt auch der Lernmodus-Zustand (beobachten/ignoriert/vertagt) sauber mit – keine Karteileichen, keine ungewollt wieder auftauchenden Lernvorschlaege.
- **Robusteres Aufraeumen:** Beim Loeschen einer Buchung werden zugehoerige Tag-Verknuepfungen zusaetzlich explizit entfernt.

## Neu in v2.2.6

- **Bessere Erststart-Fuehrung:** Im Assistenten blaettert die **Enter-Taste** weiter; Willkommen und Anleitung erklaeren Cockpit, Ampel, Naechste Schritte und die zwei Einrichtungswege.
- **Neues Hilfe-Thema Monatsabschluss:** Ueberschuss sichern, Defizit decken – verstaendlich erklaert.

## Neu in v2.2.4

- **Ehrlicher Fixkosten-Check:** Offene Fixkosten erscheinen im Cockpit erst ab ihrem Fälligkeitstag – kein Fehlalarm mehr am Monatsanfang.

## Neu in v2.2.3

- **Geführtes Cockpit:** „👉 Nächste Schritte" sagt dir konkret, was jetzt ansteht – erste Buchung, offene Fixkosten oder Monatsabschluss.

## Neu in v2.2.2

- **Tag-Filter in der Übersicht:** Kennzahlen, Diagramme und Listen nach einem Tag filtern.
- **Express-Setup:** Ein Klick – Standard-Kategorien, Lernmodus an, sofort loslegen; Budgets entstehen später aus dem Tracking.

## Neu in v2.2.1

- **Reset repariert:** Setup-Reset führt wirklich aus; Teilreset heisst jetzt "Nur Budgets zurücksetzen" und lässt Kategorien + Buchungen unangetastet.
- **Fehler sichtbar:** Der Daten-Hub meldet Probleme direkt im Fenster statt nur im Log.
- **Vorschläge erklärt:** Tooltip zeigt je Vorschlag Warum + Wirkung; Lernvorschläge mit 🆕 markiert.
- **Tracking-Feinschliff:** Kurzlabel mit Pfad-Tooltip, Auswahl-Zwang bei mehrdeutiger Suche, Undo-Hinweis nach jeder Buchung.

## Neu in v2.2.0

- **Cockpit als Startseite** mit Ampel-Monatsstatus (🟢🟡🔴) und Karte "Frei verfügbar".
- **Monatsabschluss-Assistent:** Überschuss in Ersparnis sichern oder Defizit aus Ersparnis decken – geführt, per Klick, nie automatisch; Fixkosten werden nie zur Kürzung vorgeschlagen.
- **Schnelleres Tracking:** je Konto wird die zuletzt gebuchte Kategorie vorgeschlagen.
- **Übersicht vereinfacht:** 4 klare Reiter (Plan vs. Ist, Kategorien, Verlauf, Top-Buchungen) plus Ampel.
- **Mehr Hilfe im Programm:** Tooltips zu Budgettopf, Ersparnissen, Monatsabschluss.

## Neu in v2.1.7

- **Tracking-Lernmodus:** Kategorien ohne Jahresbudget erhalten aus manuellem Tracking eigene, setzbare Budget-Vorschläge (1. Monat beobachten, ab 2 Monaten Hochrechnung, ab 3 Monaten stabil – Schwellen einstellbar). Die normale Vorschlagslogik bleibt unverändert.
- **Stabile Tabellenbreiten:** Einstellungs-/Theme-Änderungen setzen Spaltenbreiten und Resize-Modi nicht mehr zurück (Wurzelfix + feste Breiten in Budget-/Tracking-Tab und Vorschlagsdialog).
- **Besser lesbare Übersicht-Diagramme:** Der bewährte Plan/Ist-Donut bleibt erhalten; der verwirrende Kreis daneben wurde durch einen Konto-Vergleich als Balken ersetzt. Kategorien und Top-Buchungen werden als Ranking-Balken angezeigt; Bilanz rechnet Ersparnisse als gebundenen Einkommenstopf.

## Aus v2.1.3

- Budget-Anpassungsvorschlag korrigiert: als Fix (ohne Wiederkehrend) markierte, aber regelmässig monatlich gebuchte Kategorien (z.B. Lebensmittel) werden nicht mehr wie ein Jahrestopf aufsummiert und dadurch überhöht vorgeschlagen. Echte Rückstellungen/Franchise bleiben unverändert.

# BudgetManager


## Neu in v2.1.7

- 13. Monatslohn mit Auszahlungsmonat und Betrag.
- Jahreswechsel-Prüfliste für Fixkosten, wiederkehrende Kosten, Pot- und inkrementelle Kategorien.
- Vorjahresmuster-Verteilung für Jahresbeträge.

- Forecast-Modus je Kategorie: Auto, Pot/Rückstellung, Inkrementell/Jahresrechnung, Normal/Flexibel.
- Fix ohne Wiederholung wird standardmässig als Pot behandelt, z. B. Franchise/Selbstbehalt.
- Inkrementell ist explizit wählbar für Jahresrechnungen/Teilzahlungen, z. B. Hausratversicherung.
- Budgetüberschreitungs-Warnschalter ist jetzt wirksam und steuert Banner sowie Budgetwarner.

## Wichtige Härtungen seit v2.0.36

- Final-Release-Härtung für Update-Dialog, Frozen-CLI und portable ZIP-Struktur.
- Stabile Startdateien im Portable-ZIP: `BudgetManager.exe` und `BudgetManager`.
- Doku-/Help-/Manifest-Versionen synchron auf v2.1.7.
- Zusätzliche dynamische Dialogtexte über i18n statt harter deutscher Strings.
- Konto-Hub für Konto, Speicherort, Backup/Wiederherstellung und Datenbank-Wartung.
- Frei wählbarer Datenordner mit optionaler sicherer Datenübernahme.
- PBKDF2-Härtung mit automatischem Legacy-Upgrade für Vorab-Konten.
- Autobuchungs-Artfilter, optionale Budgetposten und Deckungswarnungen.
- Schnelleingabe mit Suche/Dropdown und validierter Kategorieauflösung.

## Cockpit-Startseite

Das Cockpit fasst die wichtigsten Punkte zusammen: Monatsstatus, Favoriten, aktive Sparziele, Budget-Ampel, offene Monatsbuchungen und letzte 10 Buchungen. Es ist bewusst kompakt und frei gestaltbar: Bereiche lassen sich im Cockpit oder unter `Ansicht → Anzeigen` ein-/ausblenden. Auch Hauptreiter können ausgeblendet werden, damit Einsteiger nicht von zu vielen Tabs erschlagen werden.
## v2.1.7 — Feature-Übersicht

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
- Tracker-Picker gruppiert Kategorien übersichtlicher: Favoriten, häufig manuell gebucht, normale Buchungen, variable Fix-/Wiederkehrend-Gruppen und echte Fixkosten. Parent-Kategorien mit Kindern werden im Tracking ausgeblendet; Unterkategorien erscheinen kurz als `Miete` statt `Wohnen › Miete`.
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

- Plan/Ist-Donut: Außen Einnahmen, Mitte Ausgaben, innen Ersparnisse; je Ring gebucht, offen oder über Budget.
- Kategorien-Ranking: größte Ausgaben-Kategorien als horizontale Balken.
- Konto-Vergleich: Einnahmen, Ausgaben und Ersparnisse als Balken statt als irreführender Kreis daneben.
- Monatsverlauf: Ausgaben Budget vs. gebucht.
- Monatsbilanz: echte Bilanz vs. geplante Bilanz.
- Top-Buchungen: größte zusammengefasste Kategorien/Buchungen im gewählten Zeitraum.

Ziel: Ausreißer und Trends erkennen, ohne die Übersicht zu überladen oder falsche Kuchenanteile zu zeigen.

### Sparziele im Workflow

Sparziele sind jetzt klarer eingebettet: im Budget gibt es einen kleinen 🎯-Einstieg, im Tracking erscheint bei aktiven Zielen ein ausblendbares Panel mit Fortschrittsbalken und Doppelklick zum Ziel, und die Übersicht bleibt die Kontrollstelle.

### Sparziel-Entnahme / Geld herausbuchen

Geld aus einem Sparziel wird als **negative Ersparnisse-Buchung** auf die mit dem Sparziel verknüpfte Kategorie gebucht, z. B. `-500 CHF` auf `Ersparnisse → Hochzeit`. Negative Beträge sind dafür bei `Ersparnisse` erlaubt; bei `Ausgaben` bleiben negative Beträge bewusst gesperrt.

Sparziele haben jetzt echte Grenzen: Eine Entnahme darf den Stand nicht unter `0 CHF` ziehen, und eine Einzahlung darf das Ziel nicht über `100 %` füllen. Bei beiden Fällen wird die Buchung blockiert und eine Meldung angezeigt.

Best Practice: Sparziel zuerst **freigeben**, dann die Entnahme buchen und das Ziel abschließen, wenn es erledigt ist.

### Sicherer Start

Auto-Speichern und Auto-Backup sind beim ersten Start aktiv.

### v2.1.7 integrierter Lernmodus

- Erststart-Blocker behoben: Bei aktivem Lernmodus kann der Budget-Schritt ohne Budgetwert abgeschlossen werden; ohne Lernmodus bleibt die Mindestprüfung aktiv.
- Übersichts-Banner korrigiert: Neue Lernbudgets zeigen **🆕** statt Defizit-Symbol.
- Schema-Version bleibt auf der Lernstatus-Migration (`CURRENT_VERSION >= 15`) und wird per Regression abgesichert.
- 2.1.6 bleibt die Code-Basis für die saubere Budgetart-Erkennung.
- 2.1.5 liefert wieder die fehlende Persistenz für Lernstatus-Aktionen.
- Lernstatus wird in `tracking_learning_state` gespeichert und bei Kategorie-Rename/-Delete mitgeführt.
- Rechtsklick im Budgetvorschlagsdialog: weiter beobachten, ignorieren, unregelmäßig markieren, zurücksetzen.
- Jahreswechsel-Prüfliste zeigt auch Kategorien, die nur getrackt wurden und daraus ein Startbudget fürs neue Jahr erhalten können.
- Automatisches Ausblenden nach langer stabiler Lernphase ist optional und standardmäßig aus.
- **Soft-0-Budget / sanfte Null-Bilanz:** Prüft die Gesamtplanung `Einnahmen − Ausgaben − Ersparnisse`, schlägt Überschüsse für Ersparnisse oder Übertrag vor und behandelt Defizite zuerst über Ersparnisse, danach nur über flexible Ausgaben. Keine automatische Änderung; Fixkosten/POTs bleiben geschützt.
