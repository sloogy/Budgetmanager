# BudgetManager 2.1.1 – Benutzeranleitung

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

Im Tracking erfasst du echte Geldbewegungen. Die Kategorieauswahl zeigt nur Kategorien des gewählten Typs. Favoriten und häufig manuell genutzte Kategorien erscheinen oben, automatische Fixkosten verzerren diese Reihenfolge nicht.

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

- **Übersicht / Donut**: zeigt die Verteilung nach Konto oder Kategorie. Bei Zeitraumfiltern wird das Budget über alle betroffenen Monate summiert.
- **Kategorien**: zeigt, welche Kategorien den größten Anteil ausmachen.
- **Verteilung**: zeigt Einnahmen, Ausgaben und Ersparnisse im Verhältnis.
- **Monatsverlauf**: zeigt die Entwicklung über Monate. Gut, um Trends zu erkennen.
- **Monatsbilanz**: zeigt Einnahmen minus Ausgaben und Sparen pro Monat.
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
