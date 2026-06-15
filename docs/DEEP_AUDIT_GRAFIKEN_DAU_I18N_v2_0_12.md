# Tiefenanalyse v2.0.12 – Grafiken, DAU-Nutzerfreundlichkeit und Übersetzungen

**Stand:** 15.06.2026  
**Quelle:** `BudgetManager Source 2 0 12.zip`  
**Ziel:** Logik der Grafiken prüfen, DAU-Nutzerfreundlichkeit bewerten, sichtbare Texte/Übersetzungen prüfen, sichere Übersetzungs- und UI-Fixes direkt umsetzen, übrige Punkte als Bericht dokumentieren.

---

## 1. Kurzfazit

Die Version ist auf Logik-Ebene deutlich stabiler als frühere Zwischenstände. Die Kernlogik für Budget/Tracking, Kategorien, Rename-Cascade, Parent-Löschung mit Child-Promotion, gruppierten Tracker-Picker und die neue Budget-erreicht-Logik für `fix XOR wiederkehrend` ist testbar und besteht die vorhandenen Checks.

**Kein neuer Release-Blocker in der getesteten Logik gefunden.**  
Es gab aber mehrere UX-/Übersetzungsprobleme, die ich direkt gefixt habe.

Direkt gefixt:

1. Diagramme zeigen bei leer/0-gefilterten Daten jetzt sauber einen „keine Daten“-Titel statt potenziell leer/unklar zu bleiben.
2. Gruppierte Balkendiagramme setzen keine ungültige Y-Achse `0..0` mehr, wenn alle Werte 0 sind.
3. Der verschachtelte Donut ist DAU-tauglicher: Segmente bekommen bei mehreren Ringen nun den Ring-Kontext, z. B. `Ausgaben: Gebucht`, statt nur mehrfach `Gebucht/Offen`.
4. Fälligkeitsstatus im Fixkosten-/Wiederkehrend-Dialog ist jetzt übersetzbar statt hart deutsch (`Heute`, `{n} Tage`, `in {n} T.`).
5. 86 englische und 86 französische sichtbare Übersetzungseinträge wurden korrigiert, darunter Einstellungen, Hauptmenü, Budgetdialoge, Export, Accountverwaltung, Sparziele, Themes, Tags, Login/Restore-Key und Kategorien-Tab.
6. Zusätzlich wurden die drei „Nur letzte X Tage“-Auto-Keys in Englisch/Französisch korrigiert.

---

## 2. Ausgeführte Checks

| Bereich | Ergebnis |
|---|---:|
| Python Compilecheck `python -m compileall -q .` | bestanden |
| Gesamttests `pytest -q` | **60 passed, 2 skipped** |
| Headless DAU-Erststart `tools/dau_first_run_check.py` | **alle Checks bestanden** |
| i18n-Audit Deutsch/Englisch/Französisch | alle referenzierten Keys vorhanden |
| Hardcoded-UI-String-Audit | keine verdächtigen einfachen Hardcoded-UI-Zeilen |
| Zusatzscan „Deutsch-Leaks in EN/FR“ | relevante Treffer gefixt; verbleibende Treffer sind überwiegend Begriffe wie `Name`, `Theme`, `Restore-Key` oder absichtlich mehrsprachiger Sprachwahldialog |

Einschränkung: In der Sandbox war `PySide6` nicht installiert. Deshalb konnte ich die GUI nicht visuell starten. Die Prüfung erfolgte per statischer Codeanalyse, vorhandenen headless Tests, Compilecheck und i18n-Audits.

---

## 3. Analyse der Grafiklogik

### 3.1 Was bereits gut ist

**Bereichsbezogene Budgetlogik:**  
Die Übersicht nutzt bei rollierenden Zeiträumen wie 7/30/90 Tagen nicht mehr blind einen Einzelmonat, sondern summiert Budgets über alle betroffenen Monate. Das ist fachlich richtig, weil ein 90-Tage-Fenster mehrere Monatsbudgets berührt.

**Top-Buchungen sind aggregiert:**  
Mehrere Buchungen derselben Kategorie werden zu einer Summe zusammengefasst. Beispiel: Drei Lohnbuchungen erscheinen als eine aggregierte „Lohn“-Position statt dreimal in der Top-Liste.

**Chart-Cleanup vorhanden:**  
Beim Wechsel zwischen Pie/Line/Bar werden alte Serien und Achsen entfernt. Das verhindert alte Achsenreste in Kreisdiagrammen.

