# BudgetManager 3.0.2 – Benutzerhandbuch

Dieses Handbuch beschreibt die tatsächlich vorhandenen Funktionen der Version 3.0.2. BudgetManager arbeitet lokal, bucht nichts ohne deine Bestätigung und trennt **Budget (Plan)** klar von **Tracking (echte Buchungen)**.

## Erststart in vier Schritten

1. Sprache, Währung und Zahlenformat wählen.
2. Konto erstellen und den Restore-Key getrennt sichern.
3. Kategorien per Express-Einrichtung, Vorlage oder manuell vorbereiten.
4. Erste Buchung erfassen und danach Budget oder Tracking-Lernmodus nutzen.

Die ausführliche Variante folgt im nächsten Kapitel.

## 1. Schnellstart

1. Sprache, Währung und Zahlenformat wählen.
2. Konto anlegen: Quick, PIN oder Passwort.
3. Restore-Key ausserhalb des Programmordners sichern.
4. Express-Einrichtung verwenden oder Kategorien selbst anlegen.
5. Entweder Budgetwerte erfassen oder mit dem Tracking-Lernmodus zuerst nur buchen.
6. Im Cockpit die nächsten Schritte abarbeiten.

**Best Practice:** Für den Alltag zuerst Cockpit und Tracking nutzen. Budget, Übersicht und Kategorien nur öffnen, wenn du planen oder prüfen möchtest.

## 2. Programmaufbau

Die linke Seitenleiste ist die Hauptnavigation:

- **Cockpit:** Monatsstatus, offene Aufgaben, Warnungen, Favoriten und letzte Buchungen.
- **Buchungen:** echte Einnahmen, Ausgaben und Ersparnisse.
- **Budget:** Sollwerte pro Kategorie und Monat.
- **Sparziele:** Ziele mit festem Zielbetrag, Einzahlungen und Entnahmen.
- **Übersicht:** Plan/Ist, Kennzahlen, Diagramme und Filter.
- **Kategorien:** Verwaltung der Geldstruktur, sofern dieser Expertenbereich eingeblendet ist.
- **Konto:** Datenordner, Backups und Datenbankverwaltung.

Die zentrale Aktionsleiste bietet Buchung erfassen, Fix/Wiederkehrend buchen, Kategorien, Sparziele und Suche.

## 3. Kategorien und Kontotypen

Jede Kategorie gehört zu einem Typ:

- Einnahmen
- Ausgaben
- Ersparnisse

Haupt- und Unterkategorien bilden eine Baumstruktur. Unterkategorien dürfen nur unter Kategorien desselben Typs verschoben werden.

### 3.1 Kategorieeigenschaften

- **Fixkosten:** planbarer oder geschützter Kostenblock.
- **Wiederkehrend:** regelmässige Buchung.
- **Fälligkeitstag:** Tag 1–28 oder Monatsende für fällige Buchungen.
- **Forecast-Modus:** Auto, Normal/Flexibel, POT/Rückstellung oder Inkrementell.
- **Favorit:** wichtige Kategorie im Cockpit/Favoriten-Dashboard.
- **Feste Tags:** werden neuen Buchungen dieser Kategorie automatisch angeheftet.

### 3.2 Typische Kombinationen

| Einstellung | Geeignet für |
|---|---|
| Fix + wiederkehrend | Miete, Krankenkasse, feste Abos |
| Wiederkehrend ohne Fix | variable Stromrechnung, schwankender regelmässiger Lohn |
| Fix ohne wiederkehrend | POT/Rückstellung wie Franchise oder Selbstbehalt |
| Inkrementell | Jahres- oder Quartalskosten mit Teilzahlungen |
| Normal/Flexibel | Lebensmittel, Freizeit, spontane Ausgaben |

### 3.3 Sicher umbenennen und löschen

Umbenennungen werden in Budget, Tracking, Favoriten, Tags, Warnungen, wiederkehrenden Buchungen und Sparzielen mitgezogen. Beim Löschen kannst du abhängige Daten löschen oder auf eine andere Kategorie umhängen. Budgetwerte im selben Monat werden dabei additiv zusammengeführt. Kinder einer gelöschten Hauptkategorie können eine Ebene hochgestuft werden.

Vor grossen Strukturänderungen immer ein Backup erstellen.

### 3.4 Excel-Vorlage im Setup

Der Setup-Assistent kann Kategorien aus einer XLSX-Vorlage importieren. Die normale tägliche Kategorienverwaltung läuft über **Strg+K** bzw. den Kategorie-Manager.

### 3.5 Mehrere Kategorien auf einmal bearbeiten

