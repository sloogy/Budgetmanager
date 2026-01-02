# Budgetmanager v0.18.1 - Quick Start Guide

## 🚀 Installation (5 Minuten)

### Methode 1: Direktstart (Empfohlen)
```bash
# 1. Repository klonen / ZIP herunterladen
git clone [repository-url]
# oder ZIP entpacken

# 2. Ins Verzeichnis wechseln
cd Budgetmanager_v0_18_1_Complete

# 3. Dependencies installieren
pip install -r requirements.txt

# 4. Starten!
python main.py
```

### Methode 2: Virtuelle Umgebung (Fortgeschrittene)
```bash
# 1. Virtuelle Umgebung erstellen
python -m venv venv

# 2. Aktivieren
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Dependencies installieren
pip install -r requirements.txt

# 4. Starten
python main.py
```

### Methode 3: Windows Installer (Coming Soon)
```
1. budgetmanager_setup.exe herunterladen
2. Ausführen und Anweisungen folgen
3. Desktop-Icon doppelklicken
```

---

## 📝 Erste Schritte (10 Minuten)

### 1. Kategorien einrichten (2 Min)
```
1. Reiter "Kategorien" öffnen
2. Vordefinierte Kategorien sehen:
   - Lebensmittel
   - Miete
   - Transport
   - ...
3. Eigene hinzufügen:
   - Button "Kategorie hinzufügen"
   - Name eingeben (z.B. "Streaming-Dienste")
   - Farbe wählen
   - Speichern
```

**Tipp:** Starte mit wenigen Kategorien, erweitere später!

### 2. Budget festlegen (3 Min)
```
1. Reiter "Budget" öffnen
2. Jahr/Monat auswählen
3. Für jede Kategorie Budget eintragen:
   - Lebensmittel: 300 €
   - Miete: 800 €
   - etc.
4. "Speichern" klicken
```

**Tipp:** Budget-Vorschläge nutzen (basiert auf Durchschnitt)!

### 3. Erste Buchung erstellen (2 Min)
```
1. Reiter "Tracking" öffnen
2. Button "Neue Buchung" (oder Strg+N)
3. Ausfüllen:
   - Datum: Heute
   - Kategorie: Lebensmittel
   - Betrag: -45.50 € (negativ = Ausgabe)
   - Beschreibung: "Wocheneinkauf Supermarkt"
4. "Speichern"
```

**Tipp:** Quick-Add nutzen (Strg+Q) für schnelle Eingabe!

### 4. Übersicht anschauen (1 Min)
```
1. Reiter "Übersicht" öffnen
2. Siehst:
   - Einnahmen vs Ausgaben
   - Budget-Fortschritt
   - Top-Kategorien
   - Trend-Diagramme
```

### 5. Theme anpassen (2 Min)
```
1. Einstellungen öffnen (Menü → Einstellungen)
2. Reiter "Darstellung"
3. Design-Profil wählen:
   - Hell: "Standard Hell", "Solarized Hell"
   - Dunkel: "Nord Dunkel", "Dracula Dunkel"
4. "OK" klicken
5. Fertig! 🎨
```

---

## 💡 Wichtige Funktionen

### Wiederkehrende Transaktionen
```
Menü → Transaktionen → Wiederkehrende Transaktionen

Beispiel: Miete
- Betrag: -800 €
- Kategorie: Wohnen
- Intervall: Monatlich
- Start: 01.01.2024
- Automatisch buchen: ✅

→ Wird jeden Monat automatisch gebucht!
```

### Fixkosten-Check
```
Menü → Tools → Fixkosten-Check

Zeigt:
- Welche Fixkosten noch nicht gebucht sind
- Optional: Direkt buchen
```

### Sparziele
```
Menü → Tools → Sparziele

Beispiel: Urlaub
- Ziel: 2000 €
- Frist: 31.12.2025
- Monatliche Rate: 166 € (automatisch berechnet)
```

### Quick-Add (Super schnell!)
```
Strg+Q drücken

Minimalistischer Dialog:
[Betrag] [Kategorie] [Beschreibung]
-45.50   Lebensmittel  Supermarkt

Enter → Gespeichert!
```

### Global Search
```
Strg+F drücken

Suche nach:
- Beschreibungen
- Beträgen
- Kategorien
- Zeiträumen
```

---

## 🎨 Theme-System (NEU in v0.18.1!)

### Standard-Theme anpassen
```
1. Einstellungen → Darstellung → "Profile verwalten..."
2. Standard-Theme wählen (z.B. "Solarized - Dunkel")
3. Farben ändern (klicke auf "Ändern...")
4. Änderungen werden automatisch gespeichert!
```

### Eigenes Theme erstellen
```
1. Profile verwalten → "Neu..."
2. Namen eingeben: "Mein Firmen-Theme"
3. Farben anpassen
4. "Profil anwenden" → Sofort testen!
```

### Theme exportieren/importieren
```
Export:
1. Theme wählen
2. "Export..." → JSON-Datei speichern

Import:
1. "Import..." → JSON-Datei wählen
2. Fertig!

→ Perfekt zum Teilen mit Kollegen!
```

---

## ⌨️ Wichtige Shortcuts

| Shortcut | Funktion |
|----------|----------|
| **Strg+N** | Neue Buchung |
| **Strg+Q** | Quick-Add |
| **Strg+F** | Global Search |
| **Strg+,** | Einstellungen |
| **Strg+E** | Export-Dialog |
| **Strg+S** | Speichern |
| **F5** | Aktualisieren |
| **F1** | Hilfe |
| **Esc** | Dialog schließen |