**Farblogik pro Typ konsistent:**  
Einnahmen, Ausgaben und Ersparnisse verwenden im Diagramm die Typ-/Theme-Farben. Das unterstützt die Wiedererkennung.

### 3.2 Gefundene und gefixte Grafikprobleme

#### G1 – Leere/0-Daten konnten optisch unklar bleiben

Vorher: Wenn ein Pie-Chart Daten bekam, aber alle Werte `<= 0` waren, wurde eine leere Serie erzeugt. Der Nutzer sah potenziell ein leeres Diagramm ohne klare Aussage.

Fix:

- `CompactChart.create_pie_chart()` prüft jetzt nach dem Filtern, ob wirklich Slices vorhanden sind.
- Wenn nicht, wird ein sauberer „keine Daten“-Titel gesetzt.
- Der Titel wird über `_no_data_title()` zentral formatiert, damit ohne Basistitel kein führendes Leerzeichen entsteht.

#### G2 – Nested Donut war für Anfänger missverständlich

Vorher: Im verschachtelten Donut konnten mehrere Ringe jeweils `Gebucht` und `Offen` anzeigen. Für einen DAU-Nutzer war nicht klar, ob `Gebucht` zu Einnahmen, Ausgaben oder Ersparnissen gehört.

Fix:

- Bei mehreren sichtbaren Ringen wird der Ring-Kontext in das Segmentlabel geschrieben.
- Beispiel: `Einnahmen: Gebucht`, `Ausgaben: Offen`, `Ersparnisse: Gebucht`.
- Der Klickwert bleibt unverändert über `raw_label`, Drilldown bleibt also funktional.

#### G3 – Gruppiertes Balkendiagramm konnte eine 0..0-Achse bekommen

Vorher: `create_grouped_bar_chart()` setzte bei lauter Nullwerten `axis_y.setRange(0, 0)`. Das ist für Diagrammachsen ungünstig und kann zu leerer/fehlerhafter Darstellung führen.

Fix:

- Wenn `max_val <= 0`, wird die Achse auf einen sicheren Mindestwert gesetzt.

---

## 4. Offene Grafik-/UX-Punkte

Diese Punkte sind nicht zwingend Release-blockierend, würden aber die Übersicht deutlich DAU-freundlicher machen.

### P1 – Donut sollte Überbudget separat zeigen

Aktuell zeigt der Donut `Gebucht` und `Offen`. Wenn eine Kategorie oder ein Typ über Budget liegt, wird `Offen` einfach 0. Der Nutzer sieht zwar den hohen Ist-Wert, aber nicht explizit „über Budget“.

Empfehlung:

- Zusätzliches Segment oder Warnlabel `Über Budget: X` für Ausgaben.
- Für Einnahmen umgekehrt: `Ziel nicht erreicht` statt negativ/rot denken.

### P2 – Diagramme brauchen kurze Erklär-Hinweise

Für Anfänger ist nicht offensichtlich, dass Donut-/Pie-Segmente klickbar sind.

Empfehlung:

- Tooltip auf Diagramm: „Klick auf Ring/Slice filtert die Liste rechts.“
- Kurze Legende oberhalb des Donuts: `Gebucht = real erfasst`, `Offen = noch budgetiert, aber nicht gebucht`.

### P3 – Kategorien-Pie kann bei vielen Kategorien unlesbar werden

Bei vielen Ausgabenkategorien können Labels außen überlappen.

Empfehlung:

- Top 8 Kategorien anzeigen, Rest als `Andere` aggregieren.
- Optional Tabellenansicht darunter als genaue Liste.

### P4 – „Top 5 Buchungen“ ist fachlich eher „Top 5 Kategorien/Buchungsgruppen“

Da die Daten aggregiert werden, ist der Titel „Top 5 Buchungen nach Betrag“ leicht missverständlich.

Empfehlung:

- Umbenennen in `Top 5 Kategorien nach Betrag` oder `Größte Buchungsgruppen`.

### P5 – Monatsverlauf bei benutzerdefinierten langen Zeiträumen

Die Chartlogik begrenzt auf maximal 24 Monate. Das ist sinnvoll für Lesbarkeit, aber der Nutzer sieht nicht, dass ältere Monate abgeschnitten wurden.

Empfehlung:

- Hinweis anzeigen: „Nur die letzten 24 Monate werden im Diagramm gezeigt.“

---

## 5. DAU-Nutzerfreundlichkeit

### 5.1 Was bereits gut ist