Im Budget-Tab mehrere Zeilen markieren und rechtsklicken: **⚙️ N Kategorien bearbeiten…** öffnet die Massenbearbeitung. Dort lassen sich Fixkosten, Wiederkehrend, Fälligkeitstag und Forecast-Modus für alle markierten Kategorien gemeinsam setzen. Felder, die du unverändert lässt, bleiben je Kategorie bei ihrem bisherigen Wert.

Das lohnt sich, wenn du nach einem Import viele Kategorien gleich einstellen willst - sonst öffnest du den Eigenschaften-Dialog einmal je Kategorie.

## 4. Budget

Budgetwerte sind Sollbeträge. Sie erzeugen keine Buchungen.

### 4.1 Budget erfassen

Du kannst einen Betrag setzen für:

- einen einzelnen Monat,
- alle Monate,
- einen Monatsbereich,
- optional nur leere Zellen.

Die Budgettabelle unterstützt Jahr, Monat/Gesamt, Kontotyp und Kategoriebaum. Parent-Zeilen zeigen eigene Werte plus Kinder.

### 4.1a Im Betragsfeld rechnen

Betragsfelder nehmen auch eine Rechnung entgegen: `23,40 + 12,60` ergibt beim
Verlassen des Feldes 36,00. Wer eine Quittung mit mehreren Posten bucht, tippt
sie ab, statt vorher im Kopf zu addieren.

Erlaubt sind die vier Grundrechenarten, Klammern und Vorzeichen — `2 * (3 +
4,50)`. Steht etwas im Feld, das keine Rechnung ist, bleibt es stehen und wird
gemeldet; es wird nie stillschweigend zu einer Null.

Das gilt in den Dialogen ebenso wie direkt in den Zellen der Budgettabelle.

### 4.2 Jahr kopieren

**Jahr kopieren** bietet:

- Quell- und Zieljahr,
- alle Kontotypen oder nur einen Typ,
- Übernahme mit oder ohne Beträge,
- Prüfliste pro Kategorie,
- neuen Jahresbetrag pro Kategorie,
- Prüfung von Fixkosten, Wiederholungen, POTs, inkrementellen Kategorien und Lernvorschlägen.

### 4.3 13. Monatslohn

Der Knopf **13. Lohn** erfasst einen einmaligen Einnahmenplan für genau einen Auszahlungsmonat. Verwende dafür eine eigene Kategorie, damit der normale Monatslohn und die Forecast-Logik sauber bleiben.

### 4.4 Budgetwarnungen und Vorschläge

BudgetManager prüft abgeschlossene Monate und stabile Muster. Einzelne Ausreisser oder ein einzelner 0-Monat sollen keine unnötigen Änderungen erzeugen. Vorschläge werden nie automatisch übernommen.

## 5. Forecast-Modi, POT und Lernmodus

## 5.1 Normal/Flexibel

Für variable Alltagskosten. Wiederholte Muster dürfen Erhöhungs- oder Senkungsvorschläge erzeugen.

### 5.2 POT/Rückstellung

Ein POT reserviert Budget für erwartete unregelmässige Ausgaben, zum Beispiel Franchise, Selbstbehalt, Reparaturen oder Jahresrechnungen. Cockpit und Übersicht zeigen Plan, Verbrauch und verbleibende Rückstellung. Teilverbrauch senkt das Budget nicht automatisch; erst eine Überschreitung erzeugt eine Erhöhungswarnung.

**POT ist kein Sparziel:** POT = erwartete Ausgabe. Sparziel = fester Zielbetrag für später verfügbares Geld.

### 5.3 Inkrementell

Für Kosten, die über das Jahr verteilt geplant, aber unregelmässig oder in Teilbeträgen bezahlt werden. 0-Monate sind geschützt.

### 5.4 Tracking-Lernmodus

Pfad: **Datei → Einstellungen → Verhalten → Budgetübersicht**.

Der Lernmodus erstellt Startbudget-Vorschläge nur für Kategorien ohne positives Jahresbudget. Einstellbar sind:

- Aktivierung,
- Monate bis zum ersten Vorschlag,
- benötigte stabile Monate,
- Hochrechnung des laufenden Monats,
- Anzeige im Vorschlagsbericht,
- automatisches Ende.

Im Vorschlagsdialog kannst du übernehmen, weiter beobachten, ignorieren, als unregelmässig/POT markieren oder den Lernstatus zurücksetzen.

### 5.5 Soft-0-Budget

Pfad: **Datei → Einstellungen → Verhalten → Budgetübersicht → Soft-0-Budget aktivieren**.

Die Regel prüft:

**Einnahmen − Ausgaben − Ersparnisse ≈ 0 CHF**

- Überschuss: zusätzliche Ersparnis oder Übertrag vorschlagen.
- Defizit: zuerst Ersparnisse, danach flexible Ausgaben anpassen.
- Geschützt: Fixkosten, Wiederholungen, POTs und inkrementelle Jahreskosten.

