# Tiefenanalyse — Dead Ends, Usability & Hilfe-Vollständigkeit (v2.0.8)

Stand: 14. Juni 2026
Bezug: `BudgetManager_Source_2_0_8` (RELEASE-Stand)

## 1. Zusammenfassung

Der größte Befund betrifft die **Hilfe**: Es gab **keine in der App erreichbare
Wissensdatenbank** und das **Fixkosten-Häkchen war nur unvollständig erklärt**.
Beides ist jetzt behoben. Dead Ends sind in der App überraschend selten – die
meisten Leerzustände sind bereits mit Hinweisen abgefangen; einen kleinen Punkt
habe ich ergänzt.

## 2. Hilfe-Vollständigkeit

### Befund (vorher)

- Das Menü *Hilfe* bot nur **Tastenkürzel**, **Setup-Assistent** und **Über** –
  keinerlei Themen-/Funktionshilfe. In den Locales existierte **kein einziger
  `help.*`-Inhaltsschlüssel**.
- Die **README** (gute Wissensquelle) war **nirgends in der App verlinkt**.
- Das **Fixkosten-Häkchen** hatte je nach Dialog uneinheitliche oder fehlende
  Tooltips. Vorhandener Text z. B. „Diese Kategorie ist eine monatlich feste
  Ausgabe“ bzw. „…wird in der Übersicht separat ausgewiesen“ – beides erklärte
  **nicht**, was das Häkchen tatsächlich auslöst (Buchung aus dem Budget; Schutz
  vor 0-Monats-Senkung in den Vorschlägen). Eine von zwei Fix-Checkboxen im
  Kategorie-Eigenschaften-Dialog hatte **gar keinen** Tooltip.

### Umgesetzt

- **In-App-Wissensdatenbank (Handbuch)**: *Hilfe → Handbuch* (Shift+F1).
  Durchsuchbarer Themenbrowser mit dreisprachigen Inhalten (de/en/fr):
  Einstieg · Kategorien · **Fixkosten** · Wiederkehrende · Budget & Vorschläge ·
  Sparziele · Backup · Updates · Währung/Zahlenformat.
- **Fixkosten-Thema ausführlich**: erklärt exakt, *was das Häkchen auslöst* –
  1) Betrag wird beim „Fixkosten buchen“ automatisch aus dem Budget übernommen
  (Budget 0 → übersprungen, keine 0-Buchung), 2) Schutz in Budgetvorschlägen
  (0-Monate senken nie allein; ≥ 3 echte Buchungen nötig; quartals-/jahresweise
  Fixkosten bleiben geschützt), 3) separate Anzeige; plus Abgrenzung zu
  *Wiederkehrend*.
- **Tooltips vereinheitlicht**: alle acht Fix-/Wiederkehrend-Checkboxen zeigen nun
  denselben vollständigen Hinweis inkl. Budget-Vorschlags-Wirkung und verweisen
  für Details aufs Handbuch.

> **Designentscheidung:** Statt die README 1:1 einzubetten (sie ist
> entwickler-/release-orientiert: Build-Befehle, Projektstruktur, Manifest …)
> wurde eine **kuratierte, endnutzertaugliche** Wissensdatenbank erstellt. Die
> README bleibt die technische Referenz; das Handbuch ist die Nutzerhilfe.

## 3. Dead Ends

### Bereits gut abgefangen (kein Handlungsbedarf)

| Situation | Verhalten |
|---|---|
| „Fixkosten buchen“ ohne Fix-Kategorie | Meldung **+ Tipp** „Budget setzen und als Fixkosten markieren“ |
| Sparziele leer | Hinweis **mit CTA** „Klicke auf ‹Verwalten›, um loszulegen“ |
| Keine Kategorien | „Bitte erst eine Hauptkategorie erstellen“ |
| Tags ohne Buchungen | „Es sind noch keine Tags mit Buchungen vorhanden“ |
| Übersichts-Charts ohne Daten | Titel „keine Daten“ statt leerer Fläche |
| Löschen ohne abhängige Daten | „Es hängen keine Buchungen … an dieser Kategorie“ |

### Gefundener Schwachpunkt → behoben

- **Löschen ohne Zielkategorie**: Das *Zuweisen*-Radio wird korrekt deaktiviert,
  war aber **unkommentiert** – der Nutzer sah nur eine ausgegraute Option. Jetzt
  erklärt ein **Tooltip** den Grund („Keine andere Kategorie gleichen Typs
  vorhanden“). Kein echter Dead End (Löschen bleibt möglich), aber klarer.

### Kleinere Restpunkte (optional, nicht blockierend)

- **Favoriten leer** zeigt nur „Keine Favoriten vorhanden.“ ohne CTA – ein kurzer
  Hinweis „Kategorie mit Rechtsklick anpinnen“ wäre konsistenter.
- **`setWhatsThis` wird nirgends genutzt** (0×). Tooltips (63×) + Handbuch decken
  den Bedarf; ein „?“-Kontexthilfe-Modus wäre ein nettes Extra, aber kein Muss.

## 4. Usability – weitere Beobachtungen

- **Statusleiste** zeigt dauerhaft aktiven User/DB – gut gegen „welcher Ordner?“-
  Verwirrung bei portablen Mehrfachkopien.
- **Drag & Drop** für Kategorie-Struktur und Budget-Umhängen ist vorhanden.
- **Zahlenformat** koppelt Eingabe- und Anzeigeformat (QLocale) – verhindert das
  klassische „Komma vs. Punkt“-Problem.
- **Tooltip-Abdeckung** ist mit 63 Tooltips solide, aber ungleich verteilt; die
  zentralen Flags sind jetzt vollständig erklärt.

## 5. Verifikation (Container)

```text
compileall .                 → 0 Syntaxfehler (inkl. help_dialog.py, help_content.py)
JSON-Gültigkeit              → alle gültig
i18n-Parität de/en/fr        → 3 × 1741 identisch (+6 neue Schlüssel)
tools/i18n_audit.py          → [OK] (Inhaltsdatei korrekt nicht als UI-String erfasst)
Tests (real-pytest)          → 35 passed, 1 skipped (unverändert; GUI-Smoke ohne PySide6)
```

> Der Handbuch-Dialog selbst braucht (wie alle Qt-Views) einen realen
> PySide6-Lauf zum Sicht-/Klick-Test; im Container ist nur die Syntax-/Import-
> Struktur prüfbar. Empfohlener Smoke: *Hilfe → Handbuch* öffnen, Suche testen,
> Fixkosten-Thema lesen, Sprache wechseln und erneut öffnen.

## 6. Empfehlung

Die Hilfe ist jetzt **inhaltlich vollständig** für die Kernfunktionen, das
Fixkosten-Häkchen ist an Ort und Stelle **und** im Handbuch erklärt, und die
wenigen Dead-End-Kanten sind geschlossen bzw. dokumentiert. Optionale Restpunkte
(Favoriten-CTA, WhatsThis) sind reine Komfort-Erweiterungen.
