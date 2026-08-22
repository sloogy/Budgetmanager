# Changelog

## Unveröffentlicht

### Dokumentation

- **Das README sagt jetzt zuerst, was das Programm tut.** Vorher stand dort
  Technik: ein Satz Beschreibung, dann Installationsanleitung und
  Funktionsliste. Wer wissen wollte, wofür das Programm da ist, fand einen
  Satz und danach die Bauanleitung. Der fachliche Teil steht jetzt vorn und
  beantwortet, was man mit dem Programm tut und für wen es gedacht ist; das
  Technische folgt darunter. Drei Tests halten die Reihenfolge fest.

### Sicherheit

- **Der Ausnahmen-Ratchet sah `contextlib.suppress` nicht.** Er zählt stumme
  Schlucker (`except Exception: pass`) und deckelt sie — kannte aber nur
  `except`-Handler. Dieselbe Stelle als `with contextlib.suppress(...)`
  geschrieben verschwand spurlos aus der Zählung, ohne dass sie besser
  meldete. Genau dazu rät ruffs Regel SIM105, die mit dem vollen Regelsatz
  ins Haus gekommen wäre: 17 gedeckelte Stellen hätten sich so aus dem Gate
  geschrieben. Der Ratchet zählt `suppress` jetzt mit, SIM105 bleibt
  begründet aus.
- **Der Staging-Hash des Updaters wurde zweimal berechnet.**
  `check_update` prüfte den entpackten Baum, verwarf die Prüfsumme und ließ
  `write_staged_marker` sie über denselben Baum erneut bilden. In die Marke
  kam damit nicht die Summe, die geprüft wurde, sondern eine zweite — über
  einen Baum, der inzwischen ein anderer sein kann. Jetzt wird die geprüfte
  Summe durchgereicht; der zweite volle Lauf über alle Dateien entfällt.

### Funktion

- **Die Massenbearbeitung von Kategorien war nicht erreichbar.**
  `BulkCategoryEditDialog` ist gebaut und getestet, hing aber an keinem
  Menü — ein ungenutzter Import ließ ihn benutzt aussehen. Er hängt jetzt im
  Kontextmenü des Budget-Tabs, sobald mehrere Kategorien markiert sind:
  Fixkosten, Wiederkehrend, Fälligkeitstag und Forecast-Modus für alle auf
  einmal. Handbuch in drei Sprachen nachgeführt.
- **Ein Abbruch galt als Korrektur.** Der Dialog zur Sparziel-Entnahme
  prüfte nur auf "Abbrechen" und "Entnahme"; alles andere — auch ein Dialog,
  der ohne Klick endet — fiel in den Korrektur-Zweig und veränderte den
  Sparstand. Jetzt wird der Korrektur-Knopf ausdrücklich geprüft, und der
  unbekannte Fall bricht ab.

### Stabilität

- **Der Push-Gate-Lauf war rot.** Die Schwärzung des Crashlogs suchte den
  Ausnahmetyp zweimal — einmal in der Bedingung, einmal im Text. Für mypy war
  der zweite Treffer `None`-fähig, und `mypy model/` läuft im Gate mit. Der
  Treffer wird jetzt einmal gebunden.

- **`sqlite3.Row` ist kein dict.** Beim Einführen des vollen Regelsatzes
  schrieb ruffs SIM118 `"parent_id" in r.keys()` zu `"parent_id" in r` um.
  Bei einer `Row` prüft `in` die *Werte*, nicht die Spaltennamen — jede
  Kategorie galt danach als wurzellos, und die Baumansicht zeigte
  Elternkategorien als eigenständige Einträge. Der Test fing es; die Regel
  ist für `model/category_model.py` mit Begründung abgeschaltet.

### Ordnung

- **Zwanzig Module hatten ihren Docstring verloren.** Zwei automatisierte
  Einfügeläufe hatten `from __future__ import annotations` und einen
  Logger-Block davor geschoben — damit war das Stringliteral kein Docstring
  mehr, `__doc__` war `None` und `help(modul)` leer. Der Text stand noch da,
  nur wirkungslos. In FPM traf es dieselben vier mitkopierten Dateien. Ein
  Test hält den Zustand fest.
- **`logger = logging.getLogger(__name__)` stand in 51 Dateien mitten im
  Importblock.** Jeder folgende Import stand damit nach einer Anweisung, und
  die Importordnung ließ sich nicht prüfen: Ein Sortierer sieht zwei Blöcke
  statt einem.
- **Das Lint-Gate prüfte nur `E9,F63,F7,F82`** — Syntaxfehler und unbekannte
  Namen —, während FreizeitManager und LifePlanner längst den vollen Satz aus
  einer `ruff.toml` fuhren. Der BudgetManager hat jetzt dieselbe Grundlage;
  die Auswahl steht in `ruff.toml`, kein Aufrufer übersteuert sie mehr mit
  eigenem `--select`. Rund 1000 Funde bereinigt, darunter 199 tote Importe,
  254 unsortierte Importblöcke und 15 tote Zuweisungen.
- **Ein Kategorienlauf je Tabellenzeile lief ins Leere.**
  `_update_tree_label_row` lud zu jeder Zeile die volle Kategorienliste, um
  drei Flags zu setzen, die niemand mehr liest — bei hundert Kategorien
  hundert überflüssige Abfragen je Neuaufbau.
- **Ein Test prüfte nur die Hälfte.** Sein Erwartungs-`dict` führte
  denselben Dateinamen zweimal; die zweite Zeile gewann still, die erste
  Erwartung wurde nie geprüft. Jetzt eine Liste von Paaren.

- **Die Formatprüfung lief nur über `model/`.** `views/`, `utils/`,
  `updater/`, `tools/` und `tests/` waren zwar formatiert, aber ungeprüft —
  eine Änderung dort brach die Formatierung, ohne dass ein Gate anschlug.
  Genau das passierte beim Umstellen des Auditpfads. `black --check` deckt
  jetzt jede Python-Datei ab, und ein Test hält die Abdeckung fest: Ein neues
  Verzeichnis fällt auf, weil kein Prüfziel es enthält. 29 Dateien einmalig
  nachformatiert.
- **Fünfzehn Auditmatrizen lagen im Hauptordner**, eine je Fassung seit
  2.2.60, dazu vier Nachweise aus 2.2.60 und 2.2.67. Sie liegen jetzt unter
  `docs/archive/release-evidence/`, und
  `tools/final_release_audit_1000.py` schreibt seine Matrix beim Lauf direkt
  dorthin — der Hauptordner wächst nicht mehr mit jedem Release.
- **Der Index des Beweisarchivs nannte 59 von 129 Dateien.** Von Hand
  gepflegt driftete er; wer eine Datei nicht im Index fand, hielt sie für
  nicht vorhanden. `tools/release_evidence_index.py` erzeugt ihn jetzt aus
  dem Verzeichnis, ein Test hält ihn aktuell.

### Funktion

- **Die Kategorie im Zahlungsimport wählt man jetzt wie in der
  Schnelleingabe.** Der Importdialog hatte eine schlichte Auswahlliste; die
  Schnelleingabe hat seit langem ein Suchfeld über einem gefilterten,
  gruppierten Dropdown. Bei zweihundert Kategorien ist das der Unterschied
  zwischen Tippen und Scrollen. Die Auswahl steht jetzt als eigenes Widget da
  und wird an beiden Stellen benutzt.
- **Kategorie für mehrere Vorschläge auf einmal.** Unter der Importübersicht
  stehen Typ, Kategorie und **Kategorie zuweisen**. Wer zwanzig Zahlungen
  derselben Art importiert, öffnet nicht mehr zwanzigmal den Bearbeiten-Dialog.
  Übernommene und abgelehnte Vorschläge bleiben unberührt — ihre Buchung
  existiert und würde einer nachträglichen Änderung nicht folgen. Neue
  Kategorien legt die Übersicht bewusst nicht an; das bleibt dem
  Bearbeiten-Dialog mit seiner ausdrücklichen Rückfrage.

### Fehlerdiagnose

- **Der Diagnosebericht nennt den Fehler wieder.** Aus einem eingesandten
  Bericht liess sich nichts schliessen: Das App-Log war Zeile für Zeile
  geschwärzt — und die Schlusszeile jedes Tracebacks, die einzige, die sagt,
  *was* schiefging, gleich mit. Ein `KeyError` war von einem Datenbankfehler
  nicht zu unterscheiden. Der Ausnahmetyp bleibt jetzt stehen, sein Text
  nicht: Der Typ ist ein Klassenname aus dem Programmcode und nennt keine
  Kategorien, Beträge oder Kommentare.
- **Der Kopf im Crash-Log trägt Zeit, Version und Prozessnummer.** Vorher
  hängte jeder Start dieselbe Zeile an; im eingesandten Bericht standen zwölf
  gleichlautende Zeilen und ein Absturzdump, und welcher Start dazugehörte,
  war daraus nicht zu erkennen.

### Werkzeuge

- **Der Rückfall auf die „flache Kategorienliste“ war keiner.**
  `list_for_tracking_dropdown` ruft intern dieselbe gruppierte Abfrage auf —
  fällt die aus, fällt der Rückfall mit. Im Import liest er jetzt
  `list_names`.

### Dokumentation

- **Kapitel 6.6 im Handbuch, in allen drei Sprachen:** wie Zahlungen aus
  anderen Programmen der Suite geprüft, kategorisiert und übernommen werden.
  Die Funktion gab es, beschrieben war sie nirgends.

## 2.2.73 — 22. August 2026

Inhaltlich 2.2.72: Der Tag v2.2.72 war gesetzt, bevor der Bau gruen war, und
Release-Tags werden hier nie verschoben. Der kaputte Tag bleibt als Beleg
stehen, veroeffentlicht wird 2.2.73.


### LifePlanner-Integration

- Modulmanifest auf `lifeplanner.module.v2` angehoben und die kompatible Host-Reihe dauerhaft als `>=0.5.15,<0.6` hinterlegt.
- Bridge-Verträge für BudgetManager → FPM, FPM → BudgetManager und Sparziele sind deklarativ im Modulmanifest beschrieben.
- Der LifePlanner kann die Host-Kompatibilität damit nicht nur beim Installieren, sondern auch bei späteren Starts erneut prüfen.
- Der `.lpmodule`-Builder übernimmt `requires_host` aus derselben Manifestquelle, sodass Paket- und Laufzeitvertrag nicht auseinanderlaufen können.

### Release-Härtung

- Reproduzierbarer `release-trigger/vX.Y.Z`-Vorlauf ergänzt; fehlgeschlagene Vorläufe können als `release-trigger/vX.Y.Z-rN` erneut gestartet werden, ohne den eigentlichen Release-Tag zu verschieben.
- Versionsdateien werden synchronisiert, `main` wird nur per Fast-Forward übernommen und Release-Tags werden niemals überschrieben.
- Der Prepare-Lauf startet den vollständigen bestehenden Build auf exakt derselben Commit-SHA und übernimmt dessen Exit-Status.
- `release-prepare.yml` ist im strengen Lint-/Release-Prozedurcheck zugelassen, darf aber selbst keine Assets oder GitHub Releases veröffentlichen; `build.yml` bleibt der einzige Publisher.
- Der vorher rote Gate-Lauf durch die alte Workflow-Allowlist ist damit behoben, ohne den Gate zu lockern.

### Stabilität

- **Der Release-Lauf schrieb an einer Workflow-Datei und durfte das nie.**
  Vier Anläufe für 2.2.72 scheiterten an derselben Stelle: Der Prepare-Lauf
  trug `workflow_dispatch` selbst in `.github/workflows/build.yml` ein, und
  GitHub lehnt jeden Push ab, der eine Workflow-Datei ändert, wenn er nur mit
  dem GITHUB_TOKEN kommt. Das ist keine Fehlkonfiguration, die man wegdreht —
  ein Lauf, der seine eigenen Auslöser umschreiben kann, ist genau das, was
  diese Sperre verhindern soll. Der Trigger steht jetzt fest in `build.yml`,
  und der Prepare-Lauf prüft vor dem Push, ob der Release-Commit
  `.github/workflows` berührt.
- **Das Formatgate urteilte über die Werkzeugversion, nicht über den Code.**
  black wollte `model/bridge_registry.py` umformatieren — die Datei war lokal
  mit 26.5.1 formatiert, die CI nimmt die gepinnte 25.1.0, und beide setzen
  die Leerzeile hinter dem Modul-Docstring verschieden. Derselbe Riss bei
  mypy: lokal 2.3.1 meldet drei Slice-Fehler, die gepinnte 1.15.0 kennt sie
  nicht. Die Pinnung war richtig — sie galt nur in der CI.
  `tools/gepinnte_werkzeuge.py` führt black, ruff und mypy jetzt in genau der
  Version aus, die in requirements steht. Release-Checkliste, offene Aufgaben
  und Feature-Übersicht rufen den Wrapper auf.

### Funktion

- **Beide Startarten lesen aus allen bekannten Brückenordnern.** Im
  LifePlanner gibt der Host den Ordner vor, eigenständig liegt er im
  Benutzerverzeichnis; wer gemischt startete, hatte zwei getrennte Brücken.
  Geschrieben wird weiterhin nur in den aktiven.

### Werkzeuge

- **Der Übersetzungs-Audit lief in keinem der beiden Workflows.**
  `tools/i18n_audit.py` stand nur in der Release-Checkliste; dass
  `lifeplanner_import.bridge_status_title` in allen drei Sprachen liegt und
  nirgends verwendet wird, fiel deshalb erst von Hand auf — die Überschrift
  über dem Brückenzustand fehlte im Dialog und wird jetzt angezeigt. Das
  Werkzeug läuft im Push- und im Release-Lauf mit.
- **`sync_version` zieht nur den Kopfbereich einer Datei nach.** Die
  `--base-url`-Zeile im Beispiel von `updater/generate_manifest.py` stand
  knapp ausserhalb und klebte seit 2.2.63 fest.
- **VERSION_INFO.txt:** `sync_version` benennt den obersten Block auf die
  aktuelle Version um. Seit 2.2.67 traf das den 2.2.66-Block, weil kein
  Release seither einen eigenen davorgesetzt hat.

### Dokumentation

- **README.md und README_INSTALLATION.md standen inhaltlich auf 2.2.63**,
  während die Kopfzeile mitlief: Downloadnamen, Prüfsummenbefehle und der
  Hinweis, der In-App-Updater sei abgeschaltet, waren falsch. Beide sind nach
  Ablauf geordnet, die Versionsgeschichte ist gekürzt, Notstartschalter und
  Systemvoraussetzungen sind dokumentiert.
- **Die Release-Checkliste** beschrieb `build.yml` als einzigen Workflow und
  den Tag als einzigen Auslöser; der Tag wird jetzt aus `app_info.py`
  abgeleitet statt fest eingetragen.

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
- **Black lief nur im Release-Lauf.** Der Push-Lauf prüfte die Formatierung
  nicht, deshalb fiel erst der Release-Build zu 2.2.71 über drei ungeformte
  Dateien in `model/` — nach dem Tag, mit rotem Build und ohne Artefakte.
  `black --check model/` läuft jetzt auch bei jedem Push.