„Soft“ bedeutet: nur Vorschläge, keine automatische Änderung und keine Buchung.

## 6. Tracking / Buchungen

Eine Buchung enthält Datum, Typ/Konto, Kategorie, Betrag, Bemerkung und optional Tags.

### 6.1 Buchung erfassen

Über Cockpit, Toolbar, Tracking oder **Strg+N** öffnet sich derselbe vollständige Buchungsdialog. **Speichern und weitere hinzufügen** behält sinnvolle letzte Werte wie das Konto bei.

Die Kategorieauswahl zeigt nur Kategorien des gewählten Typs. Buchbare Unterkategorien erscheinen kurz, beispielsweise **Miete** statt **Wohnen › Miete**.

### 6.2 Bearbeiten, duplizieren und löschen

Ausgewählte Buchungen lassen sich über Knöpfe oder Rechtsklick bearbeiten, duplizieren und löschen. Sicherheitsabfragen hängen von den Einstellungen ab.

### 6.3 Fix/Wiederkehrend buchen

**Strg+Umschalt+F** öffnet die Liste der fälligen Fixkosten, Wiederholungen und erwarteten Positionen für einen Monat. Es wird nur die Auswahl gebucht. Der Fälligkeitstag der Kategorie bestimmt das Datum; der Monat wird im Dialog gewählt.

### 6.4 Filter

Kombinierbar sind:

- Typ/Konto,
- Kategorie; Parent-Auswahl umfasst Children,
- Tags,
- Datum oder Zeitraum,
- Betrag,
- Bemerkung/Freitext.

**Filter zurücksetzen** zeigt wieder alles. Die Einstellung **Filter merken** kann die Auswahl über Starts hinweg bewahren.

### 6.5 Sparziel-Buchungen

Eine positive Ersparnisbuchung kann ein verknüpftes Sparziel erhöhen. Bei einer negativen Buchung fragt BudgetManager, ob sie als Entnahme des Sparziels behandelt werden soll.

### 6.6 Zahlungen aus anderen Programmen übernehmen

Andere Programme der Suite — etwa FPM — legen Ausgaben als Vorschlag in einem
gemeinsamen Ordner ab. BudgetManager öffnet dessen Datenbank nie; er liest die
Vorschläge und legt sie in eine Eingangsliste, die Sie prüfen, bevor etwas
gebucht wird.

Die Liste zeigt Datum, Beschreibung, Gegenpartei, Betrag, Währung und die
vorgeschlagene Kategorie. Unter der Tabelle wählen Sie Typ und Kategorie —
mit demselben Suchfeld und gefilterten Dropdown wie in der Schnelleingabe —
und setzen sie mit **Kategorie zuweisen** auf alle markierten Vorschläge. Für
zwanzig gleichartige Zahlungen ist das ein Schritt statt zwanzig.

Über **Bearbeiten** lassen sich Datum, Typ, Kategorie, Betrag und
Beschreibung einzeln ändern. Nur dort wird eine noch nicht vorhandene
Kategorie angelegt, und auch dann erst nach Ihrer ausdrücklichen Bestätigung.

**Übernehmen** bucht, **Ablehnen** blendet den Vorschlag aus, bis die Quelle
ihn ändert. Bereits übernommene Vorschläge bleiben unverändert stehen: Ihre
Buchung existiert und würde einer nachträglichen Änderung nicht folgen.

Weicht die Fremdwährung von Ihrer Kontowährung ab, verlangt BudgetManager
eine ausdrückliche Bestätigung, bevor der Betrag übernommen wird.

### 6.7 Meldungen im LifePlanner

Läuft BudgetManager als Modul im LifePlanner, meldet er dorthin, was gerade
ansteht: überzogene Budgets, Sparziele kurz vor oder nach ihrem Termin und
erreichte Sparziele. Der LifePlanner zeigt diese Meldungen auf seiner
Übersichtsseite, über den Modulkacheln — Sie sehen sie also, ohne den
BudgetManager zu öffnen.

Übertragen wird nur die fertige Meldung: eine Zeile Text und wie dringend sie
ist. Beträge, Buchungen und Kategorienamen bleiben in Ihrer Datenbank. Der
Stand wird beim Beenden geschrieben und beim nächsten Mal vollständig ersetzt —
was erledigt ist, verschwindet von selbst.

Ohne LifePlanner passiert hier nichts.

### 6.8 Was an FPM weitergegeben wird

Die Brücke läuft in beide Richtungen: FPM schlägt Ausgaben vor, und
BudgetManager stellt im Gegenzug Kategorienamen und Sparziele bereit — damit
FPM seine Ausgaben Ihren Kategorien zuordnen und den Fortschritt eines
Wunsches anzeigen kann.

