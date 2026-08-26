# App-Icons des BudgetManagers erzeugen

## Woher die Icons stammen

Alle App-Icons werden aus **einem** Markenbild abgeleitet:

```
resources/icons/budgetmanager-source.png    1254 x 1254, RGBA, transparent
```

Das Quellbild liegt unskaliert im Repo. Es ist Teil des Programms, kein
Build-Artefakt: nur so bleibt jede Icon-Groesse reproduzierbar erzeugbar,
ohne dass eine externe Datei zur Hand sein muss.

Daneben liegt das breite Logo-Banner, das der Startbildschirm und die
Marken-Flaechen in den Dialogen verwenden:

```
resources/icons/budgetmanager-logo.png      2172 x 724, RGBA, transparent
```

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

Skaliert wird durchgaengig mit `Image.LANCZOS` auf RGBA — die Transparenz
bleibt in jeder Groesse erhalten. Ist das Quellbild einmal nicht quadratisch,
wird es auf ein transparentes Quadrat **zentriert**, nicht beschnitten und
nicht verzerrt.

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
| Icon sieht in 16 px matschig aus | Erwartbar: das Motiv ist detailreich. Kein Nachschaerfen im Skript, sonst weichen die Groessen optisch voneinander ab. |
