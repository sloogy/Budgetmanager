# v2.2.6 – KILLCRITIC: Lernzustand folgt Rename/Reassign, robusteres Tag-Aufräumen

X10THINK-KILLCRITIC auf Basis des releasefähigen v2.2.5-Stands: 100 randomisierte Invarianten-Loops (10 Themen × 10 Loops) über die echten Modelle plus vollständige Tiefenlese von Fälligkeits-, POT-, Vorschlags-/Lernmodus-, Undo/Redo-, Sparziel- und Reset-Logik. Ergebnis: ein echter Cascade-Bug behoben, eine Datenintegritäts-Härtung ergänzt; alle strikt getrennten Kernpfade (normale Vorschlagsengine ↔ Lernmodus, POT ↔ laufende Monatsausgabe) blieben nachweislich unberührt.

- **FIX (Datenkonsistenz) – Tracking-Lernzustand verwaiste beim Umbenennen/Umhängen:** `tracking_learning_state` ist die achte namensreferenzierende Tabelle (gekeyt auf `typ`+`category`), aber Rename und Reassign führten sie – anders als der bereits korrekte Delete-Pfad – nicht mit. Folge: Nach einem Rename ging die Nutzerentscheidung (beobachten/ignoriert/vertagt/beendet) verloren, die Kategorie tauchte unter dem neuen Namen wieder im Lernmodus auf, und die alte Zeile blieb als Leiche stehen. **Neu:** `CategoryModel.rename_and_cascade`, `CategoryModel._move_category_text_references` (Reassign) und `UndoRedoModel._rename_cascade` ziehen den Lernzustand jetzt konsistent mit (`UPDATE OR IGNORE` + `DELETE`, konfliktfrei bei bereits belegtem Zielnamen). `tracking_learning_state` wurde dazu in die Undo-Whitelist aufgenommen.
- **HÄRTUNG (Defense-in-Depth) – Tag-Verknüpfungen beim Buchungs-Löschen:** `TrackingModel.delete` räumt `entry_tags` jetzt zusätzlich explizit auf, statt sich allein auf die FK-Regel `ON DELETE CASCADE` zu verlassen. Produktiv (mit `PRAGMA foreign_keys=ON`) war das Verhalten bereits korrekt; auf ohne das Pragma geöffneten Verbindungen entstehen so keine verwaisten Tag-Links mehr – analog zum Kategorie-Delete.
- **Nachgewiesen unberührt:** Strikte Trennung Vorschlagsengine ↔ Lernmodus (Lernmodus feuert weiterhin ausschließlich ohne positives Jahresbudget), POT-Topf-Cap = höchster Budgetwert (nicht Summe), POT-vs-laufende-Ausgabe-Heuristik (3-Monatsfenster: 2 aktive Monate bleiben Topf), Sparziel-Vorzeichenlogik bei Undo+Redo, Data-Start-Boundary.
- **i18n:** de/en/fr je 2285 Keys, Parität gewahrt (keine Key-Änderung nötig).
- **Neue Regression:** `tests/test_release_226_learning_state_cascade.py` (5 Tests: Rename zieht Lernzustand mit, Undo/Redo konsistent, Reassign ohne Waisen, Konflikt bei belegtem Zielnamen ohne Crash, Delete räumt weiterhin auf).

Gates: compileall, sync --check (2.2.6), i18n-Audit (de=en=fr, 2285 Keys, 0 Fehler), DAU-Erststart, Release-Logik-Audit 100/0, Deep-Logic-Audit 500/3500/0, Lint, pytest headless (362 passed, 2 skipped), zusätzlich KILLCRITIC-Invarianten-Harness 100 Loops / 0 Findings. GUI-Smoke, PyInstaller und Inno Setup in der Build-/CI-Umgebung.


# v2.2.5 – Erststart-Führung: Enter bewegt vorwärts, Willkommen & Anleitung ausgebaut

Führungs-Release auf Basis des KILLCRITIC-verifizierten v2.2.4-Stands. Behebt den gemeldeten Enter-Fehler im Erststart und baut Willkommen und Anleitung inhaltlich deutlich aus.

