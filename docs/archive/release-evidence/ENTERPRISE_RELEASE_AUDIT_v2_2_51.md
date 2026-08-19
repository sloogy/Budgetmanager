# BudgetManager v2.2.51 – Enterprise Startup Hotfix Audit

**Auditdatum:** 2. August 2026  
**Ausgangsbasis:** BudgetManager v2.2.50 Important Improvements Release Ready  
**Finaler Stand:** BudgetManager v2.2.51 Startup Hotfix Release Ready

## 1. Auslöser und Fehlerursache

Der reale Fedora-/Python-3.14-Erststart brach im Sprachwahldialog ab:

```text
FrozenInstanceError: cannot assign to field 'accent_hover'
```

`UIColors` war korrekt als `@dataclass(frozen=True)` angelegt, schrieb jedoch in
`__post_init__` vier berechnete Hover-Farben über normale Attributzuweisungen.
Frozen-Dataclasses verbieten diese Zuweisung auch während `__post_init__`.

## 2. Umgesetzter Hotfix

- `accent_hover`, `positive_hover`, `warning_hover` und `negative_hover` sind nun
  explizite Dataclass-Felder mit `field(init=False)`.
- Die Initialisierung erfolgt frozen-konform über `object.__setattr__`.
- Der Farbcontainer bleibt nach der Initialisierung unveränderlich.
- Ein neuer Laufzeittest instanziiert `UIColors()` in einem separaten Prozess,
  prüft alle vier Hover-Felder und bestätigt die weiter aktive Frozen-Sperre.
- Der Testprozess isoliert optionale Qt-Stubs vollständig und verändert keinen
  globalen Zustand der restlichen Testsuite.

## 3. Freigabeurteil

**GO für Source-Release und Git-Tag `v2.2.51`.**

**Bedingtes GO für öffentliche Binärpakete.** Die reale Fedora-/Python-3.14-
Umgebung des Nutzers muss den korrigierten Erststart einmal bestätigen. Windows-
und Linux-Binärartefakte bleiben zusätzlich von CI, Zielsystem-GUI-Smokes,
Dependency-Scannern und Signaturen abhängig.

## 4. Automatisierte Regression

Die gesamte Testsuite wurde nach dem Fix und nach der Versionsumstellung in drei
unabhängigen Gruppen ausgeführt:

- **767 Tests bestanden**
- **13 erwartete Skips** für nicht installierte optionale Qt-/Plattformkomponenten
- **0 Fehler**

Der neue Startregressionstest ist darin enthalten.

## 5. Enterprise-Nachweise

| Audit | Ergebnis |
|---|---:|
| KILLCRITIC X10THINK | 10'000 Loops / 326'584 Prüfungen / 0 Warnungen / 0 Fehler |
| Enterprise Release Audit | 10'000 Loops / 112'000 Prüfungen / 0 Findings |
| DAU Enterprise Audit | 10'000 Loops / 764'770'000 bestätigte Prüfungen / 0 Findings |
| Final Release Audit | 1'000 Loops / 19'335 Prüfungen / 0 Warnungen / 0 Fehler |
| Deep Logic Audit | 1'000 Loops / 7'000 Prüfungen / 0 Findings |
| Stability Audit | 300 Loops / 2'400 Prüfungen / 0 Findings |
| Mega Release Audit | 1'000 Loops / 6'812 Prüfungen / 0 Findings |
| Release-Logik-Audit | 100 Loops / 0 Findings |
| Handbuch-Audit | 10/10 Bereiche bestanden |

Das UI-/ADHS-Audit meldet in der Qt-freien Auditumgebung ausschliesslich die
vorgesehenen Hinweise für nicht ausführbare Qt-Formular- und Dialogprüfungen;
es enthält keinen Fehler.

## 6. Performance und Sicherheits-Coverage

Der reproduzierbare Performance-Test mit 50'000 Trackingbuchungen, 12'000
Budgetzeilen und 100 Kategorien bestand alle Grenzwerte. Der höchste gemessene
Einzelschritt lag bei **0,0177 Sekunden**.

| Kritisches Modul | Lokale Coverage |
|---|---:|
| `model/restore_bundle.py` | 72,1 % |
| `updater/manifest_signing.py` | 98,9 % |
| `utils/secure_excel.py` | 96,6 % |

Die vollständige Gesamt-Coverage bleibt ein verpflichtendes CI-Gate.

## 7. Technischer Umfang

- 285 Python-Dateien / 86'689 Zeilen inklusive Tests und Auditwerkzeugen
- 131 produktive Python-Dateien / 59'887 Zeilen
- Model: 41 Dateien / 15'797 Zeilen
- Views: 55 Dateien / 35'531 Zeilen
- Tests: 119 Dateien / 15'693 Zeilen
- Tools: 35 Dateien / 11'109 Zeilen

## 8. Noch offene externe Gates

Vor einer Stable-Binärfreigabe müssen weiterhin bestehen:

1. echter Fedora-/Wayland-Erststart mit Python 3.14 und installiertem PySide6;
2. Windows-GUI-, Installer-, Portable-, Update- und Deinstallationstest;
3. Black, Mypy, Bandit und `pip-audit` in der isolierten CI-Umgebung;
4. vollständiges Coverage-Gate;
5. signierte Binärartefakte und signiertes Update-Manifest.

## 9. Schlussurteil

v2.2.50 darf wegen des reproduzierten Erststartfehlers nicht veröffentlicht
werden. **v2.2.51 ersetzt v2.2.50 vollständig** und ist der empfohlene neue
Source-Release-Kandidat.
