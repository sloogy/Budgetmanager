# _attic — Toter Code (nicht in der App verwendet)

Diese Module wurden in v1.0.29 hierher verschoben, weil sie **nirgends importiert**
werden (verifiziert per AST-Analyse des gesamten Projekts) und teilweise
**irreführende Sackgassen** enthalten:

| Datei | Problem |
|---|---|
| `views/recurring_transactions_dialog_extended.py` | `_book_selected()` meldet "Buchung erfolgreich", **bucht aber nichts** — der eigentliche Insert ist nur als Kommentar vorhanden. Der produktive Pfad ist `views/tabs/tracking_tab.py` → `RecurringBookingsDialog`. |
| `views/fixcost_check_dialog.py` | Nicht verwendet. Produktiv: `tracking_tab.add_fixcosts()` + `MissingBookingsDialog`. |
| `model/fixcost_check_model.py` | Nicht verwendet. Öffnet zudem eigene `sqlite3.connect(db_path)`-Verbindungen, die im verschlüsselten Modus (In-Memory-DB) ins Leere greifen würden. |
| `model/budget_warnings_model.py` | Ersetzt durch `budget_warnings_model_extended.py` (das produktiv genutzte Modell). |
| `views/appearance_profiles_dialog.py` | Nicht verwendet; enthält außerdem hartkodierte deutsche Strings. Produktiv: `theme_editor_dialog.py`. |
| `views/theme_profiles_dialog.py` | Nicht verwendet. Produktiv: `theme_editor_dialog.py`. |

Wiederverwendung nur nach Reparatur der genannten Probleme.