Sie entscheiden das seit v2.5.0 Eintrag für Eintrag.
**Extras → Freigabe für FPM** zeigt Ausgabenkategorien, Sparkategorien und Sparziele
mit je einem Häkchen. Nur Angehaktes steht in der Brückendatei; alles andere
bleibt in Ihrer Datenbank. Von Kategorien geht nur der Name hinaus, kein
Budgetwert und keine Buchung; von einem Sparziel Name, Betrag und Frist.

Es gibt keinen OK-Knopf — jedes Häkchen wirkt sofort, und beim Schliessen des
Dialogs werden die Brückendateien neu geschrieben. **Alle** und **Keine**
gelten nur für den Reiter, den Sie gerade sehen. **Jetzt an FPM senden**
schreibt die Dateien sofort neu und nennt den Ordner, in dem sie liegen.

Beim Update auf 2.5.0 bleibt freigegeben, was bisher schon übertragen wurde —
sonst stünde FPM plötzlich ohne Kategorien da. Neu angelegte Kategorien und
Sparziele sind dagegen von sich aus nicht freigegeben. Ausnahme: Ein Sparziel,
das aus einem FPM-Wunsch entstanden ist, wird gespiegelt, damit der
Fortschritt dort sichtbar ist; zurücknehmen können Sie es im selben Dialog.

### 6.9 Bankimport aus PDF und CSV

**Import → Bank PDF/CSV…** liest einen Kontoauszug oder eine
Kreditkartenabrechnung ein. Gelesen wird auf Ihrem Rechner; es geht keine
Zeile an einen fremden Dienst.

Nach dem Öffnen zeigt der Dialog jede erkannte Zeile mit Datum, Typ, Betrag,
Text, Kategorie, Tags und einem Haken. **Nur angehakte Zeilen werden
gebucht.** Vorschläge für Typ und Kategorie stammen aus dem lokalen
Gedächtnis; es schlägt nur Kategorien und Tags vor, die es schon gibt.

Mehrere Zeilen wählen Sie mit **Strg+Mausklick**, **Umschalt+Mausklick** oder
**Strg+A**. Die Dropdowns über der Tabelle setzen Typ, Kategorie, Tags und
Auswahlstatus für alle markierten Zeilen auf einmal.

Die Pflicht-Tags der gewählten Kategorie werden gesetzt und bleiben gesetzt;
weitere vorhandene Tags können Sie im Tag-Dropdown ankreuzen.

Dieselbe Datei zweimal zu öffnen erzeugt keine doppelten Buchungen: Jede Zeile
trägt eine Kennung aus Datum, Betrag und Text. Der Import läuft in einem
Zug — er geht ganz durch oder gar nicht.

Gelernt wird erst **nach** dem Import und nur aus dem, was Sie bestätigt
haben. Ein Vorschlag, den Sie geändert oder abgewählt haben, wird nicht
gelernt.

**TWINT-Eingänge werden nicht als Einkommen gebucht.** Ein positiver
TWINT-Betrag ist meist die Rückzahlung einer Auslage, die als Ausgabe schon
in Ihren Zahlen steht — als Einkommen gebucht stünde der Monat doppelt
falsch. Solche Zeilen bekommen den Typ **TWINT (KI)**: Sie ordnen ihnen eine
echte Kategorie zu, das Programm merkt sich die Zuordnung, und die Buchung
selbst hat 0.00 Wirkung auf Ihr Budget.

## 7. Übersicht und Diagramme

Die Übersicht bietet Jahr, Monat oder benutzerdefinierten Zeitraum. Rechts können Typ, Kategorie inklusive Unterkategorien, Tags, Bemerkung und Betragsgrenzen kombiniert werden.

### 7.1 Kennzahlen und Tabellen

- Einnahmen, Ausgaben, Ersparnisse und Bilanz.
- Soll, Ist, Rest, Nutzung in Prozent und Überschreitungen.
- Gefilterte Buchungsliste.
- Budgetvorschläge und Lernbudgets.

### 7.2 Diagramme erklärt

- Plan/Ist-Donut.
- Kategorien-Ranking.
- Vergleich der Kontotypen.
- Monatsverlauf.
- Monatsbilanz.
- Top-Buchungen.

Klicks auf KPI oder Diagramme setzen passende Filter. Doppelklick auf eine Budgetzeile öffnet die Bearbeitung.

## 8. Sparziele

Sparziele sind eigenständige Projekt-Geldflüsse. BudgetManager trennt deshalb fünf Werte:

