# Der gemeinsame Designkatalog

LifePlanner, BudgetManager, FountainPen Manager und FreizeitManager liefern
denselben Satz von **26 Designs** aus. Die Profildateien sind in allen vier
Programmen byteweise identisch; erzeugt und geprüft werden sie von
`tools/design_sync.py`, das ebenfalls in jedem Programm gleich liegt.

## Warum

Vorher lieferte jedes Programm eigene Profile aus, und sie liefen auseinander:

| | Designs | Rollen je Design |
|---|---|---|
| BudgetManager, LifePlanner | 26 | 29 |
| FountainPen Manager | 7 | 40 |
| FreizeitManager | 7 | 38 |

Drei Auswirkungen im Betrieb:

1. **19 Designs des Hosts kannten die Module gar nicht.** Wer im LifePlanner
   „Gruvbox – Hell“ wählte, bekam im Modul den Gruvbox-Hintergrund, aber
   Standardblau für Akzent, Karten und Statusfarben — denn was der Host nicht
   mitliefert, fällt im Modul auf das eingebaute Profil zurück.
2. **Elf Kernrollen fehlten** bei BudgetManager und LifePlanner ganz
   (`rand`, `karte_hintergrund`, `erfolg`, `warnung`, `gefahr`, `text_invers`,
   `eingabe_hintergrund`, `seitenleiste_text` …).
3. **Dieselben Designs hießen verschieden.** `Kontrast - Schwarz/Weiß` gegen
   `Kontrast Schwarzweiss`, `Hell - Warm (Sepia)` gegen `Warm Sepia - Hell`,
   `Dunkel - OLED (Kontrastarm)` gegen `OLED Schwarz`. Das Modul suchte das
   Hostprofil unter einem Namen, den es selbst nicht führte.

## Aufbau

Ein Profil führt **55 Rollen**: einen Kern von 33, den alle vier Programme
lesen, und die Bedeutungsfarben der einzelnen Programme. Jedes Programm liest,
was es kennt, und überliest den Rest — so nimmt ein Designwechsel auch die
fachlichen Farben mit.

* **Kern** — Flächen, Schrift, Akzent, Tabelle, Auswahl, Karte, Status.
* **BudgetManager** — `typ_einnahmen`, `typ_ausgaben`, `typ_ersparnisse`,
  `negativ_text`, `akzent_panel_text`, `dropdown_*`.
* **FountainPen Manager** — `bereich_sammlung`, `bereich_rotation`,
  `bereich_service`, `bereich_aktivitaet`.
* **FreizeitManager** — `dringlichkeit_*`, `ruhe_*`.

`schriftgroesse` ist in allen Programmen derselbe Maßstab: **10 heißt normal.**
Der FreizeitManager zeichnet bei 10 weiterhin 14 Punkt, rechnet den Wert aber
als Faktor darauf um.

## Regeln, die das Werkzeug durchsetzt

Fehlende Rollen werden nicht erfunden, sondern aus vorhandenen Farben desselben
Profils abgeleitet. **Ein bereits gesetzter Wert gewinnt immer** — handverlesene
Farben bleiben unangetastet. Wo zwei Programme dieselbe Rolle unterschiedlich
führen, gilt der Wert des Hosts: er verteilt das gemeinsame Design, und seine 26
Profile sind die ältesten. Darüber hinaus gilt:

* **4,5:1 für jede Schrift auf jedem Grund.** Die Schwelle stammt aus dem
  BudgetManager und ist die strengste der vier Programme.
* **Wer nachgibt, ist festgelegt.** `text` und die App- und Panelflächen sind
  das Design und bleiben; nachgeben dürfen die Schriftfarbe oder eine
  abgeleitete Fläche wie die Seitenleiste.
* **Die Seitenleiste folgt der Helligkeit des Profils.** Eine dunkle Leiste im
  hellen Design war im BudgetManager ein gemeldeter Fehler. Schrift, die auf der
  Leiste nicht lesbar ist, wird verworfen und neu abgeleitet — in
  „Solarized – Hell“ war sie exakt die Farbe der Leiste selbst.
* **Signalfarben heben sich mit mindestens 2,6:1 von der Karte ab.** Ein
  abgeleitetes Gelb erreichte hier 1,77:1 — als Ampelfarbe wertlos.
* **Gedimmte Schrift unterscheidet sich mit mindestens 1,25:1 von der normalen.**
  In „Solarized – Dunkel“ waren beide Werte buchstäblich derselbe.
* **Farben, die zusammen eine Aussage tragen, bleiben auch bei
  Farbfehlsichtigkeit unterscheidbar.** Geprüft werden Erfolg/Warnung/Gefahr, die
  Budget-Typen, die vier FPM-Bereiche und die fünf Dringlichkeitsstufen — jeweils
  gegen Protanopie, Deuteranopie und Tritanopie (Simulation nach
  Viénot/Brettel/Mollon 1999). Vorher waren **348 von 1716 Farbpaaren** für
  Rotgrünblinde nicht auseinanderzuhalten, teils sogar identisch; jetzt keines.
  Repariert wird über Helligkeit und Sättigung, nicht über den Farbton — der geht
  bei Farbfehlsichtigkeit gerade verloren.

## Reproduzierbarkeit

Jede Profildatei führt mit, was das Werkzeug getan hat:

* `_abgeleitet` — Rollen, die es in der Vorlage nicht gab. Sie werden bei jedem
  Lauf neu erzeugt, damit eine verbesserte Ableitungsregel auch greift.
* `_vorlage` — die Ausgangswerte der Rollen, die nur nachjustiert wurden. Der
  nächste Lauf rechnet die Verschiebung aus dem Original neu, statt vom bereits
  verschobenen Wert aus weiterzuschieben.

Ohne diese beiden Angaben wanderte der Katalog mit jedem Lauf ein Stück weiter.
Mit ihnen ist `build` ein Fixpunkt: der zweite Lauf ändert nichts mehr.

## Bedienung

```bash
python3 tools/design_sync.py check     # prüft die eigenen Profile
python3 tools/design_sync.py build     # erzeugt den Katalog in allen vier Programmen
python3 tools/design_sync.py preview   # HTML-Übersicht aller Designs
python3 tools/design_sync.py new --name "Mein Design" --modus dunkel --akzent "#14b8a6"
```

`build` erwartet die vier Programmordner nebeneinander und ist idempotent.
`preview` schreibt eine Seite, die jedes Design als Miniatur zeigt — mitsamt den
Signalfarben, wie sie bei Rot-, Grün- und Blauschwäche erscheinen. `new` baut aus
Name, Helligkeit und einer Akzentfarbe ein vollständiges Design: die übrigen 50
Rollen entstehen über dieselben Ableitungen und erfüllen von Anfang an, was
`check` verlangt.

`tests/test_shared_design.py` fährt dieselbe Prüfung wie `check`, damit eine von
Hand geänderte Profildatei nicht unbemerkt bleibt.