### Sicherheit

- **Die Dateirechte schlugen still fehl.** `_secure_file` und
  `_secure_bundle_file` setzen `0600` auf Schlüsselmaterial und Sicherungen und
  schluckten bisher jeden Fehlschlag. Blieb eine Datei weltlesbar, war das
  nirgends zu sehen.
- **`users.json` wurde atomar geschrieben, aber mit fester `.tmp`-Endung**, die
  sich zwei gleichzeitig laufende Instanzen teilen. Bei Quick-Konten steht dort
  der Datenbankschlüssel im Klartext.

### Wo „atomar" draufstand, fehlte der fsync

- Umbenennen ist atomar, aber ohne `fsync` steht der Inhalt zu diesem Zeitpunkt
  nur im Cache — nach einem Stromausfall kann eine leere Datei an den Platz
  geschoben werden. Einstellungen, Brückendateien und Themes laufen jetzt über
  denselben Helfer, der beides tut.
- Die beiden Brücken-Outboxen gingen zeilenweise direkt in die Zieldatei. Brach
  der Lauf ab, lag dort eine JSONL-Datei mit abgeschnittener letzter Zeile — von
  einer vollständigen nicht zu unterscheiden.
- Fehler, die folgenlos bleiben dürfen, laufen über ein gemeinsames Werkzeug:
  Sie blockieren weiterhin nichts, hinterlassen aber eine Spur im Log.

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

## 2.2.70 – 22. August 2026

### Sicherheit

- **Die Brücke zu FPM** liegt eigenständig offen im Benutzerverzeichnis.
  Ordner und Dateien bekommen jetzt 0700 bzw. 0600 — es sind dieselben
  Buchungen und Sparziele wie in der Datenbank.
- **Update-Archive** werden beim Entpacken auch auf die Zahl der Einträge
  geprüft; die übrigen Grenzen galten hier schon.

### Stabilität

- **Eine unlesbare Einstellungsdatei** wird als `.kaputt-<zeitstempel>`
  beiseitegelegt, statt beim nächsten Speichern überschrieben zu werden. Oft
  ist nur ein Zeichen falsch und sie liesse sich von Hand retten.

### Darstellung

- Radien und Innenabstände wachsen mit der eingestellten Schrift, wie schon
  die Schriftgrössen und Mindesthöhen seit 2.2.68.

## 2.2.69 – 21. August 2026

### Radien und Abstände wachsen ebenfalls mit

Schriftgrössen und Mindesthöhen folgten seit 2.2.68 der Einstellung, die
Radien und Innenabstände noch nicht. Bei grosser Schrift wirkten die Rundungen
dadurch verloren. Bei 10pt bleibt das Aussehen unverändert.

## 2.2.68 – 21. August 2026

### Die Brücke zu FPM zieht von selbst nach

Ein im BudgetManager angelegtes Sparziel kam in FPM nie an. Die Ursache lag
nicht im Export, sondern darin, wann er lief: BudgetManager schrieb seine
Outboxen — Ausgabenvorschläge *und* Sparziele — ausschliesslich dann, wenn
jemand im LifePlanner-Dialog ausdrücklich auf den Knopf drückte. Wer diesen
Dialog nie öffnete, dessen Daten erreichten die Brücke nie, und in FPM blieb
die Anzeige einfach leer.

- Die Brücke wird jetzt nach jeder Datenänderung nachgezogen, beim Schliessen
  und einmal beim Start.
- Träge gebündelt: Zehn Änderungen kurz hintereinander ergeben einen Lauf,
  nicht zehn.
- Ein Fehler dabei bleibt folgenlos und geht ins Log. Die Brücke ist eine
  Spiegelung und darf die Buchhaltung nie blockieren.

### Der Kontrakt zu FPM ist jetzt geprüft

Beide Programme haben ihre Seite der Brücke bisher mit selbst erzeugten Daten
getestet. Jede Seite war grün — gesprochen haben sie trotzdem aneinander
vorbei: Sparziele gehen als `fpm.savings-goal.v1` heraus, FPM las nur die
Unterstrich-Form. Neue Kontrakttests prüfen beide Richtungen gegen Proben aus
der Gegenseite.

### Das Design folgt auf Wunsch dem Betriebssystem

- Neue Wahl „Wie das System" im Design-Dropdown. Stellt das Betriebssystem auf
  dunkel um, wechselt BudgetManager mit.
- Gespeichert wird die Wahl selbst, nicht der aufgelöste Modus — sonst stünde
  nach dem Neustart wieder „Hell" da.
- Der übersetzte Hinweistext hängt jetzt als Tooltip am Dropdown; er war in
  allen drei Sprachen vorhanden, wurde aber nirgends angezeigt.

## 2.2.67 – 21. August 2026

### Hotfix: Theme-Editor und Update-Diagnose

- Der Theme-Editor verwendet die Schliessen-Leiste jetzt im korrekten Layout-Scope; der `NameError: name 'outer' is not defined` ist behoben und regression-getestet.
- Signatur-/Vertrauensfehler des Updaters werden nicht mehr faelschlich als Netzwerk-/Manifestfehler ausgegeben.

### Einmaliger Trust Bridge fuer v2.2.61 – keine Neuinstallation

BudgetManager v2.2.61 unterstuetzt bereits einen externen Update-Public-Key unter `_internal/resources/update_signing_public_key.b64`. Der Release erzeugt deshalb `BudgetManager-v2.2.61-Trust-Bridge.ps1`. Das Skript hinterlegt ausschliesslich den oeffentlichen Ed25519-Vertrauensanker in der bestehenden Installation und startet danach den unveraenderten signaturpruefenden Updater.

Ein vorhandener abweichender Key wird nicht ueberschrieben. Der private Signierschluessel ist niemals Bestandteil des Bridge-Skripts. Damit kann eine installierte 2.2.61 direkt auf 2.2.67 aktualisiert werden, ohne Neuinstallation und ohne die Signaturpruefung auch nur temporaer abzuschalten.

## 2.2.66 – 21. August 2026

### Signierung braucht cryptography

Der Releaselauf zu 2.2.65 brach im Schritt „Build release assets“ ab:
`ModuleNotFoundError: No module named 'cryptography'`. Der `manifest`-Job
installierte bisher gar keine Abhängigkeiten — er brauchte vorher keine. Er
installiert die Bibliothek jetzt mit der Version aus `requirements.txt`.

## 2.2.65 – 21. August 2026

### Update-Signatur wieder vollständig

Das eingebaute Update lehnte bisher **jede** Version ab — mit „Kein eingebetteter
Update-Public-Key gefunden“ beziehungsweise einer fehlenden `latest.json.sig`.

Die Ursache war nicht die letzte Version, sondern eine nie verbundene Kette: Der
Schlüsselgenerator, die Signierung in `tools/build_release_assets.py` und die
Prüfung in `updater/manifest_signing.py` waren vollständig da — aber im
Repository fehlten Secret und Variable, der Workflow reichte beide nirgends
durch, und der gebaute Programmordner enthielt gar keinen Vertrauensanker.

- **Vor dem PyInstaller-Lauf** legt der Schritt „Embed update trust anchor“ den
  öffentlichen Schlüssel aus der CI-Variable in `resources/` ab. Fehlt die
  Variable, bricht der Build ab — ein Programm ohne Vertrauensanker ist ein
  Programm, das sich nie aktualisieren lässt.
- **Beim Erzeugen der Release-Dateien** stehen beide Schlüssel in der Umgebung,
  sodass `latest.json.sig` entsteht.
- **Das Release-Gate** lässt ein Release ohne Signatur nicht mehr durch.
- `resources/update_signing_public_key.b64` und das Schlüsselverzeichnis sind
  von der Versionsverwaltung ausgenommen.

> **Einmalig nötig:** Erst ab 2.2.65 trägt das Programm den Vertrauensanker. Eine
> ältere Installation muss einmal von Hand auf 2.2.65 gebracht werden; danach
> funktioniert das eingebaute Update wieder von selbst.

## 2.2.64 – 21. August 2026

### Ein gemeinsamer Designkatalog

LifePlanner, BudgetManager, FountainPen Manager und FreizeitManager liefern
jetzt dieselben **26 Designs** aus — byteweise dieselben Profildateien, erzeugt
und geprüft von `tools/design_sync.py`.

**Warum das nötig war.** Vorher kannten BudgetManager und LifePlanner 26 Designs
mit 29 Rollen, FPM und FreizeitManager sieben mit 38–40. Wer im LifePlanner ein
Design wählte, das ein Modul nicht selbst mitbrachte, bekam dort dessen
Hintergrund, aber Standardblau für Akzent, Karten und Statusfarben — was der
Host nicht mitliefert, fällt im Modul auf das eingebaute Profil zurück. Und drei
Designs trugen in beiden Lagern verschiedene Namen (`Kontrast - Schwarz/Weiß`
gegen `Kontrast Schwarzweiss`, `Hell - Warm (Sepia)` gegen `Warm Sepia - Hell`,
`Dunkel - OLED (Kontrastarm)` gegen `OLED Schwarz`), sodass das Modul das
Hostprofil unter einem Namen suchte, den es selbst nicht führte.

- **55 Rollen je Profil** — ein Kern von 33 für alle Programme plus die
  Bedeutungsfarben der einzelnen. Fehlende Rollen wurden nicht erfunden, sondern
  aus vorhandenen Farben desselben Profils abgeleitet; handverlesene Werte
  blieben unangetastet. Wo zwei Programme dieselbe Rolle unterschiedlich
  führten, gilt der Wert des Hosts.
- **Der Name des Hosts gilt.** Gespeicherte Einstellungen lösen über Aliase
  weiterhin auf.
- **Die Schriftgröße bedeutet überall dasselbe:** 10 heißt normal. Der
  FreizeitManager zeichnet dabei weiterhin 14 Punkt und rechnet den gemeinsamen
  Wert als Faktor darauf um.

### Lesbarkeit ist jetzt Bedingung, nicht Zufall

- **4,5:1 für jede Schrift auf jedem Grund** — die strengste der vier bisherigen
  Schwellen, übernommen aus dem BudgetManager.
- **Die Seitenleiste folgt der Helligkeit des Profils.** Schrift, die auf ihr
  nicht lesbar ist, wird verworfen und neu abgeleitet — in „Solarized – Hell“
  war sie exakt die Farbe der Leiste selbst.
- **Signalfarben heben sich mit mindestens 2,6:1 von der Karte ab.** Ein
  abgeleitetes Gelb erreichte 1,77:1 und war als Ampelfarbe wertlos.
- **Gedimmte Schrift unterscheidet sich messbar von der normalen.** In
  „Solarized – Dunkel“ waren `text` und `text_gedimmt` buchstäblich derselbe Wert.
- **Farbfehlsichtigkeit wird geprüft.** Erfolg/Warnung/Gefahr, die Budget-Typen,
  die vier FPM-Bereiche und die fünf Dringlichkeitsstufen müssen auch bei
  Protanopie, Deuteranopie und Tritanopie unterscheidbar bleiben (Simulation nach
  Viénot/Brettel/Mollon 1999). Vorher waren **348 von 1716 Farbpaaren** nicht
  auseinanderzuhalten, teils sogar identisch — jetzt keines. Repariert wird über
  Helligkeit und Sättigung, nie über den Farbton; der geht dabei gerade verloren.

### Werkzeug

- `tools/design_sync.py check` prüft die eigenen Profile, `build` erzeugt den
  Katalog in allen vier Programmen, `preview` schreibt eine HTML-Übersicht (mit
  den Signalfarben, wie Farbfehlsichtige sie sehen), und `new --name … --akzent …`
  baut aus einer Akzentfarbe ein vollständiges, regelkonformes Design.
- **`build` ist ein Fixpunkt.** Jede Profildatei führt mit, welche Rollen erzeugt
  (`_abgeleitet`) und welche nur nachjustiert wurden (`_vorlage`) — sonst wanderte
  der Katalog mit jedem Lauf ein Stück weiter, statt reproduzierbar zu sein.
- `tests/test_shared_design.py` hält den Katalog zusammen;
  `docs/GEMEINSAMES_DESIGN.md` erklärt Aufbau und Regeln.


### Weiteres
- Die 26 bestehenden Profile bleiben nah an ihrer Vorlage: 63 von 598 Farben
  wurden angepasst, im Mittel um einen kaum sichtbaren Betrag.
- `tools/sync_version.py` zieht jetzt auch README, Installationsanleitung,
  FEATURES, die Handbücher, den Updater und die Release-Notizen nach — und zwar
  nur im Kopf jeder Datei, damit die Versionshistorie darunter stehen bleibt.

## 2.2.63 – 20. August 2026

### Zentrale Darstellung im LifePlanner
- BudgetManager übernimmt beim Start im LifePlanner das dort zentral gewählte Designprofil. Der Host legt es im Austauschformat `lifeplanner.theme.v1` ab und nennt den Pfad in `LIFEPLANNER_THEME_FILE`.
- Die lokal gespeicherte Profilwahl (`active_design_profile`) wird dabei **nicht** überschrieben: im Standalone-Betrieb gilt weiterhin das eigene Profil. Wer im Host manuell umstellt, bleibt für die laufende Sitzung dabei.
- Ein Profil, das nur der Host mitbringt, bleibt darstellbar — die Farbwerte kommen aus der Datei, nicht aus dem lokalen Profilordner.
- Ohne LifePlanner ist die Umgebungsvariable leer und es ändert sich nichts.

## 2.2.62 – 20. August 2026

### LifePlanner-Modulrelease
- Der taggesteuerte GitHub-Workflow baut BudgetManager zusätzlich als installierbares `.lpmodule` für Windows x86_64 und Linux x86_64.
- Beide Modulpakete werden bewusst unsigned für die lokale LifePlanner-/LiveManager-Installation veröffentlicht; der Host verlangt dabei eine manuelle Vertrauensbestätigung.
- Der Release prüft Paketstruktur, Payload-Hash, eingebettetes `module.json` und plattformspezifische Runtime vor dem Upload; jedes Paket erhält zusätzlich eine eigene SHA-256-Datei.
- Portable Pakete, Windows-Setup, Updater-Manifest und SBOM bleiben unverändert Bestandteil desselben einzigen Releaseworkflows.

## 2.2.61 – 19. August 2026