- **Zielbetrag:** gewünschte Gesamtsumme des Projekts.
- **Eingezahlt:** Summe der echten Einzahlungen abzüglich ausdrücklich als Korrektur gebuchter Fehlbeträge.
- **Verwendet/Bezüge:** Geld, das aus dem Projektbestand herausgenommen wurde.
- **Aktueller Bestand:** eingezahlt minus verwendet.
- **Noch einzuzahlen:** Zielbetrag minus eingezahlt. Bezüge erhöhen diesen Wert nicht erneut.

Beispiel Hochzeit: Ziel `50’000 CHF`, eingezahlt `30’000 CHF`, davon verwendet `15’000 CHF`. Der aktuelle Bestand ist `15’000 CHF`; noch einzuzahlen bleiben `20’000 CHF`.

Workflow:

1. Ziel mit Zielbetrag und optionaler Kategorie anlegen.
2. Einzahlungen als positive Ersparnisbuchungen erfassen.
3. Eine negative Buchung ist standardmässig ein **Bezug** und wird unter „verwendet“ ausgewiesen.
4. War die negative Buchung nur eine Fehlbuchung, im Rückfragedialog ausdrücklich **Korrektur** wählen. Sie vermindert den Einzahlungsfortschritt, zählt aber nicht als Verwendung.
5. Über **Teilfreigabe** einen wählbaren Betrag verfügbar machen. Das Ziel bleibt aktiv und weitere Einzahlungen bleiben möglich.
6. Ziel erst bei endgültigem Abschluss beenden; abgeschlossene Ziele können wieder geöffnet werden.

Bestand und Einzahlungsfortschritt dürfen nicht negativ werden. Einzahlungen über den Zielbetrag sowie Bezüge über den vorhandenen Bestand werden blockiert.

### 8.1 Sparzielwünsche aus anderen Programmen

Läuft FPM als Teil der Suite, können Wunschfüller von dort als Sparziel
hierher kommen. Im Sparziel-Dialog öffnet **Wünsche aus FPM…** die offenen
Vorschläge und fragt einzeln nach — einzeln, weil ein Sparziel eine
Entscheidung über Geld ist, das monatlich zurückgelegt wird.

Zu jedem Wunsch steht der Zielbetrag und die Kategorie, unter der er erscheinen
soll. Sie kommt aus Ihrem eigenen Kategorienbaum; **gibt es sie nicht, wird sie
auch nicht angelegt** — das Ziel entsteht dann ohne Kategorie, und Sie ordnen
es hier zu. Ein anderes Programm soll Ihren Kategorienbaum nicht verändern.

„Nein" blendet den Vorschlag dauerhaft aus, „Abbrechen" lässt die übrigen
offen. Übernommene und abgelehnte Wünsche kommen nicht wieder, auch wenn FPM
sie weiterhin schickt.

## 9. Cockpit

Das Cockpit zeigt Monatsampel, nächste Schritte, KPI, offene Fälligkeiten, Warnungen, POT-Reststände, Favoriten, Sparziele und letzte Buchungen. Über **Cockpit gestalten** blendest du Karten ein/aus und änderst ihre Reihenfolge.

### 9.1 Kennzahlen und Trend

Die vier Kacheln oben zeigen Einnahmen, Ausgaben, Ersparnisse und den freien Betrag. Rechts unten in jeder Kachel steht der Vergleich zum Vormonat als Pfeil mit Betrag. Die Farbe folgt der Bedeutung, nicht dem Vorzeichen: mehr Einnahmen sind grün, mehr Ausgaben rot. Im ersten Monat ohne Vorgängerdaten bleibt der Pfeil aus.

### 9.2 Auswertung

Der Abschnitt **Auswertung** enthält zwei Diagramme. Der Ring zeigt die Ausgaben des Monats nach Kategorie mit der Gesamtsumme in der Mitte; mehr als fünf Kategorien werden zu einem Restsegment zusammengefasst. Der Flächenverlauf daneben zeigt die kumulierten Ausgaben über den Monat — er steigt an jedem Buchungstag und macht sichtbar, ob sich die Ausgaben am Monatsanfang oder -ende ballen.

### 9.3 Automatik oder fixiertes Layout

Standard ist der **Automatikmodus**: Abschnitte ohne Inhalt schrumpfen auf ihre Kopfzeile und rutschen unter die gefüllten. Bekommt ein Abschnitt wieder Inhalt, kehrt er an seine gespeicherte Position zurück. Damit steht immer oben, was gerade etwas zu sagen hat.

