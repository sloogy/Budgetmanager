## 3.1.2 – 28. August 2026

**Die lokale Import-KI bekommt einen Schalter, ein Gedächtnis mit Herkunft und einen Rückweg.** Sie hat bisher bei jedem Bankimport geraten und aus jeder bestätigten Zeile still weitergelernt — ohne Stelle, an der man das abstellen, und ohne Stelle, an der man eine falsch angelernte Zuordnung wieder loswerden konnte. Das ist der Kern dieser Fassung.

Beim Nachprüfen, ob dieses Wissen sicher liegt, kam ein Befund heraus, der nicht die KI betrifft, sondern Ihre Sicherungen. Er steht deshalb zuerst.

### Ihre Sicherung eines Schnellzugang-Kontos enthält den Schlüssel

**Wer den Schnellzugang ohne Passwort nutzt und eine Sicherung weitergibt oder ablegt, gibt den Inhalt lesbar mit.** Im Schnellzugang liegt der Datenbankschlüssel auf diesem Rechner, und jede Sicherung — die von Hand angelegte ebenso wie das automatische Backup — nimmt den Konto-Eintrag mitsamt diesem Schlüssel in die `.bmr`-Datei. Schloss und Schlüssel liegen damit in derselben Datei; wer sie hat, liest sie ohne Ihren Rechner.

Nachgestellt haben wir genau das: aus einem frisch erzeugten Bundle allein ließ sich der Text einer Buchung im Klartext herausholen. Mit PIN oder Passwort ist es anders — dort steht nur der verpackte Schlüssel, und der echte kommt in der ganzen Datei kein einziges Mal vor.

**Der Schlüssel bleibt trotzdem drin, und das mit Absicht.** Ohne ihn wäre die Sicherung eines Schnellzugang-Kontos nach einem Plattentausch nicht mehr zu öffnen — eine Sicherung, die man nicht zurückspielen kann, ist keine. Was falsch war, ist das Verschweigen: Der Hinweis im KI-Bereich sagte bisher nur, der Schlüssel liege „lesbar auf diesem Rechner". Das ist die harmlosere Hälfte, denn über jede Sicherung verlässt er den Rechner. Deutsch, Englisch und Französisch benennen jetzt beide Hälften.

**Was Sie tun können:** Behandeln Sie die Sicherung eines Schnellzugang-Kontos wie die Datenbank selbst — nicht in eine geteilte Cloud, nicht per Mail. Wer das nicht möchte, richtet für das Konto eine PIN oder ein Passwort ein; dann trägt die Sicherung den Schlüssel nicht mehr.

Alles Übrige an der Verschlüsselung hat der Nachweis bestätigt: Das KI-Wissen liegt in derselben verschlüsselten Datenbank wie Ihre Buchungen, es gibt keine zweite Datei daneben, die Zwischendatei beim Speichern trägt bereits den verschlüsselten Inhalt statt lesbaren Text, und nach dem Speichern steht kein Buchungstext irgendwo auf der Platte.

### Die Import-KI lässt sich abschalten — und zurücksetzen

In den Einstellungen gibt es jetzt den Bereich **„Lokale Import-KI"**:

- **Zwei Schalter**: ob die KI beim Import überhaupt Vorschläge macht, und ob sie aus Ihren Bestätigungen weiterlernt. Beides getrennt — man kann die Vorschläge behalten und das Lernen abstellen.
- **Zurücksetzen der Lerndaten.** Das leert das Händlergedächtnis, die Lernbeispiele, das TWINT-Gedächtnis und die gelernten Tag-Regeln — und sonst nichts. Buchungen, Budgets, Kategorien, Tags, Sparziele und die Duplikaterkennung des Imports bleiben unangetastet. Der Schritt ist unwiderruflich und liegt deshalb bewusst nur hier, nicht im Importfenster.
- **Wie viele Muster gelernt sind**, in welchem Sicherheitszustand das Konto gerade ist, und der Datenschutzhinweis. Es geht weiterhin nichts aus dem Programm hinaus; die KI rechnet auf diesem Rechner.

Im Importfenster selbst finden Sie nur den Schnellzugriff auf „KI ein/aus" und „Lernen ein/aus".

**Nebenbei behoben:** Eine von Hand gesetzte Kategorie sah nach jedem Neuaufbau der Prüfliste wieder wie ein Rateergebnis aus, weil Herkunft und Zuversicht dabei verloren gingen — beim Umlegen des KI-Schalters wäre sie als solches weggeworfen worden.

### Wenn Sie eine importierte Buchung später korrigieren, lernt die KI daraus

Wer eine importierte Zeile später von *Restaurant* auf *Lebensmittel* umbuchte, korrigierte bisher nur diese eine Buchung. Die KI behielt ihre Zuordnung und schlug beim nächsten Auszug wieder *Restaurant* vor. Das ehrlichste Signal, das es gibt — ein Mensch bessert nach —, verpuffte.

