## 3.0.6 – 25. August 2026

Fehleranalyse der ausgelieferten 3.0.5 mit anschließender Korrektur. Die Gate-Batterie war weitgehend grün, meldete aber zwei reproduzierbare Befunde; drei weitere fand eine unabhängige Nachprüfung außerhalb der bestehenden Gates, einen sechsten die Kalt-Verifikation des fertigen Pakets.

### Behobene Fehler

- **Architektur-Gate war rot.** `views/main_window.py` hatte 3502 Zeilen bei einem harten Limit von 3500. Der Diagnose-Workflow (Anwendungs- und Absturzprotokoll, Diagnoseordner, Diagnose-ZIP) liegt jetzt in `views/main_window_diagnostics.py`; das Hauptfenster hält nur noch Weiterleitungen und ist auf 3457 Zeilen gesunken. Das Muster entspricht der Auslagerung des Einstellungsworkflows aus v2.2.60.
- **Bankimport V4 war nicht tastaturnavigierbar.** Als einziger von 15 komplexen Dialogen registrierte `views/bank_import_dialog_v4.py` keine Tab-Kette. Drei Gates meldeten den Befund unabhängig voneinander; `final_release_audit_1000` schlug dadurch in 100 von 1000 Schleifen fehl. Der Dialog ruft jetzt `configure_dialog_tab_order(self)`.
- **89 unübersetzte Strings in en.json und fr.json.** Die Schlüsselparität war perfekt (2159 Schlüssel in allen drei Sprachen), deshalb schlug das bestehende i18n-Audit nicht an — es prüft Schlüssel, nicht Werte. Englische und französische Nutzer sahen deutsche Beschriftungen unter anderem im Anmeldedialog, im Erscheinungsmanager, in der Tag-Verwaltung, bei den Sparzielen und in der globalen Suche.
- **Audit-Matrizen landeten im Wurzelverzeichnis.** `killcritic_x10think_10000` und `enterprise_ui_adhs_audit_1000` legten ihre CSV im Projekt-Hauptordner ab, wo `test_project_root_holds_no_release_evidence` sie verbietet. Wer die Batterie vollständig fuhr, bekam danach einen roten Test, dessen Ursache der Testlauf selbst war. `final_release_audit_1000` schreibt seit v2.2.60 korrekt ins Beweisarchiv; beide Werkzeuge ziehen jetzt nach.
- **Undo-Pruning setzte auf undokumentiertes SQLite-Verhalten.** Die Abfrage sortierte ein `SELECT DISTINCT group_id` nach der nicht ausgewählten Spalte `id`. SQLite verlangt laut Spezifikation, dass jeder ORDER-BY-Ausdruck einer DISTINCT-Abfrage eine Ergebnisspalte ist. Heutige Builds tolerieren die alte Form, garantiert ist sie nicht — und ein Fehler wäre vom umschließenden `except` verschluckt worden, sodass das Pruning still ausgesetzt und der `undo_stack` unbegrenzt gewachsen wäre. Die Abfrage gruppiert jetzt über `MAX(id)`; ein Fehlschlag wird als Warnung protokolliert statt auf Debug-Ebene.

### Aufgeräumt

- `.release-status/` mit den Fehlschlagsmarken von 3.0.2 und 3.0.3 lag im Auslieferungsbaum und ist entfernt.
- **49 einzelne Release-Berichte der Reihen 2.1.x und 2.2.x** sind zu einer Chronik zusammengefasst: `docs/archive/release-evidence/RELEASE_AUDIT_HISTORY_v2_1_7_bis_v2_2_60.md`. Sie enthält je Version Anlass, gefundene Fehler und Behebung sowie einen Abschnitt zu den vier wiederkehrenden Fehlerklassen. Die maschinell erzeugten Nachweise (`.csv`, `.txt`, `.json`) bleiben unangetastet — sie sind Rohdaten und werden teils direkt von Gates referenziert.
- Fünf versionsgestempelte Einmal-Dokumente aus `docs/` (Wiki-Audit 2.2.36, die beiden Release-Verifikationen 2.2.33 und 2.2.36, der Budget-Baum-Patch und das Handbuch-Audit 2.2.51) sind als Anhang in die Chronik überführt. Keines war im Code oder in Gates referenziert.
- `docs/FEATURE_INVENTORY_v2.2.37.md` heißt jetzt `docs/FEATURE_INVENTORY.md` und wird fortgeschrieben statt je Version neu angelegt. Alle 13 Punkte wurden für 3.0.6 erneut gegen Modul, Bedienweg und Test geprüft.

### Neue Regressionen

`tests/test_release_306_fixes.py` hält alle sechs Befunde fest — 16 Tests, bewusst Qt-frei, damit sie in der headless Batterie mitlaufen. Enthalten ist unter anderem eine Testfassung der Tab-Ketten-Prüfung, damit ein fehlender Dialog nicht erst im 1000-Schleifen-Lauf auffällt, sowie eine Wertprüfung der Sprachdateien, die deutsche Reste unabhängig von der Schlüsselparität erkennt.

### Hinweis zur Freigabe

Diese Fassung ist als Quellpaket freigegeben. Für eine öffentliche Binärfreigabe gelten unverändert die fünf Bedingungen aus v2.2.48: grüne GitHub Actions inklusive Bandit und `pip-audit`, PySide6-GUI-Smoke unter Fedora/Wayland und Windows, Starttest von Installer und portablen Paketen auf sauberen Systemen, Authenticode-Signatur samt Build-Attestation sowie ein signiertes `latest.json` mit passenden SHA-256-Summen.
