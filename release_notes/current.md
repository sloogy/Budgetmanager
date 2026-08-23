## 3.0.1 – 23. August 2026

Der Bankimport aus 3.0.0 wird für größere Kontoauszüge deutlich schneller und sicherer bedienbar. Fokus dieses Patch-Releases ist der Review: mehrere Dateien gemeinsam laden, gezielt filtern und sortieren, Tags direkt im Import pflegen und Massenaktionen strikt auf die sichtbaren Zeilen begrenzen.

### Bankimport

- **Mehrere CSV- und PDF-Dateien gleichzeitig laden.** Alle Buchungen können in einem gemeinsamen Review geprüft werden; Duplikat- und Marker-Identität bleibt trotzdem pro Quelldatei getrennt.
- **Globale Suche und Sortierung.** Datum, Betrag, Buchungstext, Typ, Kategorie, Tags, Status und Quelldatei sind durchsuchbar; sortiert werden kann unter anderem nach Datum, Betrag, Text, Kategorie, Tags und Quelldatei.
- **Tag-Dropdown mit Suche.** Vorhandene Tags sind alphabetisch sortiert und direkt im Dropdown filterbar. Kategorie-Pflicht-Tags bleiben gesperrt und können nicht versehentlich entfernt werden.
- **Tags direkt im Import erstellen.** Neue Tags können mit Name und optionalem Aktionstext angelegt werden; Duplikate werden verhindert und die Dropdowns anschließend ohne Verlust der bestehenden Auswahl aktualisiert.
- **Alle auswählen / Alle abwählen.** Die Aktion betrifft ausschließlich aktuell sichtbare und tatsächlich checkbare Importzeilen.
- **Filter-sichere Mehrfachauswahl.** Umschalt-Auswahl und Strg+A erfassen nur sichtbare Zeilen. Versteckte Treffer werden aktiv aus der Auswahl entfernt und zusätzlich von der Massenbearbeitung ausgeschlossen.
- **Manuelle Review-Änderungen bleiben beim Sortieren erhalten.** Typ, Kategorie, Tags und Import-Häkchen werden beim Umsortieren nicht zurückgesetzt.

### Sicherheit und Stabilität

- Positive TWINT-Eingänge bleiben weiterhin reine KI-/Erstattungssignale ohne Budgetbuchung.
- Mehrdatei-Importe werden pro Quelldatei atomar und idempotent verarbeitet.
- Neue Regressionstests decken Suche, Sortierung, Mehrdatei-Digests, Tag-Erstellung und sichtbarkeitsgebundene Massenbearbeitung ab.
