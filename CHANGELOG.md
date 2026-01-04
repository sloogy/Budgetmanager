# Changelog - Budgetmanager

Alle wichtigen Änderungen an diesem Projekt werden hier dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

---

## [0.2.3.0.0] - 2026-01-04

### ✨ Neu: Einführungsassistent (Setup-Wizard)

Neuer Benutzer? Kein Problem! Der **Einführungsassistent** führt dich Schritt für Schritt durch die wichtigsten Funktionen:

1. **Startmodus wählen** – Geführtes Setup oder direkt loslegen
2. **Datenbank-Check** – Überprüfung der SQLite-Datenbank
3. **Kategorien anlegen** – Wahlweise über:
   - 📁 Kategorien-Manager (im Programm)
   - 📊 Excel-Vorlage (exportieren → ausfüllen → importieren)
4. **Budget ausfüllen** – Eigenes Budget-Fenster zum direkten Eintragen
5. **Budget-Tab erklärt** – Wie funktioniert was?
6. **Erste Buchung** – Test im Tracking-Tab
7. **Fixkosten/Wiederkehrend** – Automatische Buchungen verstehen

#### Zugriff
- **Automatisch**: Beim ersten Start (wenn noch nicht abgeschlossen)
- **Manuell**: Menü → Hilfe → 🧭 Erste Schritte...

#### Einstellungen
- "Einführung beim Start anzeigen" – In Einstellungen → Allgemein verknüpft
- Nach Abschluss wird der Haken automatisch entfernt

### 📊 Neu: Excel-Import/Export für Kategorien

- **Export**: Kategorien-Vorlage als `.xlsx` exportieren
- **Import**: Ausgefüllte Excel-Datei importieren
- Unterstützt hierarchische Pfade (z.B. `Wohnen › Miete › Nebenkosten`)
- Flags für Fixkosten, Wiederkehrend und Tag werden übernommen

### 💰 Neu: Budget-Ausfüll-Dialog

- Separates Fenster zum fokussierten Budget-Eintragen
- Wird im Setup-Assistenten automatisch geöffnet
- Auch unabhängig nutzbar

### 🐛 Fehlerbehebungen

- **Undo/Redo Fix**: `ts` Spalte wird jetzt korrekt in undo_stack hinzugefügt
  - Behebt: `sqlite3.OperationalError: table undo_stack has no column named ts`
  - Migration v7→v8 erweitert für Kompatibilität mit alten DBs
- **Migration robuster**: `.get()` statt direkter Dict-Zugriff

### 🔧 Verbesserungen

- Path-Handling verbessert (expanduser für relative Pfade)
- Über-Dialog mit neuen Feature-Highlights

---

## [0.2.2.1.10] - 2026-01-04

### Basis-Version mit folgenden Features:

- Undo/Redo-Unterstützung (Strg+Z / Strg+Y)
- Integrierte Kategorie-Verwaltung im Budget-Dialog
- Kategorien-Manager (Strg+K)
- Kategorien-Tab als optionaler Experten-Modus
- Theme-Profile und Erscheinungsmanager
- Backup & Wiederherstellung
- Sparziele-Dialog
- Globale Suche (Strg+F)
- Schnelleingabe (Strg+N)
- Export-Funktionen (CSV)
- Budgetwarnungen und Tags
- Fixkosten-Check
- Wiederkehrende Transaktionen
- Dashboard mit Budget/Gebucht/Rest-Ansicht

---

## Legende

- ✨ Neu: Neue Features
- 🔧 Verbesserung: Optimierungen bestehender Features
- 🐛 Bugfix: Fehlerbehebungen
- ⚠️ Breaking: Inkompatible Änderungen
- 🗑️ Entfernt: Gelöschte Features
