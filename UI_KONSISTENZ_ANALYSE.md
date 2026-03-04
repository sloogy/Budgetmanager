# UI-Konsistenz Tiefenanalyse — Budgetmanager

**Datum:** 2026-02-16  
**Scope:** 34 View-Dateien, 18.652 Zeilen Code  
**Schweregrad:** 🔴 Kritisch | 🟠 Mittel | 🟡 Kosmetisch

---

## Zusammenfassung

| Kategorie | 🔴 | 🟠 | 🟡 | Gesamt |
|---|---|---|---|---|
| Hardcoded Farben (Theme-Bruch) | 3 | 4 | 2 | 9 |
| API/Enum Inkonsistenzen | 1 | 2 | 1 | 4 |
| Shortcut-Kollisionen | 2 | 0 | 0 | 2 |
| Fehlende Tabellen-Features | 0 | 1 | 1 | 2 |
| MessageBox-Inkonsistenzen | 0 | 1 | 1 | 2 |
| Geldformatierung | 0 | 1 | 0 | 1 |
| Titel-Inkonsistenzen | 0 | 0 | 1 | 1 |
| Font-Hardcoding | 0 | 1 | 0 | 1 |
| Silent Exception Handling | 0 | 1 | 0 | 1 |
| Architektur (conn in Views) | 0 | 1 | 0 | 1 |
| **Gesamt** | **6** | **12** | **6** | **24** |

---

## 🔴 KRITISCH (6 Befunde)

### K1 — Shortcut-Kollision: Ctrl+E doppelt belegt

