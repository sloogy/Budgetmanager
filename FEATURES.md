# Budgetmanager Version 2.3.0.1 - Vollständige Feature-Dokumentation

## 🎯 Übersicht

Der Budgetmanager ist eine umfassende Desktop-Anwendung zur Verwaltung persönlicher Finanzen mit erweiterten Features für Budget-Planung, Tracking und Analyse.

---

## ✅ Implementierte Features (Vollständig)

### 1. Budget-Verwaltung ⭐
- **Hierarchische Kategorien**: Unterstützung für Haupt- und Unterkategorien
- **Multi-Typ-Support**: Einkommen, Ausgaben, Ersparnisse
- **Jahresplanung**: Monatlich oder jährlich planen
- **Budget-Saldo-Anzeige**: Automatische Berechnung des Saldos (Einkommen - Ausgaben - Ersparnisse)
- **Schutz vor fehlerhaften Einträgen**: Verhindert Erstellung von System-Kategorien wie "BUDGET-SALDO"

### 2. Tracking (Buchungen) 📊
- **Transaktionsverwaltung**: Erfassen, bearbeiten, löschen von Buchungen
- **Filtern & Suchen**: Nach Datum, Typ, Kategorie, Betrag, Tags
- **Schnelleingabe**: Schneller Dialog für häufige Buchungen (Strg+N)
- **Batch-Import**: Excel/CSV-Import für Massenbuchungen

### 3. Wiederkehrende Transaktionen 🔄
- **Automatische Buchungen**: Mit Soll-Buchungsdatum
- **Flexibles Intervall**: Täglich, wöchentlich, monatlich, jährlich
- **Fälligkeitsmanagement**: Automatische Erinnerungen
- **Template-Verwaltung**: Wiederkehrende Vorlagen speichern

### 4. Fixkosten-Management ⚡ (NEU ERWEITERT)
- **Monatsprüfung**: Automatische Prüfung, ob Fixkosten bereits gebucht wurden
- **Fehlende Buchungen**: Liste aller nicht gebuchten Fixkosten
- **Optionaler Dialog**: Auswahl welche Fixkosten gebucht werden sollen
- **Schätzung**: Basierend auf Durchschnitt und Vorjahr
- **Direktes Buchen**: Aus Liste heraus buchen mit einem Klick
- **Auto-Erkennung**: Erkennt potenzielle Fixkosten automatisch

### 5. Budgetwarnungen ⚠️
- **Überschreitungs-Alerts**: Warnung bei Budget-Überschreitung
- **Prozentuale Schwellwerte**: Konfigurierbare Warnstufen (z.B. 80%, 100%)
- **Kategorien-spezifisch**: Individuelle Warnungen pro Kategorie
- **Echtzeit-Überwachung**: Sofortige Benachrichtigung

### 6. Tags & Labels 🏷️
- **Flexible Kategorisierung**: Zusätzlich zu Kategorien
- **Multi-Tag-Support**: Mehrere Tags pro Buchung
- **Filter nach Tags**: Schnelle Suche nach getaggten Einträgen
- **Tag-Verwaltung**: Erstellen, umbenennen, löschen, zusammenführen
- **Tag-Statistiken**: Auswertung nach Tags

### 7. Undo/Redo ↩️
- **Änderungen rückgängig machen**: Strg+Z für Undo
- **Wiederherstellen**: Strg+Shift+Z für Redo
- **Action-History**: Zeigt letzte Aktionen
- **Batch-Undo**: Mehrere Schritte auf einmal zurück

### 8. Favoriten ⭐
- **Häufige Kategorien**: Mit Stern markieren
- **Schnellzugriff**: Favoriten oben in Listen
- **Typ-übergreifend**: Favoriten für alle Typen
- **Einfache Verwaltung**: Klick zum An/Abpinnen

