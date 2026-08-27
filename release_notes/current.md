## 3.0.9 – 27. August 2026

Diese Fassung korrigiert die Markenbilder, die 3.0.8 eingeführt hat. Sie waren richtig ausgewählt, aber falsch aufbereitet: Das Logo saß in jeder Fläche zu klein und aus der Mitte gerückt, das Programmsymbol hing schief, und auf jedem dunklen Designprofil fehlte die Hälfte des Schriftzugs.

### Das Logo saß schief und wirkte zu klein

Die gelieferten Bilddateien tragen ungleiche durchsichtige Ränder — beim Logo-Banner 37 Bildpunkte über und 119 unter dem Motiv, links 112 und rechts 90. Bis 3.0.8 wurden sie unverändert ausgeliefert. Die Folge war nicht etwa ein fehlendes Bild, sondern etwas Unauffälligeres: Ein Logo, das in jeder Fläche fester Höhe zu klein wirkt und sichtbar nach oben rutscht — im Über-Dialog, im Anmeldedialog, im Erststart-Assistenten, im Setup-Assistenten und auf dem Startbildschirm. Wer es sah, hielt es für einen Layoutfehler; das Layout war korrekt.

- **Das Banner wird jetzt randlos zugeschnitten.** Bei gleicher angeforderter Breite rendert der Schriftzug dadurch rund zehn Prozent größer.
- **Das Programmsymbol sitzt jetzt mittig** — mit gleichem Rand auf allen vier Seiten. Vorher hing es neben anderen Symbolen in der Taskleiste sichtbar daneben.

### Auf dunklen Designprofilen fehlte das halbe Wort

Der Schriftzug ist zur Hälfte dunkelblau. Auf hellem Grund ist das richtig — die Designprofile gehen aber bis zu Panelfarben von `#050505`. Dort stand im Über-Dialog nur noch „Manager"; das Wort „Budget" war schlicht unsichtbar. Weil das Standardprofil hell ist, fiel es beim Entwickeln nicht auf.

Es gibt jetzt eine zweite Fassung des Banners für dunkle Flächen, in der Dunkelblau zu Weiß wird und Petrol wie Grün aufgehellt werden. Welche Fassung erscheint, entscheidet die Anwendung selbst: im Hauptfenster anhand des aktiven Designprofils, in Anmeldedialog, Erststart-Assistent und Startbildschirm anhand der Systemfarben — denn diese Flächen erscheinen, bevor ein Profil angewendet ist.

### Für Mitentwickelnde

Die unbeschnittenen Rohbilder bleiben im Repository und stehen jetzt getrennt neben den ausgelieferten Dateien. `tools/create_icon.py` leitet daraus alle Größen, die `.ico` und beide Bannerfassungen ab; `docs/create_icon.md` beschreibt den Weg. Die Prüfungen in `tests/test_branding_assets.py` messen das Ergebnis: randloses Banner, mittiges Symbol, Mindestfüllung der Symbolfläche und ein messbarer Helligkeitsunterschied zwischen den beiden Bannerfassungen.

Eine Besonderheit der Bildquellen ist dabei festgehalten: Über jedem Blatt liegt ein Schleier mit Alphawerten von 1 bis 3 — unsichtbar, aber für eine Randmessung gegen Null deckend. Ein Zuschnitt auf „Alpha größer als Null" hätte deshalb gar nichts weggeschnitten und den Fehler unbemerkt bestehen lassen.
