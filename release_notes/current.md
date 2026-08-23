## 3.0.5 – 23. August 2026

Seit 3.0.0 ist kein Release mehr entstanden. 3.0.1 bis 3.0.4 sind alle gescheitert, und zwar zuletzt immer an derselben Stelle: Der Release-Lauf hebt die Versionsnummer, und die Testsuite verlangt daraufhin einen Auditnachweis, dessen Dateiname genau diese Versionsnummer trägt. Erzeugt hat ihn kein Schritt der Pipeline. Jeder neue Versuch hob die Version erneut und entwertete den Nachweis erneut. 3.0.5 bricht diese Schleife: Der Lauf erzeugt den Nachweis jetzt selbst.

### Release-Pipeline

- Der Prepare-Lauf fährt nach dem Setzen der Version den 1000-Loop-Release-Audit und schreibt den Evidence-Index neu; beides geht in den Release-Commit ein.
- Der `build`-Job setzt `PYTHONUTF8` und `PYTHONIOENCODING` jetzt jobweit statt nur am Testschritt. Auf dem Windows-Runner lief jeder andere Schritt in cp1252.
- Das i18n-Audit schaltet seine Ausgabe selbst auf UTF-8 und verstümmelt ein unschreibbares Zeichen, statt daran zu sterben.

### Was 3.0.1 wirklich zu Fall brachte

Das i18n-Audit hatte zehn hartkodierte deutsche Sortier-Beschriftungen im Bankimport korrekt gefunden. Beim Ausdrucken des Befunds starb es dann an einem `UnicodeEncodeError`, weil die Beschriftungen einen Pfeil tragen und die Windows-Konsole cp1252 fuhr. Die Meldung, die den Fehler beschrieb, war selbst der Fehler — sichtbar war nur Exit-Code 1 ohne Hinweis worauf.

### Bankimport

- Unverändert gegenüber 3.0.4: mehrere CSV- und PDF-Dateien gemeinsam laden, suchen und sortieren, durchsuchbares Tag-Dropdown, sichtbarkeitsgebundene Mehrfachauswahl.
