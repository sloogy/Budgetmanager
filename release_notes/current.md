## 3.0.0 – 23. August 2026

Kontoauszüge kamen bisher von Hand ins Programm: Zeile für Zeile abtippen,
Kategorie suchen, Tag setzen. Ab jetzt liest der BudgetManager PDF und CSV
selbst, schlägt Typ, Kategorie und Tags vor — und bucht nichts, bevor der
Nutzer es bestätigt hat. Die Hauptversion wechselt, weil dieser Import ein
eigenes Menü, eine eigene Datenbankspur und ein eigenes Gedächtnis mitbringt.

### Bankimport aus PDF und CSV

- **Neues Menü *Import → Bank PDF/CSV…***. Bewusst nicht unter *Hilfe* oder
  *Extras*: Wer einen Kontoauszug einliest, sucht keinen Nebenpunkt in einem
  Werkzeugmenü.
- **Kontoauszüge und Kreditkartenabrechnungen.** Der generische Leser erkennt
  Trennzeichen und Zeichensatz selbst; für das Kartenformat mit
  `TransactionId`, `MerchantName` und `OriginalCurrency` gibt es einen eigenen
  strukturierten Adapter. Buchungsdatum hat Vorrang, Valuta ist nur Rückfall —
  die ZKB lässt Valuta gelegentlich leer.
- **Alles bleibt lokal.** Gelesen wird mit `pypdf` auf dem eigenen Rechner. Es
  geht keine Zeile eines Kontoauszugs an einen fremden Dienst.
- **Doppelte Zeilen bleiben draußen.** Jede Buchung bekommt eine stabile
  Kennung aus Datum, Betrag und Text; wer denselben Auszug zweimal öffnet,
  importiert ihn nicht zweimal. Der Import läuft in einer Transaktion: Er geht
  ganz durch oder gar nicht.

### Prüfen, dann buchen

- **Review-Dialog statt Blindimport.** Jede Zeile zeigt Typ, Kategorie, Tags
  und einen Haken. Was nicht angehakt ist, wird nicht gebucht.
- **Mehrfachauswahl mit Strg und Umschalt**, dazu Dropdowns, die Typ,
  Kategorie, Tags und Auswahlstatus auf alle markierten Zeilen anwenden. Bei
  40 Zeilen aus einem Monatsauszug ist das der Unterschied zwischen zwei
  Minuten und zwanzig.
- **Tags kommen aus der Kategorie.** Der Pflicht-Tag der gewählten Kategorie
  wird gesetzt und bleibt gesetzt; zusätzliche vorhandene Tags lassen sich im
  Checkbox-Dropdown bewusst ergänzen. Erfunden wird kein Tag.

### Lokale Lern-KI

- **Sie lernt nur aus Bestätigtem.** Erst nach dem Import merkt sich der
  BudgetManager, welche Kategorie und welche Tags zu einem Buchungstext
  gehören — nie aus einem Vorschlag, den der Nutzer verworfen hat.
- **Sie erfindet nichts.** Vorgeschlagen werden ausschließlich Kategorien und
  Tags, die in der Datenbank bereits existieren.

### TWINT: markieren statt buchen

- **Ein positiver TWINT-Eingang ist kein Einkommen.** Meist ist er die
  Rückzahlung einer Auslage, die als Ausgabe schon gebucht ist. Würde er als
  Einkommen laufen, stünde das Monatsergebnis doppelt falsch.
- **Der Pseudo-Typ *TWINT (KI)*** markiert solche Zeilen, ordnet sie einer
  echten Kategorie zu und lernt daraus — mit 0.00 Budgetwirkung. Er erzeugt
  niemals einen Tracking-Eintrag.
- **Die Verrechnung bleibt bis zur Prüfung aus.** Eine einmal markierte
  TWINT-Buchung wird für keine weitere Zuordnung wiederverwendet.

### Release-Härtung

- Der schnelle Push-Prüflauf läuft jetzt auch auf `feature/**`. Der
  Bankimport-Zweig brach ruff, black, mypy, den Ausnahmen-Ratchet und das
  i18n-Gate; sichtbar wurde das bisher erst beim Merge nach main, also genau
  einen Schritt zu spät.
- Zwei Prüfungen hingen am Zeilenumbruch statt an der Zusicherung und brachen,
  sobald black denselben Ausdruck anders formatierte. Sie prüfen jetzt die
  Invariante.
- **Der CSV-Fallback fasst den globalen Standarddialekt nicht mehr an.**
  Erkannte der Sniffer kein Trennzeichen, setzte der Leser `csv.excel.delimiter`
  auf `;` — das ist eine Klasse, kein Objekt: Die Zuweisung galt danach für
  jeden CSV-Leser im gesamten Prozess.
- Alle Texte des neuen Imports laufen über den Übersetzungskatalog, deutsch
  und englisch. Rückmeldungen sind nicht-modal, wie überall sonst im Programm.
