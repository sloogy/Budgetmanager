# Soft-0-Budget – vollständige Anleitung

Gültig für BudgetManager 2.2.43.

## 1. Einstellung finden

Öffne **Datei → Einstellungen → Verhalten**. Im Bereich **Budgetübersicht** aktivierst du **Soft-0-Budget (sanfte Null-Bilanz-Regel)**. Direkt daneben öffnet der Knopf **Erklärung öffnen** das passende Kapitel im In-App-Handbuch.

Suchbegriffe im Handbuch: `Soft 0`, `0-Budget`, `Nullbudget`, `Null-Bilanz`, `Überschuss`, `Übertrag`.

## 2. Zweck

Die Regel verteilt dein geplantes Einkommen auf Ausgaben und Ersparnisse:

**Einnahmen − Ausgaben − Ersparnisse = ungefähr 0 CHF**

Das bedeutet nicht, dass du alles ausgeben sollst. Ersparnisse, Rückstellungen und Sparziele sind ebenfalls Aufgaben für dein Geld.

„Soft“ bedeutet:

- keine automatische Buchung,
- keine automatische Budgetänderung,
- kein Zwang auf exakt 0 CHF,
- jeder Vorschlag muss von dir geprüft und bestätigt werden.

## 3. Voraussetzungen

Die Regel arbeitet nur sinnvoll, wenn:

1. im ausgewählten Monat ein Einnahmenbudget größer als 0 CHF vorhanden ist,
2. Ausgaben und/oder Ersparnisse budgetiert sind,
3. die Einstellung gespeichert wurde,
4. die Budgetvorschläge in der Übersicht oder über **Extras → Budgetwarnungen/Vorschläge** geöffnet werden.

Die Planung des Zielmonats hat Vorrang. Ist sie bereits fast ausgeglichen, kann BudgetManager ein stabiles Muster aus abgeschlossenen Vormonaten verwenden. Kleine Rundungsdifferenzen werden absichtlich ignoriert.

## 4. Überschuss

Beispiel:

| Bereich | Plan |
|---|---:|
| Einnahmen | 5’000 CHF |
| Ausgaben | 3’000 CHF |
| Ersparnisse | 1’000 CHF |
| Nicht zugeordnet | **1’000 CHF** |

Unter **Überschuss verwenden für** gibt es zwei Varianten.

### Ersparnisse erhöhen

BudgetManager wählt eine plausible Ersparnisse-Kategorie, bevorzugt Namen wie Notgroschen, Reserve, Rücklage oder Sparen. Liegt deren Budget bei 1’000 CHF, wird 2’000 CHF vorgeschlagen.

### In nächsten Monat übertragen

BudgetManager zeigt 1’000 CHF als Übertrag. Der Betrag wird nicht automatisch gebucht. **Kumulation Startmonat** und **Kumulation Startjahr** bestimmen, ab wann der Übertrag in der Übersicht aufsummiert wird.

Gibt es keine Ersparnisse-Kategorie, erscheint ebenfalls ein Übertrag-Hinweis.

## 5. Defizit

Beispiel:

| Bereich | Plan |
|---|---:|
| Einnahmen | 5’000 CHF |
| Ausgaben | 4’000 CHF |
| Ersparnisse | 1’500 CHF |
| Fehlbetrag | **500 CHF** |

BudgetManager schlägt zuerst vor, Ersparnisse von 1’500 CHF auf 1’000 CHF zu reduzieren.

Reichen Ersparnisse nicht, folgen nur flexible Ausgaben. Nicht gekürzt werden:

- Fixkosten,
- fixe wiederkehrende Kosten,
- POT/Rückstellungen wie Franchise oder Selbstbehalt,
- inkrementelle Jahreskosten,
- andere geschützte Prognosearten.

Bleibt danach ein Fehlbetrag, zeigt die App ihn offen an, statt unrealistische Kürzungen zu erfinden.

## 6. Abgrenzung

| Funktion | Aufgabe |
|---|---|
| Tracking-Lernmodus | Erstes Budget aus echten Buchungen lernen, wenn noch kein Budget existiert |
| Normale Budgetvorschläge | Einzelne Kategorie mit ihren Buchungen vergleichen |
| Soft-0-Budget | Gesamtplanung aus Einnahmen, Ausgaben und Ersparnissen ausgleichen |
| Monatsabschluss | Tatsächlich abgeschlossenen Monat prüfen und bewusste Abschlussbuchungen anbieten |
| Übertrag | Nicht verbrauchte Planbeträge in der Übersicht über Monate kumulieren |

## 7. Empfehlung

Aktiviere Soft-0-Budget, wenn du deinem gesamten Einkommen bewusst Aufgaben geben möchtest. Lass es deaktiviert, wenn du absichtlich einen großen freien, nicht kategorisierten Puffer behalten willst.

## 8. Fehlersuche

### Kein Vorschlag erscheint

- Einstellung mit **Anwenden** oder **OK** gespeichert?
- Einnahmenbudget im Zielmonat größer als 0 CHF?
- Differenz möglicherweise nur eine kleine Rundung?
- Genügend abgeschlossene Vormonate für ein stabiles Muster vorhanden?
- Richtiger Monat und richtiges Jahr in der Übersicht gewählt?
- Vorschlagsdialog geöffnet?

### Ersparnisse werden nicht klassisch gesenkt

Das ist bei aktiver Regel gewollt. Ein nicht gebuchtes Sparbudget soll nicht gleichzeitig durch die normale Kategorie-Logik gesenkt und durch Soft-0-Budget erhöht werden. Die Gesamtregel hat Vorrang und verhindert widersprüchliche Vorschläge.

### Fixkosten werden nicht gekürzt

Ebenfalls gewollt. Miete, Versicherungen, POT/Rückstellungen und ähnliche geschützte Kosten sollen nicht künstlich klein gerechnet werden.

## Merksatz

**Soft-0-Budget gibt jedem geplanten Franken eine Aufgabe. BudgetManager schlägt vor – du entscheidest.**