### QtCharts- und Release-Hotfix
- Ersetzte Übersichtsdiagramme bleiben bis zu ihrem nativen Qt-`destroyed`-Signal als starke Python-Referenz erhalten und werden verzögert freigegeben. Das schließt den verbliebenen Shiboken-Lebensdauerpfad beim Refresh.
- Ein Regressionstest schützt alle sechs Diagrammaufbaupfade; ein realer QtCharts-Stresstest steht für Zielsystemprüfungen bereit.
- Der DAU-Enterprise-Audit ignoriert virtuelle Umgebungen zuverlässig und analysiert keine PySide6-/Jinja-Fremdquellen mehr als Projektcode.
- Der Windows-Releasejob installiert das erzeugte Setup nun unbeaufsichtigt, startet die tatsächlich installierte Anwendung mit ihrem Release-Selbsttest und deinstalliert sie anschließend wieder.
- Die Deinstallation entfernt den Installationsmarker, lässt den gewählten Nutzerdatenordner jedoch bewusst bestehen.
- Installer, portable Windows-/Linux-Pakete, Manifest und Prüfsummen bleiben Bestandteile desselben taggesteuerten Releaseworkflows.

## 2.2.60 – 19. August 2026

### Finale Release-Härtung
- GitHub Actions auf genau einen Tag-Workflow reduziert: `build.yml` baut Windows und Linux, erzeugt den Windows-Installer, prüft die portablen Pakete und veröffentlicht alle Release-Assets.
- BudgetManager-Tag-Releases sind wieder klar abgegrenzt: portable Windows-/Linux-Pakete, Windows-Setup, Updater-Dateien und GitHub-Quellcodearchive; LifePlanner-Checks und `.lpmodule`-Uploads laufen nicht in diesem Repository.
- Nativen Fedora-/Wayland-Abort in `CompactChart` behoben: Diagramme werden atomar ersetzt und erst im nächsten Event-Loop-Durchlauf entsorgt; `removeAllSeries()` wird im Refresh-Pfad nicht mehr verwendet.
- Diagnose-ZIPs geben keine rohen App-Logmeldungen mit Kategorien, Beträgen, Kommentaren oder externen IDs mehr weiter; technische Metadaten bleiben erhalten und Home-Pfade werden maskiert.
- LifePlanner-Import verwendet nicht-modale, barrierearme Warnhinweise; das Tastatur-Gate wächst ohne fragile Dialog-Zählkonstante mit.
- Vollständige Black-Formatierung und alle Mypy-Befunde des verpflichtenden Tag-Workflows behoben.
- `cryptography` von 49.0.0 auf 50.0.0 aktualisiert; CVE-2026-69247 ist damit geschlossen, Hash-Locks für Linux und Windows sind erneuert.
- Reale lokale PySide6-/QtCharts-Suite: 840 Tests bestanden; Bandit und Online-`pip-audit` ohne Blocker.

### Enterprise-, Funktions- und DAU-Härtung
- Einstellungsworkflow aus dem 3.600-Zeilen-Hauptfenster in `views/main_window_settings.py` ausgelagert; Architektur-Gate wieder grün.
- Versions- und Veröffentlichungsdatum über `app_info.py`, Installer, Updater, Modulmanifest und Dokumentation synchronisiert.
- Release-Artefakte werden vor Auslieferung konsequent von `__pycache__`, `.pytest_cache` und Bytecode bereinigt.
- Neue unabhängige Audit-Evidenz für Funktionsumfang, DAU-Bedienung, Sicherheit, Backup/Restore, LifePlanner-Vertrag und Releaseprozess.

## 2.2.59 – 3. August 2026

### Selektiver Merge auf der verbindlichen LifePlanner-Basis
- Ausgangsbasis bleibt `v2.2.56 LIFEPLANNER_FIXED`; v2.2.58 wurde nicht pauschal darüberkopiert.
- Alle vier Host-Variablen bleiben erhalten: `BUDGETMANAGER_DATA_DIR`, `LIFEPLANNER_MODULE_DATA_DIR`, `LIFEPLANNER_BRIDGE_DIR` und `LIFEPLANNER_CENTRAL_UPDATER`.
- Signierte `.lpmodule`-Pakete werden weiterhin für Windows x86_64 und Linux x86_64 gebaut; zusätzlich wird je Paket eine SHA256-Datei erzeugt.
- FPM-Ausgaben und Sparziele bleiben als getrennte, reviewbare Outbox-Exporte verfügbar.

### Sichere LifePlanner-/FPM-Inbox
- Persistenter Bearbeitungsstatus für neue, geänderte, abgelehnte und verwaiste Vorschläge.
- Upserts aktualisieren vorhandene Zielbuchungen statt Dubletten anzulegen.
- Datum, Typ, Kategorie, Betrag und Beschreibung können vor der Übernahme bearbeitet werden.
- Fremdwährungen erfordern eine ausdrückliche Umrechnungsbestätigung.
- Größen-, Zeilen-, Datensatz-, ID-, Datums- und Betragsvalidierung schützt die Importgrenze.
- Offene Vorschläge werden in der Seitenleiste gezählt; es findet weiterhin keine automatische Finanzbuchung statt.

### Monatsstatus nach Lohnzyklus
- Der Cockpit-Monatsstatus läuft vom tatsächlichen beziehungsweise hinterlegten Lohneingang bis zum Tag vor dem nächsten Lohntag.
- Trendpfeile vergleichen den vorherigen Lohnzyklus; ohne erkennbare Lohnkategorie bleibt der Kalendermonat als Fallback.

### Erhaltene Basisfunktionen
- Unabhängige Cockpit-Spalten mit sichtbarer Drop-Vorschau.
- QtCharts-Lebensdauer-Härtung.
- Sparziel-Flussbestand mit Einzahlung, Bezug, Korrektur und Teilfreigabe.
- Standalone-Betrieb, verschlüsselte Datenbank, Backups und eigener Updater außerhalb des LifePlanner-Modus.

## 2.2.55 – 2. August 2026

### Cockpit-Kacheln wirklich frei anordnen
- Im manuellen Layout ist nicht mehr nur der kleine `≡`-Griff, sondern die gesamte Kachel-Kopfzeile eine Drag-Zone.
- Der manuelle Modus verwendet ab 720 px eine echte, gleich breite Zwei-Spalten-Arbeitsfläche. Zuvor kollabierte das Cockpit bereits unter 1180 px in eine Spalte und wirkte dadurch nicht frei verschiebbar.
- Kacheln können innerhalb einer Spalte umsortiert oder zwischen linker und rechter Spalte verschoben werden. Reihenfolge und Spaltenzuordnung bleiben gespeichert.
- Kachelinhalte wie Tabellen, Schaltflächen und Diagramme bleiben normal bedienbar, da nur die Kopfzeile zieht.
- Deutsche, englische und französische Hilfetexte erklären die Bedienung eindeutig.

### Qualitätssicherung
- Neue Regressionstests sichern Kopfzeilen-Drag, gemeinsamen MIME-Pfad, Zwei-Spalten-Arbeitsfläche, Persistenz und Übersetzungen.

## 2.2.54 – 2. August 2026

### Kritischer Cockpit-/QtCharts-Absturz behoben
- Der native Segfault nach dem Hinzufügen von Buchungen wurde auf `QtCharts::AreaChartItem::fixEdgeSeriesDomain` zurückgeführt.
- `QAreaSeries` besitzt ihre obere `QLineSeries` nicht. Die Linie wird deshalb dauerhaft als Instanzattribut und QObject-Kind gehalten.
- Flächenserie und Achsen werden nur einmal aufgebaut. Cockpit-Refreshes ersetzen die Punktliste atomar, statt Serien und Achsen während Qt-Layout-/Paint-Ereignissen zu entfernen und neu anzulegen.
- Notstartschalter `BM_DISABLE_COCKPIT_CHARTS=1` deaktiviert nur die beiden Cockpit-Diagramme; Buchungen und alle übrigen Funktionen bleiben verfügbar.

### Qualitätssicherung
- Neue Regressionstests prüfen Objektlebensdauer, in-place Aktualisierung, stabile Achsen und den Notstartschalter.

## 2.2.53 – 2. August 2026

### Kritischer Linux-/Qt-Absturz behoben
- Der Setup-Assistent startet das verschobene Auto-Backup nicht mehr synchron innerhalb seines nativen `finished`-Signals.
- Dialogabbau und Backup-Prüfung laufen jetzt über zwei getrennte, am Hauptfenster gebundene `QTimer`-Schritte. Dadurch sind Qt-Fokus-, Destroy- und `deleteLater()`-Ereignisse abgeschlossen, bevor Verschlüsselung und ZIP-I/O beginnen.
- Die Python-Referenz auf den Setup-Dialog bleibt bis nach dem nativen Schliesspfad erhalten; ein Doppelklick-/Enter-Guard verhindert einen mehrfachen Abschluss.
- Der normale Startpfad verwendet denselben zentralen, zerstörungssicheren Auto-Backup-Scheduler.
- Diagnose-/Notstartschalter `BM_SKIP_STARTUP_AUTO_BACKUP=1` deaktiviert ausschließlich die automatische Startprüfung; manuelle Backups bleiben verfügbar.

### Qualitätssicherung
- Drei neue Regressionstests sichern die Trennung von Qt-Dialogsignal, Dialogabbau und Auto-Backup dauerhaft ab.

## 2.2.52 – 2. August 2026

### Behoben
- Kritischer Startabbruch in `views/tabs/cockpit_tab.py`: Eine Klassen-Comprehension konnte `LEFT_COLUMN_PANELS` nicht auflösen und löste beim Import einen `NameError` aus.
- Spaltenvorgaben des Cockpits werden nun ohne Zugriff auf den isolierten Klassen-Comprehension-Scope erzeugt.

### Qualitätssicherung
- Neuer AST-Regressionstest erkennt unsichere Zugriffe von Klassen-Comprehensions auf zuvor definierte Klassenattribute.
- Vollständige Headless-Suite: 768 bestanden, 13 bewusst übersprungen.

## 2.2.51 – 2. August 2026

### Kritischer Erststart-Hotfix

- Behebt den Startabbruch `dataclasses.FrozenInstanceError: cannot assign to field 'accent_hover'` im Sprachwahldialog.
- `UIColors` deklariert berechnete Hover-Farben jetzt explizit als `init=False`-Felder und initialisiert sie bei unveränderlicher Dataclass korrekt über `object.__setattr__`.
- Neuer echter Laufzeittest instanziiert `UIColors()` in einem separaten Prozess und verhindert eine Wiederkehr dieses Release-Blockers.
- Die Unveränderlichkeit des Farbcontainers bleibt nach der Initialisierung vollständig erhalten.

## 2.2.50 – 30. Juli 2026

### Wichtige Verbesserungen für Bedienung, Berichte und Release-Nachweise

- Neuer wählbarer **Einfach-/Erweitert-Modus**. Neue Installationen starten bewusst reduziert; manuelle Tab-Anpassungen werden als eigener benutzerdefinierter Zustand erkannt.
- Exportdialog unterstützt neben CSV/TXT jetzt **XLSX** mit getrennten, filterbaren Tabellenblättern und **PDF** als A4-Bericht für Weitergabe und Schwarzweissdruck.
- Diagnosepakete enthalten anonymisierte Qt-/Wayland-/Skalierungsinformationen und eine technische SQLite-Gesundheitsprüfung ohne Finanzinhalte.
- Wiederherstellungsdateien werden über eine verifizierte, synchronisierte temporäre Datei atomar installiert; bestehende Daten bleiben bei Schreib-, Rechte- oder Austauschfehlern unangetastet.
- Eindeutiges Coverage-Modell mit `coverage_full.json`, Zusammenfassung und Mindestwerten für sicherheitskritische Module.
- Neuer Release-Performance-Test mit 100 Kategorien, 12’000 Budgetzeilen und 50’000 Trackingbuchungen.
- Visuelle GUI-Smoke-Tests erzeugen Plattform-Screenshots und erkennen leere/einfarbige Hauptansichten.
- Progressive strengere Mypy-Regeln für Restore, Diagnose, Signaturprüfung, sicheren Excel-Import und Berichtsexport.
- Handbuch, In-App-Hilfe und Mindmaps in DE/EN/FR auf die neuen Bedien- und Exportfunktionen synchronisiert.

## 2.2.49 – 29. Juli 2026

### Finaler Merge und Restore-Härtung

- KILLCRITIC GREEN als stabilere Basis verwendet und die zusätzlichen Enterprise-Sicherheitsverbesserungen selektiv übernommen.
- Lokale Prüfgates behalten ihre saubere Skip-/Fehlerbehandlung, wenn optionale Entwicklungswerkzeuge wie PySide6 oder Bandit nicht installiert sind.
- Erststart-Import von `.bmr`-Backups prüft Struktur, Prüfsummen, Größen und Kompression jetzt fail-closed und streamt Datenbanken statt `zf.read()` zu verwenden.
- Normaler Restore liest Manifest und Nutzdaten aus demselben geöffneten Archiv und prüft vor dem Schreiben erneut gegen Archiv-Austausch.
- Vollständiger Konto-Restore führt das gesicherte Konto mit vorhandenen lokalen Konten zusammen; fremde Konten bleiben erhalten und Teilkollisionen werden abgewiesen.
- Direkte Kopie kompatibler verschlüsselter Datenbanken erfolgt atomar und speicherstabil über temporäre Datei und `os.replace`.
- Leere optionale Bundle-Dateien erhalten korrekte SHA-256-Werte; ungültige Hashformate werden früh abgewiesen.
- Backup-Anzeige meldet nur tatsächlich im Bundle enthaltene Einstellungen und Kontodaten.
- Englische Oberfläche und Dokumentation verwenden wieder konsistent die Schreibweise „Favorites“.
- Der englische Mindmap-Generator wurde ebenfalls auf „Favorites“ korrigiert, damit neu erzeugte HTML-/Mermaid-Grafiken nicht wieder zurückfallen.
- Der statische DAU-Enterprise-Audit liest den identischen Quellbaum bei hohen Loop-Zahlen nur einmal und bestätigt danach die Invariante; 10'000 Loops blockieren dadurch den Release-Prozess nicht mehr.
- Audit-Tests schliessen temporäre SQLite-Verbindungen sauber und kennzeichnen absichtlich erzeugte ZIP-Duplikatwarnungen ausdrücklich als erwartet.
- Neue Regressionstests für Erststart-Restore, Mehrbenutzer-Erhalt, Hashformat, atomare Kopie und Kompressions-Grenzfälle.

## 2.2.48 – 29. Juli 2026

### Enterprise-Release-Härtung: Backup, Sicherheit und DAU

