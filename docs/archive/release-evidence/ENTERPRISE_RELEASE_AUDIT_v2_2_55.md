# BudgetManager v2.2.55 – Freie Cockpit-Kachelanordnung

**Datum:** 2. August 2026  
**Status:** Zielsystem-Test erforderlich  
**Fehlerklasse:** Cockpit-Usability / Drag-and-drop praktisch nicht frei nutzbar

## 1. Ausgangslage

Im manuellen beziehungsweise fixierten Cockpit-Layout liessen sich die Kacheln für den Nutzer nicht frei verschieben.

Die Analyse zeigte zwei miteinander wirkende Ursachen:

1. Als Drag-Zone diente ausschliesslich der sehr kleine Griff `≡`. Die sichtbare Kachel-Kopfzeile selbst war nicht ziehbar.
2. Das responsive Layout wechselte bereits unter 1180 Pixel Breite in eine einzige Spalte. Auf normalen Fenstergrössen fehlten dadurch sichtbare linke und rechte Zielspalten, obwohl die Spaltenzuordnung intern gespeichert wurde.

Technisch konnte der alte Code Reihenfolge und Spalten bereits persistieren. Die Bedienfläche machte diese Funktion aber schwer auffindbar und in typischen Fenstergrössen praktisch unbrauchbar.

## 2. Umsetzung in v2.2.55

- Neue `_SectionHeader`-Drag-Zone für die komplette Kachel-Kopfzeile.
- Titel und Zähler leiten Mausereignisse an die Kopfzeile weiter.
- Der bestehende Griff `≡` bleibt als sichtbarer, barrierearmer Anfasser erhalten.
- Kopfzeile und Griff verwenden dieselbe zentrale Drag-Funktion und denselben privaten MIME-Typ.
- Interaktive Kachelinhalte bleiben von der Drag-Zone getrennt; Tabellen, Buttons und Diagramme reagieren weiterhin normal.
- Im manuellen Modus steht ab 720 Pixel Breite eine echte Zwei-Spalten-Arbeitsfläche zur Verfügung.
- Beide manuellen Spalten sind gleich breit, damit jede Zielposition eindeutig erreichbar ist.
- Bei noch kleineren Fenstern darf die umgebende Scrollansicht horizontal scrollen, statt die manuelle Arbeitsfläche unsichtbar auf eine Spalte zu reduzieren.
- Reihenfolge und Spaltenzuordnung werden nach jedem Drop weiterhin gemeinsam über `Settings.set_many()` gespeichert.
- Hilfetexte und Beschriftungen in Deutsch, Englisch und Französisch wurden auf die tatsächliche Bedienung angepasst.

## 3. Bedienung

1. Im Cockpit **Kacheln frei anordnen** aktivieren.
2. Eine Kachel an ihrer gesamten Kopfzeile oder am Griff `≡` anfassen.
3. Nach oben, unten oder in die andere Spalte ziehen.
4. Loslassen; Position und Spalte werden automatisch gespeichert.
5. Mit **Cockpit-Layout zurücksetzen** jederzeit zum Automatikmodus zurückkehren.

Das Layout bleibt rasterbasiert. Die Kacheln werden frei innerhalb der linken und rechten Spalte angeordnet, nicht pixelgenau frei schwebend. Dadurch bleibt das Cockpit responsiv, plattformstabil und dauerhaft speicherbar.

## 4. Regressionstests

Neue Gates prüfen:

1. die vollständige Kopfzeile als Drag-Quelle,
2. einen gemeinsamen Drag-/MIME-Pfad für Kopfzeile und Griff,
3. die manuelle Zwei-Spalten-Arbeitsfläche ab 720 Pixel,
4. gleich breite manuelle Spalten,
5. unveränderte atomare Persistenz von Reihenfolge und Spalte,
6. verständliche Hilfetexte in DE/EN/FR,
7. die zentrale Versionsnummer 2.2.55.

## 5. Prüfergebnisse

| Gate | Ergebnis |
|---|---:|
| Gesamte Pytest-Suite, in vier Gruppen | **782 bestanden, 13 übersprungen, 0 fehlgeschlagen** |
| Neue v2.2.55-Regressionstests | **6 bestanden** |
| Cockpit-/Layout-Regressionsblock | **26 bestanden** |
| Final Release Audit | **1’000 Loops / 19’335 Checks / 0 Warnungen / 0 Fehler** |
| Release-Logik-Audit | **100 Loops / 0 Findings** |
| i18n-Audit DE/EN/FR | **PASS** |
| Python-Syntaxprüfung | **PASS** |
| Versions- und Dokumentationssynchronisierung | **PASS – 2.2.55** |
| Release-Lint / Nutzerdatenbereinigung | **PASS** |

Die 13 übersprungenen Tests benötigen optionale GUI- oder Systemabhängigkeiten. PySide6 6.10.3 war in der isolierten Paketprüfumgebung nicht verfügbar. Deshalb konnte die Mausbewegung nicht in einer echten Fedora-Qt-Sitzung automatisiert ausgeführt werden.

## 6. Releasebewertung

**Code-, Persistenz-, Dokumentations- und Headless-Gates sind grün.**  
**Ein kurzer Fedora-Zieltest der echten Mausbedienung bleibt erforderlich.**

Die bisherige Datenstruktur wird nicht verändert. Vorhandene gespeicherte Kachelreihenfolgen und Spaltenzuordnungen bleiben kompatibel. Der Fix erweitert nur Drag-Zone und responsive Darstellung im manuellen Modus.

## 7. Empfohlener Zieltest

1. v2.2.55 in einen neuen Ordner entpacken.
2. Mit `./run.sh` starten.
3. Cockpit öffnen und **Kacheln frei anordnen** aktivieren.
4. Jede sichtbare Kachel einmal an der Überschrift verschieben.
5. Mindestens zwei Kacheln zwischen linker und rechter Spalte tauschen.
6. Kacheln innerhalb derselben Spalte nach oben und unten sortieren.
7. Zwischen Cockpit, Tracking und Übersicht wechseln.
8. Anwendung neu starten und prüfen, ob die Anordnung erhalten bleibt.
9. **Cockpit-Layout zurücksetzen** testen.