Das kommt jetzt zurück. Gelernt wird nur, wenn wirklich klar ist, woraus: Die Buchung muss aus einem Bankimport stammen, der Originaltext der Bank muss vorliegen, und Typ, Kategorie oder Tags müssen sich tatsächlich geändert haben. Eine reine Betragskorrektur lernt nichts. Und wenn Sie den Lernschalter oben ausgeschaltet haben, lernt auch eine Korrektur nichts.

Der Weg hängt an den zwei Stellen, an denen ein Mensch eine Buchung bearbeitet: der Schnelleingabe und dem Tagdialog der Buchungsliste. Automatische Änderungen — der LifePlanner-Abgleich, das Umbenennen einer Kategorie, „Rückgängig" — lernen ausdrücklich nicht mit.

### Die KI hält ihren eigenen Rat nicht mehr für einen Beleg

Bisher wog jede importierte Zeile gleich viel. Ob **Sie** eine Kategorie gesetzt oder die KI sie geraten und niemand widersprochen hatte, war im Lernspeicher nicht zu unterscheiden — und das Händlergedächtnis zählte die eigene Wiederholung als Bestätigung mit. Ein einmaliger Irrtum wurde damit bei jedem Import ein Stück sicherer.

Lernsignale tragen jetzt ihre Herkunft, und die Herkunft entscheidet:

- **Eine nachträgliche Korrektur wiegt am schwersten**, danach kommt, was Sie von Hand gesetzt haben, ganz zuletzt die bloß durchgewinkte Vermutung der KI.
- **Die KI erhöht ihren eigenen Zähler nicht mehr**, wenn sie nur bestätigt, was sie selbst vorgeschlagen hat.
- **Eine durchgewinkte Vermutung bleibt auf ihrem Startwert** und wird nicht mit der Zeit „sicher".
- **Sie verallgemeinert auch nicht** auf ähnliche, noch unbekannte Händler.
- **Widerspricht ein schwaches Signal einer besser belegten Entscheidung, wird es verworfen** — gebucht wird trotzdem, was in Ihrer Prüfliste steht. Die KI überstimmt Sie nicht.

Für bereits gelerntes Wissen aus früheren Fassungen lässt sich nicht mehr feststellen, ob es Handarbeit war; es gilt deshalb als „in der Prüfliste bestätigt". Das ist die vorsichtige Annahme.

### Auf einer bestehenden Datenbank

Für die Korrekturen oben braucht es den Originaltext der Bank, und den hat bisher niemand gespeichert. Ihre bestehende Datenbank bekommt beim Öffnen zwei zusätzliche Spalten dafür — die Tabelle wird ergänzt, nicht neu gebaut, und schon vorhandene Importzeilen bleiben unverändert stehen.

**Für Buchungen, die Sie vor dieser Fassung importiert haben, ist der Originaltext nicht nachträglich zu beschaffen.** Eine Korrektur an einer solchen Zeile lernt deshalb nichts — es wird verzichtet statt geraten. Ab dem nächsten Import schreibt das Programm den Banktext mit, und von da an wirkt es.

### Für Mitentwickelnde

Die Rangfolge der Lernquellen steht in genau einer Datei, `model/ai_learning_source.py`, die nichts vom Projekt kennt: `tracking_correction` > `manual` > `manual_bulk` > `ai_confirmed` > `import_confirmed`. Der Schnitt für die Verallgemeinerung liegt zwischen `merchant_memory`/`twint_memory` — die geben zurück, was schon gespeichert ist — und `naive_bayes`/`similar_merchant`, die auf einen unbekannten Fingerprint schließen.

Die drei Lerntabellen bekommen die Spalte `source` per `ALTER TABLE`, `bank_import_state` die beiden Textspalten `original_description` und `original_counterparty`. API-verträglich: `learn()` nimmt `source` (Vorgabe `manual`) und liefert `LearnOutcome` statt `None`, `BankImportItem` hat `learn_source`, `mark_classifications` nimmt Dreier- oder Vierer-Tupel.

Das Zurücklernen ist zweiteilig, weil der Stand davor nur davor zu haben ist: `snapshot()` vor dem Speichern, `relearn()` nach dem Setzen der Tags. Ein `relearn()` vor `set_entry_tags` lernte den Tagstand von gestern — ein Test prüft deshalb die Reihenfolge im Quelltext.

Der Reset in `model/ai_learning_store.py` schreibt jedes SQL aus, statt es aus Tabellennamen zusammenzusetzen, und läuft in einer Transaktion. `bank_import_state` sieht wie KI-Wissen aus, ist aber die Duplikaterkennung; wer sie mitlöscht, bereitet Doppelbuchungen vor.

Belegt durch 1478 Tests. Die Nachweise der Phase liegen in `tests/test_ai_settings_p21.py`, `tests/test_ai_storage_encryption_p22.py` und `tests/test_phase2_gate.py`; letzterer baut eine Datenbank im Schema *vor* dieser Fassung nach, mit einer bereits importierten Buchung darin. Die Logprobe läuft über Import, Korrektur und Reset gemeinsam auf `DEBUG`-Ebene: kein Wort aus dem Kontoauszug im Protokoll — genau dort hilft die verschlüsselte Datenbank nämlich nicht, die Logdatei liegt im Klartext. Zu jedem Baustein wurde die Gegenprobe gefahren.
