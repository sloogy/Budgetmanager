## 3.0.2 – 23. August 2026

3.0.1 wurde korrekt und unveränderlich getaggt, der Full-Release brach jedoch vor dem eigentlichen Build am i18n-Audit ab. Dieses Patch-Release übernimmt dieselben Bankimport-Verbesserungen und behebt die dabei gefundenen Release-Gates, ohne den fehlerhaften 3.0.1-Tag nachträglich zu verschieben.

### Bankimport

- **Mehrere CSV- und PDF-Dateien gleichzeitig laden.** Alle Buchungen können in einem gemeinsamen Review geprüft werden; Duplikat- und Marker-Identität bleibt trotzdem pro Quelldatei getrennt.
- **Globale Suche und Sortierung.** Datum, Betrag, Buchungstext, Typ, Kategorie, Tags, Status und Quelldatei sind durchsuchbar; sortiert werden kann unter anderem nach Datum, Betrag, Text, Kategorie, Tags und Quelldatei.
- **Tag-Dropdown mit Suche.** Vorhandene Tags sind alphabetisch sortiert und direkt im Dropdown filterbar. Kategorie-Pflicht-Tags bleiben gesperrt und können nicht versehentlich entfernt werden.
- **Tags direkt im Import erstellen.** Neue Tags können mit Name und optionalem Aktionstext angelegt werden; Duplikate werden verhindert und die Dropdowns anschließend ohne Verlust der bestehenden Auswahl aktualisiert.
- **Alle auswählen / Alle abwählen.** Die Aktion betrifft ausschließlich aktuell sichtbare und tatsächlich checkbare Importzeilen.
- **Filter-sichere Mehrfachauswahl.** Umschalt-Auswahl und Strg+A erfassen nur sichtbare Zeilen. Versteckte Treffer werden aktiv aus der Auswahl entfernt und zusätzlich von der Massenbearbeitung ausgeschlossen.
- **Manuelle Review-Änderungen bleiben beim Sortieren erhalten.** Typ, Kategorie, Tags und Import-Häkchen werden beim Umsortieren nicht zurückgesetzt.

### Release-Härtung

- Die zehn neuen Sortierbeschriftungen verwenden keine neu hartcodierten deutschen UI-Texte mehr. Übersetzte vorhandene Feldbezeichnungen werden mit sprachneutralen Sortierpfeilen kombiniert.
- Der Release-Retry mit `-rN` baut jetzt den bereits existierenden unveränderlichen Tag erneut, statt einen neuen Release-Commit zu erzeugen und anschließend am Tag-Sicherheitscheck zu scheitern.
- Fehlgeschlagene Full-Releases hinterlassen künftig einen `.failed`-Status mit der konkreten GitHub-Actions-Run-ID; erfolgreiche Läufe weiterhin einen `.ok`-Status.
- Positive TWINT-Eingänge bleiben reine KI-/Erstattungssignale ohne Budgetbuchung; Mehrdatei-Importe bleiben pro Quelldatei atomar und idempotent.