Wer eine eigene Anordnung möchte, aktiviert **Ansicht → Cockpit-Layout → Kacheln frei anordnen** oder den gleichnamigen Schalter oben im Cockpit. Danach ist die **gesamte Kopfzeile** jeder Kachel eine Drag-Zone; zusätzlich bleibt der Griff `≡` sichtbar. Linke und rechte Spalte sind unabhängige Stapel: Eine Kachel rechts kann deshalb bis ganz nach oben rücken, ohne von der Höhe einer linken Kachel blockiert zu werden. Während des Ziehens zeigt ein deutlich markierter **Ablageplatzhalter** exakt die spätere Position. Reihenfolge und Spalte werden nach jedem Loslassen sofort gespeichert. Tabellen, Buttons und Diagramme innerhalb der Kachel bleiben normal bedienbar, weil der Kachelinhalt selbst nicht als Drag-Zone dient. **Ansicht → Cockpit-Layout → Cockpit-Layout zurücksetzen** stellt Automatikmodus, Standardreihenfolge und Standardspalten wieder her.

Beides gleichzeitig geht bewusst nicht: Die Automatik würde eine von Hand gezogene Anordnung beim nächsten Aktualisieren überschreiben.

### 9.4 Ein oder zwei Spalten

Im Automatikmodus wechselt das Cockpit ab etwa 1180 Pixel Fensterbreite auf zwei Spalten. Im manuellen Modus stehen bereits ab 720 Pixel zwei gleich breite Zielspalten bereit, damit Kacheln auch in normalen Fenstergrössen frei zwischen links und rechts verschoben werden können. Bei noch schmaleren Fenstern kann die umgebende Ansicht horizontal scrollen; die gespeicherte Anordnung bleibt erhalten.

### 9.5 Aussehen anpassen

Farben und Kachelform kommen vollständig aus dem aktiven Designprofil. Unter **Einstellungen → Erscheinungsbild** stehen 26 Profile zur Auswahl; eigene lassen sich dort erstellen und speichern. Für die Optik moderner Dashboards ist **Mitternacht – Violett** gedacht: fast schwarzer Hintergrund, abgesetzte Kacheln, violetter Akzent.

## 10. Tags

Tags sind Schlagworte zusätzlich zur Kategorie, etwa „Hochzeit“, „steuerlich relevant“ oder „Urlaub 2026“. Der Tags-Manager verwaltet Name, Farbe und optionalen Aktionstext. Feste Kategorie-Tags werden automatisch ergänzt; manuelle Tags bleiben bei einem Kategorienwechsel erhalten.

## 11. Konten

BudgetManager besitzt mindestens die drei Kontotypen **Einnahmen**, **Ausgaben** und **Ersparnisse**. Zusätzliche Konten können in der Konten-/Kategorienverwaltung angelegt, farblich gekennzeichnet und bei Bedarf geschlossen werden; die drei Grundtypen bleiben erhalten.

Konten strukturieren den Geldfluss, Kategorien beschreiben den Zweck. Wähle beim Buchen zuerst das Konto bzw. den Typ; danach zeigt die Kategorieauswahl nur passende Kategorien. Benutzerkonten für Anmeldung und Verschlüsselung werden getrennt unter **Konto, Sicherheit und Restore-Key** erklärt.

## 12. Monatsabschluss

Pfad: **Cockpit → Monatsabschluss…**.

Der Assistent rechnet aus echten Buchungen:

**Einnahmen − Ausgaben − Ersparnisse = frei verfügbar**

- Überschuss kann als Ersparnis gebucht werden.
- Defizit kann aus vorhandenem Ersparnisguthaben gedeckt werden.
- Hinweise für den Folgemonat nennen nur flexible Budgets, nie Fixkosten oder Wiederholungen.

Das Häkchen **Monat als abgeschlossen markieren** setzt nur einen Erinnerungs-Vermerk für das Cockpit. Es sperrt weder Budget noch Buchungen. Nachträgliche Änderungen bleiben möglich; öffne den Assistenten erneut, um neu zu rechnen.

## 13. Favoriten und Suche

Favoriten sind Kategorien, die du häufig prüfen möchtest. Das Favoriten-Dashboard ist über **F12** oder Extras erreichbar.

**Extras → Globale Suche** oder **Strg+F** durchsucht Buchungen, Budgets und Kategorien. Mindestens zwei Zeichen eingeben. Doppelklick auf ein Ergebnis springt zum passenden Bereich.

## 14. Export, PDF und Drucken

**Extras → Export / Strg+E** exportiert Tracking, Budget und optional Kategorien für ein Jahr oder den gesamten Zeitraum.

Verfügbare Formate sind CSV mit optionalem UTF-8-BOM, tabulatorgetrenntes TXT, XLSX mit getrennten Tabellenblättern sowie ein schwarzweiss-tauglicher A4-PDF-Bericht. XLSX enthält Filter und fixierte Kopfzeilen. Eine interaktive Druckvorschau ist nicht Bestandteil des Exportdialogs.

Der Export ist kein Backup; verwende `.bmr` für die Wiederherstellung.
## 15. Benutzerkonto, Sicherheit und Restore-Key

