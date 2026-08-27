## 3.1.1 – 27. August 2026

**3.1.0 wurde nie ausgeliefert.** Version, Notizen und Tag standen bereits, als der Release-Bau abbrach: Siebzehn Dokumente trugen weiterhin die Versionsnummer 3.0.9, und die Integritätsprüfung des Baus hat das zu Recht beanstandet. Ein Tag wird nicht verschoben, deshalb bekommt dieselbe Arbeit die Nummer 3.1.1. Für 3.1.0 gibt es keine Downloads, weil es sie nie gab.

Die Ursache lag im Werkzeug, das die Versionsnummern nachzieht: Es suchte nur nach Versionen **derselben Reihe**. Solange die dritte Stelle stieg, ging das gut — beim Sprung von 3.0.9 auf 3.1.0 wechselt die Reihe, und in einem Dokumentenkopf mit „3.0.9" fand es nichts. Schlimmer noch: Die Prüfung `--check` arbeitete mit demselben blinden Muster und meldete „synchron". Der Fehler war damit lokal nicht zu sehen. Beides ist behoben; die Prüfung findet jetzt jede dreistellige Version im Kopf.

### Was für 3.1.0 vorgesehen war und jetzt ausgeliefert wird

Der Bankimport friert nicht mehr ein, zeigt endlich, wie weit er ist, und lässt sich abbrechen. Dabei kamen zwei Fehler ans Licht, die stiller waren als das Einfrieren und schwerer wiegen: Ab der zweiten Datei war der Import nicht mehr atomar, und jede Buchung schrieb die verschlüsselte Datenbank zweimal vollständig neu.

#### Der Import war ab der zweiten Datei nicht atomar

**Wer mehrere Dateien auf einmal importiert hat und dabei auf einen Fehler lief, kann Buchungen ohne Importvermerk in der Datenbank haben.** Solche Buchungen sind für die Duplikaterkennung unsichtbar — beim nächsten Importlauf derselben Datei wären sie ein zweites Mal hereingekommen.

Die Ursache lag tief: Die Buchführung für „Rückgängig" schloss ihre Datenbanktransaktion zu früh und ließ eine zweite offen, die niemandem gehörte. Der Import bemerkte das, hielt es für eine fremde Klammer und verzichtete deshalb auf seine eigene. Ohne Klammer kein Rückgängigmachen: Bei einem Fehler mitten in der zweiten Datei blieb stehen, was bis dahin geschrieben war.

Beides ist behoben. Der Import einer Datei ist jetzt ein einziger, unteilbarer Block — er geht ganz durch oder gar nicht. Ein Test löst dafür einen Fehler mitten im Import aus und prüft danach den Datenbestand; ohne die Korrektur schlägt er fehl.

**Zu tun ist nichts.** Sollte in Ihrem Bestand eine solche Buchung liegen, erkennen Sie sie daran, dass sie beim erneuten Import derselben Datei nicht als Duplikat markiert wird — dann bitte die doppelte Zeile abwählen.

#### Ein Import von 1000 Buchungen dauerte 44 Sekunden

Die Anwendung speichert die verschlüsselte Datenbank nach jeder Änderung vollständig neu. Der Import forderte das je Buchung an — und seit der Transaktionskorrektur oben sogar zweimal je Buchung. Für 1000 Buchungen waren das über 2000 vollständige Schreibvorgänge und über vierzig Sekunden ohne Rückmeldung; bei 2000 Buchungen fast drei Minuten. Windows meldete in dieser Zeit „Keine Rückmeldung".

Der Import bündelt das Speichern jetzt. **1000 Buchungen dauern 0,4 Sekunden statt 44** — und die Zahl der Schreibvorgänge wächst nicht mehr mit der Importmenge, sondern bleibt bei fünf.

#### Das Importfenster friert nicht mehr ein

- **Die Analyse läuft im Hintergrund.** Bisher stand das Fenster still, sobald Sie Dateien hinzugefügt haben — bei größeren Auszügen minutenlang. Sie können jetzt weiter suchen, sortieren und lesen, während gerechnet wird.
- **Ein schmaler Fortschrittsbalken sagt, was gerade passiert** und wie weit es ist: „Duplikate prüfen · 742 / 1086 · 68 %". Bei mehreren Dateien zählt der Balken über alle hinweg und springt nicht bei jeder Datei auf null zurück; gewichtet wird nach Buchungszahl, nicht nach Dateizahl.
- **Abbrechen geht jederzeit.** Der Knopf sitzt direkt neben dem Balken. Die Analyse hält an der nächsten sicheren Stelle an, die Quelldateien bleiben unangetastet und lassen sich anschließend löschen oder verschieben. Ein erneuter Lauf ist sofort möglich.
- **Während des eigentlichen Speicherns läuft der Balken unbestimmt** und sagt, dass der aktuelle Block sicher gespeichert wird. Das ist ehrlicher als ein Prozentwert: Dieser Block ist unteilbar, ein zeilengenauer Fortschritt wäre erfunden.

#### Zwei kleinere Fehler mit unangenehmer Wirkung

- **Eine PDF-Seite ohne Inhalt ließ den ganzen Import abstürzen.** Ein leeres Blatt im Kontoauszug ist völlig normal; die PDF-Bibliothek meldet dafür aber keinen leeren Text, sondern einen internen Fehler. Statt der Auskunft „diese Datei enthält keinen lesbaren Text" sah man eine technische Fehlermeldung. Jetzt wird die leere Seite als das behandelt, was sie ist.
- **Beim Anlegen eines neuen Tags im Import konnte der Kostenanteil lautlos verschwinden.** Die Analyse arbeitet seit dieser Fassung mit einem festen Datenstand; ein Tag, den Sie erst im Dialog anlegten, war darin noch nicht bekannt, und der Fehler wurde stillschweigend geschluckt. Der Datenstand wird jetzt nachgezogen.

#### Für Mitentwickelnde

Die Analyse rechnet nicht mehr in der Datenbank, sondern aus einem unveränderlichen Abzug (`BankImportAnalysisSnapshot`), der einmal auf dem besitzenden Thread gezogen wird — Kategorien, Tags, KI-Wissen, TWINT-Gedächtnis, Marker und bekannte Import-Kennungen. Der Arbeiter besitzt weder eine Datenbankverbindung noch eine datenbankgebundene KI-Instanz; Tests belegen das, indem sie die Modellmethoden vergiften und die Analyse trotzdem durchlaufen lassen.

Der finale Import bleibt bewusst im Bedien-Thread: Die Schreibwege brauchen die Verbindung der Oberfläche, und die Atomarität für einen Anzeigeeffekt zu zerbrechen wäre der falsche Tausch.

`db_transaction` klammert verschachtelte Blöcke jetzt per SAVEPOINT, statt wirkungslos mitzulaufen — das ist strenger als vorher und betrifft alle Schreibwege. Die Buchführung für „Rückgängig" committet in einer fremden Transaktion gar nicht mehr und fällt stattdessen mit ihr zusammen.
