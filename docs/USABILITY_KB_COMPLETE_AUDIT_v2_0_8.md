# Vergleich und Help-/Wissensdatenbank-Audit v2.0.8

## Verglichene Versionen

1. `BudgetManager Source 2 0 8 RELEASE.zip`  
2. `BudgetManager Source 2 0 8 RELEASE HELP FIXED.zip`

## Ergebnis des Vergleichs

Die `RELEASE HELP FIXED`-Version ist die fachlich bessere Basis. Gegenüber `RELEASE` enthält sie bereits:

- lokale Hilfe unter `docs/help/`,
- F1-Verknüpfung auf die Wissensdatenbank,
- Ctrl+F1 für Tastenkürzel,
- verbesserte Fixkosten-/Wiederkehrend-Erklärung,
- verbesserte Dialogtexte im Fixkosten-Buchen-Dialog,
- PyInstaller-Einbindung für `docs/help`,
- korrigierte filterinterne Werte für Fixkosten/Wiederkehrend.

Die neu hochgeladene `RELEASE.zip` enthält diese Help-Fixes nicht vollständig und ist daher aus UX-/Hilfe-Sicht schwächer.

## Neu umgesetzt in dieser Version

### 1. Vollständige Wissensdatenbank

`docs/help/README.md` und `docs/help/index.html` wurden komplett erweitert. Enthalten sind jetzt:

- Erststart,
- Restore-Key/Datenbank-Key,
- Setup-Assistent,
- Datenbank und Datenordner,
- Backup/Restore und `.bmr`,
- Kategorien/Parent/Child,
- Fixkosten/Wiederkehrend/Fälligkeitstag,
- Drag & Drop,
- Budget-Reiter,
- Tracking/Buchungen,
- Übersicht/Dashboard,
- Budgetvorschläge,
- Sparziele,
- Favoriten,
- Tags,
- Globale Suche,
- Schnelleingabe,
- Export,
- Datenbankverwaltung,
- Updates,
- Einstellungen/Themes,
- Tastenkürzel,
- Kategorie-Löschlogik,
- Datenfluss Kategorie → Budget → Tracking → Übersicht,
- typische Stolperfallen,
- Best Practice für Anfänger,
- Mini-Lexikon.

### 2. Mindmap / Informations-Laufplan

Neu:

- Mermaid-Mindmap direkt in der Wissensdatenbank,
- zusätzlicher Export unter `docs/help/mindmap.mmd`,
- praktischer Text-Laufplan für Erstnutzer.

### 3. Restore-Key beim ersten Start immer anzeigen

Bisher wurde der Restore-Key im Erststart nur bei PIN/Passwort sicher angezeigt. Jetzt wird auch im Quick-Modus ein Restore-Key aus dem Datenbank-Key abgeleitet und angezeigt.

Grund: Wenn `users.json` oder Kontometadaten verloren gehen, kann der Restore-Key für verschlüsselte Daten/Backups entscheidend sein.

### 4. Direkter Help-Weg zum Restore-Key

Neu im Hilfe-Menü:

```text
Hilfe → Restore-Key anzeigen…
```

Bei verschlüsseltem Konto öffnet dies direkt die Kontoverwaltung mit Restore-Key-Anzeige. Bei unverschlüsselter DB öffnet es Backup & Restore mit Hinweis.

### 5. README ergänzt

`README.md` und `README_INSTALLATION.md` verweisen jetzt klar auf:

- lokale Wissensdatenbank,
- Restore-Key-Pflicht,
- Hilfe-Menü-Pfade.

## Release-Einschätzung

Aus Sicht Help/Usability ist diese Version deutlich näher an Release-Reife. Offen bleibt vor öffentlichem Release nur der echte Smoke-Test im gebauten Windows-/Linux-Paket:

- F1 öffnet `docs/help/index.html`,
- `Hilfe → Restore-Key anzeigen…` öffnet die Kontoverwaltung,
- Erststart zeigt Restore-Key auch bei Quick-Konto,
- PyInstaller enthält `docs/help`,
- Update-Dialog funktioniert im gebauten Paket.
