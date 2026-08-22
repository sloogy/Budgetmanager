## 2.2.71 – 22. August 2026

### Stabilität

- **Bei jedem Push nach main laufen jetzt die Gates.** Vorher lief dort gar
  nichts: Der volle Lauf hängt am Tag beziehungsweise an einem
  `[release]`-Commit, gearbeitet wird in dieser Suite aber direkt auf main.
  Ein Fehler wäre erst beim nächsten Release aufgefallen — bis zu zehn
  Arbeitsrunden später. Der neue Lauf ist bewusst schlank: Linux, ein Python,
  keine Builds, zwei bis drei Minuten. Er reagiert nur auf main, nie auf Tags,
  damit das Doppellauf-Problem nicht zurückkommt, das den Push-Trigger im
  Release-Workflow ausgeschlossen hatte.
- **Vier Tests schrieben dieselbe Workflow-Liste ab.** `["build.yml"]` stand
  viermal im Testbaum und einmal im Lint-Werkzeug; jede Änderung war an fünf
  Stellen nachzuziehen — derselbe Fehler wie bei den Versionen in Loop 6. Die
  Liste steht jetzt an einer Stelle, die Tests lesen sie von dort.
- **Beim Beenden konnte ein NameError auftreten.** Der Timer für den
  Setup-Assistenten holte sich das Hauptfenster über die Closure. Beim
  Herunterfahren löscht `del win` diesen Namen, und das folgende
  `processEvents()` kann den Timer noch feuern lassen — dann griff er auf eine
  geleerte Zelle und protokollierte einen Fehler, der wie ein Programmfehler
  aussah.
- **Zwei kaputte Einstellungsdateien in derselben Sekunde** bekamen denselben
  Namen; die zweite überschrieb die erste und die ursprüngliche Fassung war
  doch wieder weg. Außerdem wuchsen die beiseitegelegten Fassungen unbegrenzt
  — jetzt bleiben zehn.
- **Der Ausnahmen-Ratchet ist eingebaut** und prüft den Syntaxbaum statt
  Textzeilen, mit vier Regeln: keine nackten `except:`, kein
  `except BaseException`, gedeckelte stumme Schlucker, gedeckelte breite
  Handler. Er prüft alles außerhalb von Tests und Werkzeugen —
  `settings_dialog.py` mit 19 breiten Handlern stand vorher außerhalb jeder
  Prüfliste.
- **Ruff läuft jetzt im Build.** Es fehlte ganz; der NameError oben stand
  seitdem unbemerkt im Quelltext.
- **Der Release-Marker wurde im Fliesstext getroffen.** `contains()` erkennt
  `[release]` an jeder Stelle der Commit-Nachricht — auch dort, wo sie das
  Verfahren nur erklärt. Im BudgetManager blieb es nicht beim Überspringen des
  Prüflaufs: `build.yml` nutzt dieselbe Bedingung und fuhr einen vollständigen
  Release-Build für einen gewöhnlichen Arbeitscommit. Jetzt `startsWith` — der
  Marker gehört an den Anfang der Betreffzeile.
- **Zwei stumme Schlucker in der Diagnose** räumten alte Berichte auf, ohne je
  zu sagen, wenn das misslang. Wächst der Ordner weiter, obwohl aufgeräumt
  wird, war das vorher nirgends zu sehen. Beim Präzisieren zeigte ruff, dass
  das Modul gar keinen Logger hatte — der Aufruf wäre ein `NameError` gewesen.
- **Der Übersetzungs-Audit läuft jetzt mit.** `tools/i18n_audit.py` stand nur
  in der Release-Checkliste und in keinem der beiden Workflows; ein Schlüssel,
  der in allen drei Sprachen liegt, aber nirgends verwendet wird, fiel dadurch
  erst von Hand auf. Er läuft jetzt im Push- und im Release-Lauf.

### Zusammenspiel mit FPM

- **Der Zustand der Brücke ist sichtbar.** Im LifePlanner-Dialog war nicht zu
  erkennen, ob der Austausch stattfindet — und vor allem nicht, welcher Ordner
  gerade gilt. Der hängt davon ab, wie BudgetManager gestartet wurde: Im
  LifePlanner gibt ihn der Host vor, eigenständig liegt er im
  Benutzerverzeichnis. Wer beides gemischt nutzt, hat zwei getrennte Brücken
  und sieht die jeweils andere nie.
- Der Dialog zeigt jetzt den aktiven Ordner und alle drei Dateien einzeln,
  aktualisiert nach dem Neuladen und nach dem Schreiben der Outboxen.
  Unterschieden wird zwischen „noch nichts geschrieben" und „leer": Fehlt die
  Datei, hat das andere Programm nichts abgelegt — dann liegt es dort.
