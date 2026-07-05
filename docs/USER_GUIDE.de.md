# BudgetManager 2.2.6 – Benutzeranleitung

## 1. Grundidee

BudgetManager arbeitet lokal auf deinem Computer. Das Programm speichert Budget, Buchungen, Kategorien, Backups und Einstellungen im Datenordner. Bei der portablen Version liegt dieser Ordner neben dem Programm unter `data/`.

Der normale Ablauf ist einfach:

1. Kategorien prüfen oder anlegen.
2. Monatsbudget erfassen.
3. Echte Buchungen im Tracking eintragen.
4. Übersicht und Diagramme prüfen.
5. Vor größeren Änderungen ein Backup erstellen.

## 2. Kategorien

Kategorien gehören immer zu einem Typ: Einnahmen, Ausgaben oder Ersparnisse. Unterkategorien dürfen nur innerhalb desselben Typs verschoben werden. Mit Drag & Drop kannst du Kategorien unter eine Hauptkategorie ziehen oder wieder zur Hauptkategorie machen.

Die Häkchen bedeuten:

- **Fixkosten**: planbare Kosten oder Rückstellungen, zum Beispiel Miete, Krankenkasse, Franchise oder Selbstbehalt.
- **Wiederkehrend**: regelmäßig wiederkehrende Buchung.
- **Fix + Wiederkehrend**: echte monatliche Fixkosten. Beim Buchen wird der Budgetbetrag übernommen.
- **Fix ohne Wiederholung**: geschützte variable Rückstellung. Beim Buchen darf der Betrag angepasst werden.
- **Wiederkehrend ohne Fix**: regelmäßige, aber variable Buchung. Beim Buchen darf der Betrag angepasst werden.

## 3. Budget

Im Budget-Tab trägst du pro Kategorie und Monat den geplanten Betrag ein. Ein Budget erzeugt noch keine Buchung. Es ist nur der Plan.

Wichtige Regeln:

- Leere Felder sind 0.
- Parent-Kategorien zeigen die Summe der Kinder plus eigenen Puffer.
- Die Gesamtzeile zeigt die Summe des sichtbaren Bereichs.
- Ein Jahr kann aus einem bestehenden Jahr kopiert werden, wahlweise mit oder ohne Beträge.

## 4. Tracking / Buchungen

Im Tracking erfasst du echte Geldbewegungen. Die Kategorieauswahl zeigt nur Kategorien des gewählten Typs. Favoriten und häufig manuell genutzte Kategorien erscheinen oben, automatische Fixkosten verzerren diese Reihenfolge nicht. Parent-Kategorien mit Unterkategorien werden dort nicht als eigene Buchungszeile angezeigt; Unterkategorien erscheinen kurz, z. B. **Miete** statt **Wohnen › Miete**.

Der Button **Fix/Wiederkehrend buchen** erstellt bewusst die fälligen Fixkosten und wiederkehrenden Buchungen für den gewählten Monat. Es wird nichts heimlich im Hintergrund gebucht.

Für **Sparziele** (Typ Ersparnisse) kannst du einen Zielbetrag setzen und den Fortschritt verfolgen. Einzahlungen und Entnahmen werden als Buchungen erfasst; der Fortschritt kann nie unter 0 fallen oder über das Ziel hinausgehen.

## 5. Forecast / Budgetvorschläge

Budgetvorschläge sind Hilfen, keine automatischen Änderungen. Die App prüft nur abgeschlossene Monate und vermeidet Vorschläge bei einzelnen Ausreißern.

Logik:

- Eine einzelne 0-Buchung ist nie allein ein Grund für eine Senkung.
- Bei Fixkosten und wiederkehrenden Kategorien werden 0-Monate für Senkungen ignoriert.
- Bei Fixkosten braucht es wiederholte echte Buchungen, bevor ein Vorschlag entsteht.
- Flexible Kategorien dürfen aus wiederholten Mustern lernen, auch wenn einzelne Monate 0 enthalten.
- Gegensätzliche Ausreißer, zum Beispiel 450 CHF und danach 350 CHF bei 400 CHF Budget, erzeugen keinen Vorschlag.

## 6. Übersicht und Diagramme

Die Übersicht vergleicht Plan und Ist.

Diagramme erklärt:

