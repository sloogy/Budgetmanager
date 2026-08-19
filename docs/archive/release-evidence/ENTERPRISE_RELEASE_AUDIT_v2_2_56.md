# BudgetManager v2.2.56 – Cockpit-Raster und Sparziel-Flussbestand

**Datum:** 2. August 2026  
**Status:** Zielsystem-Test erforderlich  
**Schwerpunkte:** freie Cockpit-Anordnung, sichtbare Drop-Vorschau, Sparziele für grosse Projekte

## 1. Ausgangslage

Im manuellen Cockpit-Layout wurden beide Spalten bisher über gemeinsame Rasterzeilen gekoppelt. Eine hohe Kachel links reservierte dadurch dieselbe Zeilenhöhe rechts. Eine rechte Kachel konnte nicht in den sichtbar freien Bereich hochrücken. Zusätzlich fehlte während des Ziehens eine eindeutige Vorschau der späteren Position.

Sparziele wurden ausserdem wie ein einfacher Kontostand behandelt. Für grosse Projekte fehlte die getrennte Sicht auf Einzahlungen, Verwendungen, aktuellen Bestand und den noch einzuzahlenden Betrag. Negative Buchungen konnten Fehlkorrekturen und echte Bezüge nicht sauber unterscheiden.

## 2. Cockpit-Änderungen

- Linke und rechte Cockpit-Spalte sind im manuellen Modus unabhängige vertikale Stapel.
- Eine Kachel kann innerhalb ihrer Spalte bis ganz nach oben oder unten geschoben werden.
- Der Wechsel zwischen linker und rechter Spalte bleibt möglich.
- Während des Ziehens erscheint ein deutlich markierter Ablageplatzhalter an der tatsächlichen Zielposition.
- Die gesamte Kachel-Kopfzeile sowie der Griff `≡` bleiben als Drag-Zonen nutzbar.
- Reihenfolge und Spalte werden nach dem Drop gemeinsam gespeichert.
- Im Automatikmodus bleiben das Schrumpfen leerer Abschnitte und die automatische Sortierung erhalten.
- Der DesignManager bleibt die zentrale Quelle für Farben und Darstellung.

## 3. Sparziel-Flussbestand

Ein Sparziel führt nun getrennte Werte:

| Wert | Bedeutung |
|---|---|
| Zielbetrag | Gewünschte Projektsumme |
| Eingezahlt | Einzahlungen abzüglich echter Korrekturen |
| Verwendet | Summe der Bezüge aus dem Projekt |
| Aktueller Bestand | Eingezahlt minus verwendet |
| Noch einzuzahlen | Zielbetrag minus eingezahlt |

Beispiel Hochzeit:

```text
Zielbetrag:          50'000 CHF
Eingezahlt:          30'000 CHF
Verwendet/Bezüge:    15'000 CHF
Aktueller Bestand:   15'000 CHF
Noch einzuzahlen:    20'000 CHF
```

Ein Bezug vermindert den vorhandenen Bestand, erhöht aber nicht erneut den noch einzuzahlenden Betrag. Damit bleibt sichtbar, dass bereits 30'000 CHF zum Projekt beigetragen wurden.

## 4. Buchungsarten

- Positive Sparzielbuchung: **Einzahlung**.
- Negative Sparzielbuchung: standardmässig **Bezug**.
- Negative Fehlbuchung: ausdrücklich **Korrektur** wählen; sie reduziert den Einzahlungsfortschritt und zählt nicht als Projektverwendung.
- **Teilfreigabe:** Ein wählbarer Betrag wird freigegeben, ohne das Ziel zu beenden. Das Ziel bleibt aktiv und kann weiter bespart werden.

Bestand und Einzahlungsfortschritt dürfen nicht negativ werden. Einzahlungen über den Zielbetrag sowie Bezüge über den vorhandenen Bestand werden blockiert.

## 5. Datenbankmigration

