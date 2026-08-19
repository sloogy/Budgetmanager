# Wiki-Audit v2.2.36

## Ziel

Abgleich der Benutzerhilfe mit dem implementierten Funktionsinventar und Ergänzung einer grafischen Erklärung der Zusammenhänge.

## Ergebnis

Die definierten Kernbereiche sind im In-App-Handbuch, in der statischen HTML-Hilfe oder in den verlinkten Detailseiten abgedeckt:

- Erststart, Konto, Sprache, Währung und Restore-Key
- Konten, Kategorien, Unterkategorien, Tags und Fixkostenkennzeichen
- Budgetplanung, Jahreskopie, 13. Monatslohn und inkrementelle Budgets
- Tracking, Filter, Fix-/Wiederkehrend-Buchung und Favoriten
- Lernmodus, Soft-0-Budget und Budgetvorschläge
- POT/Rückstellungen und Abgrenzung zu Sparzielen
- Cockpit, Übersicht, Diagramme und Soll-Ist-Zusammenhang
- Monatsabschluss als Erinnerungsvermerk
- Jahreswechsel, Backup, Wiederherstellung und Datenbankpflege
- CSV/TXT-Export sowie transparente Grenze: kein direkter PDF-/Druck-/XLSX-Bericht
- Diagnose, Protokolle, Designprofile und GNOME-/Linux-Hinweise

## Grafiken

1. `docs/help/assets/wiki_audit_overview.png` – Ablauf vom Erststart bis Sicherheit.
2. `docs/help/assets/dataflow_decision_logic.png` – Datenfluss und Rückkopplungen.
3. `docs/help/assets/wiki_audit_dashboard.png` – kompakte Wiki-Gesamtübersicht.
4. `docs/help/wiki-audit.html` – responsive Offline-Seite mit allen Grafiken.

## Linux-Korrektur

Der Hilfe-Einstieg in der linken Seitenleiste verwendet sichtbar `? Hilfe` als normalen Text und ist deshalb nicht von einer Emoji-Schrift abhängig. Das behebt das auf Fedora/GNOME fehlende Fragezeichen.

## Qualitätsgrenze

Die Grafiken dienen der Orientierung. Bei verkürzten Formulierungen ist das dreisprachige In-App-Handbuch die maßgebliche Beschreibung.
