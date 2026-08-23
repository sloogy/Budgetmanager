## 3.0.4 – 23. August 2026

3.0.3 hat i18n, Black und mypy erfolgreich bestanden. Der Full-Release stoppte anschließend am Ruff-Gate: zwei neue Testdateien und der Runtime-Importblock waren nicht nach Ruff sortiert, außerdem verwendete die neue Sortierfunktion sieben Lambda-Zuweisungen, die die Projektregeln verbieten. 3.0.4 übernimmt dieselbe Fachlogik und normalisiert diese vier Dateien vor dem Tag mit der im Projekt gepinnten Ruff-Version, formatiert sie danach erneut mit Black und prüft beide Werkzeuge nochmals.

### Bankimport

- Mehrere CSV- und PDF-Dateien gemeinsam laden, suchen und sortieren.
- Durchsuchbares Tag-Dropdown und Tag-Erstellung direkt im Import.
- `Alle auswählen` / `Alle abwählen` sowie Umschalt-Auswahl und Strg+A wirken bei aktivem Filter nur auf sichtbare Zeilen.
- Versteckte Zeilen bleiben von Massenbearbeitung ausgeschlossen; manuelle Review-Änderungen bleiben beim Sortieren erhalten.

### Release-Härtung

- Die neue Bankimport-Sortierung besteht das i18n-Audit ohne neue hartcodierte deutsche UI-Texte.
- Die vier Feature-/Testdateien werden mit der gepinnten Ruff-Version korrigiert und danach mit der gepinnten Black-Version formatiert.
- Ruff und Black werden vor dem unveränderlichen Release-Tag nochmals explizit als Check ausgeführt.
- Release-Retries bauen bestehende Tags unverändert neu; fehlgeschlagene Full-Releases speichern die konkrete Actions-Run-ID in einem `.failed`-Marker.
