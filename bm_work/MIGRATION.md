# 🔄 Migration von v2.3.0.0 zu v2.3.0.1

## Übersicht

Diese Anleitung hilft dir, von Version 2.3.0.0 auf 2.3.0.1 zu aktualisieren und die neuen Features zu integrieren.

---

## 📦 Was ist neu?

### Neue Dateien (Müssen hinzugefügt werden)
1. `model/database_management_model.py` - Database-Management mit Reset
2. `views/database_management_dialog.py` - UI für Database-Management
3. `views/fixcost_check_dialog_extended.py` - Erweiterter Fixkosten-Dialog
4. `FEATURES.md` - Vollständige Dokumentation
5. `CHANGELOG.md` - Versionshistorie

### Geänderte Dateien (Müssen ersetzt werden)
1. `model/budget_model.py` - Mit BUDGET-SALDO-Schutz
2. `README.md` - Aktualisiert

---

## 🚀 Schnell-Migration (5 Minuten)

### Schritt 1: Backup erstellen ⚠️
```bash
# WICHTIG: Backup ZUERST!
cp budgetmanager.db budgetmanager.db.backup_$(date +%Y%m%d_%H%M%S)
```

### Schritt 2: Neue Dateien kopieren
```bash
# Modelle
cp model/budget_model.py ../Budgetmanager_v0_2_3_0_0/model/
cp model/database_management_model.py ../Budgetmanager_v0_2_3_0_0/model/

# Views/Dialoge
cp views/database_management_dialog.py ../Budgetmanager_v0_2_3_0_0/views/
cp views/fixcost_check_dialog_extended.py ../Budgetmanager_v0_2_3_0_0/views/

# Dokumentation
cp README.md ../Budgetmanager_v0_2_3_0_0/
cp FEATURES.md ../Budgetmanager_v0_2_3_0_0/
cp CHANGELOG.md ../Budgetmanager_v0_2_3_0_0/
```

### Schritt 3: Main-Window Integration
Öffne `views/main_window.py` und füge hinzu:

```python
# Import hinzufügen (oben bei anderen Imports)
from views.database_management_dialog import DatabaseManagementDialog
from views.fixcost_check_dialog_extended import FixcostCheckDialog

# Im __init__ oder setup_menu Methode:
def setup_menu(self):
    # ... existing code ...
    
    # Extras-Menü erweitern
    extras_menu = self.menuBar().addMenu("Extras")
    
    # Database-Management hinzufügen
    db_mgmt_action = extras_menu.addAction("🗄️ Datenbank-Verwaltung")
    db_mgmt_action.triggered.connect(self.open_database_management)
    
    # Fixkosten-Check ersetzen/erweitern
    fixcost_action = extras_menu.addAction("💰 Fixkosten-Prüfung (erweitert)")
    fixcost_action.triggered.connect(self.open_fixcost_check_extended)

def open_database_management(self):
    """Öffnet Database-Management-Dialog."""
    dialog = DatabaseManagementDialog(self.db_path, self)
    dialog.exec()

def open_fixcost_check_extended(self):
    """Öffnet erweiterten Fixkosten-Check-Dialog."""
    dialog = FixcostCheckDialog(self.db_path, self)
    dialog.bookings_created.connect(self.refresh_all_tabs)
    dialog.exec()
```

### Schritt 4: Starten und Testen
```bash
python main.py
```

Die Anwendung führt automatisch eine Bereinigung durch beim ersten Start!

---

## 🔍 Detaillierte Integration

### 1. Budget-Modell aktualisieren

**Datei**: `model/budget_model.py`

**Änderungen**:
- Neue Konstante: `RESERVED_CATEGORY_NAMES`
- Neue Methode: `_is_reserved_category()`
- Neue Methode: `_cleanup_reserved_categories()`
- Neue Methode: `validate_database_integrity()`
- Geändert: `set_value()` - Mit Validierung
- Geändert: `get_matrix()` - Mit Filterung
- Geändert: Alle Methoden filtern jetzt reservierte Kategorien