**Dateien:** `main_window.py` Z.489 + Z.946  
**Problem:** `Ctrl+E` ist gleichzeitig für **Export** (Menü „Extras") und **Budget-Zeile bearbeiten** (Budget-Tab-Kontextmenü) definiert.

```
Z.489:  export_action.setShortcut("Ctrl+E")
Z.946:  edit_action.setShortcut("Ctrl+E")
```

**Auswirkung:** Je nach Fokus wird die falsche Aktion ausgelöst. Im Budget-Tab kann Export statt Edit passieren.

**Fix:** Edit → `Ctrl+Return` oder `F2`; Export bleibt `Ctrl+E`.

---

### K2 — Shortcut-Kollision: Ctrl+N doppelt belegt

**Dateien:** `main_window.py` Z.434 + Z.939  
**Problem:** `Ctrl+N` ist gleichzeitig für **Schnelleingabe** (global) und **Budget-Zeile hinzufügen** (Budget-Tab) definiert.

```
Z.434:  quick_add_action.setShortcut("Ctrl+N")
Z.939:  add_action.setShortcut("Ctrl+N")
```

**Auswirkung:** Schnelleingabe-Dialog öffnet sich statt neue Budgetzeile.

**Fix:** Budget-Tab Add → `Ctrl+Shift+N` oder `Insert`.

---

### K3 — overview_tab.py: 86 hardcoded Farbreferenzen ohne Theme-Anbindung

**Datei:** `views/tabs/overview_tab.py` (2847 Zeilen)  
**Problem:** Der Overview-Tab hat **keinen Zugriff auf `theme_manager`** und verwendet durchgehend hardcoded Farben. Bei Theme-Wechsel (z.B. Dunkel-Modus) bleiben alle Farben auf Hell-Modus-Werte.

**Betroffene Bereiche:**
- CompactKPICard: `#2196F3`, `#27ae60`, `#e74c3c` (Z.75, 553-555)
- Donut-Chart Farbpalette: 10 hardcoded Farben (Z.211)
- Budget-Warnungen Rot/Grün: `#e74c3c` / `#27ae60` (Z.1665, 1747, 1853, 1976)
- Budget-Tabelle Typ-Farben: Lokales Dict statt Theme (Z.2373-2376)
- Drilldown ProgressBar: `#ccc`, `#f0f0f0` Border/Background (Z.170-175)
- Balance-Farbe: `#27ae60` / `#e74c3c` (Z.1853)
- Savings-Items: `#27ae60`, `#2196F3` (Z.2737, 2786)
- Explain-Label: `#555` (Z.694)

**Auswirkung:** Im Dunkel-Modus sind große Teile des Overview-Tabs unleserlich oder unsichtbar.

**Fix:** `theme_manager`-Zugriff über `self.window()` analog zu `tracking_tab.py` / `budget_tab.py`. Alle Farben über `get_type_colors()`, `get_negative_color()`, `get_severity_color()` beziehen.

---

### K4 — budget_tab.py: Saldo-Farben ignorieren Theme

**Datei:** `views/tabs/budget_tab.py` Z.518-547  
**Problem:** Die Saldo-Zeile (Einnahmen − Ausgaben − Ersparnisse) verwendet hardcoded Farben:
```python
QColor("#e74c3c")   # negativ
QColor("#27ae60")   # positiv  
QColor("#95a5a6")   # neutral
```
Obwohl der Tab `_get_type_color_map()` hat und den Theme-Manager kennt, werden diese Methoden für die Saldo-Zeilen **nicht** genutzt.

**Auswirkung:** Saldo-Farben stimmen nicht mit Typ-Farben aus Theme überein.

**Fix:** `self._typ_color()` bzw. `theme_manager.get_negative_color()` verwenden.

---

### K5 — category_manager_dialog.py: Hardcoded Hintergrundfarben für Kategorie-Status

**Datei:** `views/category_manager_dialog.py` Z.262-266  
**Problem:** Fixkosten/Wiederkehrende-Markierungen verwenden RGB-Werte ohne Theme:
```python
QColor(255, 235, 200)  # Orange-ish (Fix + Recurring)
QColor(255, 230, 230)  # Light red (nur Fix)
QColor(230, 255, 230)  # Light green (nur Recurring)
```

**Auswirkung:** Im Dunkel-Modus sind diese Pastellfarben auf dunklem Hintergrund kaum sichtbar.

---

### K6 — budget_adjustment_dialog.py: 14 hardcoded QColor-Referenzen

**Datei:** `views/budget_adjustment_dialog.py` Z.183-240  
**Problem:** Jede Zelle erhält individuelle hardcoded Farben:
```python
QColor("#ffebee")   # Hintergrund Rot
QColor("#d32f2f")   # Text Rot
QColor("#ffcdd2")   # Hintergrund Dunkelrot
QColor("#b71c1c")   # Text Dunkelrot
QColor("#e8f5e9")   # Hintergrund Grün
QColor("#2e7d32")   # Text Grün
QColor("#757575")   # Text Grau
```

**Auswirkung:** Dialog ist im Dunkel-Modus komplett unleserlich.

---

## 🟠 MITTEL (12 Befunde)

### M1 — Enum-Style Wildwuchs bei Qt-Enums

**Problem:** 3 verschiedene Schreibweisen für identische Enums:
```python
# Stil A: Kurz (PySide6-kompatibel, aber deprecated-Warnung möglich)
QAbstractItemView.SelectRows
QAbstractItemView.NoEditTriggers

# Stil B: Voll qualifiziert (korrekt für PySide6)
QAbstractItemView.SelectionBehavior.SelectRows
QAbstractItemView.EditTrigger.NoEditTriggers

# Stil C: Via Widget-Klasse (funktioniert, aber inkonsistent)
QTableWidget.SelectRows
QTableWidget.NoEditTriggers
```

**Vorkommen:**
| Stil | SelectRows | NoEditTriggers |
|---|---|---|
| A (kurz) | 7× | 5× |
| B (voll) | 3× | 1× |
| C (Widget) | 2× | 1× |

**Fix:** Einheitlich Stil A verwenden (funktioniert in PySide6, kürzester Code).

---

### M2 — 8 Tabellen ohne `verticalHeader().setVisible(False)`

**Problem:** Sichtbare Zeilennummern-Spalte bei Tabellen, die sie nicht brauchen:

| Dialog | verticalHeader hidden |
|---|---|
| favorites_dashboard_dialog.py | ❌ |
| shortcuts_dialog.py | ❌ |
| budget_adjustment_dialog.py | ❌ |
| missing_bookings_dialog.py | ❌ |
| global_search_dialog.py | ❌ |
| recurring_bookings_dialog.py | ❌ |
| tracking_tab.py | ❌ |
| budget_tab.py | ❌ (gewollt für Zeilennr.) |

**Fix:** `verticalHeader().setVisible(False)` in allen 7 Dialogen (Budget-Tab absichtlich ausgenommen).

---

### M3 — Manuelle Geldformatierung statt `format_money()`

**Dateien:** `budget_adjustment_dialog.py` Z.188-237, `savings_goals_dialog.py` Z.211-255  
**Problem:** 10 Stellen verwenden manuelles Format:
```python
f"{exc.budget:,.2f}".replace(",", "'")
```
statt der zentralen Funktion:
```python
format_money(exc.budget)
```

**Auswirkung:** Bei Währungswechsel (z.B. EUR statt CHF) werden Tausendertrennzeichen und Symbol nicht angepasst.

---

### M4 — recurring_bookings_dialog.py: Buchen-Button komplett hardcoded

**Datei:** Z.197-206  
**Problem:** Der „Buchen"-Button hat ein komplett eigenes StyleSheet mit eigenen Farben und Hover-Effekt:
```python
background-color: #4CAF50;
color: white;
...
background-color: #45a049;  # hover
```
Dies überschreibt das globale Theme komplett.

---

### M5 — login_dialog.py: 22 hardcoded Farb-Referenzen

**Datei:** 789 Zeilen mit 22 individuellen Farb-Setzungen  
**Problem:** Status-Labels, Buttons, Trennlinien, Info-Texte — alles hardcoded:
- `#888` — Status-Text  
- `#a00` — Fehler-Text  
- `#ddd` — Trennlinien  
- `#2196F3` — Link-Buttons  
- `#e67e22` — Restore-Buttons  
- `#666`, `#999`, `#555` — verschiedene Grautöne

**Auswirkung:** Login-Dialog sieht im Dunkel-Modus kaputt aus.

---

### M6 — account_management_dialog.py: 15 hardcoded Farb-Referenzen

**Datei:** 744 Zeilen  
**Betroffene Elemente:**
- `#888` — Statustext (Z.67, 111)
- `#fff3cd` — Info-Box Hintergrund (Z.172)
- `#a00` — Fehlertext (Z.183)
- `#ddd` — Trennlinien (Z.663)
- `#27ae60` — Erfolg-Header (Z.678)

---

### M7 — Hardcoded `font-size` an 25+ Stellen

**Problem:** Font-Größen werden in Pixel/Punkt hardcoded statt relativ zum Theme `schriftgroesse`:
```python
# Beispiele:
"font-size: 16px;"        # overview_tab KPI icon
"font-size: 14px;"        # category_manager
"font-size: 13px;"        # account_management (6×)
"font-size: 12px;"        # budget_adjustment
"font-size: 11px;"        # login_dialog (5×)
font.setPointSize(15)     # account_management header
font.setPointSize(14)     # overview_tab KPI value
font.setPointSize(12)     # overview_tab chart
font.setPointSize(11)     # budget_tab
font.setPointSize(9)      # overview_tab KPI title
```

**Auswirkung:** Bei Änderung der Theme-Schriftgröße bleiben diese Elemente unverändert, was zu visuellen Inkonsistenzen führt.

---

### M8 — Silent Exception Handling: 25+ blanke `except Exception:`

**Problem:** 25+ Stellen in Views fangen Exceptions ohne Logging:
```python
except Exception:    # ← Kein logging, kein pass-Kommentar
```

**Top-Dateien:**
| Datei | Blanke Excepts |
|---|---|
| main_window.py | 11 |
| budget_entry_dialog_extended.py | 1 |
| budget_adjustment_dialog.py | 4 |
| account_management_dialog.py | 2 |
| favorites_dashboard_dialog.py | 2 |

**Fix:** Mindestens `logger.debug()` in jedem except-Block.

---

### M9 — Direkte SQL-Queries in Views (MVC-Verletzung)

**Problem:** 15+ direkte `conn.execute()` Aufrufe in View-Dateien statt über Model-Schicht:

| Datei | Direkte SQL |
|---|---|
| overview_tab.py | 2 (Budget-Summen) |
| main_window.py | 6 (DB-Info Dialog) |
| setup_assistant_dialog.py | 5 (Count + Delete) |
| budget_adjustment_dialog.py | 3 (Income/Expense Query) |
| backup_restore_dialog.py | 2 (DELETE FROM) |
| tracker_dialog.py | 1 |

**Auswirkung:** Doppelte SQL-Logik, schwere Wartbarkeit, Risiko bei DB-Schema-Änderungen.

---

### M10 — savings_goals_dialog.py: Hardcoded `#e3f2fd` Info-Box

**Datei:** Z.99  
```python
info.setStyleSheet("padding: 8px; background-color: #e3f2fd; border-radius: 5px; font-size: 11px;")
```
**Auswirkung:** Hellblauer Hintergrund im Dunkel-Modus.

---

### M11 — database_management_dialog.py: Roter Reset-Button hardcoded

**Datei:** Z.92, 115-123  
```python
reset_warning.setStyleSheet("color: #e74c3c;")
reset_btn.setStyleSheet("""
    background-color: #e74c3c; color: white;
    ...hover: background-color: #c0392b;
""")
```

---

### M12 — global_search_dialog.py: Farben als QColor-Literale

**Datei:** Z.124, 142  
```python
QColor(100, 150, 255)   # Budget-Treffer
QColor(255, 180, 100)   # Tracking-Treffer
```
Keine Theme-Anbindung für Suchergebnis-Highlighting.

---

## 🟡 KOSMETISCH (6 Befunde)

### L1 — Window-Titel: Inkonsistente Emoji-Nutzung

**Befund:** 11 Dialoge MIT Emoji-Prefix, 20 OHNE.

| Mit Emoji ✅ | Ohne Emoji ❌ |
|---|---|
| ⚡ Schnelleingabe | Budget-Anpassungsvorschläge |
| 📁 Kategorien-Manager | Budget erfassen / bearbeiten |
| 👤 Kontoverwaltung | Theme-Editor |
| 🔍 Globale Suche | Backup & Wiederherstellung |
| ⬆️ Updates | Sparziele |
| ⌨️ Tastenkürzel | Datenbank-Verwaltung |
| 📤 Daten exportieren | Benutzer erstellen |
| 💰 Budget ausfüllen | Budget-Jahr kopieren |
| 🧭 Setup-Assistent | Fixkosten / Wdh. Buchungen |
| ⭐ Favoriten-Dashboard | Kategorie bearbeiten |
| 🔑 Restore-Key | Neue Kategorie erstellen |

**Fix:** Entweder alle OHNE Emoji (professioneller) oder alle MIT Emoji (konsistenter).

---

### L2 — MessageBox Titel: „Fehler" als warning statt critical

**Problem:** 15 Stellen verwenden `QMessageBox.warning()` mit Titel „Fehler". Semantisch wäre bei echten Fehlern `QMessageBox.critical()` korrekt.

**Regel:**
- `warning` → Titel: „Hinweis" oder „Warnung" (Validierung, fehlende Eingabe)
- `critical` → Titel: „Fehler" (Exception, Datenbankfehler)
- `information` → Titel: „Info" oder „Erfolg"

---

### L3 — ProgressBar: Hardcoded Border im Dunkel-Modus

**Datei:** `overview_tab.py` Z.170-175  
```css
border: 1px solid #ccc;
background: #f0f0f0;
```
Im Dunkel-Modus sieht der Progress-Bar-Rahmen deplatziert aus.

---

### L4 — Donut-Chart: Statische 10-Farben-Palette

**Datei:** `overview_tab.py` Z.211  
```python
colors = ["#3498db", "#e74c3c", "#27ae60", "#f39c12", "#9b59b6",
          "#1abc9c", "#e67e22", "#34495e", "#16a085", "#c0392b"]
```
Keine Anpassung an Theme. Bei >10 Kategorien Farben-Recycling.

---

### L5 — Fehlende Accessibility

**Befund:** 0 `setAccessibleName()` / `setAccessibleDescription()` Aufrufe.  
**Auswirkung:** Screenreader können Dialoge und Widgets nicht beschreiben.

---

### L6 — Spacing/Margin: Keine einheitlichen Werte

**Problem:** Verschiedene Dialoge verwenden unterschiedliche Abstände:
- `(20, 15, 20, 15)` — AccountManagement
- `(15, 15, 15, 15)` — AccountManagement Sections
- `(10, 6, 10, 6)` — KPI-Cards
- `(8, 8, 8, 8)` — Overview Content
- `(0, 0, 0, 0)` — Diverse Sub-Layouts
- Spacing: 2, 8, 10, 12 gemischt

---

## Priorisierte Fix-Reihenfolge

### Phase 1 — Sofort (Funktionale Bugs)
1. **K1** Shortcut Ctrl+E Kollision → Export auf `Ctrl+Shift+E`
2. **K2** Shortcut Ctrl+N Kollision → Budget-Add auf `Insert`

### Phase 2 — Theme-Konsistenz (Dunkel-Modus-Fähigkeit)
3. **K3** overview_tab.py Theme-Anbindung (86 Farbreferenzen)
4. **K4** budget_tab.py Saldo-Farben Theme-fähig
5. **K5** category_manager.py Status-Farben Theme-fähig
6. **K6** budget_adjustment_dialog.py Farben Theme-fähig
7. **M4** recurring_bookings Buchen-Button
8. **M5** login_dialog.py Farben
9. **M6** account_management Farben
10. **M10** savings_goals Info-Box
11. **M11** database_management Reset-Button
12. **M12** global_search Farben

### Phase 3 — Code-Qualität
13. **M1** Enum-Style vereinheitlichen
14. **M2** verticalHeader in 7 Tabellen
15. **M3** format_money() konsistent nutzen
16. **M7** Font-Size relative Berechnung
17. **M8** Silent Exception → Logger
18. **M9** SQL aus Views in Models verschieben

### Phase 4 — Polish
19. **L1** Window-Titel Emoji-Konvention
20. **L2** MessageBox Typ/Titel Konsistenz
21. **L3-L6** Kosmetische Korrekturen

---

## Empfehlung: Theme-Helper-Utility

Um die Phase 2 effizient umzusetzen, empfiehlt sich ein zentraler **UI-Color-Helper**:

```python
# views/ui_colors.py
def get_theme_colors(widget) -> dict:
    """Holt Farben aus dem Theme-Manager via Widget-Hierarchy."""
    main = widget.window()
    tm = getattr(main, 'theme_manager', None)
    if tm:
        return {
            "type_colors": tm.get_type_colors(),
            "negative": tm.get_negative_color(),
            "ok": tm.get_severity_color("ok"),
            "warning": tm.get_severity_color("warning"),
            "danger": tm.get_severity_color("danger"),
            "text": tm.get_current_profile().get("text", "#111"),
            "text_dim": tm.get_current_profile().get("text_gedimmt", "#666"),
            "bg_panel": tm.get_current_profile().get("hintergrund_panel", "#f6f7f9"),
        }
    # Fallback
    return { ... }
```

Damit können alle Views mit einer einzigen Zeile Theme-Farben beziehen, ohne den Theme-Manager direkt kennen zu müssen.