Sicherheitsstufen:

- Quick: bequem, lokaler Schlüssel.
- PIN: kurzer Zugangsschutz.
- Passwort: stärkster normaler Schutz.

Name, Geheimnis und Sicherheitsstufe lassen sich in der Kontoverwaltung ändern. Sicherheitskritische Aktionen können eine erneute Anmeldung verlangen.

Der Restore-Key kann eine verschlüsselte Datenbank wieder zugänglich machen. Sichere ihn getrennt vom Backup, zum Beispiel in einem Passwortmanager und zusätzlich auf Papier. Wer Restore-Key und `.enc`-Datei besitzt, kann die Daten entschlüsseln.

## 16. Datenordner, Backup und Datenbankverwaltung

### 16.1 Datenordner

Pfad: Reiter **Konto** oder **Datei → Einstellungen → Konto & Daten**.

Du siehst den wirksamen Speicherort, kannst ihn öffnen oder einen neuen Ordner wählen. Bei einem leeren Ziel bietet BudgetManager eine kontrollierte Übernahme mit Sicherheits-Backup an. Der neue Speicherort wird nach Neustart vollständig wirksam.

### 16.2 Backup und Restore

Backups sind geprüfte `.bmr`-Pakete. Sie können Datenbank, Einstellungen und das zur Datenbank gehörende Benutzerkonto enthalten. Bei mehreren lokalen Konten wird nur der passende Kontoeintrag mitgesichert. Auto-Backup bietet Intervall, Anzahl aufzubewahrender Sicherungen und optionale Bereinigung.

Seit v2.2.48 werden Datenbank, Einstellungen und Konto-Metadaten jeweils mit eigener SHA-256-Prüfsumme kontrolliert. Beschädigte oder nachträglich veränderte Inhalte werden abgewiesen; alte Backups können nach ausdrücklicher Bestätigung in eine vollständig geprüfte Kopie umgewandelt werden. Die Prüfsummen beweisen jedoch nicht, von wem ein Backup stammt. Vollständige Konto-Backups deshalb nur aus vertrauenswürdiger Quelle importieren. Bei einem Quick-Konto kann das Paket den lokalen Datenbankschlüssel enthalten; behandle die `.bmr`-Datei deshalb wie ein Passwort und lege sie nicht ungeschützt in öffentliche Cloud-Ordner.

Vor Reset, Restore, Datenumzug und grossen Updates ein frisches externes Backup erstellen.

### 16.3 Datenbankverwaltung

Sie zeigt Statistiken und Migrationsstand, kann technische Altlasten bereinigen und enthält den einzigen normalen Datenbank-Reset. Reset existiert nur noch in der Datenbankverwaltung. Reset verlangt bei geschütztem Konto erneut den Benutzercode (PIN oder Passwort) und löscht Nutzdaten.

Bei Source- oder portablen Starts kann der Standardordner `data/` verwendet werden. Verlasse dich bei mehreren Programmordnern auf den Pfad in der Statusleiste.

## 17. Einstellungen und Design

Unter **Wie das System** folgt die Anzeige der Hell/Dunkel-Einstellung Ihres Betriebssystems — und zwar sofort: Stellen Sie dort um, während BudgetManager läuft, wechselt er mit. Eine feste Wahl von Hell oder Dunkel bleibt davon unberührt.

**Datei → Einstellungen** bzw. **Strg+,**.

- Allgemein: Sprache, Währung, Zahlenformat, Onboarding, Startverhalten.
- Verhalten: Auto-Speichern, Warnungen, Tracking, Fälligkeit, Lernmodus, Soft-0, Übertrag, Drag & Drop.
- Darstellung: Hell/Dunkel, Designprofile, Schriftgrösse, Tabellendichte, Fixkosten-Hervorhebung.
- Tastenkürzel: ändern oder zurücksetzen.
- Konto & Daten: Datenordner, Backups, Datenbank.

Seit v2.2.33 nimmt die Seitenleiste ihre Farbe aus dem BudgetManager-Profil. Ein dunkles GNOME-Systemtheme darf ein helles App-Profil nicht mehr übersteuern. Eine Sprachänderung wird vollständig nach einem Neustart angewendet.

### Einfach- und Erweitert-Modus

Unter **Ansicht → Bedienmodus** wechselst du jederzeit zwischen:

- **Einfach:** Cockpit, Budget, Tracking und Übersicht; Kategorien und Sparziele bleiben über Dialoge bzw. nach Umschalten erreichbar.
- **Erweitert:** zeigt alle Hauptreiter und das vollständige Standard-Cockpit.

Manuell veränderte Reiter oder Cockpit-Bereiche werden als **Benutzerdefiniert** erkannt. Es werden dabei keine Daten oder Funktionen gelöscht.

