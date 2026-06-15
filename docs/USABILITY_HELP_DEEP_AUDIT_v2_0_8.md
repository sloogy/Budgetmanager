# Deep-Audit Usability, Dead-Ends und Hilfe — BudgetManager v2.0.8

Stand: 14. Juni 2026  
Paketbasis: `BudgetManager Source 2 0 8 RELEASE.zip`

## Ergebnis

Die technische Release-Basis war stabil, aber die Version hatte aus Nutzersicht einen echten Hilfe-/Onboarding-Dead-End:

- Das Hilfe-Menü öffnete keine vollständige Hilfe.
- `F1` zeigte nur Tastenkürzel statt inhaltlicher Hilfe.
- Das Fixkosten-Häkchen war in Tooltips/README zu knapp erklärt.
- Es gab keine verknüpfte Wissensdatenbank im Programm.

Diese Punkte wurden behoben. Die neue Fassung ist als Source-Release-Kandidat deutlich releasefähiger für normale Nutzer.

## Durchgeführte Analyse

Geprüft wurden:

- Menüführung und erreichbare Aktionen,
- Hilfe-Menü und F1-Verhalten,
- Fixkosten-/Wiederkehrend-UX,
- Fixkosten-Buchen-Dialog,
- README und Installationsdoku,
- PyInstaller-Bundling der Hilfedateien,
- i18n-Keys für neue UI-Texte,
- stabile Filterdaten im Kategorien-Manager,
- automatisierte Release-Checks.

## Gefundene Dead-Ends und Fixes

### P1 — Hilfe-Menü ohne echte Hilfe

**Befund:**  
Das Hilfe-Menü enthielt Tastenkürzel, Setup-Assistent und Über-Dialog. Eine echte Wissensdatenbank fehlte. Für normale Nutzer war damit unklar, wo Begriffe wie Fixkosten, Wiederkehrend oder Fälligkeitstag erklärt sind.

**Fix:**

- Neue lokale Hilfe erstellt:
  - `docs/help/index.html`
  - `docs/help/README.md`
- Neuer Menüpunkt:
  - **Hilfe → Wissensdatenbank / Hilfe**
- `F1` öffnet jetzt die Wissensdatenbank.
- `Ctrl+F1` öffnet die Tastenkürzel.
- Öffnen funktioniert in Source/portable Ordnern und mit PyInstaller-Bundle-Fallback (`_MEIPASS`).

### P1 — Fixkosten-Häkchen nicht vollständig erklärt

**Befund:**  
Der Tooltip sagte sinngemäß nur, dass Fixkosten separat angezeigt werden. Das war nicht ausreichend, weil das Häkchen mehrere konkrete Wirkungen hat und gleichzeitig keine automatische Hintergrundbuchung auslöst.

**Fix:**

Neue Tooltips erklären:

- Fixkosten erscheinen in **Fix/Wiederkehrend buchen…**,
- Betrag kommt aus dem Monatsbudget,
- vorhandene Buchungen werden übersprungen,
- 0-Budget wird bei Fixkosten nicht gebucht,
- Fixkosten sind vor falschen 0-Monats-Vorschlägen geschützt,
- es wird nicht automatisch im Hintergrund gebucht.

Betroffene Stellen:

- `views/category_properties_dialog.py`
- `views/budget_entry_dialog_extended.py`
- `views/category_manager_dialog.py`
- `locales/de.json`, `en.json`, `fr.json`

### P1 — Fixkosten-Buchen-Dialog: Monatswahl missverständlich

**Befund:**  
Der Dialog nutzt das Datumfeld zur Auswahl des Monats. Der Tag im Feld ist aber nicht der eigentliche Buchungstag; der Buchungstag kommt aus dem Fälligkeitstag der Kategorie oder aus dem 1. des Monats.

**Fix:**