- **Vollständige Bundle-Integrität:** Nicht mehr nur die Datenbank, sondern auch `settings.json` und das zugehörige `users.json` erhalten eigene SHA-256-Prüfsummen und werden beim Restore fail-closed geprüft.
- **Eindeutige Bundle-Struktur:** Doppelte Archivnamen, mehrere Datenbankdateien, widersprüchliche Verschlüsselungsangaben und auffällige Kompressionsraten werden abgewiesen.
- **Selbstkonsistente Konto-Backups:** Bei mehreren lokalen Konten wird nur der Benutzer gespeichert, dessen `db_filename` zur gesicherten Datenbank gehört. Alte Mehrbenutzer-Bundles werden beim Konto-Restore auf den passenden Eintrag reduziert.
- **Speicherstabiler Restore:** Die Datenbank wird gestreamt und mit harter Größenbegrenzung entpackt; kein `zf.read()` der kompletten, potenziell sehr großen Datenbank mehr.
- **Atomare Zusatzdaten:** Einstellungen und Konto-Metadaten werden erst nach Verifikation über eine temporäre Datei, `fsync`, `os.replace` und restriktive Dateirechte installiert.
- **Legacy-Migration erweitert:** Bestätigte Alt-Backups erhalten beim Upgrade zusätzlich Prüfsummen für Einstellungen und Konto-Metadaten.
- **Neue Regressionstests:** `tests/test_release_2248_backup_enterprise_hardening.py` deckt Manipulation, Duplikate, Legacy-Upgrade, Multi-User-Konsistenz, atomare Extraktion und Streaming ab.
- **Manipulierte ZIP-Methoden fail-closed:** Nicht unterstützte Kompressionsarten, gepatchte ZIP-Daten und Low-Level-Lesefehler werden als kontrollierte Integritätsfehler behandelt statt bis in den Restore-Dialog durchzuschlagen.
- **Updater-Kollisionsschutz:** Update-Archive mit doppelten, nur in Gross-/Kleinschreibung abweichenden oder durch Slash/Backslash kollidierenden Pfaden werden vor dem Entpacken abgewiesen.
- **Dokumentationsintegrität:** Einen veralteten, nicht vorhandenen Release-Link in der Haupt-README korrigiert und eine automatische Prüfung aller aktiven lokalen Markdown-Ziele ergänzt.

## 2.2.47 – 28. Juli 2026

### Offene Punkte behoben

- **`ui_colors()` gab QObject-Panels still Standardfarben.** `OverviewBudgetPanel` ist ein `QObject`, kein `QWidget`, und besitzt daher kein `window()`. Die Funktion brach dort ab und lieferte kommentarlos die Voreinstellung — im Log stand nur „ui_colors fallback: 'OverviewBudgetPanel' object has no attribute 'window'". Sechs Aufrufstellen in diesem Panel ignorierten damit jedes Designprofil. Das ist die Meldung, die beim Buchen einer Franchise-Transaktion auftauchte; sie war kein Absturz, sondern ein still fehlschlagender Farbabruf. `ui_colors()` klopft jetzt vor dem Aufgeben die Eltern-Kette ab (gedeckelt bei acht Ebenen gegen Zyklen).
- **`budget_tab._apply_table_styles()` leitete Farben aus `QPalette` ab.** Vierter Fund derselben Bugklasse nach Seitenleiste (2.2.33), Login/Konto (2.2.39) und Cockpit-Beschriftungen (2.2.44). Kopf-, Eltern- und Summenzeilen kommen jetzt aus `table_alt` des aktiven Profils.
- **Neuer Prüfblock L** meldet künftig jede Farbe, die in `views/` aus `QPalette` gezogen wird. Nach vier Wiederholungen derselben Klasse gehört das in ein Gate, nicht in eine Notiz.



## 2.2.45 – 28. Juli 2026

### Anleitung konsolidiert und Enterprise-DAU-Audit gehärtet

- Technische Basis bleibt die Enterprise-auditierte v2.2.44 mit atomarer Cockpit-Layout-Persistenz und DesignManager-Hoheit.
- Aus der Guide-Variante wurden die ausführlicheren Cockpit-Kapitel in Deutsch, Englisch und Französisch übernommen.
- In-App-Hilfe ergänzt um ein eigenes Kapitel zu KPI-Trends, Auswertung, Automatik/Fixierung, Drag-and-drop, Responsive-Spalten und Designprofilen.
- DAU-Theme-Audit erkennt nun auch dreistellige fest codierte Hexfarben wie `#666`.
- Release- und Installationsbeispiele auf den aktuellen Stand synchronisiert.
- Neue Regressionstests sichern Anleitung, atomare Speicherung und die strengere Theme-Prüfung gemeinsam ab.

## 2.2.44 – 28. Juli 2026

### Beste Lösungsansätze beider v2.2.43-Varianten konsolidiert

- DesignManager-Variante bleibt funktionale Basis: Diagramm-Kachel, Theme-Neuaufbau, Objektrollen und kompatible Layoutmigration bleiben vollständig erhalten.
- Vollständigere Cockpit-Hilfe der Parallelvariante in DE/EN/FR übernommen: Automatik, Fixierung, Drag-and-drop, Responsive-Spalten und Reset sind nun direkt erklärt.
- Historische Versionsangaben erhalten ein eigenes Regression-Gate statt nur einer Nebenprüfung.
- Zusammengehörige Layout-Einstellungen werden mit `Settings.set_many()` in einem atomaren Speichervorgang geschrieben; dadurch keine Zwischenzustände zwischen neuem und altem Settings-Schema und weniger `fsync`-Schreibvorgänge.
- Layoutmodus ist idempotent: wiederholtes Setzen desselben Zustands aktualisiert die Darstellung, sendet aber kein falsches Änderungssignal.
- Release-Gate schützt ausdrücklich DesignManager-Hoheit, Diagramm-Persistenz, Legacy-Migration, Übersetzungen und Hilfeinhalt.

## 2.2.43 – 28. Juli 2026

### Dashboard-Optik und intelligentes Kachellayout zusammengeführt

- v2.2.42 (Karten, KPI-Trends, Ring- und Flächendiagramm, Profil „Mitternacht – Violett“) auf die robustere Layoutbasis aus v2.2.41 übertragen.
- Automatikmodus sortiert leere, geschrumpfte Bereiche stabil ans Ende ihrer Produktspalte.
- Fixierter Modus aktiviert einen eigenen Drag-Griff, Spaltenwechsel und persistente Reihenfolge.
- Layout-Einstellungen aus beiden Zwischenversionen (`cockpit_layout_mode`/`cockpit_panel_columns` sowie `cockpit_tiles_fixed`/`cockpit_tile_columns`) werden kompatibel gelesen und synchron gespeichert.
- DesignManager bleibt führend: Dashboard-Objektrollen, Trendzustände, Ränder, Texte und Kartenfarben kommen aus dem aktiven Profil. Theme-Wechsel aktualisieren Diagramme und Trends.
- Behoben: fehlender `icon`-Parameter in `_Card`, Diagramm-Kachel durch veraltete Panel-Liste entfernt, falsche Zielspalte im Einspalten-DnD und undefinierte QSS-Variable `border`.
- Leere Diagramm-Auswertung schrumpft wie andere leere Bereiche und sinkt im Automatikmodus nach unten.

## 2.2.42 – 26. Juli 2026

### Dashboard-Optik nach der Vorlage

- **Neues Farbprofil „Mitternacht – Violett"** (26. Profil): fast schwarzer Hintergrund, abgesetzte Kacheln, violetter Akzent. Der Akzent musste von `#7c5cfc` auf `#7150f0` nachgezogen werden — das Kontrast-Gate aus 2.2.23 fand 4.38:1 für weiße Schrift auf dem Akzent, WCAG AA verlangt 4.5:1. Jetzt 5.11:1.
- **Kartenoptik für alle Abschnitte:** 12 px Radius, Rand und Flächen aus dem Profil. Bewusst ohne feste Farbwerte, sonst bräche die Optik in den anderen 25 Profilen — dieselbe Bugklasse wie 2.2.33 und 2.2.39.
- **KPI-Kacheln im Stil der Vorlage:** Symbolkachel, gedämpfte Beschriftung, große Zahl, Bildunterschrift und Trendpfeil gegen den Vormonat. Die Trendfarbe folgt der fachlichen Richtung, nicht dem Vorzeichen — mehr Ausgaben sind rot, nicht grün. Jahreswechsel ist berücksichtigt (Januar vergleicht gegen Dezember).
- **Neuer Abschnitt „Auswertung"** mit Ringdiagramm (Ausgaben nach Kategorie, Summe in der Mitte, höchstens fünf Segmente plus Rest) und Flächenverlauf mit Farbverlauf (kumulierte Ausgaben im Monat). Beide in `views/cockpit_charts.py`, animationsfrei — eine animierte, gerade entfernte Serie hat unter Wayland bereits Abstürze erzeugt.
- Symbole und Pfeile sind Unicode-Zeichen statt Emoji, damit sie unter Fedora/GNOME ohne Emoji-Schrift sichtbar bleiben.
- 15 neue Regressionstests (`tests/test_release_2242_dashboard_look.py`).

Nicht enthalten: Statuspillen in den Tabellen und die Aktivitätenliste. Beides braucht eigene Zeichenroutinen für Tabellenzellen und ist der nächste Schritt.

## 2.2.41 – 26. Juli 2026

### Leere Kacheln sinken, fixierte lassen sich ziehen

Auflösung des Widerspruchs aus 2.2.40: schrumpfende Abschnitte hinterlassen Lücken mitten im Raster.

- **Ohne Fixierung sortiert das Cockpit selbst.** Leere Kacheln rutschen ans Ende ihrer Spalte, volle bleiben oben. Stabil sortiert — innerhalb der vollen wie der leeren Kacheln bleibt die bisherige Reihenfolge erhalten. Läuft nach jedem Aktualisieren.
- **Neuer Schalter „Kacheln fixieren"** in der Cockpit-Kopfzeile. Fixiert gilt die eigene Reihenfolge, und die Kacheln lassen sich mit der Maus an der Kopfzeile ziehen — auch über die Spaltengrenze. Ein Anfasser (`≡`) erscheint nur im fixierten Modus.
- **Ziehen und Automatik hängen bewusst zusammen.** Beides gleichzeitig ginge nicht: die Automatik würde eine gezogene Reihenfolge beim nächsten Aktualisieren stillschweigend überschreiben. Der Schalter macht diese Kopplung sichtbar, statt sie zu verstecken.
- **Spaltenzuordnung wird gespeichert** (`cockpit_tile_columns`), nicht nur die Reihenfolge. Ohne das wäre eine über die Spaltengrenze gezogene Kachel beim nächsten Start zurückgesprungen — das hätte sich wie ein Fehler angefühlt.
- Eigener MIME-Typ `application/x-budgetmanager-cockpit-tile`, damit fremde Ablagen nicht im Cockpit landen.
- 12 neue Regressionstests (`tests/test_release_2241_tile_pinning.py`).

## 2.2.40 – 26. Juli 2026

### Cockpit übersichtlicher

Vier Änderungen, gemeinsam beauftragt:

- **Leeres verschwindet.** Jede der fünf Cockpit-Tabellen stand auf `setMinimumHeight(150)` und zeigte bei leerem Inhalt eine Platzhalterzeile. In einem ruhigen Monat scrollte man an rund 1000 Pixeln „keine Einträge" vorbei. Tabellen wachsen jetzt mit dem Inhalt (gedeckelt bei acht Zeilen, danach scrollt die Tabelle selbst), leere Tabellen werden ausgeblendet und der Hinweis steht in der Kopfzeile des Abschnitts.
- **Handlungsbedarf gebündelt.** Warnungen, Budget-Ampel und fehlende Buchungen beantworten dieselbe Frage und bilden jetzt einen Abschnitt mit drei Blöcken und einem Summenzähler in der Kopfzeile. Leere Blöcke verschwinden einzeln. Panel-Schlüssel `warnings`, `budget_warnings` und `missing` werden zu `action_needed`; gespeicherte Auswahlen werden migriert (war einer der drei sichtbar, ist der gebündelte Abschnitt sichtbar).
- **Zwei Spalten ab 1180 px Fensterbreite.** Kennzahlen und Schnellaktionen links, Listen rechts. Darunter bleibt alles einspaltig — schmalere Spalten würden Tabellen horizontal scrollen lassen.
- **Abschnitte sind aufklappbar**, der Zustand wird je Abschnitt gespeichert. Beim ersten Start offen: Kennzahlen und Handlungsbedarf. Die Pfeile sind schlichte Dreiecksglyphen statt Emoji — gleiche Begründung wie beim Hilfe-`?`.

Struktur: `views/cockpit_sections.py` enthält `CollapsibleSection`, `fit_table_height` und `ResponsiveColumns` als einzeln prüfbare Bausteine.

Leere Abschnitte werden bewusst **nicht** komplett ausgeblendet, sondern schrumpfen auf Kopfzeile plus Hinweis: ein Abschnitt, der je nach Monat verschwindet und wiederkommt, lässt das Cockpit springen und man sucht ihn beim nächsten Mal.

- 11 neue Regressionstests (`tests/test_release_2240_cockpit_overview.py`).

## 2.2.39 – 26. Juli 2026

### DAU- und Enterprise-Audit über Funktionen, Verweise und Design

Neues Werkzeug `tools/dau_enterprise_audit.py` mit sechs Prüfblöcken (16.499 Prüfungen je Durchlauf), das Lücken schließt, die die bisherigen Audits nicht abdeckten. Gefunden und behoben:

- **Theme-Disziplin (15 Fundstellen, schwerwiegendster Punkt).** `views/login_dialog.py` und `views/account_management_dialog.py` verdrahteten Farben fest im Stylesheet — `#2196F3`, `#27ae60`, `#e67e22`, `#fff3cd` und Hover-Varianten. In dunklen Profilen ergab das unvorhersehbare Kontraste; `#fff3cd` mit dunkler Schrift war praktisch unlesbar. Das ist dieselbe Bugklasse wie beim Seitenleisten-Fehler in 2.2.33, nur in zwei Dialogen, die bisher niemand geprüft hatte.
- **Neuer Helfer `themed()` in `views/ui_colors.py`.** Ersetzt `%(name)s`-Marken im Stylesheet durch Profilfarben. Bewusst %-Formatierung: QSS besteht aus geschweiften Klammern, die bei f-String oder `str.format` alle maskiert werden müssten. Fällt eine Marke aus, bleibt das Stylesheet unverändert — ein Dialog darf nicht an einer Farbe scheitern.
- **Hover-Farben werden abgeleitet statt verdrahtet.** `UIColors` berechnet `accent_hover`, `positive_hover`, `warning_hover` und `negative_hover` über `_shade()` aus der jeweiligen Grundfarbe.
- **Beschriftung:** `Kontoverwaltung...` war der letzte Menüeintrag mit drei Punkten statt `…` — in allen drei Sprachen.
- **Zugriffstasten:** Die französischen Einträge `Konto & Daten` und `Vollbild` hatten keine.

Fehlalarme, die das Audit zunächst meldete und die bewusst *keine* Funde sind: `self.accept`/`self.reject` sind von `QDialog` geerbt; Signale sind klassenweite Attribute; Dialoge dürfen ausschließlich im eigenen Modul verwendet werden; und `tags.action_text_label` darf die Platzhalter sprachspezifisch dokumentieren, weil `model/tags_model.py` sowohl `{datum}` als auch `{date}` akzeptiert. Die Prüflogik unterscheidet diese Fälle jetzt sauber — Platzhalterparität wird nur für Schlüssel erzwungen, die tatsächlich über `trf()` formatiert werden.