## 18. Tastenkürzel

Wichtige Standards:

| Kürzel | Funktion |
|---|---|
| F1 | Handbuch |
| Strg+F1 | Kürzelübersicht |
| Strg+N | Buchung erfassen |
| Strg+F | Suche |
| Strg+S | Speichern |
| Strg+K | Kategorien |
| Strg+T | Tags |
| Strg+E | Export |
| Strg+0…5 | Navigation |
| Strg+Z / Strg+Umschalt+Z | Rückgängig/Wiederholen |
| Strg+Umschalt+F | Fix/Wiederkehrend buchen |
| F5 | Aktualisieren |
| F10 / F11 | Maximieren / Vollbild |

Alle Kürzel sind in den Einstellungen anpassbar.

## 19. Updates

**Extras → Updates** bzw. **Strg+U**. Der Update-Dialog prüft Manifest und Integrität, lädt die passende Variante und bereitet die Installation vor. Datenordner und Backups bleiben bestehen. Vor einem grossen Update ist ein zusätzliches externes Backup trotzdem sinnvoll.

## 20. Fehlerdiagnose

Unter **Hilfe** kannst du Anwendungslog, Crash-Log und Diagnoseordner öffnen oder einen Diagnosebericht erzeugen. Der Diagnosebericht enthält technische Informationen und Logs, aber bewusst keine Datenbank und keine Backups. Vor dem Weitergeben trotzdem prüfen.

Nach einem unsauberen Programmende erscheint beim nächsten Start ein Hinweis.

## 21. Typische Probleme

### Rechte Seite oder Seitenleiste bleibt dunkel

- App-Profil unter **Einstellungen → Darstellung** prüfen.
- Theme einmal wechseln und zurückwechseln.
- Version 2.2.33 oder neuer verwenden; GNOME Dark darf die Sidebar nicht mehr übersteuern.

### Daten fehlen scheinbar

Zeitraum und alle Filter prüfen, danach **F5**. Die Statusleiste zeigt den aktiven Datenbankpfad.

### Budget erzeugt keine Buchung

Das ist korrekt: Budget ist nur Plan. Buchung manuell oder über Fix/Wiederkehrend erfassen.

### Kein Soft-0-Vorschlag

Einnahmenbudget muss grösser als 0 CHF sein. Ausgewählten Monat, Einstellung und stabile Vormonate prüfen.

### Restore funktioniert nicht

Richtiges `.bmr`, aktives Konto und Restore-Key prüfen. Vor dem nächsten Versuch Sicherheitskopie behalten.

## 22. Best-Practice-Routine

**Täglich:** Buchungen erfassen.

**Wöchentlich:** Tracking-Filter prüfen, offene Fehler korrigieren, Übersicht ansehen.

**Monatlich:** Fix/Wiederkehrend buchen, Monatsabschluss prüfen, Vorschläge bewusst bewerten, Backup erstellen.

**Jährlich:** Jahr kopieren, Fixkosten/POTs/inkrementelle Kategorien kontrollieren, 13. Monatslohn separat planen.

## Wiki-Audit und grafische Zusammenhänge

Unter **Hilfe → Zusammenhänge und Grafiken** öffnet sich eine lokale Offline-Seite mit drei Grafiken. Sie zeigt den Gesamtprozess, den Datenfluss zwischen Budget und Tracking sowie die Rückkopplung über Übersicht, Warnungen und Budgetanpassung. Das **?** rechts oben in der Menüleiste – direkt neben Minimieren/Maximieren/Schließen – öffnet das durchsuchbare In-App-Handbuch. Zusätzlich gibt es den Knopf **? Hilfe** unten links in der Seitenleiste. Beide Wege sind bewusst normaler Text statt Emoji, damit sie unter Fedora/GNOME auch ohne Emoji-Schrift sichtbar bleiben.

Im Cockpit sinken leere Kacheln seit v2.2.41 automatisch ans Ende ihrer Spalte. Wer eine eigene Anordnung will, schaltet **Kacheln fixieren** ein: dann bleibt die Reihenfolge, und die Kacheln lassen sich an ihrer Kopfzeile mit der Maus ziehen — auch von einer Spalte in die andere.

Das Menü **Hilfe** ist seit v2.2.38 in fünf Gruppen aufgeteilt: Nachschlagen (Handbuch, Wissensdatenbank, Visuelle Übersichten), Lernen (Tastenkürzel, Erste Schritte), **Problembehandlung** als Untermenü (Anwendungsprotokoll, Absturzprotokoll, Diagnoseordner, Diagnosebericht, Wiederherstellungsschlüssel), Version (Nach Updates suchen, Neuerungen in dieser Version) und zuletzt Über. Die Update-Prüfung stand vorher unter Extras.