**Erststart-Logik headless bestanden:**

- Sprache/Währung/Zahlenformat funktionieren.
- Quick-User kann angelegt werden.
- Datenbank wird erstellt/migriert.
- Default-Kategorien werden geladen.
- Kategorienbaum ist baubar.
- Budgeteintrag funktioniert.
- Trackingbuchung funktioniert.
- Kategorie-Rename wandert in Budget und Tracking mit.
- Parent-Löschung hebt Children korrekt hoch.
- Keine verwaisten Kategorie-Referenzen.

**Tracker-Kategorieauswahl ist deutlich besser:**

- Favoriten oben.
- Häufig manuell gebuchte Kategorien oben.
- Normale Buchungen separat.
- Fix/variabel und wiederkehrend/variabel separat.
- Echte Fixkosten separat unten.
- Baum-Pfade wie `Wohnen › Miete` bleiben sichtbar.
- Header sind nicht auswählbar.
- Such-/Completer-Logik berücksichtigt echte Einträge.

**Fixkosten-/Wiederkehrend-Logik ist fachlich sauberer:**

- `fix UND wiederkehrend`: echte Monatsfixkosten, nach einer Buchung abgeschlossen.
- `fix XOR wiederkehrend`: bleibt offen, bis Budget erreicht ist.
- Franchise/Selbstbehalt-Fall ist abgedeckt: Teilbuchung bleibt offen, Restbetrag ist editierbar.
- Quick-Button „Nur Fixkosten“ bucht bewusst nur echte Fixkosten und lässt variable Fixkosten außen vor.

### 5.2 Gefixte DAU-/Textprobleme

- Fixkosten-/Wiederkehrend-Dialog hatte harte deutsche Statuswörter: `Heute`, `{n} Tage`, `in {n} T.`. Diese sind jetzt i18n-Keys.
- Englische/französische UI hatte noch viele deutsche Auto-Übersetzungen. Die häufig sichtbaren Bereiche sind korrigiert.

### 5.3 Offene DAU-Punkte

#### D1 – Begriffe „Fix“, „Wiederkehrend“, „Fix / variabel“ sind fachlich korrekt, aber erklärungsbedürftig

Empfehlung:

- In Kategorieeigenschaften eine 2-Zeilen-Erklärung anzeigen:
  - `Fixkosten`: Betrag ist planbar/fest.
  - `Wiederkehrend`: erscheint regelmäßig im Monatsdialog.
  - `Fix + wiederkehrend`: automatisch einmal pro Monat buchbar.
  - `Nur Fix` oder `nur wiederkehrend`: Betrag bleibt editierbar und gilt erst als erledigt, wenn das Budget erreicht ist.

#### D2 – Setup-Assistent braucht visuellen Endzustand pro Schritt

Der headless Test ist gut, aber ein DAU braucht im GUI klare Bestätigung:

- „Kategorien erstellt: X“
- „Budgetwerte gesetzt: X“
- „Erste Buchung erfasst“
- „Du kannst jetzt mit Tracking starten“

#### D3 – Fehlertexte sollten immer mit Handlung enden

Beispiel Best Practice:

- Nicht nur: „Keine Daten“
- Besser: „Keine Daten für diesen Zeitraum. Erfasse eine Buchung oder ändere den Filter.“

---

## 6. Übersetzungsanalyse

### 6.1 Ergebnis offizieller i18n-Audit

- Deutsch: alle im Code referenzierten Keys vorhanden.
- Englisch: alle Deutsch-Keys vorhanden.
- Französisch: alle Deutsch-Keys vorhanden.
- Kein einfacher hardcodierter UI-String in den bekannten UI-Call-Mustern gefunden.

### 6.2 Was ich zusätzlich geprüft habe

Der Standard-Audit findet fehlende Keys, aber nicht automatisch „englischer Key enthält noch deutschen Text“. Deshalb habe ich zusätzlich auf Deutsch-Leaks in `en.json` und `fr.json` geprüft.

Gefixt wurden unter anderem:

- Einstellungen: `Start & Bedienung`, `Eingabe & Workflow`, `Tabellen & Listen`, Backup-Erfolgstext.
- Budgetdialoge: `Eigenschaften`, `Neue Unterkategorie`, `Umbenennen`, `Fehlt`, `Monat`.
- Datenbankverwaltung: Titel und Bereinigen-Button.
- Export: `Zeitraum`, `Exportieren`, `Export speichern unter`.
- Accountverwaltung: Passwort/PIN, Sicherheitsstufe, Restore-Key, Zwischenablage, Schutz entfernen.
- Hauptfenster: Bearbeiten, Zeilen aus Kategorien, Jahr kopieren, neue Haupt-/Unterkategorie, Neustart erforderlich.
- Sparziele: Bearbeiten, Ziel, Aktuell, Restbetrag, Freigeben, Abschließen, Synchronisiert.
- Theme-/Tag-Dialoge.
- Login/Restore-Key-Aktionen.
- Kategorien-Tab: Neu Hauptkategorie, Neu Unterkategorie, Umbenennen.
- Tracking-Schnellfilter `Nur letzte X Tage`.

### 6.3 Verbleibende i18n-Hinweise

Der Audit meldet weiterhin viele „ungenutzte Keys“. Das ist nicht automatisch ein Fehler. Gründe:

- Auto-generierte Keys können dynamisch genutzt werden.
- Einige Keys sind Fallbacks oder für optionale Dialoge gedacht.
- Default-Kategorien werden über eigene Hilfslogik übersetzt und erscheinen deshalb nicht immer als direkter `tr()`-Treffer.

Verbleibende Deutsch-Leak-Treffer nach Zusatzscan sind überwiegend unkritisch:

- `Name` ist in Englisch korrekt identisch.
- `Theme` ist als UI-Begriff auch Englisch verwendbar.
- `Restore-Key` ist Produkt-/Feature-Begriff.
- Sprachwahldialog ist absichtlich dreisprachig.

---

## 7. Geänderte Dateien

| Datei | Änderung |
|---|---|
| `views/tabs/overview_widgets.py` | bessere No-Data-Behandlung, Donut-Kontextlabels, sichere Balken-Y-Achse |
| `views/recurring_bookings_dialog.py` | Fälligkeitsstatus übersetzbar gemacht |
| `locales/de.json` | neue Keys für Buchungsstatus |
| `locales/en.json` | neue Keys + 86 korrigierte englische Übersetzungen + Tracking-Schnellfilter |
| `locales/fr.json` | neue Keys + 86 korrigierte französische Übersetzungen + Tracking-Schnellfilter |
| `docs/DIFF_v2_0_12_graphics_i18n.patch` | Patch-Diff dieser Änderungen |
| `docs/DEEP_AUDIT_GRAFIKEN_DAU_I18N_v2_0_12.md` | dieser Bericht |

---

## 8. Release-Einschätzung

**Releasefähigkeit Logik:** gut.  
**Releasefähigkeit i18n:** gut genug für RC, aber GUI-Build muss wegen nativer Qt-Kontextmenüs noch auf Zielsystem geprüft werden.  
**Releasefähigkeit Grafik/Übersicht:** funktional gut, UX mit kleinen offenen Verbesserungen.  
**Releasefähigkeit DAU:** gute Basis, aber für finales Release empfehle ich einen echten manuellen GUI-Smoke-Test auf Fedora und Windows.

### Empfohlener nächster manueller Smoke-Test

1. App frisch starten, Sprache Deutsch wählen.
2. Quick-User ohne Passwort anlegen.
3. Setup-Assistent vollständig durchklicken.
4. Eine Ausgabe manuell buchen.
5. Eine Kategorie als `Fix`, eine als `Wiederkehrend`, eine als `Fix + Wiederkehrend` markieren.
6. Fixkosten-/Wiederkehrend-Dialog öffnen und prüfen:
   - echte Fixkosten sind nicht editierbar,
   - variable Fix-/Wiederkehrend-Kategorien sind editierbar,
   - Status wirkt verständlich.
7. Übersicht öffnen und prüfen:
   - Donutlabels sind verständlich,
   - leere Filter zeigen „keine Daten“,
   - Klick auf Diagramm filtert/reagiert nachvollziehbar.
8. Sprache auf Englisch und Französisch wechseln und die häufigen Dialoge öffnen.

---

## 9. Empfehlung für v2.0.13

Für die nächste Version würde ich diese Reihenfolge nehmen:

1. Donut-Überbudget-Segment bzw. Warnlabel einbauen.
2. Top-5-Titel in „Top 5 Kategorien/Buchungsgruppen“ umbenennen.
3. Pie-Chart auf Top 8 + Andere begrenzen.
4. Mini-Hilfe direkt über den Diagrammen einbauen.
5. GUI-Smoke-Test als Checkliste in `docs/RELEASE_CHECKLIST` integrieren.

