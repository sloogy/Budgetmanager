# BudgetManager 2.2.13 – UX-Testversion

Datum: 11. Juli 2026

## Ziel

Diese Version dient ausschliesslich dem praktischen Test einer vereinheitlichten Bedienung. Die Budget-, Tracking-, Sparziel- und POT-Berechnungen wurden nicht verändert.

## Umgesetzt

### Zentrale Aktionsleiste

Die häufigsten Aktionen sind dauerhaft oben sichtbar:

- Buchung erfassen
- Fixkosten buchen
- Kategorien verwalten
- Sparziele öffnen
- Globale Suche

Alle Einstiege verwenden dieselben bestehenden Dialoge und Methoden. Dadurch entstehen keine parallelen Buchungs- oder Kategorie-Logiken.

### Redundante Schaltflächen reduziert

Die zusätzliche Schaltfläche „Buchung erfassen“ wurde in folgenden Reitern ausgeblendet:

- Budget
- Kategorien
- Übersicht

Cockpit und Tracking behalten ihre kontextnahen Einstiege. Diese öffnen aber weiterhin denselben QuickAddDialog.

### Sparziel und POT bleiben getrennt

Die Systeme wurden ausdrücklich nicht zusammengeführt:

- **POT-System:** Rückstellungen für Franchise, Selbstbehalt und ähnliche periodische Belastungen.
- **Sparziel:** Fester Zielbetrag, beispielsweise Hochzeit, mit Fortschritt, Freigabe, Entnahmen und Abschluss.

Ein neuer Tooltip an der Sparziel-Aktion erklärt diese Trennung.

## Testfokus

1. Ist die obere Aktionsleiste sofort verständlich?
2. Vermisst du die ausgeblendeten Buchungs-Knöpfe in Budget, Kategorien oder Übersicht?
3. Ist klar, dass Fixkosten über Tracking gebucht werden?
4. Ist die Trennung von Sparziel und POT verständlich?
5. Wirkt die Oberfläche ruhiger oder eher voller?

## Technische Prüfung

- 403 Tests bestanden
- 2 Qt-GUI-Smoke-Tests übersprungen
- Python-Kompilierung bestanden
- Versionsprüfung bestanden
- Release-Lint bestanden

## Empfehlung

Diese Version noch nicht als öffentliches Release verwenden. Zuerst im normalen Alltag testen und danach entscheiden, welche Teile in die reguläre Version übernommen werden.
