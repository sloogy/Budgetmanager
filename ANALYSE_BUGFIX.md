# Tiefenanalyse BudgetManager – priorisierte Issues

## KRITISCH

| Datei:Zeile | Schweregrad | Problem | Vorgeschlagener Fix |
|---|---|---|---|
| `views/tabs/budget_tab.py:1332`, `views/tabs/budget_tab.py:1366` | KRITISCH | Falsche Spaltenlogik im Bearbeitungsdialog: Monats-Spalten sind inzwischen `4..15`, der Code prüft aber `1..12` und übergibt `month=c` (Offset +3). Ergebnis: Okt–Dez nicht editierbar, Jan–Sep auf falschen Monat gemappt. | Monatsprüfung auf `4..15` ändern und `month = c - 3` verwenden. |
| `views/tabs/budget_tab.py:1754` | KRITISCH | `_copy_row_to_all_months()` liest `self.table.item(row, m)` mit `m=1..12` statt Monats-Spalten `m+3`. Dadurch werden Nicht-Monatszellen (Fix/Recurring/Tag) mitgelesen und Monatswerte verschoben. | Lesen auf `self.table.item(row, m + 3)` umstellen. |
| `views/tracker_dialog.py:130`, `views/tracker_dialog.py:138`, `views/tracker_dialog.py:172`, `views/tracker_dialog.py:176` | KRITISCH | Dialog arbeitet mit Anzeige-Text (`currentText`) als `typ` statt DB-Key. Kategorie-Queries und Rückgabe (`TrackingInput.typ`) sind damit sprachabhängig und in EN/FR inkonsistent zur DB. | ComboBox mit `userData=DB-Key` füllen, intern nur `currentData()` verwenden. |
| `views/tabs/tracking_tab.py:613`, `views/tabs/tracking_tab.py:838` | KRITISCH | `tracking_tab` speichert/updated `inp.typ` direkt aus `TrackerDialog`; bei nicht-deutscher UI landet Display-Text in `tracking.typ`. | Vor Persistenz immer auf DB-Key normalisieren (`db_typ_from_display`/`normalize_typ`). |
| `views/quick_add_dialog.py:114`, `views/quick_add_dialog.py:119`, `views/quick_add_dialog.py:156`, `views/quick_add_dialog.py:167` | KRITISCH | Gleiches Muster wie oben: Kategorieabfrage und Speichern laufen mit Display-`typ`. Führt zu leeren Kategorie-Listen und inkonsistenten Typwerten in der DB. | `typ_combo` mit DB-Keys im `userData`, überall `currentData()` nutzen. |
| `views/budget_entry_dialog.py:250`, `views/budget_entry_dialog.py:278`, `views/budget_entry_dialog.py:427` | KRITISCH | BudgetEntryDialog nutzt Display-`typ` für Kategorie-Queries und Request-Rückgabe. In nicht-deutschen Locales brechen Lookups/Zuordnungen. | Analog: `userData=DB-Key`, Rückgabe nur DB-Key. |
| `views/budget_entry_dialog_extended.py:596`, `views/budget_entry_dialog_extended.py:731` | KRITISCH | Extended-Dialog hat dieselbe typ-Display/DB-Key-Verwechslung. | `typ` intern auf DB-Key umstellen, nur Anzeige lokalisieren. |
| `views/category_properties_dialog.py:491`, `views/category_properties_dialog.py:525` | KRITISCH | Kategorie-Erstellung/-Rückgabe nutzt `currentText()` als Typ; kann falsche Typwerte schreiben. | Typ-Combo mit DB-Key-`userData`; Rückgabe via `currentData()`. |
| `views/recurring_transactions_dialog_extended.py:260`, `views/recurring_transactions_dialog_extended.py:371` | KRITISCH | Harte Typwerte `"Ausgaben", "Einnahmen"`; `"Einnahmen"` ist nicht DB-Standard (`"Einkommen"`). Daten driften semantisch auseinander. | Typen auf `TYP_*`/`normalize_typ` umstellen; Anzeige via `display_typ`. |
| `views/tabs/budget_tab.py:1809` | KRITISCH | Auto-Warnungen nutzen `abs(spent)` für alle Typen und `spent > budget`. Für Einkommen ist die Logik fachlich invertiert (Warnung bei “zu viel Einkommen”, nicht bei Zielverfehlung). | Typabhängige Regel mit `rest_sign()`/`is_income()` verwenden. |
| `model/budget_overview_model.py:144`, `model/budget_overview_model.py:153`, `model/budget_overview_model.py:159` | KRITISCH | `typ_db` wird berechnet, aber Queries laufen weiterhin mit `typ` (ggf. Display-String). i18n-abhängiger Datenabriss möglich. | In allen DB-Zugriffen konsequent `typ_db` verwenden. |

## WICHTIG