- Schema-Version auf **18** angehoben.
- `tracking.savings_action` ergänzt.
- `savings_goals.contributed_amount` ergänzt.
- `savings_goals.withdrawn_amount` ergänzt.
- Bestehende positive Sparzielbuchungen werden als Einzahlungen klassifiziert.
- Bestehende negative Sparzielbuchungen werden als Bezüge klassifiziert.
- Vorhandene Bestände werden in die neue Flussdarstellung übernommen.
- Die bestehende Pre-Migration-Backup-Funktion bleibt aktiv.

Vor dem ersten produktiven Öffnen von v2.2.56 sollte das vorhandene Datenverzeichnis zusätzlich unverändert aufbewahrt werden.

## 6. Cockpit-Sparziele

- Aktive Sparziele werden anhand der tatsächlich geladenen Ziele gezählt.
- Die Sparziel-Kachel wird bei vorhandenen Zielen standardmässig geöffnet.
- Fortschrittsbalken basiert auf dem Einzahlungsfortschritt, nicht auf dem nach Bezügen verbliebenen Bestand.
- Tooltip und Tabellen zeigen Eingezahlt, Verwendet, Bestand und Noch einzuzahlen getrennt.

## 7. Prüfergebnisse

| Gate | Ergebnis |
|---|---:|
| Gesamte Pytest-Suite, in vier Gruppen | **789 bestanden, 13 übersprungen, 0 fehlgeschlagen** |
| Neue v2.2.56-Regressionstests | **7 bestanden** |
| Final Release Audit | **1'000 Loops / 19'365 Checks / 0 Warnungen / 0 Fehler** |
| Release-Logik-Audit | **100 Loops / 0 Findings** |
| i18n-Audit DE/EN/FR | **PASS** |
| Python-Syntaxprüfung | **PASS** |
| Versions- und Dokumentationssynchronisierung | **PASS – 2.2.56** |
| Release-Lint und Nutzerdatenbereinigung | **PASS** |
| Bandit-Gate | **Nicht ausgeführt: Bandit-Modul fehlte in der isolierten Prüfumgebung** |

Die 13 übersprungenen Tests benötigen optionale GUI- oder Systemabhängigkeiten. Der echte Maus-Drag sowie die PySide6-Darstellung müssen deshalb auf dem Fedora-Zielsystem geprüft werden.

## 8. Releasebewertung

**Geschäftslogik, Migration, Dokumentation, Übersetzungen, Persistenz und Headless-Regressionen sind grün.**

Die Version bleibt als **Zielsystem-Testpaket** gekennzeichnet, weil folgende Punkte nur in einer echten Qt-Sitzung abschliessend beurteilbar sind:

1. Sichtbarkeit und Position des Drop-Platzhalters während realer Mausbewegungen.
2. Verschieben einer rechten Kachel bis ganz nach oben.
3. Persistenz nach Programmneustart.
4. Anzeige und Bedienung bestehender Sparziele nach Migration einer realen Datenbank.
5. Dialogauswahl Bezug/Korrektur und Teilfreigabe unter Fedora/PySide6.

## 9. Empfohlener Zieltest

1. v2.2.56 in einen neuen Ordner entpacken.
2. Den alten Programm- und Datenordner nicht löschen.
3. Programm starten und die automatische Pre-Migration-Sicherung kontrollieren.
4. **Kacheln frei anordnen** aktivieren.
5. Eine rechte Kachel über die oberste rechte Kachel ziehen und den Platzhalter prüfen.
6. Kacheln mehrfach zwischen beiden Spalten verschieben.
7. Anwendung neu starten und die gespeicherte Anordnung kontrollieren.
8. Ein Test-Sparziel mit 50'000 CHF anlegen.
9. 30'000 CHF einzahlen und 15'000 CHF als Bezug buchen.
10. Prüfen: 30'000 eingezahlt, 15'000 verwendet, 15'000 Bestand, 20'000 noch einzuzahlen.
11. Eine negative Testbuchung als Korrektur erfassen und prüfen, dass sie nicht unter verwendet erscheint.
12. Eine Teilfreigabe ausführen und prüfen, dass das Ziel aktiv bleibt.