- 10 neue Regressionstests (`tests/test_release_2239_dau_enterprise_audit.py`).

## 2.2.38 – 26. Juli 2026

### Hilfe-Menü nach Desktop-Richtlinien überarbeitet

- **Ausgangslage:** Das Hilfe-Menü war eine flache Liste aus zwölf gleichrangigen Einträgen. Anwenderthemen (Handbuch, Tastenkürzel) und Werkzeugthemen (Protokolle, Diagnosepakete, Wiederherstellungsschlüssel) standen unsortiert nebeneinander.
- **Neuer Aufbau:** neun oberste Einträge in fünf durch Trennlinien getrennten Gruppen – Nachschlagen · Lernen · Problembehandlung · Version · Über. Zwei Untermenüs (`Visuelle Übersichten`, `Problembehandlung`) nehmen das selten Gebrauchte auf.
- **Auslassungszeichen vereinheitlicht.** Vorher standen `...` (drei Punkte) und `…` (ein Zeichen) gemischt nebeneinander. Jetzt gilt durchgehend: `…` nur vor Befehlen, die einen Dialog öffnen; `Diagnoseordner öffnen` führt sofort aus und bekommt keine.
- **Zugriffstasten vervollständigt.** Vorher hatten nur fünf von zwölf Einträgen ein `&`. Jetzt jeder – mit je Menüebene eindeutigem Buchstaben, geprüft in allen drei Sprachen.
- **Anwendersprache statt Entwicklerjargon:** „Crash-Log" → „Absturzprotokoll", „Restore-Key" → „Wiederherstellungsschlüssel", „Log" → „Anwendungsprotokoll", „Fehlerbericht" → „Diagnosebericht".
- **`Nach Updates suchen` aus Extras ins Hilfe-Menü verschoben.** Die Extras-Sammlung war der falsche Ort; alle drei großen Desktop-Richtlinien führen die Update-Prüfung unter Hilfe. Der französische Eintrag hieß bisher unübersetzt `&Updates...`.
- **Neu: `Neuerungen in dieser Version`.** Zeigt den obersten Abschnitt aus `CHANGELOG.md` in einem Lesefenster. `CHANGELOG.md` wird dafür in den PyInstaller-Build aufgenommen — ohne diesen Eintrag bliebe der Dialog im Frozen-Build leer.
- **Struktur:** Der Menüaufbau liegt jetzt in `views/help_menu.py`. `views/main_window.py` schrumpft dadurch von 3499 auf 3419 Zeilen und hat wieder Luft unter der 3500er-Grenze des Architektur-Gates.
- 16 neue Regressionstests (`tests/test_release_2238_help_menu_standards.py`): Menülänge, Gruppierung, Position von „Über", Auslassungszeichen-Konvention, Eindeutigkeit der Zugriffstasten je Ebene und Sprache, Jargonfreiheit sowie die Auslieferung des Changelogs.

### Unverändert

- Das `?` oben rechts in der Menüleiste und der Knopf `? Hilfe` unten links in der Seitenleiste bleiben beide erhalten.

## 2.2.37 – 26. Juli 2026

### Hilfe-Fragezeichen in die obere Leiste verlegt

- **Wunsch aus dem Sichttest:** Das `?` gehört in die Top-Leiste — entweder bei `Hilfe` oder neben dem Minimieren-Knopf.
- **Umsetzung:** Die Menüleiste erhält ein Corner-Widget in `Qt.TopRightCorner`. Das `?` sitzt damit ganz rechts in derselben Zeile wie `Datei … Hilfe`, optisch unmittelbar links neben Minimieren/Maximieren/Schließen der Fensterdekoration. Ein Klick öffnet direkt das durchsuchbare In-App-Handbuch.
- **Weiterhin reines ASCII-`?`** — kein Emoji, kein Icon-Theme. Unter Fedora/GNOME ohne Emoji-Schrift bleibt das Zeichen dadurch sichtbar, unabhängig vom installierten Icon-Theme.
- **Theming:** Neue QSS-Regeln (`QToolButton#menuBarHelpButton`) beziehen Akzent-, Hover- und Fokusfarben aus dem aktiven Profil. Ohne diese Regeln griff auf manchen Desktops die generische Palette und das Zeichen verschwand optisch in der Leiste — derselbe Fehlertyp wie beim Seitenleisten-Bug in 2.2.33.
- **Sprachwechsel-Härtung:** `_retranslate_ui` ruft `menuBar().clear()` + `_create_menu()` auf. `clear()` entfernt jedoch nur Aktionen, nicht das Corner-Widget. Der Knopf wird deshalb einmalig erzeugt und danach nur noch neu beschriftet — sonst wäre bei jedem Sprachwechsel ein verwaistes `QToolButton` zurückgeblieben.
- **Barrierefreiheit:** Tooltip, Statuszeilentext, `accessibleName` und `accessibleDescription` in Deutsch, Englisch und Französisch; Tastaturfokus über Tab erreichbar.
- Der bisherige Einstieg `?  Hilfe` unten links in der Seitenleiste bleibt zusätzlich erhalten.
- 12 neue Regressionstests (`tests/test_release_2237_help_topbar.py`), darunter ein optionaler Offscreen-Funktionstest, der bei vorhandenem PySide6 prüft, dass das Corner-Widget tatsächlich in `Qt.TopRightCorner` hängt.

### Funktionsinventar bestätigt

- Die eingereichte Funktionsliste (wiederkehrende Buchungen mit Soll-Buchungsdatum, Fixkosten-Monatsprüfung mit optionaler Auswahlliste, Budgetwarnungen, Tags, Undo/Redo, Favoriten, Sparziele, Backup/Wiederherstellung, Datenbank-Reset, Erscheinungsmanager, Windows-Installer, Update-Tool) wurde vollständig gegen die Codebasis geprüft. Alle Punkte sind bereits ausgeliefert; siehe `docs/FEATURE_INVENTORY_v2.2.37.md` mit Modul- und Testnachweis je Punkt.

## 2.2.36 – Wiki-Audit, grafische Zusammenhänge und Linux-Hilfe

- Wiki-Audit gegen das dokumentierte Funktionsinventar ergänzt.
- Drei Offline-Grafiken sowie responsive `docs/help/wiki-audit.html` integriert.
- Neuer Hilfe-Menüpunkt und Handbuchknopf für die grafischen Zusammenhänge.
- Linux-Fix: Seitenleiste zeigt `? Hilfe` als normalen Text statt als Emoji.

## 2.2.35 – 25. Juli 2026

### Handbuch-Vollständigkeit

- In-App-Handbuch anhand des realen Funktionsinventars erweitert.
- Eigene Kapitel für Tracking-Lernmodus, POT/Rückstellung, Jahreswechsel und 13. Monatslohn, Suche/Filter, Export/Druckgrenzen, Einstellungen/GNOME, Tastenkürzel, Datenverwaltung und Diagnose ergänzt.
- Falsche Aussage zum Monatsabschluss korrigiert: Der Abschluss setzt einen Erinnerungs-Vermerk, sperrt den Monat aber nicht.
- Export-Dokumentation auf den tatsächlichen Umfang korrigiert: CSV/TXT vorhanden; direkter PDF-Druck, Druckvorschau und XLSX-Berichte noch nicht implementiert.
- Deutsche, englische und französische Benutzerhandbücher vollständig neu strukturiert und die statische HTML-Hilfe sowie Mindmaps synchronisiert.
- Automatischen Handbuch-Vollständigkeitsaudit und Regressionstests ergänzt.

## 2.2.34 – 25. Juli 2026

### Anleitung und Auffindbarkeit: Soft-0-Budget

- Die bisher schwer auffindbare **sanfte Null-Bilanz-Regel** heißt in der Oberfläche jetzt eindeutig **Soft-0-Budget**.
- Direkt unter der Einstellung steht eine kurze Erklärung; ein Knopf öffnet das passende Handbuchkapitel.
- Das In-App-Handbuch enthält ein eigenes ausführliches Kapitel mit Formel, Voraussetzungen, Prioritäten, Beispielen, Fehlersuche und Abgrenzung zum Tracking-Lernmodus.
- Deutsche, englische und französische Benutzeranleitungen wurden erweitert.
- HTML-Wissensdatenbank und Mindmaps nennen die Funktion ausdrücklich.
- Keine fachliche Berechnungslogik wurde verändert; es handelt sich um eine Dokumentations- und Usability-Härtung.

## 2.2.33 – 24. Juli 2026