**Rückwärtskompatibel**: ✅ Ja, alle bestehenden Methoden funktionieren weiter

### 2. Database-Management hinzufügen

**Neue Datei**: `model/database_management_model.py`

**Features**:
- `DatabaseManagementModel` Klasse
- Backup-Verwaltung
- Reset-Funktionalität
- Bereinigung
- Statistiken
- SQL-Export

**Integration in Main-Window**:
```python
# Menü-Eintrag
db_mgmt_action = QAction("🗄️ Datenbank-Verwaltung", self)
db_mgmt_action.triggered.connect(self.open_database_management)
extras_menu.addAction(db_mgmt_action)

# Handler-Methode
def open_database_management(self):
    from views.database_management_dialog import DatabaseManagementDialog
    dialog = DatabaseManagementDialog(self.db_path, self)
    dialog.exec()
    # Optional: Refresh nach Änderungen
    self.refresh_all_tabs()
```

### 3. Erweiterten Fixkosten-Check hinzufügen

**Neue Datei**: `views/fixcost_check_dialog_extended.py`

**Features**:
- Monatliche Prüfung
- Status-Übersicht
- Schätzung aus Historie
- Batch-Buchung
- Signal `bookings_created`

**Integration in Main-Window**:
```python
# Menü-Eintrag
fixcost_action = QAction("💰 Fixkosten-Prüfung", self)
fixcost_action.triggered.connect(self.open_fixcost_check)
extras_menu.addAction(fixcost_action)

# Handler-Methode
def open_fixcost_check(self):
    from views.fixcost_check_dialog_extended import FixcostCheckDialog
    dialog = FixcostCheckDialog(self.db_path, self)
    # Signal für Aktualisierung nach Buchungen
    dialog.bookings_created.connect(self.refresh_tracking_tab)
    dialog.exec()
```

---

## ⚙️ Konfiguration

### Optional: Startup-Check für BUDGET-SALDO

In `main.py` nach Datenbank-Initialisierung hinzufügen:

```python
def cleanup_database_on_startup(db_path: str):
    """Führt automatische Bereinigung beim Start durch."""
    try:
        from model.budget_model import BudgetModel
        import sqlite3
        
        conn = sqlite3.connect(db_path)
        budget = BudgetModel(conn)
        
        # Validierung prüfen
        is_valid, issues = budget.validate_database_integrity()
        
        if not is_valid:
            print("⚠️ Datenbank-Probleme gefunden:")
            for issue in issues:
                print(f"  - {issue}")
            print("🔧 Automatische Bereinigung wird durchgeführt...")
            budget._cleanup_reserved_categories()
            print("✅ Bereinigung abgeschlossen!")
        
        conn.close()
    except Exception as e:
        print(f"❌ Fehler bei Startup-Bereinigung: {e}")

# In main():
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    db_path = get_database_path()  # Deine Methode
    cleanup_database_on_startup(db_path)  # NEU!
    
    window = MainWindow(db_path)
    window.show()
    sys.exit(app.exec())
```

---

## 🧪 Testing-Checkliste

Nach der Migration folgende Tests durchführen:

### Budget-Tab
- [ ] BUDGET-SALDO wird korrekt angezeigt (nicht kumuliert)
- [ ] Keine "📊 BUDGET-SALDO" Kategorie in Liste
- [ ] Budget-Einträge können gespeichert werden
- [ ] Warnung bei Versuch, "BUDGET-SALDO" als Kategorie zu erstellen

### Database-Management
- [ ] Dialog öffnet sich
- [ ] Statistiken werden angezeigt
- [ ] Bereinigung funktioniert
- [ ] Backup kann erstellt werden
- [ ] Reset-Funktionen funktionieren (mit Backup testen!)

### Fixkosten-Check
- [ ] Dialog öffnet sich
- [ ] Fehlende Fixkosten werden angezeigt
- [ ] Schätzung wird berechnet
- [ ] Buchung aus Liste funktioniert
- [ ] Signal-Aktualisierung funktioniert

