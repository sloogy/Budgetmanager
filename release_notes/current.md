## 3.0.3 – 23. August 2026

3.0.2 hat den i18n-Fehler aus 3.0.1 erfolgreich behoben und das Übersetzungs-Audit bestanden. Der Full-Release stoppte danach am nächsten Gate: Die beiden neuen Bankimport-Dateien waren nicht mit der im Projekt gepinnten Black-Version 25.1.0 formatiert. 3.0.3 übernimmt die Bankimport-Verbesserungen mit identischer Fachlogik und formatiert diese Dateien vor dem unveränderlichen Release-Tag mit genau der CI-Version.

### Bankimport

- Mehrere CSV- und PDF-Dateien können gemeinsam geladen und geprüft werden; Duplikat- und Marker-Identität bleibt pro Quelldatei getrennt.
- Globale Suche und sichere Sortierung nach Datum, Betrag, Buchungstext, Kategorie, Tags und Quelldatei.
- Durchsuchbares Tag-Dropdown sowie Tag-Erstellung direkt im Import.
- `Alle auswählen` / `Alle abwählen`, Umschalt-Auswahl und Strg+A wirken bei aktivem Filter ausschließlich auf sichtbare Zeilen.
- Versteckte Zeilen sind zusätzlich von der Massenbearbeitung ausgeschlossen; manuelle Review-Änderungen bleiben beim Sortieren erhalten.

### Release-Härtung

- Die Sortierbeschriftungen bestehen das i18n-Audit ohne neue hartcodierte deutsche UI-Texte.
- `views/bank_import_dialog.py` und `views/bank_import_dialog_runtime.py` werden für den Release mit der projektweit gepinnten Black-Version formatiert und anschließend nochmals mit `--check` geprüft.
- Release-Retries mit `-rN` bauen existierende unveränderliche Tags neu, statt sie zu verschieben.
- Fehlgeschlagene Full-Releases hinterlassen einen `.failed`-Marker mit der konkreten GitHub-Actions-Run-ID; erfolgreiche Läufe einen `.ok`-Marker.