- **FIX (Führung) – Enter-Taste im Setup-Assistenten wirkungslos:** Auf der Willkommensseite (ohne fokussiertes Eingabefeld) tat die **Enter-Taste** nichts, weil „Weiter" kein Default-Button war – Einsteiger mussten zur Maus greifen. **Neu:** Ein `keyPressEvent` bildet Enter/Return auf „Weiter" bzw. auf der letzten Seite „Fertig" ab; „Weiter"/„Fertig" sind Default-Buttons und werden bei jedem Seitenwechsel neu fokussiert. In mehrzeiligen Textfeldern (QTextEdit/QPlainTextEdit) bleibt Enter ein Zeilenumbruch, Modifier (Shift/Strg/Alt) werden durchgelassen, und „Zurück" feuert nie versehentlich per Enter.
- **NEU – Willkommen ausgebaut:** Die erste Assistent-Seite begrüßt jetzt richtig und erklärt die **zwei Wege** (⚡ Express: sofort tracken, Budgets später aus dem Lernmodus / geführt: Kategorien→Budget→Buchung Schritt für Schritt) samt Enter-Tipp – dreisprachig.
- **NEU – Anleitung ausgebaut:** Das Hilfe-Thema **Einstieg** ist von einer kurzen Reihenfolge zu einem echten Willkommen gewachsen: Cockpit als Startseite, **Ampel** (🟢🟡🔴), **👉 Nächste Schritte**, beide Einrichtungswege, Monatsende-Hinweis und Enter-Tipp. Neu hinzugekommen ist ein eigenes Hilfe-Thema **Monatsabschluss** (Überschuss sichern, Defizit aus Ersparnissen decken, Ampel-Zusammenhang, und die Kernregel „Fixkosten werden nie zur Kürzung vorgeschlagen") – alles in de/en/fr.
- **Historie geschützt:** Der v2.2.3-KILLCRITIC-Bericht wurde vom Versions-Sweep ausgenommen.
- **i18n:** Willkommenstexte in de/en/fr aufgewertet (Werte, keine Key-Änderung); Parität gewahrt (2277 Keys).
- **Neue Regression:** `tests/test_release_225_onboarding_enter.py` (5 Tests: Enter-Navigation inkl. Textfeld-Ausnahme und Default-Buttons, ausgebautes Einstiegsthema dreisprachig, neues Monatsabschluss-Thema mit Fixkosten-Regel, alle Hilfethemen dreisprachig, Willkommenstexte mit beiden Wegen).

Gates: compileall, sync --check (2.2.5), i18n-Audit (de=en=fr, 2277 Keys, 0 Fehler), DAU-Erststart, Release-Logik-Audit 100, Deep-Logic-Audit 500/3500, Lint, pytest headless. GUI-Smoke (Enter blättert durch den Assistenten, Willkommen/Anleitung lesbar), Qt-Translation-Verify, PyInstaller und Inno Setup in der Build-/CI-Umgebung.


# v2.2.4 – Fixkosten-Check respektiert den Fälligkeitstag

Stabilisierungs- und Führungs-Release auf Basis des KILLCRITIC-geprüften v2.2.3-Stands (dort drei Fixes übernommen: fehlender `trf`-Import im Cockpit – ein echter Release-Blocker bei offenen Fixkosten –, vollständige Zählung offener Positionen statt nur der 10 Tabellenzeilen, und ein an den echten Button angepasster Empty-State-Text).

- **FIX (Stabilität/Führung) – Fixkosten galten vor Fälligkeit fälschlich als „fehlt":** Der Cockpit-Check „offene Fixkosten/wiederkehrende Buchungen" markierte jede noch nicht gebuchte Position sofort als offen – auch am Monatsanfang, obwohl der Soll-Buchungstag (z.B. 25.) noch nicht erreicht war. Am 3. des Monats meldete das Cockpit so jede Miete als fehlend und trieb die „Nächste Schritte"-Zahl unnötig hoch. **Neu:** Im laufenden Monat gilt eine Position erst ab ihrem Fälligkeitstag als offen; vergangene Monate bleiben unverändert (Fälligkeit längst überschritten). Bereits gebuchte oder budgetlich erfüllte Positionen zählen wie bisher nicht.
- **Sauber gekapselt:** Die Fälligkeitslogik liegt jetzt Qt-frei in `model/fixed_cost_due.py` (`is_open_this_month`) und ist damit regressionsgesichert; das Cockpit nutzt sie, statt die Bedingung inline zu führen.
- **Historie geschützt:** Der v2.2.3-KILLCRITIC-Bericht wurde vom Versions-Sweep ausgenommen.
- **Neue Regression:** `tests/test_release_224_fixed_cost_due.py` (7 Tests: vor/nach Fälligkeit im laufenden Monat, vergangener Monat immer fällig, bereits gebucht, XOR-Wiederkehrend mit Teilbuchung, kein Budget/keine Flags, Cockpit-Verdrahtung).

Gates: compileall, sync --check (2.2.4), i18n-Audit (de=en=fr, 2277 Keys), DAU-Erststart, Release-Logik-Audit 100, Deep-Logic-Audit 500/3500, Lint, pytest headless. GUI-Smoke, Qt-Translation-Verify, PyInstaller und Inno Setup in der Build-/CI-Umgebung.


# v2.2.3 – Geführtes Cockpit: „Nächste Schritte“

Stabilisierungs- und Führungs-Release auf Basis des RECURRING_DAY_DEFAULT-Fixstands (Fälligkeitstag-Fix über 7 Pfade verifiziert, alle Gates grün).

- **NEU – „Nächste Schritte" im Cockpit:** Direkt unter der Ampel beantwortet eine dynamische Zeile die Einsteigerfrage „Und was mache ich jetzt?" mit bis zu 3 konkreten, aus echten Daten abgeleiteten Handlungen: Empty State ohne Buchungen („erste Buchung über ➕ Buchung erfassen"), offene Fixkosten/wiederkehrende Buchungen mit Anzahl (gespeist aus der bestehenden Fixkosten-Prüfung), Monatsabschluss-Hinweis ab dem 25. (nur solange der Monat nicht abgeschlossen ist). Ist nichts zu tun: „✅ Alles erledigt". Fehler in der Ableitung können die Anzeige nie brechen (defensiv gekapselt).
- **Stabilität:** Vollständige Gate-Battery auf dem Fix-Stand erneut grün; der Fälligkeitstag-Fix (recurring_preferred_day statt DB-Default 1 auf allen Kategorie-Pfaden) ist mit eigenen Regressionen übernommen.
- **Historie geschützt:** Beide v2.2.2-Audit-Berichte vom Versions-Sweep ausgenommen.
- **i18n:** 5 neue Keys, de/en/fr je **2278 Keys**, Parität geprüft.
- **Regression:** +1 statischer Test (Verdrahtung, Datenquellen, alle Keys).

Gates: compileall, sync --check, i18n-Audit (2278), DAU, Logik-Audit 100, Deep 500/3500, Lint, pytest headless. GUI-Smoke/Qt-Translate/PyInstaller/Inno in der Build-Umgebung.


# v2.2.2 – KILLCRITIC Nachhärtung Tag-Filter/Favoriten-Begriffe

- **FIX – Übersicht Tag-Filter vollständig zentralisiert:** Die Tag-Combo in der Übersichts-Kopfzeile löst jetzt sofort einen Refresh aus. KPIs, Diagramme, Budgetübersicht, Kategoriebaum, Budget-Tabelle und Transaktionsliste nutzen dieselbe `tag_id`-Filterbasis über `TrackingModel.get_entries_in_range(..., tag_id=...)`.
- **FIX – Ist-Werte bei aktivem Tag-Filter:** Budgets bleiben planseitig unverändert, Ist-Werte zeigen nur Buchungen mit dem gewählten Tag. Damit ist die Tooltip-Aussage „Budgets tragen keine Tags“ korrekt umgesetzt.
- **UX – Begriffsklärung:** Die rechte Übersichts-Seitenleiste beschriftet den Filter jetzt als „Tags“ statt missverständlich „Tag“/Kalendertag. In-App-Hilfe und Wissensdatenbank erklären Favorit vs. Tag/Label vs. Fälligkeitstag.
- **Regressionen:** `tests/test_release_221_reset_and_ux.py` schützt die Verdrahtung des zentralen Filters und prüft `TrackingModel.get_entries_in_range(..., tag_id=...)` funktional.
- **Release-Gates:** `compileall`, Versions-Sync, i18n-Audit, DAU-Erststart, Release-Logik-Audit 100, Deep-Logic-Audit 500/3500, Lint und `pytest` headless grün.

# v2.2.2 – Tag-Filter in der Übersicht, Express-Setup

Setzt die beiden in v2.2.1 dokumentierten offenen Punkte um; Basis ist der KILLCRITIC-geprüfte FIXED-Stand (Black-Pin-Fix im CI-Workflow übernommen, alle Gates grün, Grenzfall-Stichproben Dezember-Abschluss/Doppel-Abschluss/Null-Betrag sauber).

- **NEU – Tag-Filter in der Übersicht:** Neue Filter-Combo („🏷 Alle Tags" + alle vorhandenen Tags) in der Übersichts-Filterleiste. Der Filter greift **zentral** auf die geladenen Buchungen und wirkt damit konsistent auf KPIs, alle Diagramm-Reiter und Listen. Auswahl bleibt beim Aktualisieren erhalten. Budgets tragen keine Tags – der Tooltip erklärt, dass bei aktivem Filter die Ist-Sicht des Tags gezeigt wird.
- **NEU – Express-Setup:** Button „⚡ Express-Einrichtung (nur das Nötigste)" auf der ersten Assistent-Seite: legt Standard-Kategorien an (nur falls noch keine existieren, über die gemeinsame `insert_default_categories`-Routine), aktiviert den Tracking-Lernmodus (der Budget-Schritt gilt damit als erfüllt – Budgets entstehen später aus echten Buchungen), markiert alle optionalen Schritte als erledigt und springt zur Abschluss-Seite. Sicherheitsabfrage vorab; alles bleibt später in den Einstellungen änderbar. Der sicherheitskritische Konto-/Verschlüsselungs-Wizard ist nicht betroffen.
- **Historie geschützt:** Der v2.2.1-Audit-Bericht wurde vom Versions-Sweep ausgenommen und unverändert wiederhergestellt; docs/open-tasks.md markiert die beiden Punkte als umgesetzt.
- **i18n:** 5 neue Keys, de/en/fr je **2273 Keys**, Parität geprüft.
- **Regressionen erweitert:** `tests/test_release_221_reset_and_ux.py` +3 Tests (Tag-Filter-Verdrahtung inkl. zentraler Row-Filterung, Express-Pfad inkl. Lernmodus-Aktivierung und Sprung zur Abschluss-Seite, i18n-Parität der neuen Keys).

Validierte Gates: `compileall`, `sync_version.py --check`, i18n-Audit (2273 Keys), DAU-Erststart, Release-Logik-Audit 100, Deep-Logic-Audit 500/3500, Lint, `pytest` headless. GUI-Smoke (Tag-Filter live, Express-Durchlauf auf leerer und gefüllter DB), Qt-Translation-Verify, PyInstaller/Inno in der Build-/CI-Umgebung.


# v2.2.1 – Reset-Fixes, sichtbare Hub-Fehler, erklärte Vorschläge, Tracking-Feinschliff

Setzt die offenen Punkte aus dem v2.1.7-Release-Bericht (1–6) und die verbliebenen KILLCRITIC-Punkte aus v2.2.0 um.

- **FIX (Bericht 1) – Setup-Reset führt jetzt wirklich aus:** Die Reset-Bestätigung im Setup-Assistenten öffnete bisher nur den DB-Verwaltungsdialog – der bestätigte Reset passierte NICHT. Jetzt wird `reset_database()` direkt ausgeführt (mit automatischem Backup), das Ergebnis angezeigt und der Setup-Fortschritt neu bewertet; Fehler erscheinen als Dialog.
- **FIX (Bericht 2+3) – Teilreset sauber definiert und zentralisiert:** `keep_user_data=True` löschte bisher Budget UND Kategorien, liess aber Buchungen stehen – Tracking und Nebentabellen referenzierten gelöschte Kategorien. **Neue Semantik: „Nur Budgets zurücksetzen"** – Kategorien und Buchungen bleiben; geleert werden Budgets plus budgetbezogene Nebentabellen (`budget_warnings`, `suggestion_accepted`, `tracking_learning_state`). Neuer Key `database.msg.reset_budget_only`; Radio-Beschriftung präzisiert (de/en/fr). Vollreset weiterhin dynamisch über `sqlite_master` (inkl. Lernstatus), `system_flags` geschützt – per Regression abgesichert.
- **FIX (Bericht 4) – Tracking-Tabelle mit Kurzlabel:** Kategorie-Spalte zeigt den Namen, voller Pfad „Parent › Kind" als Tooltip.
- **FIX (Bericht 5) – Schnelleingabe erzwingt Auswahl bei Mehrdeutigkeit:** Passt der Suchtext auf mehrere Kategorien ohne explizite Dropdown-Auswahl, stoppt das Speichern mit Hinweis (Trefferzahl) und das Dropdown öffnet sich – kein stiller Erst-Treffer mehr.
- **FIX (Bericht 6) – Daten-Hub zeigt Fehler sichtbar:** Rote Fehlerzeile im Hub plus Warn-Dialog bei fehlgeschlagenen Aktionen (Speicherort, Backup/Restore/DB) und unvollständigem Laden.
- **NEU (KILLCRITIC) – Vorschläge erklären sich („Warum?"):** Tooltip je Vorschlagszeile mit Rechenweg aus vorhandenen Engine-Daten (Monate, Ø-Abweichung, alt → neu); Lernvorschläge erklären, dass ein NEUES Budget entsteht und die Budgetart bestätigt wird. 🆕-Kennzeichnung trennt Lern- von Anpassungsvorschlägen.
- **NEU (KILLCRITIC) – Undo-Hinweis:** Nach jeder Schnellerfassungs-Buchung zeigt die Statuszeile 6 Sekunden „…gebucht – rückgängig mit Ctrl+Z".
- **Offen dokumentiert (geplant 2.2.2):** Tag-Filter in der Übersicht und Express-Setup (docs/open-tasks.md) – bewusst nicht halbgar eingebaut.
- **i18n:** 10 neue Keys + 1 präzisierter Text, de/en/fr je **2268 Keys**, Parität geprüft.
- **Neue Regression:** `tests/test_release_221_reset_and_ux.py` (9 Tests: Teilreset erhält Kategorien/Buchungen/Ersparnisse und leert Nebentabellen, Vollreset schützt system_flags, Setup-Direktausführung, Kurzlabel+Tooltip, Mehrdeutigkeits-Zwang, Hub-Fehleranzeige, Warum-Tooltips + 🆕).

Validierte Gates: `compileall`, `sync_version.py --check`, i18n-Audit (2268 Keys), DAU-Erststart, Release-Logik-Audit 100, Deep-Logic-Audit 500/3500, Lint, `pytest` headless. GUI-Smoke, Qt-Translation-Verify, PyInstaller/Inno in der Build-Umgebung.


# v2.2.0 – Cockpit-Start, Ampelstatus, Monatsabschluss-Assistent, vereinfachte Übersicht

Usability-Release nach Schwächenanalyse: Das Programm beantwortet jetzt beim Start sofort die Kernfrage "Wie stehe ich diesen Monat da?" und führt am Monatsende durch Überschuss/Defizit.

- **NEU – Cockpit als Startseite:** Das Programm startet immer auf dem Cockpit (Einstellung `start_on_cockpit`, Standard an), unabhängig vom zuletzt offenen Reiter. Das Cockpit zeigt jetzt zusätzlich eine **Ampel-Statuszeile** (🟢 im Plan / 🟡 knapp / 🔴 über Plan) und die KPI-Karte **"Frei verfügbar"** (Einnahmen − Ausgaben − Ersparnisse; vorher missverständlich "Monatsgefühl"). Warnungen, letzte Buchungen, offene Fixkosten und Sparziele waren bereits vorhanden.
- **NEU – Ampel-Monatsstatus (eine Logik überall):** `model/month_status.py` bewertet den Monat einheitlich für Cockpit und Übersicht: Rot bei Budget-Überschreitung oder negativem frei verfügbarem Rest; Gelb ab 90% des Ausgaben-Budgets oder Rest < 5% der Einnahmen; sonst Grün. Tooltip erklärt die Regeln.
- **NEU – Monatsabschluss-Assistent:** Cockpit-Button "Monatsabschluss…" öffnet einen geführten Dialog (`views/month_close_dialog.py`, Logik Qt-frei in `model/month_close_model.py`): Zusammenfassung Einnahmen − Ausgaben − Ersparnisse; **Überschuss** auf Klick in eine Ersparnis buchen (Vorschlag: offenes Sparziel mit grösstem Restbedarf, Betrag/Ziel änderbar, Buchung am Monatsletzten); **Defizit** auf Klick aus einer Ersparnis **mit Guthaben** decken (Entnahme als negative Ersparnis-Buchung). Zusätzlich reine Info, welche **variablen** Budgets im Folgemonat Spielraum bieten – **Fixkosten und wiederkehrende Kategorien werden nie zur Kürzung vorgeschlagen** (per Regression abgesichert). Abschluss-Vermerk in `system_flags`; alle Buchungen sind normale Tracking-Einträge und per Undo widerrufbar. Nichts geschieht automatisch.
- **NEU – Tracking merkt letzte Auswahl je Konto:** Schnellerfassung und Buchungsdialog schlagen beim Öffnen die zuletzt gebuchte Kategorie des gewählten Kontos vor (`tracking_last_category`). Kategorie-Suche, Favoriten-zuerst-Sortierung und gruppierter Picker waren bereits vorhanden – täglich Wiederkehrendes ist damit ein Zwei-Klick-Vorgang.
- **Übersicht endgültig vereinfacht:** 4 statt 6 Diagramm-Reiter in klarer Lese-Reihenfolge: 1. Plan vs. Ist, 2. Kategorien-Ranking, 3. **Verlauf** (Monats-Ausgaben + Monatsbilanz untereinander, zusammengelegt), 4. Top-Buchungen. Der Konto-Vergleichs-Reiter entfiel (identische Aussage wie Plan vs. Ist). Ampel-Statuszeile über den KPI-Karten. Die v2.1.7-Lesbarkeitsverbesserungen (Balken statt Donut, Erklärtexte je Reiter) bleiben erhalten.
- **Hilfe direkt im Programm:** Neue erklärende Tooltips an den Begriffen **Budgettopf** (Prognose-Modus im Kategorie-Manager), **Ersparnisse** und **Monatsabschluss** (Cockpit-Karte, Abschluss-Dialog) sowie an der Ampel. Fixkosten, Wiederkehrend, Fälligkeitstag und Lernmodus hatten bereits Tooltips.
- **i18n:** 52 neue Keys (Status, Cockpit, Hilfe, Monatsabschluss) – de/en/fr je **2259 Keys**, Parität geprüft.
- **Neue Regression:** `tests/test_release_220_cockpit_monthclose.py` (14 Tests: Ampel-Grenzfälle, Überschuss-/Defizit-Fluss inkl. Monatsletzter-Buchung, Sparziel-Priorität, nur gedeckte Ersparnisse als Quelle, Fixkosten-Ausschluss, UI-Verdrahtung statisch).

Validierte Gates: `compileall`, `sync_version.py --check`, i18n-Audit (de=en=fr, 2259 Keys), DAU-Erststart, Release-Logik-Audit 100 Loops, Deep-Logic-Audit 500 Loops / 3500 Checks, Lint-Prozedur, `pytest` headless. PySide6-GUI-Smoke (Cockpit-Start, Ampel, Monatsabschluss beide Pfade, letzte-Kategorie-Vorauswahl, 4 Übersichts-Reiter), Qt-Translation-Verify, PyInstaller und Inno Setup laufen in der Build-/CI-Umgebung.


# v2.1.7 – Lernmodus-Integration finalisiert, Erststart- und Banner-Blocker behoben

## 2.1.7 - 2026-07-02

### Übersicht-Diagramme lesbarer gemacht

- **Plan/Ist statt Donut:** Der Hauptgraph zeigt Budget und gebuchte Beträge je Konto als Balkenvergleich. Das ist für Monatskontrolle verständlicher als verschachtelte Donuts.
- **Kategorien als Ranking:** Ausgaben-Kategorien werden als horizontale Balken mit Top-8 + „Übrige“ angezeigt, nicht mehr als schwer lesbarer großer Kreis.
- **Konto-Vergleich statt Schein-Verteilung:** Einnahmen, Ausgaben und Ersparnisse werden nicht mehr als Kuchenanteile dargestellt, weil sie keine Anteile desselben Topfs sind.
- **Erklärtexte direkt im Diagramm-Tab:** Jeder Graph erklärt nun kurz, wie er zu lesen ist.
- **Wiki/Handbuch erweitert:** README, FEATURES, User-Guides, In-App-Hilfe und HTML-Wiki beschreiben die neue Logik.

### Added
- Separater Lernmodus finalisiert: Startbudgets aus Tracking nur für Kategorien ohne positives Jahresbudget.
- Budgetart-Erkennung und Bestätigung beim Übernehmen von Lernvorschlägen.
- Lernmodus-Optionen im Erststart-Assistenten und in den Einstellungen.
- Jahreswechsel-Prüfliste zeigt Tracking-only-Kategorien als Startbudget fürs neue Jahr.

### Changed
- Lernvorschläge verwenden `direction="initial"` und bleiben damit fachlich von Defizit-/Überschuss-Vorschlägen getrennt.
- Konservative Rundung: Einkommen abrunden, Ausgaben/Ersparnisse aufrunden.

### Fixed
- Offene Lernphasen beim Jahreswechsel werden nicht durch zukünftige Nullmonate verfälscht.


Konsolidierter Release aus zwei v2.1.4-Ständen. Macht den Nur-Tracking-Workflow rund (nur Einkommen/Fixkosten budgetiert, alles Weitere wird erst getrackt) und behebt die zwei sichtbaren UI-Fehler an der Wurzel.

- **NEU – Separater Tracking-Lernmodus:** Kategorien, die im **gesamten Jahr** kein Budget > 0 haben, aber manuell getrackt werden, erhalten eigene Budget-Vorschläge – bewusst **getrennt** von der normalen Budget-Vorschlagsengine (`get_tracking_budget_suggestions` in `model/budget_overview_model.py`, ergänzt NACH der Engine, ohne deren Logik zu berühren). Stufen: 1. Monat beobachten → ab Vorschlags-Schwelle (Standard 2 Monate) Hochrechnung/Vorschlag → ab Stabilitäts-Schwelle (Standard 3 Monate) stabiler Vorschlag. Betrag = Median (ausreisserrobust), nur manuelle Buchungen (`tracking.source`), laufender Monat optional taggenau hochgerechnet. Sobald irgendwo im Jahr ein Budget gesetzt ist, greift wieder ausschliesslich die normale Anpassungslogik.
- **Einstellbar:** Neue Optionen unter Einstellungen → Budget-Übersicht: Lernmodus an/aus, „Vorschlag ab X Monaten", „stabil ab X Monaten", „laufenden Monat hochrechnen".
- **Budget-Vorschlagsdialog:** Lernvorschläge erscheinen als „neu" (i18n) statt Prozentwert; DB-Typ wird sprachunabhängig über `Qt.UserRole` transportiert (Anwenden bricht in en/fr nicht mehr); stabile feste Spaltenbreiten.
- **BUG-FIX – Tabellenbreiten „springen" nach Einstellungsänderungen (Wurzelursache):** `utils/table_autosize.py` setzte bei jeder Theme-/Schriftanwendung die Standard-**Spaltenbreite** aller Tabellen zurück (Default-Section-Size auf dem Horizontal-Header ≙ Spaltenbreite, nicht Header-Höhe) und zwang alle Resize-Modi global auf Interactive. Jetzt wird nur noch die Zeilenhöhe angepasst. Ergänzend behalten Budget-, Tracking- und Vorschlagsdialog-Tabellen feste Spaltenbreiten.
- **BUG-FIX – Diagramme Theme-fremd/abgeschnitten:** `QChart` ignoriert Qt-Stylesheets; Hintergrund blieb weiss, Titel/Achsen/Pie-Aussenlabels schwarz (im dunklen Theme teils unlesbar), Margins=0 schnitt Aussenlabels ab. `CompactChart` rendert jetzt transparent, färbt nach jedem Serienaufbau Titel, Legende, Achsen und Slice-Labels über `ui_colors`, 4px-Margins.
- **Übersicht inhaltlich korrigiert:** Donut zeigt Über-Budget-Anteile als eigene Slice; Bilanz und Monatsbilanz-Verlauf rechnen Einkommen − Ausgaben − Ersparnisse (Ersparnisse binden den Einkommenstopf).
- **i18n:** Neue Keys `suggestion.suggestion_tracking_projection`, `suggestion.suggestion_tracking_stable`, `budget_adjustment.new_budget_label` sowie die Lernmodus-Einstellungstexte – de/en/fr jetzt je **2183 Keys** (Parität geprüft, Einfügereihenfolge erhalten). Die Lernmodus-Meldung ist nicht mehr hardcoded deutsch.
- **Neue Regressionen:** `tests/test_tracking_budget_learning.py` (Lernstufen, Jahres-Budget-Sperre, manuelle-Buchungen-Filter) und `tests/test_release_214_ui_fixes_static.py` (Horizontal-Header bleibt unangetastet, Theme-Anwendung in allen Chart-Buildern, i18n-Keys + Parität, keine hardcodierten Lernmodus-Texte).

Validierte Gates: `compileall`, `sync_version.py --check`, i18n-Audit (de=en=fr, 2183 Keys), DAU-Erststart, Release-Logik-Audit 100 Loops, Deep-Logic-Audit 500 Loops / 3500 Checks, Lint-Prozedur, `pytest` headless. PySide6-GUI-Smoke (Lernvorschlag nach 2 getrackten Monaten, Budget setzen → normale Logik übernimmt, Tabellenbreiten nach Einstellungsänderung, Diagramme dunkel/hell), Qt-Translation-Verify, PyInstaller und Inno Setup müssen weiter in der Build-/CI-Umgebung laufen.

### Fixed (Release-Blocker aus dem 2.1.5/2.1.6-Vergleich)
- **Erststart blockiert nicht mehr bei aktivem Lernmodus:** Der Budget-Ausfüllschritt des Setup-Assistenten verlangte weiterhin mindestens einen Budgetwert > 0 – im Widerspruch zum Lernmodus-Ziel „erst tracken, Budget später lernen". Jetzt gilt der Schritt auch als erledigt, wenn die Lernmodus-Checkbox aktiv ist (eigener Hinweistext `setup.budget_learning_skip_ok`, de/en/fr); das Umschalten der Checkbox aktualisiert die Freigabe sofort. Mit deaktiviertem Lernmodus bleibt die harte Mindestdaten-Prüfung unverändert.
- **Banner-Symbol für neue Lernbudgets:** `initial`-Vorschläge erhielten im Übersichts-Banner das Defizit-Symbol 📉. Neue Budgets sind kein Defizit – sie zeigen jetzt 🆕. (Die Dialog-Sortierung behandelte `initial` bereits korrekt an erster Stelle; `is_chronic_deficit` matcht weiterhin nur echte Defizite.)
- **Schema-Version bestätigt nicht rückläufig:** `CURRENT_VERSION = 15` mit idempotenter v14→v15-Migration (`tracking_learning_state`) ist enthalten; per Regression abgesichert (`test_schema_version_not_regressed`).
- **CHANGELOG-Struktur repariert:** Der 2.1.7-Eintrag war in den 2.1.4-Block gerutscht; die vollständigen 2.1.5- und 2.1.4-Einträge fehlten und wurden aus dem verifizierten 2.1.5-Release wiederhergestellt.
- **Neue Regression:** `tests/test_release_217_blocker_fixes_static.py` (Erststart-Freigabe, Banner-Symbol, i18n-Key + Parität, Schema-Version).

Validierte Gates: `compileall`, `sync_version.py --check`, i18n-Audit (de=en=fr, 2208 Keys), DAU-Erststart, Release-Logik-Audit 100 Loops, Deep-Logic-Audit 500 Loops / 3500 Checks, Lint-Prozedur, `pytest` headless. PySide6-GUI-Smoke (Erststart mit/ohne Lernmodus, Banner-Anzeige, Budgetart-Dialog), Qt-Translation-Verify, PyInstaller und Inno Setup laufen weiter in der Build-/CI-Umgebung.


# v2.1.5 – Lernmodus-Ausbau: Budgetart-Erkennung, Berichtsaktionen, Jahresend-Auswertung

Setzt die Lernmodus-Spezifikation vollständig um. Basis ist der konsolidierte v2.1.4-Stand; die parallel erstellte „UNIFIED"-Variante wurde verworfen (sie enthielt wieder den Engine-Bootstrap statt des separaten Lernmodus und verletzte damit die zentrale Regel: Kategorien ohne Budget ausschliesslich Lernmodus, Kategorien mit Budget ausschliesslich normale Vorschlagslogik).

- **NEU – Budgetart-Erkennung („Erkannt als"):** Jeder Lernvorschlag klassifiziert die Kategorie: *fix, wiederholend* (nahezu konstante Beträge, z.B. Miete), *wiederholende schwankende Einnahme* (z.B. Stundenlohn – Vorschlag konservativ als **Minimum** der beobachteten Monate, abgerundet), *variabler wiederholender Topf* (z.B. Essen – Median) oder *unregelmässig* (Null-Lücken zwischen Buchungen, z.B. Franchise – **kein** Monatsbudget-Vorschlag, sondern Empfehlung Jahres-/inkrementelles Budget mit Richtwert). Die Erkennung steht in der Berichtsmeldung.
- **NEU – Budgetart beim Übernehmen bestätigen:** Beim Übernehmen eines Lernvorschlags öffnet sich ein Bestätigungsdialog mit wählbarer Budgetart (Fix+wiederholend, Fix+inkrementell, nur wiederholend, variabler Topf, Ersparnis-Topf, schwankendes Einkommen, einmalig/unregelmässig – vorbelegt aus der Erkennung) und änderbarem Betrag. Erst die Bestätigung erzeugt das Budget und setzt die Kategorie-Flags (`is_fix`, `is_recurring`, `forecast_mode`); Abbruch überspringt die Kategorie.
- **NEU – Berichtsaktionen (Kontextmenü auf Lernvorschlags-Zeilen):** *Weiter beobachten* (stellt den Vorschlag bis Monatsende zurück), *Ignorieren* (beendet den Lernmodus für die Kategorie manuell), *Als unregelmässig markieren*, *Lernstatus zurücksetzen*. Persistiert in der neuen Tabelle `tracking_learning_state` (Migration **v14→v15**, idempotent); Kategorie-Umbenennen/-Löschen kaskadiert über die bestehende Textreferenz-Mechanik (jetzt 8 abhängige Tabellen).
- **NEU – Automatisch beenden (Einstellung, Standard aus):** Vergehen nach der Stabilitätsphase zwei weitere aktive Monate ohne Übernahme, endet der Lernmodus für die Kategorie automatisch (Status `ended`, im Bericht zurücksetzbar). Zusätzlich neue Einstellung „Lernvorschläge im Vorschlagsbericht anzeigen".
- **NEU – Jahresend-Auswertung:** Der Jahreswechsel-Dialog zeigt Kategorien, die im Quelljahr getrackt wurden, aber nie ein Budget hatten, mit Startbudget-Vorschlägen fürs neue Jahr (`get_year_end_learning_suggestions`). Budgets werden nicht automatisch gesetzt; Übernahme läuft über den Vorschlagsbericht. Kategorien mit Budget laufen unverändert über Jahreskopie + normale Anpassungslogik.
- **Erststart:** Der Lernmodus ist ab dem ersten Start aktiv (Standard an) und in den Optionen vollständig konfigurierbar; der sicherheitskritische Startup-Wizard bleibt bewusst unangetastet.
- **i18n:** 25 neue Keys (Erkennungsarten, Berichtsaktionen, Budgetart-Dialog, Einstellungen, Jahresend-Hinweis) – de/en/fr je **2208 Keys**, Parität geprüft.
- **Neue Regression:** `tests/test_tracking_learning_v215.py` (12 Tests: alle vier Erkennungsarten inkl. Spec-Beispiele Miete/Lohn/Essen/Franchise, konservatives Einnahmen-Minimum, alle vier Berichtsaktionen, Auto-Ende mit Persistenz, Berichtsschalter, Jahresend-Auswertung, Kaskaden-Abdeckung, Migrations-Idempotenz).

Validierte Gates: `compileall`, `sync_version.py --check`, i18n-Audit (de=en=fr, 2208 Keys), DAU-Erststart, Release-Logik-Audit 100 Loops, Deep-Logic-Audit 500 Loops / 3500 Checks, Lint-Prozedur, `pytest` headless. PySide6-GUI-Smoke (Kontextmenü-Aktionen, Budgetart-Dialog beim Übernehmen, Jahreswechsel-Hinweis, Einstellungen), Qt-Translation-Verify, PyInstaller und Inno Setup müssen weiter in der Build-/CI-Umgebung laufen.


# v2.1.4 – Tracking-Lernmodus, stabile Tabellenbreiten, Theme-konforme Diagramme

Konsolidierter Release aus zwei v2.1.4-Ständen. Macht den Nur-Tracking-Workflow rund (nur Einkommen/Fixkosten budgetiert, alles Weitere wird erst getrackt) und behebt die zwei sichtbaren UI-Fehler an der Wurzel.

- **NEU – Separater Tracking-Lernmodus:** Kategorien, die im **gesamten Jahr** kein Budget > 0 haben, aber manuell getrackt werden, erhalten eigene Budget-Vorschläge – bewusst **getrennt** von der normalen Budget-Vorschlagsengine (`get_tracking_budget_suggestions` in `model/budget_overview_model.py`, ergänzt NACH der Engine, ohne deren Logik zu berühren). Stufen: 1. Monat beobachten → ab Vorschlags-Schwelle (Standard 2 Monate) Hochrechnung/Vorschlag → ab Stabilitäts-Schwelle (Standard 3 Monate) stabiler Vorschlag. Betrag = Median (ausreisserrobust), nur manuelle Buchungen (`tracking.source`), laufender Monat optional taggenau hochgerechnet. Sobald irgendwo im Jahr ein Budget gesetzt ist, greift wieder ausschliesslich die normale Anpassungslogik.
- **Einstellbar:** Neue Optionen unter Einstellungen → Budget-Übersicht: Lernmodus an/aus, „Vorschlag ab X Monaten", „stabil ab X Monaten", „laufenden Monat hochrechnen".
- **Budget-Vorschlagsdialog:** Lernvorschläge erscheinen als „neu" (i18n) statt Prozentwert; DB-Typ wird sprachunabhängig über `Qt.UserRole` transportiert (Anwenden bricht in en/fr nicht mehr); stabile feste Spaltenbreiten.
- **BUG-FIX – Tabellenbreiten „springen" nach Einstellungsänderungen (Wurzelursache):** `utils/table_autosize.py` setzte bei jeder Theme-/Schriftanwendung die Standard-**Spaltenbreite** aller Tabellen zurück (Default-Section-Size auf dem Horizontal-Header ≙ Spaltenbreite, nicht Header-Höhe) und zwang alle Resize-Modi global auf Interactive. Jetzt wird nur noch die Zeilenhöhe angepasst. Ergänzend behalten Budget-, Tracking- und Vorschlagsdialog-Tabellen feste Spaltenbreiten.
- **BUG-FIX – Diagramme Theme-fremd/abgeschnitten:** `QChart` ignoriert Qt-Stylesheets; Hintergrund blieb weiss, Titel/Achsen/Pie-Aussenlabels schwarz (im dunklen Theme teils unlesbar), Margins=0 schnitt Aussenlabels ab. `CompactChart` rendert jetzt transparent, färbt nach jedem Serienaufbau Titel, Legende, Achsen und Slice-Labels über `ui_colors`, 4px-Margins.
- **Übersicht inhaltlich korrigiert:** Donut zeigt Über-Budget-Anteile als eigene Slice; Bilanz und Monatsbilanz-Verlauf rechnen Einkommen − Ausgaben − Ersparnisse (Ersparnisse binden den Einkommenstopf).
- **i18n:** Neue Keys `suggestion.suggestion_tracking_projection`, `suggestion.suggestion_tracking_stable`, `budget_adjustment.new_budget_label` sowie die Lernmodus-Einstellungstexte – de/en/fr jetzt je **2183 Keys** (Parität geprüft, Einfügereihenfolge erhalten). Die Lernmodus-Meldung ist nicht mehr hardcoded deutsch.
- **Neue Regressionen:** `tests/test_tracking_budget_learning.py` (Lernstufen, Jahres-Budget-Sperre, manuelle-Buchungen-Filter) und `tests/test_release_214_ui_fixes_static.py` (Horizontal-Header bleibt unangetastet, Theme-Anwendung in allen Chart-Buildern, i18n-Keys + Parität, keine hardcodierten Lernmodus-Texte).

Validierte Gates: `compileall`, `sync_version.py --check`, i18n-Audit (de=en=fr, 2183 Keys), DAU-Erststart, Release-Logik-Audit 100 Loops, Deep-Logic-Audit 500 Loops / 3500 Checks, Lint-Prozedur, `pytest` headless. PySide6-GUI-Smoke (Lernvorschlag nach 2 getrackten Monaten, Budget setzen → normale Logik übernimmt, Tabellenbreiten nach Einstellungsänderung, Diagramme dunkel/hell), Qt-Translation-Verify, PyInstaller und Inno Setup müssen weiter in der Build-/CI-Umgebung laufen.


# v2.1.3 – Budget-Vorschlag: Fehlklassifizierte Monatsausgaben nicht mehr aufblähen

Korrigiert einen Fehler im Budget-Anpassungsvorschlag: Eine als **Fix ohne Wiederkehrend** markierte Kategorie wird per Default als Pot/Rückstellung behandelt. Die Pot-Logik verglich jedoch die **Summe mehrerer Monate Ist** gegen **ein einzelnes Monatsbudget**, was bei regelmässigen Monatsausgaben absurde Vorschläge erzeugte (z.B. Lebensmittel mit Budget 400/Monat → Vorschlag 1230).

- **Ursache:** Im Pot-Zweig der Vorschlagsengine wurde `Summe(Ist über N Monate)` gegen `max(Monatsbudget)` (ein Monat) verglichen. Bei einem echten Einmal-Topf (Franchise) ist `Summe = max`, daher fiel es dort nicht auf; bei einem gleichmässig monatlichen Budget (z.B. 400 in jedem Monat) war die Fenster-Kapazität aber N×400, nicht 400.
- **Fix – Regelmässigkeits-Heuristik:** Eine „Pot"-Kategorie, die in (nahezu) jedem Fenstermonat gebucht wird, ist faktisch eine laufende Monatsausgabe und wird **pro Monat** verglichen (Fenster-Ist gegen Fenster-Budget, Erhöhung monatlich normiert). Echte, lumpy bezogene Töpfe (Franchise/Selbstbehalt) behalten unverändert die Topf-Cap-Logik. Ein einzelner Null-Monat (Ferien) kippt eine sonst monatliche Kategorie nicht zurück in die Topf-Inflation (`aktiv ≥ Fenster−1`).
- **Wirkung:** Lebensmittel (400/Monat, jeden Monat gebucht) erhält jetzt sinnvolle monatliche Vorschläge (z.B. +40/+60) statt +830. Echte Töpfe sind byte-genau unverändert.
- **Neue Regression:** `tests/test_suggestion_regular_monthly_pot.py` sichert die Monatslogik bei regelmässiger Buchung, die Selbstkorrektur am aktuellen Budget und die unveränderte Franchise-/Topf-Semantik ab.
- **Dokumentation konsolidiert:** Die uneinheitlichen Testzahlen der v2.1.0-Nachweise (243/246/252) wurden auf die massgebliche Zahl 258 vereinheitlicht; veralteter Datei-Versionsstempel in `views/budget_entry_dialog.py` auf 2.1.3 nachgezogen.

Validierte Gates: `compileall`, `sync_version.py --check`, i18n-Audit (de=en=fr, 2171 Keys), DAU-Erststart, Release-Logik-Audit 100 Loops, Deep-Logic-Audit 500 Loops / 3500 Checks, `pytest` headless 262 passed. PySide6-GUI-Smoke, Qt-Translation-Verify, PyInstaller und Inno Setup müssen weiter in der Build-/CI-Umgebung laufen.


# v2.1.0 – Release-Härtung, Performance und Konsolidierung

Diese Version bündelt die Fix-Runden aus dem kritischen Release-Audit und setzt die offene Review-Liste vollständig um. Schwerpunkt: weniger doppelte korrektheitskritische Logik, schnellere Datumsabfragen, robusteres SQLite-Locking und nachvollziehbare Release-Dokumentation.

- **Single Source of Truth für Datumsbereiche:** Neuer zentraler Helfer `model/date_ranges.py` mit `month_bounds()` und `year_bounds()`. `tracking_model.py` und `cockpit_tab.py` haben keine lokalen `_month_bounds()`-Dubletten mehr.
- **Weitere Datums-Hotspots bereinigt:** `get_month_total()`, Budgetübersicht, Budgetwarnungen, Vorschlagsengine und KPI-Monatswerte nutzen jetzt denselben halb-offenen Monatsbereich `[start, end)`. Das vermeidet Off-by-one-Risiken und hält SQLite-Abfragen indexfreundlich.
- **SQLite-Lock-Verhalten konsistent:** `connect(timeout=10.0)` wird nicht mehr durch `PRAGMA busy_timeout = 5000` auf effektiv 5 Sekunden zurückgestutzt. Alle relevanten Verbindungen verwenden nun `busy_timeout = 10000`.
- **Kanonische Typ-Sprache bereinigt:** Veraltete interne Kommentare mit „Einnahmen” als DB-Typ wurden auf den kanonischen Wert „Einkommen” korrigiert. Anzeige-Aliasse und nutzerfreundliche Texte bleiben unverändert.
- **Release-Traceability verbessert:** Die vorher getrennten Fix-/Performance-Reports wurden zu einem konsolidierten Release-Nachweis `RELEASE_REPORT_v2_1_0.md` zusammengeführt.
- **Neue Regressionen:** `tests/test_release_210_hardening.py` sichert Datumsbereichs-Grenzen, ungültige Monatswerte, entfernte lokale `_month_bounds()`-Dubletten und den 10-Sekunden-`busy_timeout` ab.
- **Windows-/Portable-Diagnose ergänzt:** Unter Hilfe/Info gibt es jetzt `Log anzeigen`, `Crash-Log anzeigen`, `Diagnoseordner öffnen` und `Fehlerbericht erstellen`.
- **Crash-Hinweis beim Neustart:** Ein Qt-freier `runtime_state.json`-Wächter erkennt einen vermuteten Crash/Kill/Stromausfall und bietet beim nächsten Start Loganzeige oder lokalen Fehlerbericht an.
- **Lokaler Fehlerbericht ohne Nutzerdatenbank:** Das Diagnose-ZIP enthält Logs, System-/Versionsinfo und bereinigte Einstellungen, aber keine DB, keine Backups und keine Exporte.
- **Version hochgezogen:** App, Installer, Manifest-Vorlagen, README und Versionsdateien sind auf `2.1.0` synchronisiert.

Validierte Gates: `compileall`, `sync_version.py --check`, i18n-Audit, DAU-Erststart, Release-Logik-Audit 100 Loops, Deep-Logic-Audit 500 Loops / 3500 Checks, `pytest` headless mit 258 PASS. PySide6-GUI-Smoke, Qt-Translation-Verify, PyInstaller und Inno Setup müssen weiter in der Build-/CI-Umgebung laufen.


# v2.0.41 – Sicherheits-Härtung: Verifikations-Hash vom DB-Schlüssel getrennt

Aus einem Hardening- und Stabilitäts-Audit von v2.0.40. Ein kritischer Kryptografie-Befund wurde behoben; SQL-Injection-Fläche, Subprozess-Aufrufe, Restore-Pfade (ZipSlip), Qt-Absturzvektoren und Migrations-Idempotenz wurden geprüft und sind sauber.

- **Kritisch behoben – PIN/Passwort-Schutz war aushebelbar:** Der in `users.json` gespeicherte Passwort-Verifikations-Hash (`pw_hash`) wurde mit exakt derselben PBKDF2-Eingabe erzeugt wie der Schlüssel zum Verpacken des db_key (gleiches Secret, gleicher Salt, 600k Runden, 32 Byte). Dadurch war der gespeicherte Hash byte-identisch zum Wrapping-Key (nur hex statt base64). Wer Lesezugriff auf `users.json` hatte, konnte daraus zusammen mit dem ebenfalls dort liegenden verpackten Schlüssel den db_key **ohne Passwort** rekonstruieren und die verschlüsselte `.enc`-Datenbank entschlüsseln. PIN/Passwort bot damit kryptografisch keinen Schutz über den Quick-Modus hinaus.
- **Fix – Domain-Trennung:** Der Verifikations-Hash wird jetzt über einen Kontext-Präfix (`PW_VERIFY_CONTEXT`) domain-getrennt abgeleitet und kann den Wrapping-Key nicht mehr ergeben. Ein Angreifer muss wieder das Passwort gegen PBKDF2 600k brute-forcen.
- **Automatische Migration:** Bestehende Konten werden beim nächsten erfolgreichen Login transparent auf das sichere Format gehoben – inklusive Salt-Rotation und Neuverpackung. Der Upgrade greift jetzt auch bei Konten, die bereits auf 600k Runden liegen, aber noch den alten key-äquivalenten Hash haben (diese Lücke verfehlte der bisherige reine Rundenzahl-Trigger). `verify_password` akzeptiert weiterhin Alt-Hashes, damit kein Bestandskonto ausgesperrt wird.
- **Neue Sicherheitstests:** `test_password_hash_keysep_v2041.py` – der gespeicherte Hash kann den Wrapping-Key nicht rekonstruieren, `verify_password` akzeptiert neues und altes Format, und ein Alt-Konto wird beim Login nachweisbar migriert.
- **Audit-Ergebnis sonst:** keine `eval`/`exec`/`pickle`/`shell=True`; alle dynamischen SQL-Identifier sind whitelisted oder literal, Nutzerdaten immer parametrisiert; Restore liest fest benannte ZIP-Einträge ohne `extract()` (kein ZipSlip); bekannte Qt-Absturzvektoren (`QChart.NoAnimation`, `closeEditor`/`commitData` ohne `installEventFilter`) sind mitigiert; `migrate_all` ist idempotent.
- **Release-Prozedur fest verdrahtet:** `lint_procedure_check.py` prüft jetzt zusätzlich, dass kritische Regressionstests für Prozedur, Account-Management, Sprache und Passwort-Hash-Härtung im Release-Baum vorhanden bleiben.
- **Account-/Sprach-Härtung:** Sicherheitsstufen und PIN/Passwort-Platzhalter werden nun über zentrale lokalisierte Helper angezeigt, damit EN/FR-Oberflächen keine deutschen Model-Labels wie „Passwort“ oder „Ohne Passwort“ mehr durchreichen.
- **Neue Regressionstests:** `test_lock_procedure_account_language_v2041.py` deckt Lockfile-/Prozedur-Gates, Account-Lifecycle Quick → PIN → Passwort → Löschen und Security-Label-Lokalisierung in de/en/fr ab.
- Changelog, Release-Nachweise und Paketwurzel auf v2.0.41 synchronisiert.



Diese Version geht aus einer kritischen Release-Ready-Tiefenanalyse von v2.0.39 hervor. Funktionen, Forecast-/Null-Bilanz-Logik und der gesamte Update-Pfad wurden geprüft; statische Analyse fand keine Dead-Ends, undefinierten Aufrufe oder unerreichbaren Code. Ein echtes Updater-Race wurde behoben:

- **Updater-Race behoben (Stabilität):** Der Update-Dialog löschte `last_check.json` direkt nach dem Start des abgekoppelten `apply_update`-Prozesses. Da der EXE-Bootstrap langsamer ist, konnte die Datei verschwinden, bevor `target_staged_version()` sie las – `apply_update` fiel dann auf `latest_staged_version()` zurück und hätte einen veralteten, höher nummerierten Staging-Ordner (z. B. einen Beta-Rest) anwenden können. Das redundante Löschen wurde entfernt; `_check()` setzt den Zustand ohnehin vor jeder Prüfung zurück.
- **Staging-Hygiene (Defense-in-Depth):** `check_update` entfernt nach erfolgreichem Staging alle anderen Staging-Ordner und veralteten `update_*`-Cache-Dateien. Damit ist die höchste vorhandene Staging-Version immer die gerade vorbereitete – der sichere Fallback in `apply_update` kann keine Altversion mehr aufgreifen, und der Update-Ordner wächst nicht unbegrenzt. Fremde Dateien im Cache bleiben unangetastet.
- **Neue Regressionstests:** `test_updater_staging_pruning_v2040.py` deckt ab: Pruning behält die Zielversion und entfernt Geschwister-Ordner, Cache-Pruning fasst nur eigene Artefakte an, der End-to-End-Check räumt einen alten Beta-Staging-Ordner ab (Race-Sicherheitsnetz), und ein statischer Schutz verhindert eine Regression des Race-Fixes im Update-Dialog.
- **Testisolation:** `test_shortcuts_i18n.py` stellt die globale Sprache am Ende wieder her, damit nachfolgende Tests nicht von einer hängengebliebenen Sprache abhängen.
- Changelog, Release-Nachweise und Paketwurzel auf v2.0.40 synchronisiert.



- Neuer Jahreswechsel-Review für Fixkosten, wiederkehrende Kosten, Pot- und inkrementelle Kategorien: beim Kopieren ins neue Jahr können Positionen übernommen, abgewählt oder mit geändertem Jahresbetrag verteilt werden.
- Jahreskopie verteilt geprüfte Kategorien nach dem tatsächlichen Vorjahresmuster, damit unregelmäßige Jahres-/Teilzahlungen nicht pauschal auf 12 Monate verfälscht werden.
- 13. Monatslohn kann als eigenes einmaliges Einkommen mit Auszahlungsmonat und Betrag geplant werden; der normale Monatslohn bleibt dadurch forecast-sauber.
- 13.-Monatslohn-Dialog gehärtet: aktive Währung statt festem CHF-Suffix, lokalisierte Standardkategorie, kein 0.00-Betrag, Erfolgstext über zentrale Geldformatierung.
- Jahreswechsel-Dialog gehärtet: Regel-/Flag-Labels werden jetzt in de/en/fr lokalisiert statt hart auf Deutsch aus dem Modell angezeigt.
- i18n-Audit erweitert: EN/FR werden nicht nur auf Key-Parität, sondern auch auf deutsche Restübersetzungen in tatsächlich referenzierten UI-Keys geprüft.
- Changelog, Release-Nachweise und Paketwurzel auf v2.0.39 synchronisiert.

# v2.0.38 – Sanfte Null-Bilanz-Vorschläge

- Einkommen wird optional als Topf betrachtet: Einnahmen minus Ausgaben minus Ersparnisse.
- Neuer Einstellungs-Schalter „Sanfte Null-Bilanz-Regel aktivieren“.
- Überschüsse können in Ersparnisse vorgeschlagen oder als Carryover-Hinweis angezeigt werden.
- Negative Bilanzen reduzieren zuerst Ersparnisse und danach nur flexible Ausgaben; Fixkosten, Pots und inkrementelle Jahresrechnungen bleiben tabu.
- Forecast-Pot-/Fixkostenfälle aus v2.0.37 bleiben unverändert abgesichert.

# Changelog

### v2.0.37 – Forecast-Pot, inkrementelle Fixkosten und Budgetwarn-Schalter

- Neuer Kategorie-Forecast-Modus: Auto, Pot/Rückstellung, Inkrementell/Jahresrechnung, Normal/Flexibel.
- Auto-Regel: Fix ohne Wiederholung wird als Pot behandelt; Fix oder Wiederkehrend als inkrementell.
- Forecast-Fälle für Franchise/Pot und Jahresrechnung mit Regressionstests abgesichert.
- Einstellung „Budgetüberschreitung warnen“ steuert jetzt Budgetwarner, Auto-Warnungen und Deckungslücken-Banner.
- Datenbankschema auf v13 erweitert (`categories.forecast_mode`).

### v2.0.36 – Update-Sicherheit gehärtet (fail-closed Integritätsprüfung)

Diese Version geht aus einem kritischen Review von v2.0.35 hervor. Logik (Forecast), i18n, DAU-Freundlichkeit und der neue Startup-Update-Check wurden unabhängig geprüft und sind solide. Zwei Härtungspunkte rund um die Update-Sicherheit wurden behoben:

- **Integritätsprüfung jetzt fail-closed (Sicherheit):** Lädt der Update-Check ein Asset, dessen Manifest keinen SHA256 enthält, wird das Update jetzt **abgelehnt** statt „ohne Integritätscheck akzeptiert". Damit kann ein manipuliertes Manifest die Prüfung nicht mehr umgehen. Der GitHub-Build setzt für jedes Asset (Installer, Standalone-EXE/-Binary, Portable-ZIP) immer einen echten SHA256 ein, daher blockiert das keine legitimen Releases. Ein falscher Hash wurde bereits zuvor korrekt abgelehnt.
- **Versionsvergleich konservativ bei unlesbaren Versionen:** `is_newer()` liefert bei nicht interpretierbaren Versionsangaben jetzt `False` (kein Update-Hinweis), statt bei blosser Ungleichheit fälschlich ein – womöglich älteres – „Update" zu signalisieren. Der reguläre SemVer-Vergleich (z. B. 2.0.9 < 2.0.10) bleibt unverändert.
- **Neue Sicherheitstests:** `test_update_integrity_failclosed.py` deckt ab: Ablehnung ohne SHA256, Ablehnung bei falschem SHA256, konservatives `is_newer`. Die bestehenden Staging-Erfolgstests prüfen jetzt mit einem gültigen SHA256 (statt leerem Feld) und damit zusätzlich die Hash-Verifikation.

Hinweis: Der Startup-Update-Check selbst lädt nichts herunter und war von der fail-open-Schwäche nicht betroffen; die Härtung betrifft den eigentlichen Download-/Staging-Pfad (`check_update`).

### v2.0.35 – Installer-Updater für Windows-Setup-Version

- Installierte Windows-Versionen aktualisieren jetzt über das `windows_installer`-Asset statt über Portable-/Standalone-Dateiersatz.
- Der In-App-Updater lädt `BudgetManager_Setup_<version>.exe`, staged sie als Installer und startet nach App-Ende einen sichtbaren Batch-Helfer.
- Der Batch wartet auf das Ende von `BudgetManager.exe`, startet das Setup im Update-Modus und übergibt den bestehenden App-Ordner sowie den gewählten Datenordner.
- Inno Setup bewahrt den vorhandenen Datenordner bei Updates über `/DATA_DIR`, vorhandene `installation.json` oder Standard-Fallback.
- Datenordner-/Grundeinstellungsseiten werden im Update-Modus übersprungen; Uninstaller, Startmenü und Installationspfad bleiben unter Kontrolle des Installers.
- Regressionstests für Installer-Staging, Installer-Apply-Batch und Inno-Update-Parameter ergänzt.

### v2.0.33 – Installer-Datenordnung, Standalone-Updater und Linux-Start

- Windows-Installer bündelt veränderliche Daten jetzt sauber im gewählten Datenordner: `budgetmanager_settings.json`, `users.json`, `.enc`/DB, Backups, Exporte, Updates und Theme-Overrides landen dort statt verteilt in Programmordner/AppData/Home.
- `installation.json` bleibt nur als kleiner Bootstrap-Marker im Programmordner und enthält den gewählten Datenordner für App und Updater.
- Windows-Standalone-EXE bevorzugt nun das direkte EXE-Asset und ersetzt beim Update die tatsächlich gestartete EXE-Datei, damit Doppelklick/Verknüpfung weiter funktionieren.
- Updater-Cache/Staging liegt bei Installer-Installationen im gewählten Datenordner; Installer-Updates starten weiter die neue Setup-EXE.
- Linux-Start vereinfacht: `run.sh`/`start-linux.sh` setzen Qt-Scaling, starten eine vorhandene `BudgetManager`-Binary oder erstellen für den Source-Start automatisch eine lokale `.venv`.
- Regressionstests für Installer-Datenpfad, Updater-Asset-Priorität und zentrale Datenordner-Logik angepasst/ergänzt.

### v2.0.28 – Release-Blocker-Fix Budget-Modi, Money-Validation und Hardcoded-Audit

- Budget-Erfassungsmodus von sichtbaren Labels entkoppelt: Geschäftslogik nutzt jetzt stabile Werte `month`, `all`, `range`.
- Legacy-/Anzeigewerte `Monat`, `Alle`, `Bereich`, `Month`, `All`, `Range`, `Mois`, `Tous`, `Période` werden robust normalisiert.
- Budget- und Tracking-Dialoge validieren Beträge strikt; nicht-numerische Eingaben werden nicht mehr als `0.0` akzeptiert.
- Copy-Year-Bereich nutzt sprachneutrale itemData statt sichtbarem `Alle`-Text.
- i18n-Audit erkennt zusätzliche harte UI-Strings in `addRow`, `addItem`, `addItems`, `insertItem` und `setItemText`.
- Bekannte deutsche EN/FR-Restwerte übersetzt und Regressionstests für Money-Parser, Budget-Modi und i18n-Rückfälle ergänzt.

### v2.0.27 – Final-Release-Härtung Updater, Portable-ZIP und i18n

- Frozen/In-App-Updater korrigiert: Update-Dialog startet im PyInstaller-Build jetzt `--check-update --gui` und `--apply-update` statt nur die normale EXE.
- Portable-ZIP stabilisiert: Im ZIP heißen die Startdateien `BudgetManager.exe` und `BudgetManager`; GitHub-Release-Assets dürfen weiterhin versioniert sein.
- Windows-Updatepfad gehärtet: alte versionierte Portable-Binaries werden nach dem Schließen der App entfernt und der stabile neue Startpunkt wird gestartet.
- Linux/DEV-Updatepfad startet nach erfolgreichem Apply wieder neu, bleibt aber in Tests per `BM_UPDATER_NO_RESTART` deaktivierbar.
- Release-Dokumentation, Help-Dateien, Manifest-Vorlagen und Versionsangaben auf v2.0.27 synchronisiert.
- Mehrere dynamische Dialogtexte in Budget, Sparzielen, Tags, Themes, Login, Tracking, Backup/Restore und Datenbank-Info über i18n-Keys gehärtet.
- Zusätzliche Release-Tests für Updater-Einstiegspunkte, ZIP-Struktur, Dokumentversionen und i18n-Parität ergänzt.

### v2.0.26 – i18n-Härtung Fehler-/Eingabepfade (de/en/fr)
- **Fehlermeldungen vollständig lokalisiert:** Restore-/Entschlüsselungs- und Kategorie-Fehler erschienen in seltenen Fehlerpfaden noch hart auf Deutsch (bzw. als roher i18n-Key), wenn ein Dialog sie nur generisch als `{error}` einbettete. Neu werden sie in de/en/fr angezeigt.
- **Krypto-Fehler übersetzbar:** Neue `CryptoUserError(ValueError)` in `model/crypto.py` rendert Restore-Key-, Entschlüsselungs- und „Salt zu kurz"-Fehler zur Anzeigezeit lokalisiert (Fallback Deutsch nur, falls i18n nicht initialisiert). Bleibt `ValueError`-Subklasse – bestehende `except`-Pfade unverändert. Zwei neue Schlüssel `crypto.*` in de/en/fr.
- **Kategorie-Fehler übersetzbar:** Neue `CategoryError(ValueError)` in `model/category_model.py` für die fünf Stellen, die bisher einen i18n-Key als Exception-Text warfen (Umbenennen auf bestehenden Namen, Lösch-Ziel-Validierung, Reparent-Zyklus/Typ). `str()` liefert nun den übersetzten Text inkl. Format-Argumente statt des rohen Keys – behebt u. a. den rohen `categories.category_exists` im Budget-Tab-Umbenennen und im Budget-Eingabedialog.
- **Erststart-Assistent: fehlende Namensprüfung ergänzt.** `views/startup_wizard.py` prüft jetzt – wie der Login-Dialog – vor dem Anlegen auf einen leeren Namen und zeigt `account.bitte_einen_namen_eingeben` (de/en/fr), statt mit leerem Namen in `create_user` zu laufen und dort eine harte deutsche Meldung auszulösen.
- **Hardcodierter SpinBox-Suffix entfernt:** `views/category_properties_dialog.py` nutzt für „… des Monats" jetzt den bestehenden Schlüssel `categories.day_suffix` (de/en/fr) statt eines fest verdrahteten deutschen Suffix (zwei Stellen).
- **Qualität abgesichert:** Statische Loops über doppelte Methoden, kaputte Signal-Verbindungen, `trf()`-Platzhalter/kwarg-Parität, Exception-Variablen-Mismatch, vergessene f-Präfixe und Header-/Eingabedialog-Hardcodes – ohne weitere Funde. i18n-Parität de=en=fr (1978 Schlüssel), Qt-freie Regressionstests, DAU-Erststart und Versions-Synchronisation grün.

### v2.0.25 – Release-Readiness-Härtung Konto-Hub
- **Vergleich gegen v2.0.24 Release-Hardening:** Konto-Hub/Datenübernahme wurde mit der gehärteten v2.0.24 zusammengeführt, ohne die PBKDF2-Legacy-Kompatibilität und zentrale Datenordner-Pfadlogik zu verlieren.
- **PBKDF2 rückwärtskompatibel:** Vorab-Konten mit 200 000 Iterationen können sich weiter anmelden und werden nach erfolgreichem Login automatisch auf 600 000 Iterationen umverpackt.
- **Datenordner vollständig durchgezogen:** Default-DB und Default-Backup-Pfade folgen jetzt auch im Konto-Hub/Backup/Starter/Auto-Backup dem aktiven Datenordner. Explizite Sonderpfade bleiben erhalten.
- **Datenübernahme sicherer:** Der Konto-Hub übernimmt den neuen Speicherort nur noch, wenn der zentrale Handler die Änderung tatsächlich angewandt hat; bei abgebrochener oder fehlgeschlagener Migration bleibt der alte Zustand sichtbar und aktiv.
- **i18n nachgehärtet:** Letzte hartcodierte Statusleisten-Texte wurden durch de/en/fr-Schlüssel ersetzt.
- **Release-Artefakte bereinigt:** `.pytest_cache`, `__pycache__`, `.pyc` und veraltete Runtime-Audit-Dateien sind aus dem Paket entfernt und per Ignore-/Regressionstest abgesichert.
- **Zusätzliche Regressionstests:** Datenordner-Defaultpfade, explizite Pfade, Konto-Hub-Abbruchpfad, PBKDF2-Legacy-Upgrade und Release-Integrität.

### v2.0.24 – Konto & Daten gebündelt + Datenübernahme
- **Neuer Reiter „Konto":** Konto, Speicherort, Sicherung (Backup) und Zurücksetzen sind jetzt an **einem** Ort gebündelt – als eigener Hauptreiter und identisch unter Einstellungen → „Konto & Daten". Eine wiederverwendbare Hub-Komponente (`views/account_data_hub.py`) wird in beiden Stellen eingebettet.
- **Schluss mit verstreuten Einstiegen:** Backup und Datenbank-Verwaltung sind nicht mehr einzeln im Extras-Menü verteilt, sondern über den Hub erreichbar. Das Konto-Menü verlinkt zusätzlich direkt auf den neuen Reiter. Die bestehenden, getesteten Dialoge (Konto verwalten, Backup & Wiederherstellung, Datenbank-Verwaltung) bleiben unverändert und werden vom Hub geöffnet.
- **Datenübernahme beim Ordnerwechsel:** Wird ein neuer Datenordner gewählt und liegen im bisherigen Ordner bereits Daten, bietet die App an, diese zu übernehmen. Dabei wird zuerst ein **Sicherheits-Backup** (ZIP) im Zielordner erstellt, anschließend werden `.enc`-Dateien, `users.json` und der `backups`-Ordner **kopiert** (der bisherige Ordner bleibt unangetastet als zusätzliche Sicherung). Erst nach Neustart aktiv.
- **Sicher gegen Vermischen:** In einen Zielordner, der bereits Daten enthält, wird nicht übernommen; bei Übernahme wird die aktive verschlüsselte Sitzung vorher auf die Platte gesichert. Bei Fehlern bleibt der bisherige Speicherort aktiv. Logik liegt Qt-frei in `model/data_location.py`.
- **Speicherort jetzt im Hub:** Die Datenordner-Auswahl wurde aus der alten Einstellungen-Seite „Datenbank" in den Hub verschoben; die Auto-Backup-Feineinstellungen bleiben darunter erhalten.
- i18n: neue Schlüssel für Reiter, Hub und Datenübernahme in de/en/fr (Parität gewahrt).
- Regressionstests ergänzt: Datenübernahme (Allowlist, Sicherungs-ZIP, Kopieren statt Verschieben, Schutzregeln) und Hub-Struktur/Delegation.

### v2.0.23 – Wählbarer Datenordner + stärkere Schlüsselableitung
- **Datenverzeichnis frei wählbar:** Der Speicherort für Datenbank, Backups und verschlüsselte `.enc`-Dateien lässt sich jetzt in den Einstellungen (Seite „Datenbank") wählen. Leer = portabel (Ordner `data` neben dem Programm); ein gesetzter absoluter Pfad wird verwendet.
- **Installer-Datenpfad wirkt jetzt:** Der im Installer gewählte Datenordner (`data_directory`) wird von der App tatsächlich ausgewertet. Zuvor wurde der Wert geschrieben, aber nie gelesen – die Daten landeten immer im Programmordner.
- **Zentrale Pfadlogik:** `model/app_paths.data_dir()` liest `data_directory` aus der portablen Einstellungsdatei; ist nichts gesetzt, bleibt es beim portablen Standard. Die Einstellungsdatei selbst bleibt bewusst immer portabel (Bootstrap, kein Zirkelbezug).
- **Sicherheits-Hinweis bei Änderung:** Ein neuer Datenordner wird erst nach einem Neustart wirksam; bestehende Daten werden nicht automatisch verschoben (klarer Hinweis im Dialog und nach dem Speichern).
- **PBKDF2 auf 600 000 Iterationen erhöht** (zuvor 200 000) gemäß OWASP-2023-Empfehlung für PBKDF2-HMAC-SHA256. Da noch keine veröffentlichte Version existiert, ist keine Migration bestehender Datenbanken nötig.
- i18n: neue Schlüssel für den Datenordner-Bereich in de/en/fr (Parität gewahrt).

### v2.0.22 – Autobuchungs-Artfilter + Deckungswarnungen
- **Autobuchungsdialog erweitert:** Neben dem Kontofilter gibt es jetzt einen eigenen Artfilter für Alle Arten, echte Fixkosten (Fix + Wiederkehrend), Fix/variabel, Wiederkehrend/variabel und optionale Budgetposten.
- **Deckungswarnung im Budget-Tab:** Wenn geplante Ausgaben + Ersparnisse die Einnahmen übersteigen, erscheint oberhalb der Tabelle eine klare Warnung mit größtem Monatsfehlbetrag und Spar-Vorschlag.
- **Deckungswarnung im Tracking-Tab:** Bei Konto-Filter „Alle” warnt das Tracking, wenn gebuchte Ausgaben + gebuchte Ersparnisse höher sind als gebuchte Einnahmen.
- **Spar-Vorschläge:** Die Warnungen nennen eine einzelne Ersparnis-Kategorie, wenn diese den Fehlbetrag decken kann; sonst wird eine kombinierte Reduktion vorgeschlagen oder transparent gemeldet, dass keine Sparposition reicht.
- **Gemeinsame Fachlogik:** Die Berechnung liegt zentral in `model/coverage_model.py`, damit Budget und Tracking dieselbe Deckungslogik nutzen.
- Regressionstests ergänzt: Artfilter-Marker, Budget-/Tracking-Warnhooks und funktionale Coverage-Berechnung.

### v2.0.21 – Autobuchungen optional + Budget-Mehrfachauswahl
- **Autobuchungen erweitert:** Der Dialog zeigt jetzt neben echten Fixkosten und variablen Fix-/Wiederkehrend-Posten auch optionale Budgetposten ohne Fix- und ohne Wiederkehrend-Flag an. Diese Posten sind nicht vorausgewählt und werden als „Optional“ markiert.
- **Null-Budgets ausgeblendet:** Kategorien mit Budgetbetrag 0 werden im Autobuchungsdialog nicht mehr angeboten. Das betrifft echte Fixkosten, variable Fix-/Wiederkehrend-Posten und optionale Budgetposten.
- **Restbetrag statt Gesamtbetrag:** Variable und optionale Posten werden mit dem noch offenen Monatsbetrag vorbelegt. Bereits erreichte Budgets gelten als erledigt und werden übersprungen.
- **Kontofilter im Autobuchungsdialog:** Die Liste kann nach Alle, Ausgaben, Einnahmen oder Ersparnisse gefiltert werden. Auswahlbuttons wirken nur auf die sichtbaren Zeilen.
- **Budget-Tab Mehrfachauswahl:** Budgetzeilen können mit Strg/Shift + Mausklick mehrfach markiert werden. Rechtsklick auf eine Mehrfachauswahl erlaubt das Löschen mehrerer Budgetpositionen im aktuellen Jahr oder mehrerer Kategorien über den zentralen Sicherheitsdialog.
- **v2.0.19-Fix wieder abgesichert:** Die fehlenden Regressionstests für Kategorie-Validierung und doppelte Tracking-Methoden wurden wieder integriert; der Tracking-Tab ist erneut frei von den alten Methoden-Duplikaten.
- Regressionstests ergänzt: Autobuchungs-Optionen, Typfilter, Budget-Mehrfachauswahl, Kategorie-Validierung und Tracking-Duplikate.

### v2.0.20 – Schnelleingabe mit Suche + Dropdown
- **Usability-Fix:** Die Schnelleingabe nutzt für Kategorien jetzt ein klares Suchfeld plus ein echtes Dropdown-Menü. Tippen filtert die Kategorien live, das Dropdown zeigt nur passende Kategorien des gewählten Kontotyps.
- Das Dropdown bleibt gruppiert: Favoriten, häufig manuell gebucht, normale Buchungen, variable Fix-/Wiederholungs-Kategorien und echte Fixkosten. Leere Gruppen werden bei aktiver Suche ausgeblendet.
- Parent-Kategorien mit Kindern werden im Tracking nicht mehr als buchbare Zeile angezeigt; Unterkategorien erscheinen kurz als `Miete` statt `Wohnen › Miete`.
- Nach einer Dropdown-Auswahl wird der echte Datenbankname der Kategorie gespeichert. Kopfzeilen, Favoritenstern und Baum-Pfade bleiben reine Anzeige und werden nicht als Kategorie übernommen.
- Beim Kontotypwechsel wird die Suche zurückgesetzt, damit keine alte Ausgaben-Suche versehentlich Einkommen oder Ersparnisse leerfiltert.
- Regressionstests erweitert: Suche filtert Gruppen korrekt, Kindnamen/Pfade werden gefunden, nicht-editierbare Dropdowns verwenden nur echte `itemData()`.

### v2.0.19 – Schnelleingabe-/Kategorie-Picker-Fix
- **Bugfix:** Editierbare Kategorie-Comboboxen konnten bei getipptem Suchtext noch die vorherige `currentData()`-Kategorie zurückgeben. Dadurch konnte die Schnelleingabe bzw. der Tracking-Dialog auf eine falsche Kategorie buchen, wenn der Benutzer tippte, aber keinen Completer-Eintrag aktiv auswählte.
- Zentraler Kategorie-Resolver in `views/category_picker.py`: sichtbarer/getippter Text wird zuerst gegen echte Einträge geprüft; `currentData()` wird nur noch verwendet, wenn Text und aktueller Eintrag zusammenpassen. Favoritenstern und Baum-Pfade werden bereinigt.
- Schnelleingabe und Tracking-Dialog validieren vor dem Speichern, dass die Kategorie im gewählten Typ wirklich existiert; gespeichert wird der exakte Datenbankname.
- Budget-Kategorie-Dialoge nutzen dieselbe robuste Kategorieauflösung. Im erweiterten Dialog erzeugt „Nein“ bei nicht existierender Kategorie keinen verwaisten Budget-Eintrag mehr.
- Regressionstest ergänzt: `tests/test_category_combo_resolution.py`.

### v2.0.18 – Budgetvorschläge respektieren den Tracking-Beginn
- **Bugfix:** Mit nur einem gebuchten Monat (aber Budgets über mehrere Monate) erschienen bereits Anpassungsvorschläge, und die Häufigkeit zeigte unmögliche Werte wie „5/3". Ursache: Die Vorschlags-Engine zählte stur bis Januar/Vorjahr zurück und las Monate VOR der ersten echten Buchung als reale „0-Ausgaben"-Monate.
- Neue untere Analysegrenze in `BudgetSuggestionEngine`: der spätere von (erste echte Buchung global, konfigurierter Startmonat `carryover_start_*`). Monate davor werden in Abweichungsfenster, aktiven Monaten und Strähnen ignoriert (`_data_start_boundary`, `not_before`-Clamping in allen Rückwärts-Scans).
- Auto-Erkennung ohne neue Eingabe: Liegt keine Buchung und kein Startmonat vor, wird NICHT geklammert – die gewollte Langzeit-0-Reduktion (Budget gesetzt, 6+ Monate nie gebucht) bleibt damit erhalten.
- Häufigkeits-Boden entfernt (`budget_overview_model`): Der Zähler wird nicht mehr künstlich auf das Fenster angehoben; die Anzeige zeigt die echte Strähne. Im Dialog wird der Bruch zusätzlich auf das Fenster begrenzt – kein „5/3" mehr.
- „Chronischer Überschreiter" ist jetzt richtungsabhängig: dauerhaft UNTER-Budget-Kategorien werden nicht mehr fälschlich als Überschreiter markiert.
- Regressionstests ergänzt: `tests/test_suggestion_tracking_start.py` (6 Fälle). Alle bestehenden Fixkosten-Vorschlagstests bleiben grün.

### v2.0.17 – Konsolidierter Pre-Release-Fix
- Kombiniert den robusten Budget-Tab Editor-Lifecycle-Fix mit der verbesserten Bulk-Commit-Drossel `coalesced_commits(conn)`.
- Beibehaltung des rückwärtskompatiblen Alias `suspend_after_commit_autosave(conn)`, damit vorhandene Bulk-Pfade stabil bleiben.
- Fix/Wiederkehrend-Sammelbuchung im Tracking wird ebenfalls gebündelt.
- Kategorie-Import, Kategorien-Massenbearbeitung und Setup-Budgetgerüst behalten ihre Bulk-Bündelung aus der Final-Version.

### v2.0.17 – Budget-Tab Reentrancy-/Editor-Lifecycle-Fix
- Commit-Autosave bleibt für einzelne Aktionen sofort aktiv, wird bei Bulk-Pfaden aber gebündelt, damit verschlüsselte `.enc`-Dateien nicht unnötig oft vollständig neu geschrieben werden.
- Gebündelt wurden u. a. Kategorien-Massenbearbeitung, Sparziel-Neuberechnung, Kategorie-Import, Setup-Budgetgerüst, Budget-Jahr kopieren, Budget aus Kategorien erzeugen, Zeile auf alle Monate kopieren und automatische Budgetwarnungen.
- Aktiven QTableWidget-Zell-Editor vor Budget-Reload, Budget-Save, Dialog-Apply, Tabwechsel-Save und Fokuswechseln deterministisch schließen.
- Posted Editor-/View-Events gezielt drainen, bevor `setRowCount(0)` oder ein Tabellen-Rebuild Editorobjekte freigibt.
- Budget-Dialog-Apply blockiert doppelte Reloads durch `typ_cb.currentTextChanged`, damit nach `Budget erfassen` nur noch ein kontrollierter Tabellen-Rebuild läuft.
- Automatischer Fokus nach `Budget erfassen/bearbeiten` über zentrale Editor-Schleuse geführt und auf den konkreten Kontotyp eingeschränkt.
- Version auf 2.0.17 synchronisiert.

### v2.0.16 – Budget-Dialog-Segfault-Hotfix
- Budget-Tab nutzt kein `QObject.installEventFilter()` mehr für Enter-Navigation. Das beseitigt die Qt-Warnung `Cannot filter events for objects in a different thread`, die vor dem nativen `QAbstractItemView::closeEditor`-Segfault erschien.
- Enter-Navigation wurde in den Tabellen-Subclass verschoben und bleibt damit im normalen Qt-Eventfluss.
- `SelectedClicked` als Edit-Trigger entfernt: Zellen öffnen den Editor jetzt nicht mehr durch einen einfachen Auswahlklick, sondern per Doppelklick oder Edit-Taste. Das reduziert offene Zell-Editoren beim Öffnen von Dialogen und beim Tabellen-Reload.
- Automatischer Fokus nach Budget-Erfassen/Bearbeiten wird nur noch verzögert und defensiv gesetzt; wenn Qt noch einen Tabelleneditor schließt, wird der Fokus übersprungen statt erzwungen.

### v2.0.16 – DB-Autosave & Budget-Eingabe-Stabilisierung
- Verschlüsselte In-Memory-Datenbank speichert jetzt nach erfolgreichen `conn.commit()` automatisch in die `.enc`-Datei. Dadurch bleiben Budget-/Tracking-/Sparziel-Änderungen auch erhalten, wenn danach ein nativer Qt/PySide-Crash passiert.
- Bulk-Saves im Budget-Tab bündeln viele interne Commits zu einem verschlüsselten Disk-Save, damit Tabwechsel/Schließen sicher bleiben ohne hunderte `.enc`-Schreibvorgänge.
- Beim Tabwechsel wird der vorherige Budget-Tab still gespeichert, wenn Auto-Save aktiv ist (Standard). Beim Schließen über `X` oder `Datei → Beenden` wird ebenfalls gespeichert.
- Budget-Erfassen/Bearbeiten speichert nach Übernahme zusätzlich explizit die verschlüsselte Session und schreibt Diagnose-Logs.
- Fokuswechsel nach Budget-Dialog/Reload wird per `QTimer.singleShot(0, ...)` verzögert, um Qt-Reentrancy-Crashes unter XCB/Wayland zu vermeiden.
- Regressionstests für den Commit-Autosave-Hook ergänzt.

### v2.0.16 – Erststart-Segfault-Hotfix
- Auto-Backup wird beim aktiven First-Start-Assistenten nicht mehr parallel zur Dialog-Initialisierung ausgeführt, sondern bis nach dem Assistenten verschoben.
- Setup-Assistent startet verzögert nach dem Hauptfenster, damit Qt das Fenster vollständig realisieren kann.
- Riskante `raise_()`/`activateWindow()`-Fokusaktivierung beim automatischen Setup-Start entfernt, weil sie unter Fedora/Wayland via XCB sporadische native Qt-Segfaults auslösen kann.
- Zusätzliche Diagnose-Logs für Setup-Assistent und verschobenes Auto-Backup ergänzt.

### v2.0.16 – Sparziel-Grenzen fachlich erzwungen
- Sparziel-Stände werden nicht mehr nur in der Anzeige gedeckelt, sondern fachlich validiert.
- Entnahmen, die den Stand unter **0 CHF** ziehen würden, werden blockiert und melden den maximal entnehmbaren Betrag.
- Einzahlungen, die das Ziel über **100 %** füllen würden, werden blockiert und melden den maximal noch einzahlbaren Betrag.
- Die Prüfung greift im Sparziel-Dialog, in der Schnellerfassung, im Tracking-Dialog und beim Sync mit Tracking.

### v2.0.16 – Sparziel-Fortschritt unten gedeckelt
- `SavingsGoal.progress_percent` begrenzt Fortschritt jetzt beidseitig auf **0 % bis 100 %**. Dadurch zeigen Label und Fortschrittsbalken bei negativem Sparzielstand konsistent **0 %** statt negativer Prozentwerte.
- Regressionstest ergänzt: negative, normale, überfüllte und Zielbetrag-0-Fälle werden geprüft.
- Hinweis überholt durch die nachfolgende Fachregel: Der gespeicherte Stand darf nicht mehr unter 0 fallen; die Anzeige bleibt zusätzlich bei 0–100 %.


### v2.0.16 – Sparziel-Entnahme expliziter erklärt
- Hilfe, README und Feature-Übersicht erklären jetzt ausdrücklich, wie Geld aus einem Sparziel herausgebucht wird: `Ersparnisse` wählen, Ziel-Kategorie wählen, Betrag negativ erfassen, z. B. `-500 CHF`.
- Klarstellung ergänzt: Negative Beträge sind bei `Ersparnisse` erlaubt, bei `Ausgaben` bleiben sie bewusst gesperrt.
- Schnellerfassung erlaubt nun negative Beträge für `Ersparnisse` und zeigt bei aktiven/freigegebenen Sparzielen eine Sicherheitsinformation bzw. Bestätigungsfrage.

### v2.0.16 – Audit-Härtung & Release-Dokumentation
- Aktive Dokumentation, Installationshinweise, Feature-Übersichten, Hilfe-Kopfzeilen, Release-Checkliste und Updater-/Manifest-Beispiele auf v2.0.16 synchronisiert. Historische Changelog-Einträge bleiben absichtlich bei ihren alten Versionsnummern.
- `requirements.lock` ergänzt und Build-/Dev-Anforderungen auf den Lockfile-Pfad ausgerichtet, damit Release-Builds reproduzierbarer werden.
- CI erweitert: `black --check model/` und `mypy model/` laufen vor den Tests.
- `model/` mit Black formatiert und kleinere Typannotationen für den mypy-Lauf ergänzt.
- `CategoryModel` nutzt jetzt eine zentrale Tabellen-Whitelist für dynamische interne Tabellennamen (`PRAGMA table_info`, Lösch-Cascade).
- `recurring_transactions_model.py` als Legacy/experimentell kommentiert, damit klar ist, dass der aktive Wiederholungsworkflow kategoriebasiert läuft.

### v2.0.16 – Selbstheilung bei defektem Konto (kein Aussperren mehr)
- **Behebt das Aussperren durch ein defektes/verwaistes Konto.** Konnte beim Start die Datenbank eines Kontos nicht geöffnet werden – etwa nach einem **Erststart-Restore mit falschem Wiederherstellungscode**, einem abgebrochenen Schreibvorgang oder einer gesperrten Datei – beendete sich die App hart, und man kam erst wieder hinein, **nachdem man den `data`-Ordner manuell geleert** hatte.
- **Neu: Selbstheilung beim Start.** Statt hart zu beenden, bietet die App an, das nicht öffenbare Konto **inklusive seiner verschlüsselten DB zu entfernen** und die **Ersteinrichtung erneut zu starten** (Backup neu einspielen oder neuen Benutzer anlegen). Der `data`-Ordner muss **nie mehr manuell geleert** werden. Vorhandene Backup-Dateien bleiben unangetastet.
- Greift für den **automatischen Quick-Login** (Authentifizierung fehlgeschlagen) **und** für **jeden Einzelbenutzer**, dessen DB sich nicht öffnen lässt; die Benutzerauflösung läuft dafür in einer wiederholbaren Schleife.
- Neue dreisprachige Hinweise `startup.recover_title` / `startup.recover_question` (de/en/fr) und Regressionstests `tests/test_startup_recovery_no_brick.py`.

### v2.0.15 – Erststart-Restore gehärtet (kein Brick-Loop)
- **Behebt einen Sackgassen-/„Brick"-Loop beim Erststart.** Wer beim ersten Start ein Backup einspielt und den **Wiederherstellungscode falsch** eingibt (oder abbricht), bleibt nicht mehr auf der Sicherheitsseite des Assistenten hängen.
- **Neuer Ablauf:** Die Entschlüsselung wird **zuerst** versucht. Nur bei Erfolg geht es weiter. Schlägt sie fehl (falscher Restore-Key, Abbruch oder defektes Backup), wird der eben angelegte Benutzer **sauber zurückgerollt** und der Assistent kehrt zur **Auswahlseite** zurück – „wieder von vorne": neuen Benutzer anlegen **oder** Backup erneut einspielen.
- Der **Restore-Key des neuen Benutzers** wird erst **nach** erfolgreicher Entschlüsselung angezeigt (vorher konnte er für einen wieder verworfenen Benutzer erscheinen).
- Neuer dreisprachiger Hinweistext `startup.restore_retry_from_start` (de/en/fr) und Regressionstests `tests/test_startup_restore_brick_loop.py`.

### v2.0.14 – Dokumentationsbereinigung
- Aktive technische Dokumente unter `docs/` auf v2.0.14 gebracht.
- Alte Zwischenstands-, Audit- und Fix-Berichte aus dem Release-Paket entfernt.
- Python-Cache- und Test-Cache-Ordner aus dem ZIP entfernt.
- Release-Checkliste als aktuelle `docs/release-checklist.md` neu erstellt.


### v2.0.14 – Merge: Cockpit-Kontextmenü, Budgetwarnungen, Wayland-Fallback & i18n

- **Release-Dokumentation:** README, Installations-README, Feature-Übersicht, Updater-Doku und Hilfe-Kopfzeilen wurden auf v2.0.14 aktualisiert, damit keine v2.0.11/v2.0.9-Beispiele mehr als aktueller Stand erscheinen.
- **v2.0.14 und der v2.0.13-Fixstand wurden zusammengeführt.** Der automatische
  XCB/XWayland-Stabilitätsfallback aus v2.0.13 bleibt erhalten, damit der
  Wayland-TextInput-Segfault nicht wiederkehrt. Native Wayland-Nutzung ist
  weiterhin per `BM_ALLOW_WAYLAND=1` möglich.
- **Rechtsklick im Cockpit ist wieder nützlich statt tot.** Das Cockpit zeigt
  ein eigenes Kontextmenü mit Schnellaktionen: Buchung erfassen,
  Fix/Wiederkehrend buchen, Budgetwarnungen prüfen, Budget, Übersicht,
  Sparziele, Aktualisieren, Cockpit gestalten und alle Bereiche einblenden.
  Die Fachreiter behalten ihre normalen Bearbeiten-Kontextmenüs.
- **Neues Panel „Budgetwarnungen" im Cockpit.** Zeigt die echten,
  schwellenbasierten Budgetwarnungen (gleiche Engine wie der
  Budget-Anpassungsdialog, `BudgetWarningsModelExtended`): überschrittene
  Budgets, nach Auslastung absteigend, mit Auslastung in %,
  Überschreitungszähler und – sofern verfügbar – vorgeschlagenem Budget.
  Doppelklick öffnet die Budgetwarnungsprüfung. Die bestehende
  „Budget-Ampel" bleibt zusätzlich erhalten.
- **Hardcoded Cockpit-Texte entfernt.** Paneltitel, Buttons, Tooltips,
  Tabellenköpfe, Statusmeldungen und Leerzustände laufen wieder über i18n-Keys
  in Deutsch, Englisch und Französisch.

### v2.0.13 – Absturz-Fix: „double free or corruption" beim Chart-Neuzeichnen

- **QtCharts-Animationen deaktiviert.** Die Übersicht-Charts liefen mit
  `SeriesAnimations` (400 ms). Beim Neuzeichnen (z.B. **nach einer
  Budgetanpassung**) ruft jede Grafik `removeAllSeries()` auf; lief dabei noch
  eine Animation, gab QtCharts eine bereits gelöschte Serie frei → nativer
  Absturz **„double free or corruption"** (SIGABRT). Besonders unter
  **Wayland/Linux** trat das auf.
- Fix: `QChart.NoAnimation` in `CompactChart`. Das Umzeichnen aller Diagramme
  ist damit gefahrlos; an Aussehen/Funktion der Charts ändert sich sonst nichts.
- Hinweis: Falls unter Wayland weiterhin Grafikprobleme auftreten, hilft als
  Workaround der Start mit `QT_QPA_PLATFORM=xcb` (X11-Backend).

### v2.0.12 – Übersicht-Charts: 90-Tage-Budget & Top-Buchungen

**Donut/Ring-Chart bei rollierenden Zeiträumen (7/30/90 Tage) korrigiert**
- Das Budget im Ring-Chart wurde bisher über das **deaktivierte Monats-Combo** berechnet (Default: aktueller Monat) und mit dem Ist des gesamten Zeitraums verglichen. Bei 90 Tagen wurde so ~3 Monate Ist gegen **1 Monat Budget** gestellt → „offen"-Ring fälschlich 0 bzw. ~300 % Auslastung.
- Jetzt nutzt der Donut das **bereichsbezogene Budget** (über die Monate des gewählten Zeitraums summiert) — identisch zur KPI-Leiste darüber. Damit verschwindet der Widerspruch zwischen KPI-Leiste und Ring.
- Im Jahr-/Monats-Modus bleibt das Ergebnis unverändert (das Bereichsbudget entspricht dort Jahr bzw. Einzelmonat).

**Top-Buchungen pro Kategorie aggregiert**
- Bisher wurden **einzelne Buchungszeilen** nach Betrag sortiert; wiederkehrende Posten wie **Lohn** erschienen dadurch mehrfach (z.B. 3× im 90-Tage-Fenster).
- Jetzt werden Buchungen **pro Kategorie summiert** und die größten 5 Kategorien gezeigt (Lohn = eine Summe). Aggregationslogik in `model/overview_aggregation.py` (Qt-frei, testbar).

**Tests**
- `tests/test_overview_charts.py`: bereichsbezogenes Budget (90-Tage-Fenster) und Top-Buchungen-Aggregation.

### v2.0.11 – Aufräumen: Experten-Tab entfernt, Erststart-Name, Version

- **Separater Kategorien-Tab (Experten-Modus) entfernt.** Er war redundant: Kategorienverwaltung läuft weiterhin über den **Kategorie-Manager** (`Strg+K`, Menü Extras → Kategorien verwalten) und direkt im **Budget**-Tab (inkl. Drag & Drop). Der Schnellzugriff `Strg+2` öffnet jetzt den Kategorie-Manager-Dialog.
- Zugehörige **Settings-Option „separaten Kategorien-Tab anzeigen"** und der Menü-Umschalter entfernt.
- **Erststart-Platzhalter** des Anzeigenamens von „Christian Krämer" auf **„Max Mustermann"** geändert (de/en/fr).
- Hilfe/Wissensdatenbank: Verweise auf den entfernten Tab auf Kategorie-Manager/Budget-Tab umgestellt (de/en/fr, HTML + Markdown).
- Doppelten Platzhalter in `data/` aufgeräumt (`.keep` entfernt, `.gitkeep` bleibt).
- Version zentral auf **2.0.11** gezogen (app_info, version.json, Installer-`.iss`, `latest.json`-Templates, README/FEATURES/Updater-Doku).

### v2.0.10 – Fixkosten ohne Wiederholung, Budget-erreicht-Logik & Tracker-Picker

**Fixe Beträge ohne Wiederholung (Franchise, Selbstbehalt etc.)**
- Kategorien mit **fix XOR wiederkehrend** (genau ein Flag) gelten im Monat erst dann als abgeschlossen, wenn der **Budgetbetrag erreicht** ist — nicht mehr schon bei der ersten Buchung.
- Der **buchbare Betrag ist editierbar** und mit dem noch offenen **Restbetrag** vorbelegt. Damit lassen sich z.B. Krankenkassen-Franchise oder Selbstbehalt in mehreren Teilbeträgen über den Monat verbuchen.
- Kategorien mit **beiden** Flags (fix + wiederkehrend) bleiben wie bisher: fixer Monatsbetrag, gesperrt, einmal pro Monat.
- Budget-Voraussage unverändert: fix- oder wiederkehrend-markierte Kategorien sind weiter vor 0-Monats-Senkungen geschützt (≥3 echte Buchungsmonate >0 nötig).

**Cockpit „Offene Monatsbuchungen"**
- Nutzt dieselbe Budget-erreicht-Logik und zeigt eine neue **Restbetrag-Spalte** (was im Monat noch offen ist).

**Übersichtlichere Kategorieauswahl im Tracker**
- Neuer gruppierter Picker in Schnelleingabe und Buchungsdialog.
- Reihenfolge: **Favoriten ★**, dann **häufig manuell gebucht**, dann **normale Buchungen**, danach **Fix / variabel**, **Wiederkehrend / variabel** und **echte Fixkosten**.
- Automatische Fix-/Wiederkehrend-Buchungen zählen nicht fürs Ranking, damit Alltagskategorien nicht verdrängt werden.
- Unterkategorien bleiben durch **Baum-Pfade** sichtbar; das Suchfeld filtert per Texteingabe.
- Der Schnellbutton **Nur echte Fixkosten** bucht nur Kategorien mit beiden Flags. Fix-only Kategorien wie Franchise/Selbstbehalt bleiben im editierbaren Dialog.

**Tests**
- Neue Datenschicht-Tests: gruppierter Picker, Franchise-/Wiederkehrend-/Both-Flags-Abschlusslogik (`tests/test_picker_and_budget_reached.py`).

### v2.0.9 – Release-Konsolidierung

- Versionsnummer auf **2.0.9** angehoben, weil nach dem 2.0.8-Tag mehrere funktionale Fixes hinzugekommen sind (Backup-Import, Kategorie-Dropdown-Ranking, Tracking-Quelle, Theme-Hauptbalken, Cockpit-/Startablauf, Single-Instance, Updater).
- Veröffentlichungsstand ist der frühere „SETUP BACKUP IMPORT FIXED"-Arbeitsstand, **nicht** der ältere 2.0.8-RELEASE-Schnitt (dem das Cockpit und 86 i18n-Keys fehlten).
- Zurückgemergt, da im FIXED-Stand verloren: `.github/workflows/build.yml` (CI-Build), `.gitignore`, `data/.gitkeep`.
- Versionssync zentral auf 2.0.9 gezogen (version.json, Installer-`.iss`, `latest.json.template`, `docs/latest.json.template`, README/FEATURES/Installations- und Updater-Doku).
- Headless-Stabilitätstest der gesamten Datenschicht durchgeführt (siehe `STABILITAETSTEST_v2_0_9.md`).

### Fix: Backup-Import im geführten Starter

- Setup-Assistent: „Backup wiederherstellen“ nutzt jetzt den BackupRestoreDialog mit korrektem DB-/User-/Session-Kontext.
- Direkter Restore eines ausgewählten Backup-Pfads ist über `restore_external_path()` sauber unterstützt.
- Restore-Optionen für Settings und Benutzerdatei werden auch beim direkten Restore abgefragt.
- Erststart-Import von `.bmr`-Quick-Backups kann den im Bundle enthaltenen Quick-DB-Key aus `users.json` nutzen und fragt nicht unnötig nach dem Restore-Key.
- Neue `.bmr`-Manifeste enthalten `source_db_name` zur besseren Zuordnung.


### v2.0.8 – Single-Instance Release-Blocker-Fix

- Mehrfachstart robust und **datenordnerspezifisch** blockiert: mehrere BudgetManager-Instanzen können nicht mehr parallel dieselbe verschlüsselte Datenbank öffnen.
- Wichtig: Der Schutz blockiert nicht global `python main.py`. Andere Programme mit eigenem App-/Datenordner, z. B. ein Füller-Sammelprogramm, dürfen parallel laufen.
- Der alte `QLockFile`-Schutz mit 30-Sekunden-Stale-Timeout wurde ersetzt, weil lange laufende Apps dadurch fälschlich wieder freigegeben werden konnten.
- Neuer atomarer Lock-Ordner `data/budgetmanager.instance.lock` mit gespeicherter PID.
- Bei normalem Beenden wird das Lock entfernt; nach Crash wird ein veraltetes Lock beim nächsten Start automatisch erkannt und bereinigt.
- Regressionstests für aktive und stale Locks ergänzt.


### v2.0.8 – Übersicht Graphen-Erweiterung

- Übersicht erweitert um **Monatsverlauf**: Ausgaben Budget vs. Gebucht pro Monat.
- Übersicht erweitert um **Monatsbilanz**: echte Bilanz vs. geplante Bilanz.
- Übersicht erweitert um **Top-Buchungen**: größte Buchungen im gewählten Zeitraum.
- Chart-Widget bereinigt Achsen beim Wechsel zwischen Pie/Donut/Line/Bar, damit keine alten Achsen hängen bleiben.
- Wissensdatenbank, HTML-Hilfe und Mindmap um die neuen Diagramme ergänzt.


Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

---

## [2.0.8] - 2026-06-13 — Merge (release_ready-Basis) + Fixkosten-Vorschlagsregel

Zusammenführung der beiden 2.0.7-Linien zu einem releasefähigen Stand. Basis ist
das `release_ready`-Paket (4 distinkte Zahlenformate swiss/german/french/anglo,
`set_money_locale`/`preferred_number_format_for_currency`, geführter Update-Dialog
mit GUI-Modus, `BUDGETMANAGER_APP_DIR`-Override, Release-Integritätstest). Aus dem
Schwesterpaket übernommen: `docs/DAU_TEST_ERSTSTART.md`. Das dortige
`dau_first_run_check.py` rief die nicht existierende API
`delete_category(strategy=…)` auf und war defekt — die korrekte
`delete_category_safely(...)`-Variante aus `release_ready` bleibt.

### Hilfe & Mindmap-Merge

- Beste Lösung aus `RELEASE 2` und `RELEASE KB COMPLETE` zusammengeführt:
  - durchsuchbares In-App-Handbuch behalten,
  - vollständige lokale HTML-/Markdown-Wissensdatenbank wieder eingebunden,
  - `docs/help` wieder in PyInstaller `datas` aufgenommen,
  - direkt anzeigbare `docs/help/mindmap.html` ergänzt,
  - Help-Menü vereinheitlicht: F1 = Handbuch, Ctrl+F1 = Tastenkürzel, direkter Restore-Key und direkter Mindmap-Aufruf.
- Kategorie-Filterwerte wieder sprachunabhängig gemacht (`all`, `fix`, `recurring`), damit Filter nicht durch Übersetzungen brechen.

### Neu / Korrektheit

- **Fixkosten-Regel in der Budget-Vorschlagslogik** (`budget_suggestion_engine.py`):
  0-Monate dürfen bei Fixkosten/wiederkehrenden Kategorien (`is_fix=1` oder
  `is_recurring=1`) keinen senkenden Budgetvorschlag beweisen. Für diese
  fixed-like Kategorien werden 0-Monate aus der Änderungsanalyse entfernt;
  es braucht mindestens 3 echte Buchungsmonate (> 0), bevor ein Vorschlag
  entsteht. Damit sind inkrementelle/lumpy Fixkosten (quartalsweise, jährlich
  oder in Raten) geschützt, während wiederholte echte Überschreitungen weiterhin
  eine Erhöhung auslösen können. Steuerbar über `respect_fixed_costs`
  (Standard `True`). Nach der Rundung werden Mindeständerungen nochmals geprüft.
- **Erweiterter Regressionstest** `tests/test_fixed_cost_suggestion.py` (8 Fälle):
  Fixkosten+0 → kein Vorschlag; Nicht-Fixkosten+0 → Vorschlag; wiederholte echte
  Fixkostenbuchungen → Erhöhung; Schutz abschaltbar; Versicherung 250/0/0 → kein
  Senken; `is_recurring` geschützt; Hobby 20/30/0 bleibt flexibel;
  Nahrungsmittel 450/350 bleibt stabil.
- **Update-Dialog-Freischaltung repariert** (`updater/check_update.py`):
  Nach erfolgreichem Download/Staging wird wieder ein strukturiertes Ergebnis
  (`available=true`, `staged=true`) geschrieben. Ohne diesen Fix hätte der
  GUI-Dialog den Installationsbutton nach erfolgreichem Check nicht zuverlässig
  freigeschaltet. Ein Release-Integritätstest schützt diese Stelle.
- **Updater wendet die geprüfte Version an** (`updater/apply_update.py`):
  Bisher nahm `apply_update` blind die höchste vorhandene Staging-Version.
  Lag ein alter, höher nummerierter Staging-Ordner herum (z. B. ein Beta-Rest
  `2.1.0`), während Stable gerade `2.0.9` vorbereitet hatte, wurde das falsche,
  ältere Update angewendet (Staging-Ordner werden nie aufgeräumt, der Fall ist
  also erreichbar). `check_update` schreibt nun `staged_version`, und
  `apply_update` bevorzugt genau diese Version (neue Funktion
  `target_staged_version()`), mit sicherem Fallback auf die höchste vorhandene
  Version, falls kein/kein gültiges Prüfergebnis vorliegt. Regressionstest
  `test_apply_uses_checked_version_not_highest_stale_staging`.

### Hilfe & Usability

- **In-App-Wissensdatenbank (Handbuch)** über *Hilfe → Handbuch* (Shift+F1):
  durchsuchbarer Themenbrowser (`views/help_dialog.py`, Inhalte in
  `views/help_content.py`), dreisprachig (de/en/fr), **17 Themen** über den
  gesamten Funktionsumfang: Einstieg, Kategorien, **Drag & Drop** (wo/wie/was),
  Budget & Vorschläge, **Buchungen/Tracking**, **Fixkosten** (ausführlich),
  Wiederkehrende, **Übersicht**, **Sparziele** (wann/wie/wo), **Favoriten**
  (wofür), **Tags**, **Rückgängig/Wiederholen**, Backup, **Datenbank & Schlüssel**,
  **Konten & Sicherheit**, Updates, Währung/Zahlenformat.
- **Datenbank-/Restore-Key zugänglich gemacht:**
  - Der Restore-Key wird jetzt **beim Erststart für ALLE Konten** angezeigt – auch
    für Quick-Konten (ohne Passwort), mit passendem Hinweis, dass er zum
    Wiederherstellen nötig ist (`views/startup_wizard.py`).
  - **Direkter Zugang aus der Hilfe**: Knopf *„DB-Schlüssel / Restore-Key
    anzeigen“* im Handbuch öffnet den Schlüssel der aktuell geöffneten Datenbank
    (neuer, jederzeit aufrufbarer `views/restore_key_dialog.py` mit Kopieren).
    Das schließt auch die Lücke, dass PIN-/Passwort-Konten den Key bisher nach dem
    Erststart nicht erneut einsehen konnten.
  - Das Handbuch-Thema *Datenbank & Schlüssel* erklärt Zweck, Fundorte und
    Sicherheit des Schlüssels.
- **Fixkosten-/Wiederkehrend-Tooltips vereinheitlicht und vervollständigt** (alle
  acht Checkboxen) inkl. Budget-Vorschlags-Wirkung; Verweis aufs Handbuch.
- **Dead-End-Feinschliff**: Tooltip am deaktivierten *Zuweisen*-Feld erklärt, warum
  es ausgegraut ist (keine Zielkategorie vorhanden).

### i18n

- 2 in `release_ready` fehlende Schlüssel ergänzt (`catdel.opt_cascade_all`,
  `dlg.create_account`) in de/en/fr → wieder **1735 identische Schlüssel** je Sprache.

### Verifiziert (Container)

- `compileall`: 0 Syntaxfehler · alle JSON gültig · i18n-Parität 3×1735
- `tools/i18n_audit.py`: keine hardcoded UI-Strings
- `tools/dau_first_run_check.py`: ALLE CHECKS BESTANDEN
- `tools/sync_version.py --check`: alle Versionsdateien synchron auf **2.0.8**
- Tests: **34 passed, 1 skipped**
  (22 core + 4 release-integrity + 8 fixcost; GUI-Tests ohne PySide6 übersprungen)
- Paket-Hygiene: kein `users.json`, keine `*.enc`, kein `__pycache__`/`.pyc`/`.pytest_cache`

> Offen (nur außerhalb des Containers möglich): realer Windows-/Linux-Smoke-Test,
> Qt-Übersetzungskataloge im Build (`verify_qt_translations.py`), Installer-Bau,
> Git-Tag `v2.0.8` + echte SHA256 in `latest.json`.

---

## [2.0.7] - 2026-06-13 — Release-Fixloop nach v2.0.2/v2.0.6 Vergleich

### Fixed
- v2.0.2 als stabile Basis behalten und v2.0.6-Regressionen bei Kategorie-Reassign, Mehrfachlöschung und Undo/Redo nicht übernommen.
- Update-Dialog auf geführten Ablauf umgestellt: automatische Prüfung, strukturiertes `updates/last_check.json`, ein Installationsknopf, sichtbarer Windows-Update-Helfer.
- Erststart verbessert: Zahlenformat bereits bei Sprache/Region wählbar, QLocale an BudgetManager-Zahlenformat gekoppelt.
- Setup-Assistent blockiert Budget-/Tracking-Schritte erst dann frei, wenn wirklich ein Budgetwert > 0 bzw. eine Buchung vorhanden ist.
- Release-Paket bereinigt: keine Testuser, keine `.enc`-Userdaten, keine `.pytest_cache`.

### Tests
- `python -m compileall -q .` erfolgreich.
- `pytest -q`: 26 passed, 1 skipped.
- `tools/dau_first_run_check.py`: alle Headless-Erststartchecks bestanden.

## [2.0.2] - 2026-06-13 — Kategorie-Integrität (Rename/Delete/Parenting)

### Behoben (kritisch)

- **Rename zentralisiert**: `rename_and_cascade` aktualisiert jetzt ALLE
  namensbasierten Tabellen (budget, tracking, budget_warnings, favorites,
  recurring_transactions, savings_goals) atomar. Vorher blieben Warnungen,
  Favoriten, wiederkehrende Buchungen und Sparziele auf dem alten Namen hängen.
- **Löschen integritätssicher** (`delete_category`): keine verwaisten Daten mehr.
  Drei Wege, vom Nutzer wählbar (neuer `CategoryDeleteDialog`):
  1. *Mit allen abhängigen Daten löschen* (Buchungen/Budget/Favoriten/…),
  2. *Daten einer anderen Kategorie zuordnen* (Reassign),
  zusätzlich werden `category_tags` und `funded_by_category_id` sauber behandelt.
- **Parent-Löschung stuft Kinder hoch**: direkte Unterkategorien werden nicht
  mehr verwaist, sondern auf die Ebene der gelöschten Kategorie gezogen
  (Hauptkategorie gelöscht → Kinder werden selbst Hauptkategorien).
- **Zahlenformat-Migration**: alte/abweichende Codes (`ch/eu/us`, `de/fr`, …)
  werden über `normalize_number_format` auf die kanonischen Keys gemappt –
  bestehende Einstellungen fallen nicht mehr still auf `swiss` zurück.

### Hinweise

- Alle bestehenden Löschpfade (`delete`, `delete_by_ids`) laufen jetzt über die
  zentrale, integritätssichere Logik (Default-Strategie `cascade`).
- Reparenting-Validierung (Zyklen/Typ-Mix) war bereits in `update_parent`
  vorhanden und bleibt erhalten.



### Neu

- **Konfigurierbares Zahlenformat** (Dezimal-/Tausendertrennzeichen) unabhängig
  von der Währung: `swiss` (1'234.56), `german` (1.234,56), `french` (1 234,56),
  `anglo` (1,234.56). Umgesetzt in `utils/money.py` (`set_number_format` /
  `get_number_format`), persistiert als Setting `number_format`.
- **Neuer Schritt „Zahlenformat" im Setup-Assistenten** direkt nach der
  DB-Erstellung – mit Live-Vorschau. Auch nachträglich in den Einstellungen
  (Region) änderbar.

### Behoben

- **Native Kontextmenüs konstant englisch** (Rückgängig/Ausschneiden/Kopieren/
  Einfügen/Löschen/Alles auswählen): Es wurde nie ein `QTranslator` installiert.
  Neu: `utils/qt_translator.py` lädt `qtbase_<lang>.qm` beim Start und bei jedem
  Sprachwechsel. `.spec` bündelt die nötigen `.qm`-Dateien für Frozen-Builds.
- **i18n-Inkonsistenz**: 151 in EN bzw. 151 in FR unübersetzte (deutsche) Strings
  übersetzt – inkl. der `auto.*`-Schlüssel. Platzhalter (`{value_0}`, `{e}` …)
  bleiben konsistent; Locale-Parität de/en/fr = 1648 Keys.
- **`parse_money` formatbewusst**: `"1.234"` wird je nach aktivem Format korrekt
  als 1.234 (swiss/anglo) bzw. 1234 (german/french) interpretiert.

### Intern

- Setup-Assistent: fragile, hartcodierte Schritt-Indizes der Branch-Navigation
  durch symbolische Konstanten ersetzt (robust gegen Reihenfolge-Änderungen).



### Zusammengeführt

- Stabile Codebasis aus `1.0.42_clean_merged` beibehalten.
- Versionsziel aus `BudgetManager_Source_2_0_0` übernommen.
- Dokumentation bereinigt und auf `v2.0.2` aktualisiert.

### Behoben / erhalten

- Installer schreibt Erststart-Einstellungen nach `data/budgetmanager_settings.json`.
- Windows-Pfade in Installer-Settings bleiben gültiges JSON.
- `Settings._load()` merged Teil-JSONs über vollständige Defaults.
- Budget-Drag&Drop, Kategorien-Drag&Drop und Dropdown-Settings bleiben enthalten.
- Updater-/Installer-Manifestdateien sind auf `v2.0.2` synchronisiert.

### Bereinigt

- `CLAUDE.md`, alte Arbeitsordner, lokale Settings, i18n-Audit-Ausgaben und alte Merge-/Analyse-/Bugfix-Berichte nicht übernommen.
- Stale Markdown-Dateien mit 0.x-, 1.0.35- oder internen Analysebezügen nicht übernommen.
- Aktive Markdown-Dokumente neu geschrieben oder auf den aktuellen Release reduziert.

---

## [1.0.42] - 2026-06-13 — Install-Manager, Dropdowns und Budget-Drag&Drop

- Install-/Erststartdialog fragt zusätzlich Währung und bevorzugten Monatstag ab.
- Bei Sprachauswahl werden Währung und bevorzugter Tag sinnvoll vorbefüllt.
- Option „Kein bevorzugter Tag“ ergänzt.
- Einstellungen → Verhalten: Überschuss-/Defizit-Vorschlag als Dropdown.
- Einstellungen → Verhalten: Drag & Drop in der Budgetübersicht ein-/ausschaltbar.
- Kategorien-Manager: Fälligkeitstag als Dropdown.
- Budgetübersicht: Kategorien können per Drag & Drop umgehängt werden.
- Installer-Regression korrigiert: Settings werden in `data/budgetmanager_settings.json` geschrieben.
- Settings-Defaults-Merge korrigiert.

---

## [1.0.41] - 2026-06-13 — Kategorien-Manager: Fenster & Spaltenlayout

- Kategorien-Manager unter Windows mit Minimieren/Maximieren ergänzt.
- Abgeschnittene Kategorie-Spalte behoben.
- Splitter-Verhalten verbessert: Kategorie-Baum bekommt beim Vergrößern den zusätzlichen Platz.

---

## [1.0.38] - 2026-06-13 — i18n Hardcoding Fix + Kategorie Drag & Drop

- i18n-Audit repariert.
- Verdächtige hardcodierte UI-Texte in aktiven Views/Dialogen auf i18n-Keys umgestellt.
- Fehlende i18n-Keys in `de.json`, `en.json` und `fr.json` ergänzt.
- Kategorien-Manager unterstützt Drag & Drop für Ebenenwechsel.
- Kontextmenü-Aktion „Zur Hauptkategorie machen“ ergänzt.
- Kategorien-Filter arbeitet mit internen Werten statt übersetzten Texten.

---

## Ältere Historie

Ältere Zwischenstände wurden aus dem Release-Paket entfernt, weil sie teilweise veraltete Versionsnummern, alte Architekturstände oder Analyseberichte enthielten. Für Git-Historie und alte Release-Artefakte bleibt die vollständige Historie im Repository/Tag erhalten.

## v2.0.8 Workflow-Finalisierung

- Sparziele besser in Budget und Tracking eingebettet.
- Aktive Sparziele werden im Tracking nur bei Bedarf mit Fortschrittsbalken angezeigt.
- Budget-Tab erhält einen kleinen 🎯 Sparziele-Einstieg.
- Sparziel-Dialog erklärt den roten Faden von Plan → Buchung → Fortschritt → Freigabe → Verbrauch.
- Auto-Speichern und Auto-Backup sind beim ersten Start aktiv.
- Wissensdatenbank und Mindmap um den Sparziel-Workflow erweitert.