- Dialogtitel auf **Fix/Wiederkehrend buchen…** geändert.
- Feldbeschriftung auf **Buchungsmonat** geändert.
- Hinweistext ergänzt, der das Verhalten erklärt.

Betroffene Datei:

- `views/fixcost_dialog.py`

### P2 — Kategorien-Manager Filterdaten waren unnötig übersetzungsabhängig

**Befund:**  
Die Filterwerte `all`, `fix`, `recurring` wurden aus i18n-Texten geladen. Aktuell waren sie zwar zufällig in allen Sprachen stabil, aber interne Steuerwerte dürfen nicht übersetzt sein.

**Fix:**

- Filterdaten sind jetzt feste interne Werte: `all`, `fix`, `recurring`.
- Angezeigte Texte bleiben übersetzt.

Betroffene Datei:

- `views/category_manager_dialog.py`

### P2 — Hilfedateien wären im PyInstaller-Build nicht automatisch enthalten

**Befund:**  
Die Spec-Datei bündelte `locales`, Default-Kategorien und Theme-Profile, aber keine Hilfe.

**Fix:**

- `BudgetManager.spec` bündelt jetzt `docs/help`.

### P2 — README war keine Nutzer-Hilfe

**Befund:**  
README war technisch okay, aber keine echte Wissensbasis für normale Nutzer.

**Fix:**

- README verweist jetzt auf lokale Wissensdatenbank.
- README erklärt kurz das Fixkosten-Häkchen.
- `README_INSTALLATION.md` verweist ebenfalls auf die Hilfe.

## Was das Fixkosten-Häkchen jetzt dokumentiert auslöst

Das Häkchen **Fixkosten** bedeutet:

1. Die Kategorie wird beim Button **Fix/Wiederkehrend buchen…** berücksichtigt.
2. Der Betrag wird aus dem Budgetwert des ausgewählten Monats genommen.
3. Das Buchungsdatum wird aus dem Fälligkeitstag der Kategorie gebildet, sonst aus dem 1. des Monats.
4. Die Bemerkung wird automatisch als `Monat - Kategorie` gesetzt.
5. Wenn im Monat bereits eine Buchung dieser Kategorie existiert, wird sie übersprungen.
6. Wenn der Budgetwert `0` ist, wird bei Fixkosten keine Buchung erzeugt.
7. Fixkosten werden in Übersicht/Fixkostenprüfung gesondert behandelt.
8. Die Forecast-/Budgetvorschlagslogik senkt Fixkosten nicht allein wegen 0-Monaten.

Es bedeutet **nicht**:

- keine automatische Buchung beim Start,
- keine Zahlung,
- keine stille Hintergrundbuchung,
- keine automatische Budgetänderung.

## Verifikation nach Fix

```text
compileall                         OK
sync_version --check               OK, 2.0.8 synchron
i18n_audit                         OK, alle referenzierten Keys vorhanden
DAU first-run check                 OK
pytest                              35 passed, 1 skipped
```

## Offene Punkte außerhalb des Containers

Diese Punkte bleiben vor öffentlichem Release als echte Smoke-Tests nötig:

1. Windows-Start der gebauten EXE.
2. Linux-Start des gebauten Pakets.
3. Hilfe-Menü öffnet `docs/help/index.html` im echten Build.
4. `F1` öffnet Hilfe, `Ctrl+F1` öffnet Tastenkürzel.
5. Fix/Wiederkehrend buchen mit echten Testdaten prüfen.
6. Update-Durchlauf mit echter `latest.json` und echten SHA256-Werten prüfen.
7. Qt-Systemübersetzungen im Build prüfen (`qtbase_de.qm`, `qtbase_fr.qm`).

## Verdikt

Nach den Hilfe- und Usability-Fixes ist v2.0.8 aus Source-/Container-Sicht ein deutlich besserer Release-Kandidat. Der größte verbleibende Release-Risikopunkt liegt nicht im Source-Code, sondern im echten Windows-/Linux-Build- und Update-Smoke-Test.