**Alle Shortcuts anzeigen:** Menü → Hilfe → Tastaturkürzel

---

## 📊 Typische Workflows

### Workflow 1: Tägliche Buchung
```
1. Strg+Q (Quick-Add)
2. Betrag eingeben
3. Kategorie wählen
4. Kurze Beschreibung
5. Enter
→ Fertig in 10 Sekunden!
```

### Workflow 2: Monatsabschluss
```
1. Reiter "Übersicht" → Monat prüfen
2. Fixkosten-Check → Fehlende buchen
3. Budget anpassen (falls nötig)
4. Export → PDF-Bericht erstellen
5. Backup erstellen
```

### Workflow 3: Jahreswechsel
```
1. Backup erstellen (wichtig!)
2. Budget kopieren:
   - Menü → Tools → Jahr kopieren
   - Von: 2024 → Nach: 2025
3. Anpassungen vornehmen
4. Sparziele aktualisieren
```

---

## 🛠️ Troubleshooting

### Problem: Anwendung startet nicht
```bash
# Dependencies prüfen
pip list | grep PySide6

# Neu installieren
pip install -r requirements.txt --upgrade

# Python-Version prüfen (mindestens 3.11)
python --version
```

### Problem: Datenbank-Fehler
```
1. Backup wiederherstellen:
   Menü → Tools → Backup/Wiederherstellung

2. Falls kein Backup:
   - ~/.budgetmanager/budgetmanager.db umbenennen
   - Neu starten (leere Datenbank wird erstellt)
```

### Problem: Theme sieht falsch aus
```
1. Einstellungen → Darstellung
2. Anderes Theme wählen und anwenden
3. Zurück zum Original-Theme

Oder:
Profile verwalten → "Auf Standard zurücksetzen"
```

### Problem: Langsam bei vielen Daten
```
1. Datenbank optimieren:
   Menü → Tools → Datenbank-Management → "Optimieren"

2. Cache leeren:
   rm -rf ~/.budgetmanager/cache/

3. Ältere Daten archivieren:
   Export → CSV → Alte Daten löschen
```

---

## 📱 Best Practices

### 1. Regelmäßig buchen
- **Täglich:** Quick-Add für kleine Ausgaben
- **Wöchentlich:** Belege abarbeiten
- **Monatlich:** Fixkosten prüfen

### 2. Kategorien sinnvoll nutzen
- **Nicht zu viele:** 10-15 Haupt-Kategorien reichen
- **Nicht zu wenige:** Mindestens 5 für guten Überblick
- **Konsistent:** Gleiche Ausgaben → Gleiche Kategorie

### 3. Beschreibungen kurz halten
- ✅ "REWE Wocheneinkauf"
- ❌ "Eingekauft am 24.12.2024 bei REWE am Marktplatz..."

### 4. Backups machen
- **Automatisch:** Einstellungen → Backup aktivieren
- **Manuell:** Vor großen Änderungen
- **Extern:** In Cloud sichern

### 5. Budget realistisch setzen
- Nicht zu knapp (sonst ständig überschritten)
- Nicht zu großzügig (sonst kein Anreiz zu sparen)
- Puffer einplanen (~10%)

---

## 🎯 Fortgeschrittene Features

### Wiederkehrende Transaktionen automatisieren
```python
# config.json
{
  "auto_book_recurring": true,
  "auto_book_days_before": 3
}
```

### Eigene Export-Templates
```
Ordner: ~/.budgetmanager/export-templates/
Format: Excel mit Makros (.xlsm)
```

### Datei-Shortcuts
```
~/.budgetmanager/
├── budgetmanager.db      # Datenbank
├── settings.json         # Einstellungen
├── themes/              # Themes
├── backups/            # Auto-Backups
└── exports/            # Export-Dateien
```

---

## 📚 Weitere Ressourcen

### Dokumentation
- **Theme-System:** `THEME_DOCUMENTATION.md`
- **Feature-Roadmap:** `FEATURE_ROADMAP.md`
- **Changelog:** `CHANGELOG_v0_18_1.md`
- **Versions-Historie:** `VERSION_HISTORY.md`

### Support
- **GitHub Issues:** [Link]
- **E-Mail:** [E-Mail]
- **Discord:** [Discord-Link]

### Video-Tutorials (geplant)
- Erste Schritte (10 Min)
- Wiederkehrende Transaktionen (5 Min)
- Theme-System erklärt (7 Min)
- Tipps & Tricks (15 Min)

---

## ✅ Checkliste: Fertig eingerichtet?

- [ ] Anwendung startet
- [ ] Kategorien erstellt/angepasst
- [ ] Budget für aktuellen Monat eingetragen
- [ ] Erste Buchungen erstellt
- [ ] Theme gewählt
- [ ] Shortcuts getestet
- [ ] Backup aktiviert
- [ ] Wiederkehrende Transaktionen eingerichtet (falls gewünscht)

**Alles erledigt? Glückwunsch! 🎉**

Du bist jetzt bereit, deine Finanzen im Griff zu haben!

---

## 🚀 Nächste Schritte

1. **Eine Woche nutzen** - Gewöhne dich an die App
2. **Kategorien optimieren** - Passe an deine Bedürfnisse an
3. **Community beitreten** - Teile Tipps, hole Feedback
4. **Feature-Requests** - Was fehlt dir?

---

**Version:** 0.18.1  
**Autor:** Christian  
**Datum:** 24.12.2024  
**Viel Erfolg! 💰**