| Datei:Zeile | Schweregrad | Problem | Vorgeschlagener Fix |
|---|---|---|---|
| `views/category_manager_dialog.py:85`, `views/category_manager_dialog.py:295`, `views/category_manager_dialog.py:307` | WICHTIG | Filterlogik vergleicht harte Strings (`"Alle"`, `"Nur Fixkosten"`, `"Nur Wiederkehrend"`). Bei Übersetzung bricht Filterverhalten. | Filter über stabile `itemData`-Keys (`all/fix/rec`) statt Textvergleich. |
| `views/export_dialog.py:77`, `views/export_dialog.py:167` | WICHTIG | Sprachabhängiger Vergleich auf `"Alle Jahre"`; bei lokalisierter Anzeige kann `int(...)`-Parse fehlschlagen. | Combo mit `userData=None|year` belegen und auf `currentData()` prüfen. |
| `views/tabs/overview_kpi_panel.py:175` | WICHTIG | KPI-`balance` rechnet `income - expenses`, während andere Bereiche `income - expenses - savings` nutzen. Inkonsistente Finanzkennzahl zwischen Panels. | Einheitliche Bilanzdefinition zentralisieren und überall gleich anwenden. |
| `views/tabs/overview_tab.py:477` + `views/tabs/tracking_tab.py:261` | WICHTIG | Inkonsistente Kategoriequellen: Overview übergibt flache Namensliste ohne Typpräfix/Hierarchie, TrackingTab zeigt typpräfixte Tree-Labels. Unterschiedliches Filterergebnis je Panel. | Gemeinsame Kategorie-Provider-API (inkl. typ-sicherer IDs) für beide Panels verwenden. |
| `views/tabs/overview_right_panel.py:229`, `views/tabs/overview_right_panel.py:275`, `views/tabs/overview_right_panel.py:300` | WICHTIG | Kategorie-Filter arbeitet nur über sichtbaren Text; bei gleichnamigen Kategorien in mehreren Typen ist Filter ambig/uneindeutig. | Kategorie-Combo mit `userData=(typ,cat_id|cat_name)` und Filter anhand stabiler IDs. |
| `model/budget_warnings_model_extended.py:294` | WICHTIG | `_get_exceed_count()` zählt nur `spent >= budget` (100%) und ignoriert konfigurierten `threshold_percent`. Statistik passt nicht zur Warnschwelle. | Threshold in Zählung einbeziehen (`spent/budget*100 >= threshold`). |
| `model/budget_warnings_model_extended.py:233` | WICHTIG | Ein Warn-Eintrag wird auch ohne Schwellenüberschreitung gezeigt, sobald ein Suggestion-Wert existiert. Das mischt “Warnung” und “Vorschlag” fachlich. | Warnungen und Vorschläge separat ausweisen (zwei Listen/Sections). |
| `views/tabs/budget_tab.py:271` | WICHTIG | `_row_typ`-Fallback liefert `tr("kpi.expenses")` (Display), nicht DB-Key. Folgelogik (`cats.list`, `budget.set_amount`) kann dadurch sprachabhängig fehlschlagen. | Fallback immer auf `TYP_EXPENSES` setzen. |
| `views/tabs/overview_budget_panel.py:314` | WICHTIG | Tabular-Tree zeigt `typ` als DB-String in der UI statt lokalisierter Anzeige. | Für UI-Spalten `display_typ(typ)` verwenden; DB-Key intern behalten. |
| `views/tabs/overview_budget_panel.py:757` | WICHTIG | Panel instanziiert bei jedem Refresh eigenes `TrackingModel` statt den bereits vorhandenen Shared-Tracker zu nutzen (doppelte Query-Pfade). | `TrackingModel` vom Orchestrator injizieren und wiederverwenden. |

## MINOR

| Datei:Zeile | Schweregrad | Problem | Vorgeschlagener Fix |
|---|---|---|---|
| `views/tabs/budget_tab.py:1296` | MINOR | Fokus nach Speichern springt auf falsche Spalte (`month` statt `month+3`). | `setCurrentCell(r, month + 3)` verwenden. |
| `views/tabs/tracking_tab.py:233`, `:417`, `:463`, `:588`, `:617`, `:806`, `:842` | MINOR | Massive Methodenduplikate (`_current_filter_typ_db`, `_is_all_typ`, `set_recent_days`) deuten auf Merge-Artefakte; erhöht Fehlerrisiko. | Duplikate konsolidieren, einmal zentral definieren. |
| `views/tabs/budget_tab.py:1959`, `views/tabs/tracking_tab.py:56`, `:163`, `:167`, `:174`, `:176`, `:184`, `:186` | MINOR | Mehrere harte UI-Texte ohne `tr()` in Kern-Tabs. | Alle sichtbaren Strings auf i18n-Keys migrieren. |
| `views/type_color_helper.py:35`, `views/type_color_helper.py:41`, `views/type_color_helper.py:43` | MINOR | Spaltenerkennung stützt sich auf Literal-Header (`"typ"`) + harte Fallback-Indizes; fragil bei Spaltenumbau. | Spalten explizit über bekannte Rollen/konfigurierbare Indizes übergeben. |
| `utils/i18n.py:225`, `utils/i18n.py:227`, `utils/i18n.py:229` | MINOR | `db_typ_from_display()` kennt nur `typ.*`-Anzeigenamen; bei abweichenden Display-Strings (z. B. andere Label-Namespaces) kommt Raw-Text zurück. | Robustere Normalisierung über `normalize_typ()` + zentrale Typ-Registry. |
| `views/tabs/budget_tab.py:1622`, `views/tabs/budget_tab.py:1633`, `views/tabs/budget_tab.py:1792` | MINOR | Harte Status-/Info-Texte ("aktiviert/deaktiviert", Favoriten-Text) nicht lokalisiert. | auf `tr`/`trf` umstellen und Placeholders nutzen. |
| `views/quick_add_dialog.py:163` | MINOR | `month_names` ist gemischt hartkodiert/lokalisiert; inkonsistente Sprache in Auto-Details. | Monatstexte vollständig über `tr("month.X")` erzeugen. |

