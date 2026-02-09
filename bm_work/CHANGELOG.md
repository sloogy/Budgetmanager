# Changelog

## 0.3.0.0 - 2026-02-09

- Fix: Tabs aktualisieren automatisch beim Tab-Wechsel (keine Neustarts mehr nötig)

# Changelog - Budgetmanager

## Version 2.3.0.1 (08.02.2026) 🎉

### 🐛 Kritische Bugfixes

#### BUDGET-SALDO Kumulierungs-Problem behoben
- **Problem**: "📊 BUDGET-SALDO" wurde fälschlicherweise als echte Kategorie in der Datenbank gespeichert
- **Symptom**: Saldo kumulierte sich über Monate statt korrekten monatlichen Saldo anzuzeigen
- **Lösung**:
  - Automatische Bereinigung fehlerhafter Einträge beim Start
  - Neue Validierung verhindert Erstellung reservierter System-Kategorien
  - Filterung in allen Budget-Funktionen implementiert
  - Liste reservierter Namen: BUDGET-SALDO, TOTAL, SUMME, etc.
  
#### Verbessertes Budget-Modell
- `budget_model.py` komplett überarbeitet
- Methode `_is_reserved_category()` für Schutz vor fehlerhaften Einträgen
- Methode `_cleanup_reserved_categories()` entfernt existierende fehlerhafte Daten
- Methode `validate_database_integrity()` für Integritätsprüfung

### ✨ Neue Features

#### 1. Database-Management-Dialog 🗄️
**Datei**: `views/database_management_dialog.py`

Features:
- **Statistik-Übersicht**: 
  - Dateigröße
  - Anzahl Kategorien, Budget-Einträge, Buchungen
  - Anzahl Tags, Sparziele, etc.
  - Verfügbare Jahre
  
- **Datenbank-Bereinigung**:
  - Entfernt verwaiste Budget-Einträge
  - Löscht fehlerhafte System-Kategorien
  - Entfernt ungültige Tags
  - Löscht Einträge mit ungültigen Daten
  - VACUUM für Optimierung
  
- **Reset-Funktionen**:
  - **Komplett-Reset**: Löscht ALLE Daten (mit doppelter Bestätigung)
  - **Partiell-Reset**: Löscht nur Budget & Kategorien, behält Buchungen
  - Automatisches Backup vor Reset (optional abwählbar)
  - Standard-Kategorien werden automatisch erstellt

#### 2. Erweiterter Fixkosten-Check 💰
**Datei**: `views/fixcost_check_dialog_extended.py`

Features:
- **Monatliche Prüfung**: Zeigt welche Fixkosten im gewählten Monat fehlen
- **Status-Übersicht**: 
  - Anzahl gebuchte vs. fehlende Fixkosten
  - Prozentuale Fertigstellung
  - Farbcodierte Status-Anzeige (Grün/Orange/Rot)
  
- **Intelligente Schätzung**:
  - Durchschnitt der letzten 12 Monate
  - Betrag vom Vorjahr (gleicher Monat)
  - Automatische Berechnung
  
- **Batch-Buchung**:
  - Mehrfachauswahl von Fixkosten
  - Alle auswählen/abwählen Buttons
  - Individuelle Buchungsdaten
  - Direktes Buchen aus Liste
  - Signal `bookings_created` für UI-Update

#### 3. Database-Management-Modell 🔧
**Datei**: `model/database_management_model.py`

Neue Klasse: `DatabaseManagementModel`

Features:
- **Backup-Verwaltung**:
  - Erstellen manueller/automatischer Backups
  - Liste verfügbarer Backups mit Metadaten
  - Wiederherstellung aus Backup
  - Temp-Backup bei Wiederherstellung für Sicherheit
  
- **Reset-Funktionalität**:
  - Kompletter oder partieller Reset
  - Optional mit Backup
  - Standard-Kategorien vordefiniert
  - Typ-spezifische Standard-Kategorien
  
- **Bereinigung**:
  - Entfernt verwaiste Einträge
  - Löscht reservierte Kategorien
  - Statistik über gelöschte Einträge
  - VACUUM für Optimierung
  
- **Utilities**:
  - Datenbank-Statistiken
  - SQL-Export
  - Integritätsprüfung

### 📚 Dokumentation

#### Neue Dateien
- `FEATURES.md`: Vollständige Feature-Dokumentation
  - Übersicht aller implementierten Features
  - Technische Details
  - Benutzungsanleitungen
  - Tipps & Best Practices
  
- `CHANGELOG.md`: Diese Datei (Versionshistorie)

#### Aktualisierte Dateien
- `README.md`: Aktualisiert mit neuen Features
- `VERSION_INFO.txt`: Version 2.3.0.1

### 🔄 Verbesserungen

#### Budget-Verwaltung
- Robustere Validierung bei Kategorie-Erstellung
- Schutz vor fehlerhaften System-Kategorien
- Bessere Fehlerbehandlung
- Automatische Bereinigung beim Start

#### Fixkosten-Management
- Erweiterte Historie-Ansicht
- Bessere Schätzung durch multiple Datenquellen
- Intuitivere Benutzeroberfläche
- Signal-basierte UI-Updates

