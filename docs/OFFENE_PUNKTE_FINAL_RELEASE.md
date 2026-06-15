# Offene Punkte — Final Release BudgetManager v2.0.8

Stand: 14. Juni 2026

## Code-Status

Es sind nach Container-Prüfung keine offenen P0/P1-Codeblocker mehr bekannt.

Behoben im letzten Release-Fix:

- Update-Check schreibt bei erfolgreichem Download/Staging wieder ein strukturiertes GUI-Ergebnis (`available=true`, `staged=true`).
- Der Update-Dialog kann dadurch den Installationsbutton nach erfolgreichem Check freischalten.
- Der GUI-Text nach der Update-Prüfung ist nicht mehr irreführend: Installation wird freigeschaltet, nicht automatisch ohne Nutzeraktion gestartet.

## Noch manuell vor Veröffentlichung prüfen

Diese Punkte benötigen einen echten Build beziehungsweise ein echtes Windows-/Linux-System:

1. Windows-EXE/Installer starten.
2. Frischer Erststart: Sprache, Währung, Zahlenformat und bevorzugter Buchungstag.
3. Kategorie umbenennen/löschen inklusive Reassign und Parent-Children-Hochstufung.
4. Fixkosten-/wiederkehrende Budgetvorschläge in der GUI gegenprüfen.
5. Update-Dialog gegen ein echtes `latest.json` testen.
6. `latest.json` mit echten Release-URLs und SHA256 veröffentlichen.
7. About-Dialog und Fenstertitel zeigen `2.0.8`.

## Ergebnis

Source-Stand: releasefähig als v2.0.8-RC.

Öffentliches Release erst nach bestandenem Windows-/Linux-Smoke-Test und finalem Manifest hochladen.
