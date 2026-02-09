# 🔧 Quick-Fix: AttributeError 'get_amount' 

## Problem
```
AttributeError: 'BudgetModel' object has no attribute 'get_amount'
```

Tritt auf beim Öffnen der grafischen Übersicht (Tracking-Tab).

---

## Schnelle Lösung (2 Minuten)

### Option 1: Methode manuell hinzufügen

Öffne `model/budget_model.py` und füge nach der `get_matrix()` Methode folgende Methode ein:

```python
def get_amount(self, year: int, month: int, typ: str, category: str) -> float:
    """
    Gibt Budget-Betrag für spezifische Kombination zurück.
    
    Args:
        year: Jahr
        month: Monat (1-12)
        typ: Typ (Einkommen/Ausgaben/Ersparnisse)
        category: Kategoriename
        
    Returns:
        Budget-Betrag oder 0.0 wenn nicht gefunden
    """
    cur = self.conn.execute(
        "SELECT amount FROM budget WHERE year=? AND month=? AND typ=? AND category=?",
        (int(year), int(month), typ, category)
    )
    result = cur.fetchone()
    return float(result["amount"]) if result else 0.0
```

**Stelle sicher, dass die Methode korrekt eingerückt ist (gleiche Ebene wie `get_matrix`)!**

### Option 2: Automatischer Patch (Python-Skript)

Erstelle eine Datei `patch_budget_model.py`:

```python
#!/usr/bin/env python3
"""
Patch-Skript für budget_model.py
Fügt fehlende get_amount Methode hinzu
"""

import os
import sys

def patch_budget_model(filepath='model/budget_model.py'):
    """Fügt get_amount Methode hinzu falls sie fehlt."""
    
    # Datei lesen
    if not os.path.exists(filepath):
        print(f"❌ Datei nicht gefunden: {filepath}")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Prüfen ob Methode bereits existiert
    if 'def get_amount(' in content:
        print("✅ get_amount() existiert bereits - kein Patch nötig")
        return True
    
    # Methode die hinzugefügt werden soll
    method_code = '''
    def get_amount(self, year: int, month: int, typ: str, category: str) -> float:
        """
        Gibt Budget-Betrag für spezifische Kombination zurück.
        
        Args:
            year: Jahr
            month: Monat (1-12)
            typ: Typ (Einkommen/Ausgaben/Ersparnisse)
            category: Kategoriename
            
        Returns:
            Budget-Betrag oder 0.0 wenn nicht gefunden
        """
        cur = self.conn.execute(
            "SELECT amount FROM budget WHERE year=? AND month=? AND typ=? AND category=?",
            (int(year), int(month), typ, category)
        )
        result = cur.fetchone()
        return float(result["amount"]) if result else 0.0
'''
    
    # Finde get_matrix Methode und füge danach ein
    if 'def get_matrix(' in content:
        # Finde das Ende der get_matrix Methode
        lines = content.split('\n')
        insert_index = -1
        in_get_matrix = False
        
        for i, line in enumerate(lines):
            if 'def get_matrix(' in line:
                in_get_matrix = True
            elif in_get_matrix and line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                # Nächste Methode gefunden
                insert_index = i
                break
            elif in_get_matrix and (line.strip().startswith('def ') and 'get_matrix' not in line):
                # Nächste Methode gefunden
                insert_index = i
                break
        
        if insert_index > 0:
            lines.insert(insert_index, method_code)
            new_content = '\n'.join(lines)
            
            # Backup erstellen
            backup_path = filepath + '.backup'
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"💾 Backup erstellt: {backup_path}")
            
            # Neue Datei schreiben
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print("✅ Patch erfolgreich angewendet!")
            print(f"📝 get_amount() Methode hinzugefügt nach get_matrix()")
            return True
    
    print("❌ Konnte get_matrix() nicht finden - manueller Patch nötig")
    return False

if __name__ == '__main__':
    filepath = 'model/budget_model.py'
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    
    print(f"🔧 Patche {filepath}...")
    success = patch_budget_model(filepath)
    sys.exit(0 if success else 1)
```

**Ausführen**:
```bash
python patch_budget_model.py
```

---

## Prüfen ob Fix funktioniert

Nach dem Patch:

```python
# Test in Python-Shell
import sqlite3
from model.budget_model import BudgetModel

conn = sqlite3.connect('budgetmanager.db')
conn.row_factory = sqlite3.Row
budget = BudgetModel(conn)

# Sollte jetzt funktionieren
amount = budget.get_amount(2026, 1, "Ausgaben", "Miete")
print(f"Betrag: {amount}")  # Sollte Wert ausgeben, nicht Fehler
```

Wenn das funktioniert, starte die Anwendung:
```bash
python main.py
```

---

## Alternative: Neue Version verwenden

Im Update-Paket v2.3.0.1 ist dieser Fehler bereits behoben.

**Empfehlung**: 
1. Backup deiner Datenbank erstellen
2. Dateien aus v2.3.0.1 verwenden
3. Datenbank zurückkopieren

---

## Warum passiert das?

Die Methode `get_amount()` wurde in einer älteren Version entfernt oder fehlt in deiner Version. Sie wird aber in `tracking_tab.py` Zeile 456 benötigt:

```python
amt = self.budget.get_amount(year, month, typ, cat.name)
```

Der Fix fügt die Methode wieder hinzu.

---

## Support

Falls der Patch nicht funktioniert:
1. Prüfe ob `model/budget_model.py.backup` erstellt wurde
2. Öffne die Datei und suche nach `def get_matrix(`
3. Füge die Methode manuell danach ein
4. Achte auf korrekte Einrückung (4 Spaces oder 1 Tab)

**Bei Problemen**: Die v2.3.0.1 Version enthält die korrekte, getestete Datei.