#### Datenbank-Integrität
- Automatische Validierung
- Proaktive Bereinigung
- Bessere Fehler-Logs
- Wiederherstellungsmechanismen

### 🎨 UI/UX Verbesserungen

- **Database-Management-Dialog**:
  - Klare Strukturierung in Gruppen
  - Farbcodierte Warnungen
  - Intuitive Buttons mit Icons
  - Doppelte Bestätigung bei kritischen Aktionen
  
- **Fixkosten-Check-Dialog**:
  - Übersichtliche Tabelle mit 7 Spalten
  - Status-Header mit Icon und Farbe
  - Alle-auswählen Funktionalität
  - Datum-Picker für flexible Buchungsdaten

### ⚙️ Technische Änderungen

#### Neue Abhängigkeiten
- Keine neuen externen Abhängigkeiten

#### Datenbank-Schema
- Keine Schema-Änderungen (kompatibel mit v2.3.0.0)
- Neue Validierung bei INSERT/UPDATE
- Automatische Bereinigung bei Start

#### Performance
- VACUUM nach Bereinigung für bessere Performance
- Optimierte Abfragen in Fixkosten-Check
- Caching von wiederkehrenden Berechnungen

### 📋 Migration von 2.3.0.0

#### Automatische Schritte (beim Start)
1. Fehlerhafte BUDGET-SALDO Einträge werden gelöscht
2. Reservierte Kategorien werden entfernt
3. Keine manuellen Schritte nötig!

#### Empfohlene Schritte
1. Backup erstellen (über Datei > Backup oder Database-Management)
2. Update installieren
3. Anwendung starten (automatische Bereinigung läuft)
4. Database-Management > Bereinigung durchführen (optional)
5. Statistiken prüfen

### 🎯 Status aller angefragten Features

| Feature | Status | Datei/Modul |
|---------|--------|-------------|
| Wiederkehrende Transaktionen | ✅ Vorhanden | `recurring_transactions_model.py` |
| Fixkosten-Check (Monatsprüfung) | ✅ **NEU** | `fixcost_check_dialog_extended.py` |
| Optionale Liste fehlender Buchungen | ✅ **NEU** | `fixcost_check_dialog_extended.py` |
| Budgetwarnungen | ✅ Vorhanden | `budget_warnings_model.py` |
| Tags/Labels | ✅ Vorhanden | `tags_model.py` |
| Undo/Redo | ✅ Vorhanden | `undo_redo_model.py` |
| Favoriten | ✅ Vorhanden | `favorites_model.py` |
| Sparziele | ✅ Vorhanden | `savings_goals_model.py` |
| Backup/Wiederherstellung | ✅ Vorhanden | `backup_restore_dialog.py` |
| Datenbank-Reset | ✅ **NEU** | `database_management_model.py` |
| Erscheinungsmanager | ✅ Vorhanden | `appearance_profiles_dialog.py` (24 Themes!) |
| Windows-Installer | ✅ Vorhanden | `build_windows.py`, `installer/` |
| Update-Tool | ✅ Vorhanden | `tools/update_manager.py` |

**Alle Features implementiert! 🎉**

### 🐛 Bekannte Einschränkungen

- Database-Management-Dialog sollte nicht während aktiver Buchungen geöffnet werden
- Reset-Funktion erstellt Backup nur wenn Option aktiviert
- Fixkosten-Auto-Erkennung basiert auf Buchungshistorie (min. 6 Monate)

### 🔜 Geplant für zukünftige Versionen

- Mobile App (Android/iOS)
- Cloud-Synchronisation (optional)
- Mehr Report-Templates
- API für Drittanbieter-Integration
- Verschlüsselung der Datenbank

---

## Version 2.3.0.0 (04.01.2026)

### Features
- Hierarchische Kategorien mit Parent-Child-Beziehungen
- 24 vordefinierte Themes
- Erweiterte Budget-Ansicht mit 17 Spalten
- Fixkosten und wiederkehrende Buchungen
- Tags-System
- Favoriten-Verwaltung
- Sparziele-Tracking
- Excel-Import/Export
- PDF-Reports
- Globale Suche
- Shortcuts-System
- Windows-Installer

### Technisch
- Migration auf PySide6
- SQLite mit automatischen Migrationen
- Modular aufgebaut (MVC-Pattern)
- Umfangreiche Dokumentation

---

## Version 2.2.x - Frühere Versionen

*(Details siehe Git-History)*

### Version 2.2.0 (10.12.2025)
- Theme-System eingeführt
- Performance-Verbesserungen
- Neue Diagramme

### Version 2.1.0 (15.11.2025)
- Undo/Redo-System
- Bulk-Edit-Funktionen
- Verbessertes Tracking

### Version 2.0.0 (01.10.2025)
- Komplettes Redesign der UI
- SQLite-Integration
- Kategorie-Manager

---

## Ältere Versionen

### Version 1.x
- Basis-Funktionalität
- Einfaches Budget-Tracking
- CSV-Export

### Version 0.15 (Initial)
- Erste funktionierende Version
- Grundlegende Budget-Verwaltung