### 9. Sparziele 💰
- **Ziel definieren**: Name, Betrag, Zieldatum
- **Fortschritt tracken**: Automatische Berechnung
- **Visualisierung**: Fortschrittsbalken und Prozentanzeige
- **Automatische Synchronisation**: Mit Ersparnisse-Buchungen
- **Prioritäten**: Mehrere Ziele gleichzeitig verwalten

### 10. Backup & Wiederherstellung 💾
- **Manuelles Backup**: Jederzeit Datenbank sichern
- **Auto-Backup**: Vor kritischen Operationen
- **Wiederherstellung**: Aus Backup-Liste auswählen
- **Backup-Verwaltung**: Liste aller Backups mit Datum und Größe
- **Export**: Als SQL-Dump exportieren

### 11. Datenbank-Verwaltung 🗄️ (NEU)
- **Statistiken**: Übersicht über DB-Größe, Einträge, etc.
- **Bereinigung**: Entfernt verwaiste Einträge und ungültige Daten
- **Reset-Funktion**: 
  - Komplett-Reset (alle Daten)
  - Partiell-Reset (nur Budget/Kategorien, Buchungen behalten)
- **Integritätsprüfung**: Validiert Datenbank-Konsistenz
- **Optimierung**: VACUUM für Größenreduktion

### 12. Erscheinungsmanager (Themes) 🎨
- **24 vordefinierte Themes**: 
  - Hell: Standard, Warm, Grün, Pastell, etc.
  - Dunkel: Standard, Blau, Grün, Graphite, Purple Night, etc.
  - Speziell: Solarized, Gruvbox, Nord, Dracula, Monokai, etc.
- **Theme-Editor**: Eigene Themes erstellen
- **Farbprofile**: Als JSON speichern
- **Import/Export**: Themes teilen
- **Live-Preview**: Sofortige Vorschau
- **Persistenz**: Theme bleibt nach Neustart erhalten

### 13. Windows-Installer 📦
- **PyInstaller**: Erstellt standalone .exe
- **Inno Setup**: Professioneller Installer
- **Auto-Updates**: Update-Check integriert
- **Startmenü-Integration**: Verknüpfungen
- **Deinstallation**: Saubere Entfernung
- **Build-Script**: `build_windows.py` für einfaches Packaging

### 14. Update-Tool 🔄 (Optional)
- **Version-Check**: Prüft auf neue Versionen
- **Auto-Download**: Download neuer Versionen
- **Changelog**: Zeigt Änderungen an
- **Update-Benachrichtigung**: Optional beim Start

### 15. Erweiterte Features
- **Excel-Export**: Daten als Excel exportieren
- **PDF-Reports**: Berichte als PDF generieren
- **Diagramme**: Pie-Charts, Balkendiagramme
- **Globale Suche**: Durchsucht alle Buchungen (Strg+F)
- **Shortcuts**: Umfangreiche Tastaturkürzel
- **Multi-Jahr-Ansicht**: Jahresübergreifende Analysen
- **Jahr kopieren**: Budget von Jahr zu Jahr übernehmen
- **Kategorie-Manager**: Umbenennen, Verschieben, Zusammenführen
- **Bulk-Edit**: Mehrere Einträge gleichzeitig bearbeiten

---

## 🔧 Technische Details

### Architektur
- **GUI**: PySide6 (Qt 6)
- **Datenbank**: SQLite mit automatischen Migrationen
- **Modular**: Model-View-Controller Pattern
- **Erweiterbar**: Plugin-System vorbereitet

### Datenbank-Schema
- **Version 8**: Aktuelle Schema-Version
- **Automatische Migration**: Von älteren Versionen
- **Backup vor Migration**: Sicherheit bei Updates
- **Integrität**: Foreign Keys, Unique Constraints

### Performance
- **Caching**: Für häufige Abfragen
- **Lazy Loading**: Bei großen Datenmengen
- **Batch-Operations**: Für Massenänderungen
- **Indizierung**: Optimierte Datenbank-Indizes

---

## 📊 Benutzung