### Seitenleiste folgte der System-Palette statt dem App-Theme (behoben)
- **Fehlerbild (vom Nutzer gemeldet):** Bei aktivem hellem Profil („V2 Hell – Neon Cyan") blieb die linke Navigationsleiste dunkel.
- **Ursachenkette:**
  1. `ThemeManager.apply_theme()` setzt ausschliesslich `app.setStyleSheet()` und **nie** `app.setPalette()`.
  2. `MainWindow._apply_modern_shell_style()` färbte die Seitenleiste aber über `palette(base)`, `palette(highlight)`, `palette(alternate-base)` und `palette(text)`. Diese lösen gegen die **System**-Palette auf — auf einem dunklen Desktop (GNOME/KDE dark) also dunkel.
  3. `QFrame#mainSidebar` ist ein spezifischerer Selektor als das generische `QWidget` des App-Themes und gewann deshalb. Alle übrigen Flächen wurden korrekt hell gefärbt — nur die Leiste nicht.
  4. Der in **allen 25 Profilen** vorhandene und im Erscheinungsmanager einstellbare Schlüssel `hintergrund_seitenleiste` wurde von keinem Widget gerendert; `ui_colors` las ihn zwar als `bg_sidebar` ein, aber niemand nutzte den Wert. Die Einstellung war faktisch wirkungslos.
- **Fix:** Die Sidebar-Farben liegen jetzt im App-Theme (`theme_manager.build_stylesheet`) und speisen sich aus `hintergrund_seitenleiste`; Hover und Auswahl nutzen die Profilfarben. `_apply_modern_shell_style()` liefert nur noch Geometrie (Abstände, Radien, Schriftgewicht) — genau das, was sein Docstring immer behauptet hat.
- **Zweiter Fehler in derselben Methode (behoben):** Der Stil wurde per `setStyleSheet(self.styleSheet() + …)` **angehängt**, und die Methode läuft bei *jedem* Theme-Wechsel erneut — das Stylesheet wuchs unbegrenzt. Der Block wird jetzt idempotent gesetzt.
- 10 neue Regressionstests (`tests/test_release_2233_sidebar_theming.py`), darunter eine Luminanzprüfung über alle 25 Profile (helles Profil ⇒ helle Leiste, dunkles ⇒ dunkle) und eine Kontrastprüfung Text/Leiste ≥ 4,5:1.

### Bekannt, noch offen
- `views/tabs/budget_tab.py:_apply_table_styles()` liest `self.table.palette()` und leitet daraus Header-/Parent-/TOTAL-Farben ab. Das ist derselbe Fehlertyp: Stylesheet-Farben landen nie in der `QPalette`. Nicht mitbehoben, weil die Auswirkung nur am laufenden GUI beurteilbar ist und ein Umbau die sichtbaren Abstufungen der Budget-Tabelle verändert.

## 2.2.32 – 24. Juli 2026

### DAU-Audit: Fehleingabe-Härtung gegen inf/nan-Beträge
- **Befund (fail-open, hoch):** `float()` akzeptiert `"inf"`, `"Infinity"`, `"nan"` und Overflow-Strings wie `"1e400"` oder sehr lange Ziffernfolgen (→ inf). Solche Werte rutschten durch `utils.money.parse_money` und damit durch **jeden** Betrags-Dialog (Budget, Tracking, Sparziel, Fixkosten) in die Datenbank — kein Dialog hatte einen eigenen Guard. Ein einziges inf/nan hätte dort alle Summen, Budget-/Restberechnungen, Sparziel-Grenzen und Diagramme vergiftet (inf+x=inf; nan verunreinigt jeden Vergleich). Das widersprach dem dokumentierten fail-closed-Verhalten von `parse_money`.
- **Fix, mehrschichtig (defense-in-depth):**
  1. `parse_money` prüft das Ergebnis mit `math.isfinite()` und lehnt nicht-endliche Werte fail-closed mit `ValueError` ab — Primärabwehr an jeder GUI-Eingabe. Endliche wissenschaftliche Notation (`1e10`) bleibt gültig; alle normalen Formate unverändert.
  2. Neuer Helfer `utils.money.require_finite_amount()` sichert die **Datenbank-Schreibgrenze** ab, sodass der Invariant „in der DB stehen nur endliche Beträge" *by construction* gilt — unabhängig vom Eingabepfad (auch Excel-Import, Migration, programmatische Aufrufe, die `parse_money` umgehen).
  3. Guards eingezogen in `budget_model.set_amount`, `tracking_model.add` und zentral in `validate_savings_goal_bounds` (deckt create/deposit/withdraw/Tracking-Sparbuchung ab). Ein inf-Ziel hätte sonst die Sparziel-Obergrenze faktisch deaktiviert (alles ≤ inf).
- Neuer trilingualer Fehlertext `savings.bounds.not_finite` (de/en/fr, Platzhalter-Parität `{goal_name}`).
- `tools/dau_first_run_check.py` um Schritt 8 erweitert: prüft, dass inf/nan an parse_money **und** an allen drei DB-Schreibstellen abgewiesen werden und nach einem Fehleingabe-Sturm kein nicht-endlicher Betrag in der DB steht.
- 16 neue Regressionstests (`tests/test_release_2232_dau_input_hardening.py`).
- **Weiter geprüft, ohne Befund:** SQL-Sonderzeichen in Kategorie-/Tag-Namen (parametrisiert, keine Injection), Kategorie-Deduplizierung, sehr lange/Unicode-Namen. Leere/Whitespace-Namen werden bereits an der GUI abgefangen (`if not name.strip()` in Kategorie- und Tag-Dialogen).

## 2.2.31 – 24. Juli 2026

### Deep-Release-Audit auf v2.2.30
- Vollständige Werkzeugbatterie gegen den entpackten Auslieferungsstand neu durchlaufen: `compileall`, `sync_version --check`, `i18n_audit` (de/en/fr je 95 Keys, identische Reihenfolge), `dau_first_run_check`, `release_logic_audit_100` (100 Loops), `deep_logic_release_audit` (500 Loops / 3500 Checks), `final_release_audit_1000` (18.975 Checks), `mega_release_audit_1000` (6.811 Checks), `pre_release_stability_audit_300` (2.400 Checks), `fresh_logic_audit_100`, `architecture_quality_gate`, `verify_hashed_lock`, `lint_procedure_check` – alle ohne Befund. Headless-Suite: 580 bestanden, 9 übersprungen (PySide6 nicht verfügbar).
- Alle 13 Funktions-Backlog-Punkte erneut funktional gegen eine echte SQLite-Instanz nachgeprüft (u. a. Soll-Datum-Klemmung Tag 31 → 28./30., sechs Fälligkeitsszenarien, Überschreitungserkennung, Bundle-Integrität, 25 valide Farbprofile, Installer-Versionsgleichheit).

### Befund A – toter Artefakt-Check im Release-Gate (behoben)
- `tools/lint_procedure_check.py:check_generated_artifacts()` war **beweisbar toter Code**: Die Funktion hat `dirnames` zuerst per `_is_excluded_path()` beschnitten – was exakt die Namen aus `EXCLUDED_DIRS` entfernt – und anschließend die *bereits beschnittene* Liste gegen `EXCLUDED_DIRS - {".git"}` geprüft. Die Meldebedingung konnte für keinen einzigen Namen mehr wahr werden, und `.git` war explizit ausgenommen.
- Auswirkung: 34 `__pycache__`-Einträge (inkl. fremdversionierter `cpython-313.pyc`) und ein vollständiges `.pytest_cache/` wurden im v2.2.30-ZIP ausgeliefert, während das Gate PASS meldete. Der Cleaner `tools/clean_release_tree.py` war korrekt – nur seine Durchsetzung fehlte.
- Fix: Erkennung läuft strikt **vor** dem Pruning. Das Pruning bleibt erhalten, damit nicht in die Ordner abgestiegen und pro Nachfahre erneut gemeldet wird – gemeldet wird der oberste Treffer.
- **Befund A2 (gleiche Funktion):** `GENERATED_FILE_PATTERNS` wurden per `ROOT.glob()` nur wurzelrelativ gesucht. `*.pyc`/`*.pyo` liegen ausschließlich in `__pycache__`-Unterordnern und waren damit ebenfalls unauffindbar. Reine Namensmuster werden jetzt per `rglob()` baumweit geprüft; Muster mit Pfadtrenner (z. B. `data/users.json`) bleiben bewusst wurzelrelativ.

### Befund B – uneinheitlicher Tags-Rückgabetyp (behoben)
- `TagsModel` lieferte je nach Methode `Tag`-Objekte (`list_all`, `get_tags_for_category`, `get_tags_by_ids`) oder rohe `dict`s (`get_all_tags`, `list_tags`, `get_tags_for_entry`). Aufrufer mussten pro Methode wissen, welcher Typ kommt; ein Methodenwechsel hätte still zu `AttributeError`/`TypeError` zur Laufzeit geführt.
- Fix *by construction* statt Aufrufer-Migration: Die `Tag`-Dataclass unterstützt zusätzlich lesenden Mapping-Zugriff (`__getitem__`, `get`, `keys`, `values`, `items`, `__contains__`, `to_dict`). Alle Lesemethoden geben einheitlich `Tag` zurück – `tag.name` und `tag["name"]` funktionieren gleichermaßen, `dict(tag)` ebenfalls. **Kein Aufrufer musste geändert werden.**
- Release-Baum bereinigt; das Auslieferungs-ZIP enthält keine generierten Artefakte mehr.
- 15 neue Regressionstests (`tests/test_release_2231_gate_and_tags_api.py`), davon 6 als Anti-Regression gegen exakt das Pruning-vor-Erkennung-Muster.

## 2.2.30 – 18. Juli 2026

### Unabhängiges Deep-Audit auf v2.2.29 (Fehler-, Enterprise-, UI-, Usability-Audit)
- Zusätzlich zur grünen Werkzeugbatterie wurden unabhängige Prüfungen durchgeführt, die die internen Audits nicht abdecken: i18n-Platzhalter-Parität über alle drei Sprachen, Migrations-Idempotenz mit FK-Integritätsprüfung, Datums-Fuzz der Fälligkeits- und Soll-Datum-Logik über alle Monats-/Schaltjahr-Kombinationen (inkl. Nicht-Schaltjahr 2100), 400-Schritte-Undo/Redo-Fuzz gegen ein Schattenmodell, Geldformat-Roundtrips aller vier Zahlenformate mit Cross-Format-Eingaben, Backup-Bundle-End-to-End mit Byte-Manipulation und Legacy-Pfad, Krypto-Domänentrennung, Secret-Logging-Scan, Thread-/Worker-Muster und Default-Buttons destruktiver Bestätigungen.
- **Login-Härtung (Befund 2):** Ein von Hand korrumpierter `pw_hash` in users.json (Nicht-ASCII oder falscher Typ) liess `hmac.compare_digest` in `verify_password`/`is_legacy_password_hash` mit `TypeError` abstürzen; der Login crashte statt abzulehnen. Beide Funktionen behandeln nicht vergleichbare Werte jetzt über den neuen Guard `_is_comparable_stored_hash` fail-closed als ungültig, und `UserModel.authenticate` fängt zusätzlich `TypeError` ab.
- **Theme-Editor (Hinweis A):** Die Bestätigungen für Profil-Löschen und -Zurücksetzen erhalten einen expliziten sicheren Default (Nein); zuvor machte Qt implizit „Ja" zum Enter-Default.
- **Tag-Aktionstexte (Hinweis B):** Der Hinweistext `tags.action_text_label` dokumentiert nun in allen drei Sprachen auch den unterstützten Monats-Platzhalter ({monat}/{month}).
- 10 neue Regressionstests (`tests/test_release_2230_deep_audit_fixes.py`); alle übrigen unabhängigen Proben ohne Befund, u. a. bestätigt: Suggestion-Engine (Datenstart-Grenze, Fixkosten-Schutz, echte Über-/Unterschreitung), Restore mit automatischem `before_restore`-Vollbackup, Bundle-Manipulationserkennung, 0600-Dateirechte.

## 2.2.29 – 18. Juli 2026

### Release-Gate-Resynchronisation (Enterprise-Audit v2.2.28, Befund 1)
- Der Workflow-Step „Verify updater manifest stays updater-safe" war beim Merge im Sammel-Step „Build signed release assets, updater manifest and SBOM" aufgegangen; dadurch schlug `tools/release_logic_audit_100.py` fehl und die explizite Nach-Build-Verifikation des generierten Update-Manifests entfiel.
- Neues headless testbares Gate `tools/verify_release_manifest.py`: prüft das GENERIERTE `latest.json` fail-closed auf den Updater-Vertrag (Plattform-Assets als portable-zip mit korrekten URL-Suffixen, exakte Installer-Typen, keine Direkt-Binär-Keys, https-URLs, gültige SHA-256-Hashes, keine unbekannten Asset-Keys) und verifiziert die Ed25519-Manifest-Signatur, sobald ein Public Key verfügbar ist.
- Der Verifikations-Step ist im Tag-Build unter dem historischen Namen direkt nach der Asset-Erzeugung reaktiviert (Defense-in-Depth zusätzlich zur By-Construction-Sicherheit des Builders).
- `tools/release_logic_audit_100.py` pinnt jetzt beide Step-Namen sowie den Werkzeug-Aufruf; das 100-Loop-Audit läuft wieder vollständig grün.
- 19 neue Regressionstests (`tests/test_release_2229_manifest_verify_gate.py`) sichern Verdrahtung, Vertragsprüfungen, CLI-Verhalten und den kryptografischen Signaturpfad ab; End-to-End gegen echten Builder-Output verifiziert.
- Vollaudit v2.2.28 abgeschlossen: alle 13 Funktions-Backlog-Punkte (wiederkehrende Buchungen mit Soll-Datum, Fixkosten-Monatscheck mit Offen-Liste, Budgetwarnungen, Tags, Undo/Redo, Favoriten, Sparziele, Backup/Restore, Datenbank-Reset, Erscheinungsmanager, Windows-Installer, Update-Tool) sind implementiert und wurden headless funktional nachgeprüft; ausser Befund 1 keine weiteren Findings.

## 2.2.28 – 18. Juli 2026

### Enterprise-Härtung
- Ed25519-signierte Update-Manifeste; fehlende oder ungültige Signaturen werden abgelehnt.
- Authenticode-Pflicht und GitHub Build-Provenance im Release-Workflow.
- Vollständig transitive, SHA-256-gehashte Runtime-, Dev- und Build-Lockfiles sowie CycloneDX-SBOM.
- Sicherer Excel-Import mit ZIP-/XML-Bomben-Schutz und Hintergrund-Parsing.
- Alte Backups ohne Prüfsumme werden nicht direkt restauriert, sondern nach Bestätigung in eine verifizierte Kopie konvertiert.
- Fail-closed Bandit-Gate, vollständiger Black-Check und Coverage-Gates.
- Korrekte Fernet-Dokumentation (AES-128-CBC + HMAC-SHA256).

## 2.2.27 – 18. Juli 2026

### Merge v2.2.25 + v2.2.26
- UI-/Accessibility-Härtungen aus v2.2.26 vollständig übernommen.
- Schema v17 und Bereinigung verwaister `entry_tags` aus v2.2.25 wiederhergestellt.
- Monatsende-Klemmung für Fälligkeitstage 29–31 wiederhergestellt.
- SQL-Identifier-/Whitelist-Härtungen in Kategorien, Migrationen, Tags, Tracking und Undo/Redo wiederhergestellt.
- Tag-Bereinigung beim Löschen über Undo/Redo wiederhergestellt.
- Sichtbaren Schließen-Button im Theme-Editor wiederhergestellt.
- Auditwerkzeuge und Regressionstests beider Zweige zusammengeführt.
- KILLCRITIC-Auditwerkzeug auf zentrale DB-Typ-Konstanten umgestellt.

# v2.2.26 – KILLCRITIC X10THINK Usability 10.000 (17. Juli 2026)

- 10.000 dynamische Qt-Usability-Loops über zehn Domänen und 31 Dialogtypen.
- Verschachtelte Felder und Standardbuttons barrierearm/lokalisiert.
- Tab-Ketten auf sichtbare Steuerelemente desselben Fensters begrenzt.
- Budget- und Setup-Dialog notebooktauglich scrollbar.
- Klickflächen, Bulk-Texte und Versionskontrast verbessert.
- Isolierte Qt-Worker und verpflichtendes Release-Gate ergänzt.

# v2.2.25 – Enterprise Release-Audit 10.000 (17. Juli 2026)

- Neuer reproduzierbarer 10.000-Loop-Zustandsaudit mit zehn Release-Themen und 112.000 Einzelprüfungen.
- Kategorienwechsel entfernt veraltete feste Kategorie-Tags und bewahrt manuelle Tags.
- Undo/Redo stellt die vollständige Tag-Belegung von Tracking-Buchungen wieder her.
- Tracking-Listen erhalten die echte Buchungsquelle (`manual`, `auto_fixcost`, `auto_recurring`, `auto_optional`).
- SQL-Lesewege für die Buchungsquelle statisch gehärtet; gegenüber v2.2.24 keine zusätzliche Bandit-Warnung.
- Der 10.000er-Audit ist als verpflichtendes Tag-Build-Gate mit JSON-Nachweis verdrahtet.
- Audit-Artefakte verwenden dynamisch die aktuelle Versionsnummer statt einen fest codierten v2.2.24-Dateinamen.
- Abschluss: 519 Tests sowie sämtliche UI-, Logik-, Stabilitäts-, Versions-, I18N- und Paketgates bestanden.

# v2.2.24 – Release-Warnungen geschlossen (16. Juli 2026)

- 107 modale Informationsdialoge und 97 passive Warnungsdialoge durch nicht-modale, fokus-erhaltende und screenreader-benannte Statushinweise ersetzt.
- Sicherheitsabfragen, irreversible Bestätigungen und echte Fehler bleiben bewusst modal. AST-Bilanz: 305 auf 101 QMessageBox-Aufrufe; 0 Information, 0 passive Warnung.
- Deterministische Tab-Reihenfolge für 13 komplexe Dialogdateien beziehungsweise 20 Dialogklassen ergänzt.
- Reale GUI-Selbsttests für Fedora/Wayland mit 100/125/150/200 %, Windows mit 100/125/150/200 % und einen Accessibility-Vertrag als verpflichtende Release-Gates ergänzt.
- Windows-Installer wird im Tag-Build still installiert, aus der installierten EXE geprüft und wieder deinstalliert; der gewählte Nutzerdatenordner muss erhalten bleiben.
- Isolierter Updater-End-to-End-Test prüft Staging-Hash, Top-Level-Ordner, Rollback-Backup, Austausch und Datenerhalt. Dabei wurde die Marker-Erkennung für Update-ZIPs mit einem Top-Level-Ordner korrigiert.
- Online-`pip-audit` und Dependabot ergänzt. Der Tag-Build hängt zwingend von Plattform- und Dependency-Gates ab und erzeugt keine Release-Binaries, wenn eines davon fehlschlägt.
- Abschluss: 506 Tests, Enterprise UI/ADHS 1000 Loops mit 0 WARN/0 FAIL sowie alle Logik-/Stabilitätsaudits ohne Finding.

# v2.2.24 – Enterprise-Merge und Fedora/Python-3.13-Release-Härtung

- v2.2.22 und v2.2.23 strukturell, funktional und per AST/API verglichen; keine Klasse, Funktion oder Methode aus v2.2.22 ging verloren.
- v2.2.23 als sichere Merge-Basis bestätigt: 491 Tests bestanden; v2.2.22 reproduzierbar mit 3 Release-Sauberkeitsfehlern.
- Release-Lockfile auf die tatsächlich geprüfte Python-3.13/PySide6-6.10.3-Kombination aktualisiert.
- CI prüft nun Python 3.12 und 3.13 und führt `pip check` aus.
- Regressionstest schützt Versionssynchronität, Dependency-Lock und CI-Matrix.
- **M1 (Portabilität):** `tests/test_release_2223_enterprise_ui_adhs.py` überspringt ohne Qt nur die drei echten GUI-Tests; fünf Qt-unabhängige Release-, Theme- und Quelltests bleiben auch headless aktiv. Unter Qt läuft die vollständige Suite.
- **M2 (Portabilität):** `tools/enterprise_ui_adhs_audit_1000.py` besitzt in d3/d4 Qt-freie Kern-Fallbacks. Ohne PySide6 werden diese ehrlich als WARN statt als vollständiger Qt-PASS ausgewiesen; unter Qt läuft weiterhin der Volltest.
- Final-Nachprüfung: Black-Formatfehler im portablen Audit-Werkzeug behoben; Headless-Suite überspringt nur noch die drei echten Qt-Tests und kennzeichnet reduzierte Fallbacks transparent als WARN.
- Enterprise-Audit erneut ausgeführt: UI/ADHS, Legacy-UI, Mega-Release, Deep Logic, Stabilität, Release Logic, Fresh Logic, I18N, Black und Mypy grün.

# v2.2.23 – Enterprise-UI-/Usability-/ADHS-Nachaudit

- Release-Cleaner entfernt nun zuverlässig testweise erzeugte Settings, Datenbanken, Nutzerdateien und Theme-Profile.
- Vorbefüllte Textfelder werden beim automatischen Erstfokus nicht mehr komplett markiert; versehentliches Überschreiben wird verhindert.
- Accessibility-Namen nutzen QFormLayout-Beschriftungen und werden bei Qt-Sprachereignissen kontrolliert neu aufgebaut.
- Icon-only-Löschaktionen werden zusätzlich über Tooltip/A11y-Metadaten als destruktiv erkannt.
- Datums-/Zeitfelder sind in der globalen Erstfokuslogik vollständig berücksichtigt.
- Sprachwechsel werden konsistent erst nach Neustart angewendet, statt eine gemischte Teilübersetzung zu erzeugen.
- Zu kleine Farbaktionen im Tag-Manager auf 36 × 32 px vergrößert.

# v2.2.19 – Logic-Fixes und Dokumentation zusammengeführt

# v2.2.22 – Enterprise-UI-/Usability-/ADHS-Audit: eigenes 1000-Loop-Werkzeug, sechs Findings behoben

Eigenständige Verifikation der v2.2.21-UI-Härtung mit neuem `tools/ui_adhs_audit_1000.py` (10 Domänen × 100 = 1000 Loops; echte Funktionsläufe für Destruktiv-Erkennung, Preset-/Migrationslogik und i18n statt reiner Quelltext-Behauptungen). **Vorher-Lauf auf v2.2.21: 252 Findings. Nachher: 0** (15'593 Checks).

## Behoben

- **F5 (KRITISCH, ADHS-Kernziel verfehlt): Neuinstallation startete NICHT im Fokus-Modus.** Die v2.2.14-Zwangsmigration lief bedingungslos im Konstruktor und materialisierte die ALL-TRUE-Panel-Defaults – die Preset-Combo zeigte "Fokus", sichtbar waren aber ALLE Bereiche. Neu: `utils/cockpit_presets.py` ist die EINE Qt-freie Wahrheit (Presets, wirksamer Zustand, Materialisierung, Migration); die Alt-Migration gilt nur noch für Custom-Bestand.
- **F6 (KRITISCH): Ein Panel-Toggle im Fokus-Modus liess alle Panels aufpoppen.** Die Merge-Basis `{**PANEL_DEFAULTS, **cfg}` mischte die ALL-TRUE-Map ein; ausserdem widersprachen sich die Default-Maps in `settings.py` und im Cockpit-Tab. Neu: Basis ist der wirksame Zustand; `settings.py` bezieht den Default aus dem Fokus-Preset; Alt-Bestand ohne Preset-Feature erhält sein bisheriges "alles sichtbar" als Custom festgeschrieben.
- **F3 (Enter-Sicherheit): Destruktiv-Erkennung war lückenhaft und substring-basiert.** `réinitialiser`, `retirer`, `clear`, `vider`, `verwerfen`, `discard`, `purge(r)`, `leeren` fehlten; "Preset" hätte über das enthaltene "reset" gematcht. Neu: Qt-freie `is_destructive_text` mit Wortgrenzen in `utils/ui_text_rules.py` (vom Audit mit Golden-Set in 100 Loops geprüft).
- **F1 (Accessibility/i18n): Screenreader-Hinweis für Tabellen/Listen war hartkodiert deutsch** – Bruch der de=en=fr-Regel. Neu: `a11y.itemview_hint` in drei Sprachen.
- **F2 (Performance/Ruhe): Der Show-Eventfilter lief bei JEDEM Anzeigen über den gesamten Widgetbaum** – auch bei Combo-Dropdowns und Menüs. Neu: Einmal-Marker `_bm_ui_enhanced` pro Widget plus Popup-/Menü-/Tooltip-Skip.
- **F4 (Stabilität): Der Erstfokus-Timer konnte auf einen bereits zerstörten Dialog feuern** (Show → sofortiges Schliessen). Neu: RuntimeError-Guard und Sichtbarkeitsprüfung; `install_ui_usability` ist idempotent.

## Audit-Bilanz (alle Läufe auf dieser Version)

| Prüfung | Umfang | Ergebnis |
|---|---|---|
| **UI-/ADHS-Audit (NEU, eigenes Werkzeug)** | **1000 Loops / 15'593 Checks** | **0 (vorher 252)** |
| Mega-Release-Audit | 1000 Loops / 6'812 Checks | 0 |
| Deep-Logic / Stability / Logik / Fresh | 500+300+100+100 Loops | 0 |
| pytest headless | 479 Tests | **477 passed, 2 skipped** |
| Sync / Compile / i18n (2308×3, inkl. neuem a11y-Key) / Lint / DAU | – | PASS |



## [2.2.21] - 2026-07-13

### UI, Usability und Accessibility
- Globaler Accessibility- und Fokusfilter für alle Fenster und Dialoge.
- Sichere Dialog-Defaults: destruktive Aktionen reagieren nicht unbeabsichtigt auf Enter.
- Cockpit-Modi **Fokus**, **Standard** und **Analyse**; Fokus ist für neue Installationen voreingestellt.
- Neue Regressionstests für UI-Härtung und i18n-Parität.

# v2.2.20 – Vor-Release-Vollaudit: Funktion, Logik, Sicherheit, Stabilität (1000 Loops)

Komplettes Audit vor dem Release auf v2.2.19. Neu dazu: `tools/mega_release_audit_1000.py` – 10 Stress-/Stabilitätsthemen × 100 = **1000 Loops** (6811 Checks) über Massen-Buchungen, Undo/Redo-Stürme, Rename-Kaskaden unter Last, Unicode-Namen, Extrembeträge, Jahreskopie-Roundtrips, Backup-Bundle-Fuzzing (1-Byte-Flips), Reset-Semantik, Vorschlags-Engine und Tag-Chaos. Ergebnis der Datenschicht: **0 Findings**. Zwei echte Fehler lagen ausserhalb:

## Behoben

- **A (SICHERHEIT, HOCH): "Notfall-Reset" entfernt.** v2.2.18/19 hatte einen Notfall-Reset-Button in den Backup-Dialog eingebaut, der ALLE Tabellen löschte – laut eigenem Tooltip "funktioniert auch ohne Passwort". Damit umging er die Sicherheitsabfrage aus v2.2.10/16, brach die K4-Regel "Reset an genau EINEM Ort", und seine Tabellenliste vergass `suggestion_accepted` und `tracking_learning_state` (verwaiste Lern-/Vorschlagszustände nach dem Reset – das v2.2.6-Thema). Der Button, die Methode und 9 zugehörige/verwaiste i18n-Keys sind entfernt (de/en/fr, Parität 2301). Der reguläre Reset im DatabaseManagementDialog ist conn-basiert, funktioniert auch im verschlüsselten Modus und läuft IMMER hinter `require_reauth`.
- **B (RELEASE-HYGIENE): Laufzeit-Artefakte im Release-Baum.** `data/budgetmanager_settings.json` (Nutzer-Settings!) und ein `data/theme_profiles/`-Ordner lagen im ZIP – und der Lint war dafür blind. Beides entfernt; `lint_procedure_check` prüft die Muster jetzt (empirisch verifiziert: angelegte Probe-Datei wird gemeldet).
- **Doku-Regressionstest robust gemacht:** Der in v2.2.19 ergänzte Test hatte die Versionsnummer hartkodiert und wäre bei jedem Release erneut gebrochen; er liest jetzt `APP_VERSION` dynamisch.

## Audit-Ergebnis (alle Läufe auf dieser Version)

| Prüfung | Umfang | Ergebnis |
|---|---|---|
| pytest headless | 457 Tests | **457 passed, 2 skipped** |
| Release-Logik-Audit | 100 Loops | 0 Findings |
| Deep-Logic-Audit | 500 Loops / 3500 Checks | 0 Findings |
| Fresh-Logic-Audit | 100 Loops | 0 Findings |
| Stability-Audit | 300 Loops / 2400 Checks | 0 Findings |
| KILLCRITIC-Harness | 100 Loops | 0 Findings |
| **Mega-Release-Audit (NEU)** | **1000 Loops / 6811 Checks** | **0 Findings** |
| Sicherheits-Quickscan | Rechte, Bundle-Verify, Apply-Verify, Backup-Pflicht, Minima, Re-Auth, SQL, Logs, Updater-Limits | alle Zusicherungen intakt |

Gesamt: **2100 Loops, > 12 700 Einzel-Checks, 0 offene Findings.**


- LOGIC-FIXES als Codebasis übernommen.
- Regression im Dialog „Fällige Buchungen“ behoben: Signalanschluss, Filter und Status sind wieder erreichbar.
- Leere Monate deaktivieren sämtliche Buchungsaktionen, lassen den Monatswechsel aber offen.
- Eindeutiger Leerzustand statt irreführendem „bereits alles gebucht“.
- Dokumentations-Regressionstest aus WIKI/GUIDE ALIGNED wiederhergestellt.
- Zusätzliche Regressionstests für Monatsworkflow und leere Zustände.

# Changelog

# v2.2.17 – Logikanalyse: vier Fehler behoben, Datenschicht neu abgesichert

Systematische Logikpruefung auf v2.2.16 – mit frischem Blick auf die Nahtstellen der juengsten Konsolidierung und auf bislang ungepruefte Randfaelle der Datenschicht. Die Datenschicht selbst ist sauber (neuer 100-Loop-Invarianten-Lauf, 0 Findings); vier Fehler lagen in der Oberflaechen-Logik.

## Behoben

- **F1 (Funktionsregression aus K3): Komplett gebuchter Monat sperrte den Faelligkeiten-Dialog aus.** War der aktuelle Monat bereits vollstaendig gebucht, brach `add_fixcosts` mit einer Info-Box ab, BEVOR der Dialog oeffnete – der in v2.2.16 integrierte Monatswechsel war damit unerreichbar (vorher kam die Monatsauswahl zuerst). Jetzt oeffnet der Dialog immer (Abbruch nur, wenn gar keine relevanten Kategorien existieren); bei leerer Liste zeigt er den Hinweis "bereits gebucht", der Buchen-Button ist deaktiviert, und der Monat laesst sich oben wechseln.
- **F2: Bearbeiten verfaelschte die Merkliste "zuletzt gebuchte Kategorie".** Das blosse Korrigieren einer alten Buchung ueberschrieb `tracking_last_category` je Typ – die Schnellerfassung schlug danach die korrigierte statt der zuletzt wirklich gebuchten Kategorie vor. Nebenwirkung jetzt nur noch beim Anlegen.
- **F3: Statuszeile meldete "gebucht – Undo" auch beim Bearbeiten.** Der Hinweis gehoert nur zum Anlegen; im Edit-Modus entfaellt er.
- **F4: Ergebnis-Statistik nach dem Buchen bezog sich auf den Startmonat.** Wer im Dialog den Monat wechselte, bekam Zaehler (uebersprungen/bereits gebucht) des falschen Monats gemeldet. Der Dialog exponiert jetzt `current_month()`, die Statistik wird fuer den tatsaechlich gewaehlten Monat erhoben.

## Geprueft und fuer korrekt befunden (nicht veraendert)

- **Datenschicht** via neuem `tools/fresh_logic_audit_100.py` (10 Themen x 10 Loops, 0 Findings): `tracking.update` erhaelt die Buchungsquelle (`source`); Sparziel-Staende bleiben bei Typwechsel savings↔expenses exakt synchron; Ueberbuchung beim Typwechsel wird VOR jeder Aenderung geblockt (Eintrag und Ziel unveraendert); Undo/Redo eines Updates stellt ALLE Spalten inkl. `source` wieder her; Faelligkeitstag 29–31 wird in kurzen Monaten (Februar!) korrekt geklemmt; `set_entry_tags` ist idempotent; leere Details bleiben beim Update leer; Edit ohne Typ/Kategorie-Wechsel laesst Sparziel-Staende unangetastet.
- `is_pot` wird aus Kategorie-Flags abgeleitet – `copy_year` kann den Pot-Modus nicht verlieren.
- `requires_code(None)` (Legacy-Modus ohne Konto) laeuft korrekt ohne Abfrage durch.

## Dateien
`views/tabs/tracking_tab.py`, `views/recurring_bookings_dialog.py`, `views/quick_add_dialog.py`, `tools/fresh_logic_audit_100.py` (neu), `tests/test_release_2217_logic_fixes.py` (neu, 6 Tests).

Gates: compileall, sync --check (2.2.17), i18n-Audit (de=en=fr, 2309 Keys), DAU, Release-Logik-Audit 100/0, Deep-Logic-Audit 500/3500/0, Lint, pytest headless **442 passed / 2 skipped**, KILLCRITIC-Harness 100/0, **Fresh-Logic-Audit 100/0**.


# v2.2.16 – Bedienbarkeit: doppelte Werkzeuge vereinheitlicht

Umsetzung der kritischen Redundanzanalyse. Fuer dieselbe Aufgabe gab es bis zu vier parallele Wege mit unterschiedlichen Formularen; das wurde konsolidiert. Netto weniger Code, ein Ort pro Aufgabe.

- **K1 – Buchung Neu = Bearbeiten:** Der `TrackerDialog` (aermeres Bearbeiten-Formular) ist entfallen. Neu UND Bearbeiten laufen jetzt ueber denselben `QuickAddDialog` (Edit-Modus via `edit_row_id`), inkl. Tag-Erstellung, Aktionstexten und Sparziel-Grenzen. Der v2.1.7-Schutz (ungelistete/Parent-Kategorie bleibt beim Bearbeiten erhalten) wurde uebernommen.
- **K2 – Budget-Erfassung:** Nur noch der erweiterte Dialog (`BudgetEntryDialogExtended`). Der schlanke `BudgetEntryDialog` ist entfallen; je nach Einstiegspunkt gab es vorher zwei verschiedene Formulare.
- **K3 – Fixkosten buchen:** Aus drei Werkzeugen (Monatsauswahl-Dialog + zwei Listen-Dialoge) wurde EINER. Die Monatsauswahl ist in den `RecurringBookingsDialog` integriert (Monatswechsel laedt die Kandidaten neu); `FixcostDialog` und `MissingBookingsDialog` sind entfallen. Der Nur-Fixkosten-Fall nutzt dieselbe Liste (Fixkosten vorangehakt).
- **K4 – Reset an EINEM Ort, hinter der Sicherheitsabfrage:** Der Reset-Button ist aus dem `BackupRestoreDialog` entfernt. Der Datenbank-Reset lebt nur noch im `DatabaseManagementDialog` und laeuft jetzt hinter derselben Code-Abfrage (`views/reauth.py`) wie Export/Import/Restore – vorher lief er daran vorbei. Beide Dialoge teilen sich die eine `require_reauth`-Implementierung.
- **K7 – UI-Rework-Reste entfernt:** Die sechs `goto_*`-Menuepunkte (die Sidebar navigiert) sowie die Steuerung der alten Tab-Leiste (Anzeigen/Position/Reihenfolge zuruecksetzen) sind aus dem Menue entfernt. Die Tastenkuerzel bleiben fensterweit aktiv. Die alte Tab-Leiste ist dauerhaft ausgeblendet.
- **K8 (Variante B) – Kategorien: ein Kern, zwei Rahmen:** Die getrennt implementierte Sidebar-Seite (740 Zeilen) und der Manager-Dialog (971 Zeilen) teilen sich jetzt EINEN `CategoryManagerWidget`. Dialog und Tab sind duenne Huellen darum. Damit muss die fehleranfaellige Kategorie-Kaskade (acht namensgekeyte Tabellen) nur noch an einer Stelle konsistent gehalten werden.

Gates: compileall, sync --check (2.2.16), i18n-Audit (de=en=fr, 2309 Keys), DAU, Release-Logik-Audit 100/0, Deep-Logic-Audit 500/3500/0, Lint, pytest headless. Zur Kontrolle zusaetzlich: KILLCRITIC-Invarianten-Harness 100 Loops / 0 Findings.


# v2.2.15 – Rest-Lücken der Pre-Release-Analyse geschlossen

Basis war v2.2.14 (UI-Rework-Testversion). Die Analyse ergab: Das parallel implementierte v2.2.12-Hardening deckt die fünf Release-Blocker im Kern ab, liess aber vier Punkte offen. Diese sind jetzt geschlossen.

- **B5-Rest – Rollback-Backup ist Pflicht:** Schlug das Rollback-Backup vor einem Update fehl, lief das Update bisher trotzdem weiter ("fahre fort") – ein Abbruch mitten im Dateitausch hätte dann keinen Rettungsweg gehabt. Jetzt bricht `apply_update` in beiden Pfaden (Windows-Helfer und Linux) mit Code 12 ab, wenn kein Rollback-Backup erstellt werden konnte.
- **B2-Verschärfung – onedir-Pflicht für ZIP-Updates:** `validate_staged_payload` verlangt für Portable-ZIP-Assets jetzt Binary **plus nicht-leeres `_internal/`** – ein ZIP mit nur einer Binary wäre nach dem Anwenden nicht startfähig gewesen. Installer-Staging erwartet genau eine Setup-EXE. Der bewusst unterstützte Quelltext-Fall (main.py + app_info.py) bleibt gültig; rohe Einzel-Binaries laufen unverändert über Nicht-ZIP-Assets.
- **M4 – CI vor dem Release-Tag:** Neuer Workflow `.github/workflows/ci.yml` führt Compile, Versions-Sync, i18n-Audit, Lint, Logik-Audit und die Testsuite bei jedem Push auf `main` und bei Pull Requests aus. Fehler fallen damit VOR dem Tag auf; `build.yml` bleibt für Builds/Veröffentlichung.
- **M5 – Mindestlängen für neue Geheimnisse:** Neue PIN 6–8 Ziffern (vorher 4–8), neues Passwort mindestens 10 Zeichen (vorher 4). Gilt für Neuanlage und Wechsel (Model als letzte Schutzschicht; Login-, Konto- und Assistent-Dialoge nutzen jetzt die Model-Konstanten). **Bestandskonten mit kürzeren Geheimnissen bleiben anmeldbar** – der Login läuft nicht über diese Validierung. i18n-Texte in de/en/fr angepasst (Parität 2309 unverändert).
- **M2-Rest – Lint prüft README:** `lint_procedure_check` verifiziert jetzt auch das APP_VERSION/APP_RELEASE_DATE-Codebeispiel im README und den exakten PyInstaller-Pin. Dabei aufgefallene 2.2.13-Stempel-Reste (Badge, Beispielkommandos, "Stand der Analyse") wurden auf 2.2.15 gehoben; Historien-Sektionen blieben unangetastet.
- **Neue Regression:** `tests/test_release_2215_gap_fixes.py` (12 Tests), inkl. Abbruch-Test bei fehlgeschlagenem Rollback-Backup und Nachweis, dass ein Bestandskonto mit 4-stelliger PIN weiterhin authentifiziert. Drei bestehende Staging-Fixtures wurden onedir-konform gemacht.

Gates: compileall, sync --check (2.2.15), i18n-Audit (de=en=fr, 2309 Keys), DAU, Release-Logik-Audit 100/0, Deep-Logic-Audit 500/3500/0, Lint (inkl. neuer README-Prüfung), pytest headless **420 passed / 2 skipped**, KILLCRITIC-Invarianten-Harness 100/0.


## 2.2.12 – 11. Juli 2026

### Security- und Release-Hardening
- Update-Staging wird nach jedem verifizierten Download vollständig neu aufgebaut.
- Portable ZIPs benötigen einen erkennbaren BudgetManager-Startpunkt.
- ZipSlip-, Symlink-, Größen-, Dateianzahl- und Zip-Bomb-Schutz ergänzt.
- Staging-Inhalt wird gehasht und unmittelbar vor der Installation erneut geprüft.
- Full-Tree-Updates verwenden einen transaktionalen Austausch mit Rollback.
- Vollständiger Konto-Restore tauscht Datenbank und users.json als gemeinsame Transaktion.
- Importierte Backup-Dateien erhalten restriktive Dateirechte.
- Neue Regressionstests für Update- und Restore-Ausfallszenarien.

# v2.2.11 – Sicherheitsanalyse: Schlüsselmaterial geschützt, Backups verifiziert

Die Datenbank ist immer verschlüsselt. Der Schutz steht und fällt damit an zwei Stellen: **wo der Schlüssel liegt** und **was ungeprüft in die Installation gelangen darf**. Eine systematische Analyse (Krypto, Schlüsselspeicher, Backup/Restore, SQL, Pfade) hat an beiden Stellen Lücken gefunden.

## Behoben

- **HOCH – Schlüsselmaterial war world-readable.** `users.json` wurde mit dem Standard-umask geschrieben, auf typischen Linux-Systemen also `0644`. Bei **Quick-Konten steht dort `db_key_b64` im Klartext**: Jeder andere lokale Benutzer konnte die Datei lesen und damit die verschlüsselte `.enc` entschlüsseln. Bei PIN/Passwort-Konten lagen dort `wrapped_db_key_b64` und `pw_hash` offen — Material für Offline-Brute-Force. **Neu:** `users.json`, `.enc` und `.bmr`-Backups werden mit `0600` abgelegt. Die Rechte werden auf der Temp-Datei **vor** dem `os.replace` gesetzt, damit kein Zeitfenster mit offenen Rechten entsteht. Neues Qt-freies Modul `model/file_permissions.py` (unter Windows folgenlos, dort greifen die Profil-ACLs).

- **HOCH – Backups wurden nie auf Integrität geprüft.** Das Manifest enthielt seit jeher einen SHA256 der Datenbank, aber **niemand hat ihn je verifiziert**. Ein beschädigtes oder gezielt manipuliertes `.bmr` wurde kommentarlos über die aktive Datenbank gespielt. **Neu:** `restore_bundle.verify_bundle()` prüft Archiv-Struktur, Grössen und SHA256 gegen das Manifest — eingehängt in **beide** Restore-Pfade (normaler Restore und Konto-Restore mit `users.json`). Bundles ohne Hash (sehr alte) werden nicht hart abgewiesen, aber protokolliert.

- **MITTEL – Zip-Slip strukturell ausgeschlossen.** Ein `.bmr` ist ein ZIP. Es wird jetzt eine Whitelist erlaubter Einträge erzwungen (`manifest.json`, `database.enc|db`, `settings.json`, `users.json`); ein Archiv mit Fremdeinträgen wird abgewiesen. Kein Name aus dem Archiv wird je als Pfad verwendet.

- **MITTEL – Zip-Bomb-Schutz.** Harte Grössenlimits für die Metadateien (je 5 MB) und die Datenbank (4 GB). Es wird zusätzlich hart begrenzt gelesen, damit ein gefälschter Header nicht ausreicht, um den Speicher zu fluten.

- **MITTEL – Dateiname aus dem Backup gehärtet.** Im Konto-Restore stammte der Ziel-Dateiname aus dem Manifest. Neben `Path(...).name` (Traversal) wird jetzt auch die Endung erzwungen, damit ein präpariertes Bundle die DB-Bytes nicht über `users.json` oder `settings.json` schreiben kann.

## Geprüft und für gut befunden (nicht verändert)

- **Krypto:** PBKDF2-HMAC-SHA256 mit 600 000 Runden, `os.urandom` für Salt und db_key, Fernet für die Nutzdaten.
- **Domain-Separation:** `pw_hash` nutzt `PW_VERIFY_CONTEXT` und ist damit nicht key-äquivalent; Vergleiche laufen über `hmac.compare_digest` (keine Timing-Leaks). Legacy-Hashes werden beim Login erkannt und migriert.
- **SQL-Injection:** Alle Werte gehen über Platzhalter; die wenigen f-String-SQL betreffen ausschliesslich Tabellennamen aus festen Whitelists (`_safe_table`, `_RESET_TABLE_WHITELIST`).
- **Logging:** Keine Geheimnisse (Passwort, PIN, db_key, Restore-Key) werden protokolliert.

## Bewusst unverändert

Bei **Quick-Konten** liegt der `db_key` naturgemäss im Klartext in `users.json` — ohne Geheimnis gibt es nichts, womit man ihn schützen könnte. Das ist der Preis des schnellen Zugangs und jetzt wenigstens durch Dateirechte abgesichert. Wer echten Schutz vor lokalen Mitbenutzern braucht, nutzt PIN oder Passwort.

## Dateien
`model/file_permissions.py` (neu), `model/restore_bundle.py`, `model/user_model.py`, `model/crypto.py`, `views/backup_restore_dialog.py`, `tests/test_release_2211_security_hardening.py` (neu, 13 Tests).

Gates: compileall, sync --check (2.2.11), i18n-Audit (de=en=fr, 2308 Keys), DAU, Release-Logik-Audit 100/0, Deep-Logic-Audit 500/3500/0, Lint, pytest headless **397 passed / 2 skipped**.


# v2.2.10 – Sicherheitsabfrage vor Backup-Export, -Import und -Restore

Backup-Aktionen liefen bisher ohne jede Code-Abfrage. Das ist heikel: **Export** schreibt die (verschlüsselte) Datenbank – und optional `users.json` – an einen frei wählbaren Ort ausserhalb des Programms, **Import/Restore** überschreibt die aktive Datenbank. Wer kurz an einem entsperrten Fenster sass, konnte Daten ausleiten oder ersetzen.

- **NEU – Re-Authentifizierung:** Vor `Exportieren`, `Importieren` und `Wiederherstellen` wird der Benutzercode abgefragt (Eingabe verdeckt). Drei Fehlversuche brechen die Aktion ab. Eine erfolgreiche Eingabe gilt für die restliche Lebensdauer des Backup-Dialogs, damit man beim Ablauf Import→Restore nicht zweimal tippen muss.
- **Bewusste Ausnahme – Quick-Konten:** Konten ohne PIN/Passwort werden **nicht** gefragt. Dort existiert kein Geheimnis, das man prüfen könnte (der db_key liegt base64-kodiert in `users.json`), und der schnelle Testbetrieb soll nicht ausgebremst werden. Gleiches gilt für den unverschlüsselten Legacy-Modus ohne User-Objekt.
- **Kein zweiter Krypto-Pfad:** Die Prüfung nutzt `UserModel.authenticate()` – exakt denselben Weg wie der Login. `users.json` bleibt unverändert die Kontenquelle; es wurde kein neues Format und keine neue Ableitung eingeführt.
- **Neues Modul `model/backup_auth.py`:** Die Policy (`requires_code`, `verify_secret`) ist Qt-frei und damit headless testbar; der Dialog enthält nur noch die Eingabemaske.
- **i18n:** Vier neue Keys (`backup.auth_title`, `backup.auth_text`, `backup.auth_failed`, `backup.auth_aborted`) in de/en/fr; Parität gewahrt (je 2308 Keys).
- **Neue Regression:** `tests/test_release_2210_backup_auth.py` (11 Tests: Quick frei, PIN/Passwort geprüft, leerer Code ohne Modell-Aufruf abgelehnt, defektes UserModel führt zu Verweigerung statt Absturz, Guards in Export/Import/Restore verdrahtet, verdeckte Eingabe).

Gates: compileall, sync --check (2.2.10), i18n-Audit (de=en=fr, 2308 Keys), DAU-Erststart, Release-Logik-Audit 100/0, Deep-Logic-Audit 500/3500/0, Lint, pytest headless. GUI-Smoke und Qt-`.qm`-Prüfung wie immer auf dem Live-System.


# v2.2.9 – Kategorie-Tags + Tag-Aktionen

KILLCRITIC-Korrektur auf Basis von v2.2.8. Schwerpunkt: Tags sind jetzt nicht nur nachträglich an Buchungen nutzbar, sondern können an Kategorien fix hinterlegt und als kleine Buchungsautomatik verwendet werden.

- **NEU (Kategorie-Tags):** Tags können Kategorien fix zugewiesen werden. Mehrere Tags pro Kategorie sind möglich.
- **FIX/NEU (Tracking-Regel):** Jede neue Buchung übernimmt automatisch die fixen Tags der gewählten Kategorie – auch wenn die Buchung nicht aus dem Schnellbuchungsdialog kommt.
- **HÄRTUNG:** Manuelles „Tag setzen“ kann fixe Kategorie-Tags nicht versehentlich entfernen; zusätzliche manuelle Tags bleiben möglich.
- **NEU (Tag-Aktionen):** Tags haben einen optionalen freien Aktionstext für Buchungsdetails, z. B. `{datum} UBS essen`.
- **NEU (Schnellbuchung):** Beim Anhaken eines Tags wird der Aktionstext als Details vorgeschlagen, ohne bewusst eingegebenen Nutzertext zu überschreiben.
- **FIX (Tags sichtbar):** Der Schnellbuchungsdialog nutzt nun eine vorhandene `list_tags()`-Kompatibilitätsmethode; Tags bleiben im Cockpit-/Tracking-QuickAdd sichtbar.
- **UX:** Wenn bei „Tag setzen“ noch kein Tag existiert, öffnet direkt das Erstellungsmenü statt einer Sackgassenmeldung.
- **DB:** Schema v16 ergänzt `tags.action_text` rückwärtskompatibel.

Gates: compileall, i18n-Audit, DAU-Erststart, Release-Logik-Audit 100/0, Deep-Logic-Audit 500/3500/0, neue Tag/Kategorie/Action-Regressionen 5/0, Kern-Regressionen 56/0.


## 2.2.13 – Usability-Testversion

- Zentrale Aktionsleiste für Buchung, Fixkosten, Kategorien, Sparziele und Suche.
- Alle Buchungs-Einstiege verwenden weiterhin denselben QuickAddDialog.
- Redundante Schnelleingabe-Schaltflächen in Budget, Kategorien und Übersicht ausgeblendet.
- Sparziele sprachlich klar vom POT-System für Franchise/Selbstbehalt getrennt.
- Keine Änderung an Sparziel-, POT-, Budget- oder Tracking-Berechnungen.