### Allgemein
- [ ] Keine Python-Fehler beim Start
- [ ] Alle Tabs laden korrekt
- [ ] Bestehende Features funktionieren weiter
- [ ] Performance ist vergleichbar

---

## 🐛 Troubleshooting

### Problem: "ModuleNotFoundError: No module named 'model.database_management_model'"

**Lösung**:
```bash
# Prüfe ob Datei existiert
ls -l model/database_management_model.py

# Falls nicht: Datei kopieren
cp /path/to/new/version/model/database_management_model.py model/
```

### Problem: BUDGET-SALDO erscheint weiterhin in Liste

**Lösung**:
```python
# Manuelle Bereinigung in Python-Shell
import sqlite3
conn = sqlite3.connect('budgetmanager.db')
cur = conn.cursor()
cur.execute("DELETE FROM budget WHERE category LIKE '%BUDGET-SALDO%'")
cur.execute("DELETE FROM categories WHERE name LIKE '%BUDGET-SALDO%'")
conn.commit()
conn.close()
```

### Problem: Themes funktionieren nicht mehr

**Lösung**: Theme-Dateien sind unverändert, prüfe ob `views/profiles/` Ordner existiert.

### Problem: Fehler beim Öffnen von Dialogen

**Lösung**: Prüfe Imports in `main_window.py`:
```python
from views.database_management_dialog import DatabaseManagementDialog
from views.fixcost_check_dialog_extended import FixcostCheckDialog
```

---

## 📊 Vergleich: Alt vs. Neu

### Fixkosten-Check

| Feature | v2.3.0.0 | v2.3.0.1 |
|---------|----------|----------|
| Monatsprüfung | ❌ | ✅ |
| Status-Übersicht | Einfach | Detailliert mit % |
| Schätzung | Basic | Multi-Source (Avg + Vorjahr) |
| Batch-Buchung | ❌ | ✅ |
| Signal-Updates | ❌ | ✅ |

### Budget-Modell

| Feature | v2.3.0.0 | v2.3.0.1 |
|---------|----------|----------|
| Kategorie-Validierung | ❌ | ✅ |
| BUDGET-SALDO-Schutz | ❌ | ✅ |
| Auto-Bereinigung | ❌ | ✅ |
| Integritätsprüfung | ❌ | ✅ |

---

## 🎉 Nach der Migration

### Empfohlene Schritte

1. **Backup-Test**:
   - Database-Management öffnen
   - Backup erstellen
   - Wiederherstellen testen

2. **Bereinigung**:
   - Database-Management > Bereinigung
   - Statistiken vorher/nachher vergleichen

3. **Fixkosten-Setup**:
   - Kategorien als Fixkosten markieren
   - Ersten Check durchführen
   - Fehlende Buchungen erfassen

4. **Dokumentation lesen**:
   - FEATURES.md durchgehen
   - Neue Features testen
   - Best Practices beachten

---

## 📞 Support

Bei Problemen nach Migration:

1. **Backup wiederherstellen** falls nötig
2. **Log-Datei prüfen**: `budgetmanager.log`
3. **Validierung laufen lassen**:
   ```python
   # In Python-Shell
   from model.budget_model import BudgetModel
   import sqlite3
   conn = sqlite3.connect('budgetmanager.db')
   budget = BudgetModel(conn)
   is_valid, issues = budget.validate_database_integrity()
   print(f"Valid: {is_valid}")
   print("Issues:", issues)
   ```

---

## ✅ Migrations-Checkliste

- [ ] Backup der Datenbank erstellt
- [ ] Neue Dateien kopiert
- [ ] Main-Window aktualisiert (Menü-Einträge)
- [ ] Anwendung gestartet (keine Fehler)
- [ ] BUDGET-SALDO Problem behoben
- [ ] Database-Management getestet
- [ ] Fixkosten-Check getestet
- [ ] Dokumentation gelesen
- [ ] Alle Tests bestanden

**Nach erfolgreicher Migration: Version 2.3.0.1 läuft! 🎉**
