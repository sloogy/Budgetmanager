Loaded cached credentials.
I will search for `budget_tab.py` to confirm its location and examine its current implementation of cell editing, amount formatting, and total calculation.

I will read the `budget_tab.py` file to understand its current logic for cell editing, amount formatting, and total calculation, and also check the version files to prepare for the update.

I will check the `VERSION_INFO.txt` and `version.json` files to see how the version is tracked and where to update it to `v1.0.16`.

I will read both `version.json` and `VERSION_INFO.txt` to determine which one needs to be updated to `v1.0.16`.

I will read the `VERSION_INFO.txt` file to confirm if the version is already set to `1.0.16` or if it needs updating.

I will read the `utils/money.py` file to see if there are existing formatting functions that I should use instead of or to improve `fmt_amount`.

I will read the `locales/de.json` file to check the value of `budget.parent.marker` and other related i18n keys.

Hier ist der Plan und die i18n-Checkliste für die Anpassungen in `budget_tab.py`.

### Plan

1.  **`fmt_amount(0)` Fix**:
    *   In `views/tabs/budget_tab.py` die Funktion `fmt_amount(val)` anpassen, sodass sie bei `0` den String `"0.00"` zurückgibt (statt `""`), um die Konsistenz in der Tabelle zu wahren.
2.  **Parent-Zellen READ-ONLY**:
    *   In der `load()`-Methode von `BudgetTab` für alle Parent-Zeilen (`has_children=True`) die Flags der Monats-Zellen (Spalten 4–15) auf `Qt.ItemIsEnabled | Qt.ItemIsSelectable` setzen (Entfernen von `Qt.ItemIsEditable`).
3.  **Anzeige `total = puffer + kinder`**:
    *   In der `load()`-Schleife für Parent-Zellen den Zellentext von `{total}+` auf `{puffer} + {kinder}` ändern.
    *   Dabei `fmt_amount` nutzen, um sicherzustellen, dass auch `0.00` angezeigt wird.
4.  **Version Bump**:
    *   `VERSION_INFO.txt` um den Block für `v1.0.16` ergänzen (in `version.json` bereits vorhanden).
5.  **Validierung**:
    *   Manuelle Prüfung: Sind Parent-Zellen schreibgeschützt? Erscheint die Formel korrekt? Werden Nullwerte als `0.00` angezeigt?
    *   `python ai/i18n_check.py` zur Synchronitätsprüfung ausführen.

### i18n-Checkliste

- [ ] **Tausender-Trenner/Dezimalpunkt**: Sicherstellen, dass `fmt_amount` dem Schweizer Stil (`1'234.56`) entspricht oder einheitlich `f"{val:.2f}"` nutzt (Projekt-Standard).
- [ ] **Formel-Separator**: Das Trennzeichen ` + ` als festen Bestandteil der Anzeige verifizieren (identisch für de/en/fr).
- [ ] **Tooltips**: Prüfen, ob die Tooltips (`budget.tooltip.puffer`, `budget.tooltip.children_sum`) weiterhin korrekt übersetzt und passend zur neuen Anzeige sind.
- [ ] **Key-Sync**: Mit `ai/i18n_check.py` sicherstellen, dass keine neuen Keys in `de.json` fehlen, falls Texte angepasst wurden.