### Ersteinrichtung
1. **Datenbank erstellen**: Beim ersten Start automatisch
2. **Kategorien anlegen**: Standard-Kategorien oder eigene erstellen
3. **Budget planen**: Für aktuelles Jahr

### Tägliche Nutzung
1. **Buchungen erfassen**: Via Schnelleingabe oder Detail-Dialog
2. **Fixkosten prüfen**: Monatlich über Fixkosten-Check
3. **Budget überwachen**: Übersicht-Tab für aktuellen Stand
4. **Sparziele tracken**: Fortschritt verfolgen

### Monatliche Aufgaben
1. **Fixkosten buchen**: Über Fixkosten-Dialog
2. **Budget anpassen**: Falls nötig
3. **Backup erstellen**: Sicherheitskopie

### Jährliche Aufgaben
1. **Jahr kopieren**: Budget für neues Jahr
2. **Kategorien überprüfen**: Anpassen falls nötig
3. **Jahres-Report**: Analyse des vergangenen Jahres

---

## 🐛 Bekannte Probleme (Behoben in 2.3.0.1)

### ✅ BEHOBEN: BUDGET-SALDO Kumulierung
**Problem**: BUDGET-SALDO Einträge wurden fälschlicherweise als echte Kategorien in der Datenbank gespeichert.

**Lösung**: 
- Automatische Bereinigung beim Start
- Validierung verhindert Erstellung reservierter Kategorien
- Filterung in allen Budget-Funktionen

### ✅ BEHOBEN: Fixkosten ohne Monatsprüfung
**Problem**: Keine Prüfung, ob Fixkosten bereits gebucht wurden.

**Lösung**:
- Neuer erweiterter Fixkosten-Dialog
- Automatische Monatsprüfung
- Schätzung basierend auf Historie

---

## 🚀 Neue Features in Version 2.3.0.1

### 1. Verbessertes Budget-Modell
- Schutz vor System-Kategorien
- Validierung bei Eingabe
- Automatische Bereinigung

### 2. Database-Management-Dialog
- Statistiken-Übersicht
- Bereinigung-Funktion
- Reset-Funktionen (komplett/partiell)
- Backup-Integration

### 3. Erweiterter Fixkosten-Check
- Monatliche Prüfung
- Fehlende Buchungen auflisten
- Schätzung aus Historie
- Direktes Buchen aus Liste
- Mehrfachauswahl

### 4. Dokumentation
- Vollständige Feature-Liste
- Technische Details
- Benutzungsanleitungen

---

## 📝 Installation

### Voraussetzungen
- Python 3.11+
- PySide6
- SQLite (inkludiert in Python)

### Installation (Development)
```bash
pip install -r requirements.txt
python main.py
```

### Windows-Installation
1. Installer herunterladen: `Budgetmanager_Setup_v2.3.0.1.exe`
2. Installer ausführen
3. Installationsverzeichnis wählen
4. Fertig!

---

## 🔐 Datenschutz & Sicherheit

- **Lokale Datenbank**: Alle Daten bleiben lokal
- **Keine Cloud**: Kein automatisches Hochladen
- **Backups**: Empfohlen in sicheren Ordner
- **Verschlüsselung**: Optional (kann aktiviert werden)

---

## 📞 Support

Bei Problemen oder Fragen:
1. Dokumentation prüfen
2. Backup erstellen
3. Database-Management-Dialog > Statistiken
4. Fehler-Log prüfen (`budgetmanager.log`)

---

## 🎉 Zusammenfassung

Budgetmanager v2.3.0.1 ist eine vollständige Personal-Finance-Lösung mit:
- ✅ Alle angeforderten Features implementiert
- ✅ Professionelle UI mit 24 Themes
- ✅ Robuste Datenbank mit Schutzfunktionen
- ✅ Windows-Installer verfügbar
- ✅ Umfangreiche Dokumentation
- ✅ Aktive Wartung und Updates

**Bereit für produktiven Einsatz! 🚀**
