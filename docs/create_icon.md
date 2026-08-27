# App-Icons des BudgetManagers erzeugen

## Woher die Icons stammen

Im Repo liegen zwei unskalierte Quellbilder aus der Suite-Bildmappe:

```
resources/icons/budgetmanager-source.png        1254 x 1254, RGBA, transparent
resources/icons/budgetmanager-logo-source.png   2172 x  724, RGBA, transparent
```

Sie sind Teil des Programms, kein Build-Artefakt: nur so bleibt jede Ausgabe
reproduzierbar erzeugbar, ohne dass eine externe Datei zur Hand sein muss.

**Ausgeliefert wird keines von beiden direkt.** Beide tragen ungleiche
unsichtbare Raender — beim Banner 37 Bildpunkte ueber und 119 unter dem
Motiv, links 112 und rechts 90. Ein solches Bild in einer Flaeche fester
Hoehe wirkt zu klein und rutscht sichtbar nach oben, obwohl das Layout
korrekt zentriert. Zusaetzlich liegt ueber dem ganzen Blatt ein Schleier mit
Alpha 1 bis 3: unsichtbar, aber fuer jede Randmessung gegen Null deckend.
`tools/create_icon.py` misst deshalb gegen eine Alphaschwelle von 8 und

* schneidet beim **Banner** die unsichtbaren Raender weg — danach ist die
  Bildkante die Motivkante,
* setzt das **Icon-Motiv** anschliessend mittig auf ein transparentes Quadrat
  mit 2 % Rand je Seite. Randlos darf ein Icon nicht sein (in 16 px klebt es
  sonst an der Kante), aber der Rand muss ringsum gleich sein, sonst haengt
  das Symbol neben anderen Symbolen sichtbar schief.

---

## Icons neu erzeugen

Voraussetzung ist Pillow (nur fuer dieses Werkzeug, keine Laufzeit-Abhaengigkeit
des Programms):

```
pip install Pillow
```

Aus dem **Projektroot** ausfuehren:

```bash
python tools/create_icon.py
```

Das Skript schreibt:

| Datei | Inhalt |
|---|---|
| `resources/icons/budgetmanager-{16,32,48,64,128,256,512}.png` | Einzelgroessen fuer Qt/Desktop |
| `resources/icons/budgetmanager.png` | 1024 px, generisches App-Icon |
| `resources/icons/budgetmanager.ico` | Mehrfachaufloesung 16/24/32/48/64/128/256 px |
| `resources/icons/budgetmanager-logo.png` | Banner fuer helle Flaechen, randlos zugeschnitten |
| `resources/icons/budgetmanager-logo-hell.png` | Dieselbe Zeichnung fuer dunkle Flaechen |

Skaliert wird durchgaengig mit `Image.LANCZOS` auf RGBA — die Transparenz
bleibt in jeder Groesse erhalten. Das Motiv wird **zentriert**, nie
beschnitten und nie verzerrt.

---

## Warum es das Banner zweimal gibt

Der Schriftzug ist zur Haelfte dunkelblau (`#0D1B3A`). Auf hellem Grund ist
das richtig; auf den dunklen Designprofilen — die Panelfarben gehen bis
`#050505` — verschwindet genau dieses halbe Wort. Ein einziges Banner kann das
nicht loesen. `tools/create_icon.py` erzeugt deshalb eine zweite Fassung, in
der Dunkelblau zu Weiss und Petrol wie Gruen aufgehellt werden; zugeordnet
wird ueber den naechstliegenden der vier Ankerpunkte der Bildmappe.

Welche Fassung erscheint, entscheidet `utils/branding.py`, nicht die
Aufrufstelle — sonst muesste jeder Dialog dieselbe Fallunterscheidung erneut
treffen und einer wuerde sie vergessen. Entschieden wird in zwei Stufen:

| Lage | Quelle |
|---|---|
| Im Hauptfenster (ThemeManager erreichbar) | `bg_panel` des aktiven Designprofils |
| Anmeldedialog, Erststart-Assistent, Startbildschirm | Qt-Palette |

Die zweite Zeile ist kein Notnagel: Diese Flaechen erscheinen, **bevor** das
Hauptfenster ein Profil anwendet. Sie liegen auf der Systemflaeche, und genau
die beschreibt die Palette. Umgekehrt waere die Palette im Hauptfenster
falsch — der ThemeManager setzt ausschliesslich ein Stylesheet und nie eine
`QPalette`, ein dunkler Desktop mit hellem Profil ergaebe sonst das helle
Banner auf heller Flaeche.

---

## Wo die Icons eingebunden sind

| Ort | Verwendung |
|---|---|
| `main.py` (`_apply_application_icon`) | Fenster-/Taskleisten-Icon, sucht `.ico`, dann `.png` |
| `BudgetManager.spec` | `icon="resources/icons/budgetmanager.ico"`, und `resources/icons` wird als Datenordner mitgeliefert |
| `installer/budgetmanager_setup.iss` | `SetupIconFile=resources\icons\budgetmanager.ico`, ausserdem wird `resources\icons\*` mitinstalliert |
| `views/startup_splash.py` / `utils/branding.py` | Logo-Banner fuer Startbildschirm und Dialoge |

Wer eine Groesse ergaenzt, aendert `PNG_SIZES` bzw. `ICO_SIZES` in
`tools/create_icon.py` und laesst das Skript erneut laufen.

---

## Troubleshooting

| Problem | Loesung |
|---|---|
| `ModuleNotFoundError: PIL` | `pip install Pillow` |
| `Quellbild fehlt: ...budgetmanager-source.png` | Das Quellbild wurde aus dem Repo entfernt — aus der Versionsgeschichte zurueckholen |
| Logo sitzt im Dialog zu hoch oder wirkt zu klein | `python tools/create_icon.py` erneut laufen lassen; vermutlich liegt eine unbeschnittene Quelldatei als `budgetmanager-logo.png` im Ordner |
| Icon sieht in 16 px matschig aus | Erwartbar: das Motiv ist detailreich. Kein Nachschaerfen im Skript, sonst weichen die Groessen optisch voneinander ab. |