- **Plan/Ist-Donut**: Außen Einnahmen, Mitte Ausgaben, innen Ersparnisse. Jeder Ring zeigt gebucht, offen oder über Budget. Das ist der wichtigste Monatscheck.
- **Kategorien-Ranking**: zeigt die größten Ausgaben-Kategorien als Balken. Das ist leichter lesbar als ein großes Kreisdiagramm.
- **Konto-Vergleich**: zeigt Einnahmen, Ausgaben und Ersparnisse als Balken. Das ersetzt den verwirrenden Kreis daneben, weil diese Werte keine Anteile desselben Topfs sind.
- **Monatsverlauf**: zeigt die Entwicklung über Monate. Gut, um Trends zu erkennen.
- **Monatsbilanz**: zeigt Einnahmen minus Ausgaben minus Ersparnisse pro Monat.
- **Top-Buchungen**: fasst Kategorien zusammen und sortiert nach Betrag, damit wiederholte Lohn- oder Mietbuchungen nicht mehrfach als Einzelzeilen verwirren.

Wenn keine Daten vorhanden sind, zeigt die App einen Hinweis statt eines leeren Diagramms.

## 7. Updates

Über **Extras → Updates…** prüft die App auf neue Releases. Das Update-Fenster zeigt die Schritte an.

Updatewege:

- **Portable Windows/Linux**: lädt das portable ZIP, ersetzt Programmdateien und lässt `data/` sowie `updates/` bestehen.
- **Direkte Windows-EXE/Linux-Binary**: migriert alte versionierte Startdateien auf stabile Namen.
- **Windows Installer**: lädt die neue Setup-EXE, wartet bis die App geschlossen ist und startet den Installer im Update-Modus. Der gewählte Datenordner bleibt erhalten.

## 8. Backup und Restore-Key

Der Restore-Key ist wichtig für verschlüsselte Datenbanken und Wiederherstellung. Sichere ihn außerhalb des BudgetManager-Ordners, zum Beispiel in Bitwarden.

Vor großen Änderungen: Backup erstellen. Der Datenordner und `data/backups/` werden bei Updates nicht überschrieben.

## 5.1 Tracking-Lernmodus

Der Tracking-Lernmodus hilft, wenn du noch kein Budget gesetzt hast. Er schaut nur auf manuelle Buchungen und erstellt daraus einen Vorschlag für ein neues Budget.

Im Erststart darfst du mit aktivem Lernmodus ohne Budgetwert weitergehen. Das ist Absicht: Du kannst zuerst nur tracken und die Budgets später aus echten Daten lernen lassen. Wenn du den Lernmodus deaktivierst, verlangt der Erststart weiterhin mindestens einen Budgetwert.

Wichtig: Der Lernmodus und die normale Budget-Vorschlagslogik sind getrennt.

- Ohne Budget im gewählten Jahr: Lernmodus darf ein Startbudget vorschlagen.
- Mit Budget im gewählten Jahr: Lernmodus ist beendet, normale Vorschläge übernehmen.
- Ein Vorschlag ändert nichts automatisch.
- Beim Übernehmen musst du die Budgetart bestätigen.

Im Vorschlagsdialog kannst du einen Lernvorschlag per Rechtsklick steuern:

- **Weiter beobachten**: Vorschlag für den aktuellen Monat ausblenden.
- **Ignorieren**: Lernvorschlag für diese Kategorie beenden.
- **Als unregelmäßig / Rückstellung markieren**: gut für Franchise, Selbstbehalt, Reparaturen oder seltene Jahreskosten.
- **Lernstatus zurücksetzen**: Kategorie wieder normal lernen lassen.

Empfehlung: Bei schwankendem Einkommen eher vorsichtig budgetieren. Bei unregelmäßigen Kosten lieber einen Monats-Topf/Rückstellung verwenden statt eine starre Fixkostenbuchung.

In der Übersicht erkennst du neue Lernbudgets am Symbol **🆕**. Das unterscheidet Startbudgets klar von echten Defizit-Warnungen (**📉**) und Überschuss-/Senkungsvorschlägen (**📈**).

## 5.2 Jahreswechsel mit Lernmodus

Beim Kopieren eines Jahres prüft die App zusätzlich Kategorien, die im Quelljahr getrackt wurden, aber noch kein Budget hatten. Diese erscheinen als mögliche Startbudgets für das neue Jahr. Übernimm sie nur, wenn die Kategorie auch im neuen Jahr geplant werden soll.
