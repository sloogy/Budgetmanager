# Änderungen: Budget-Tab Tree + Parent/Child Summen (V2.0 Patch)

## Was ist neu?

- Kategorien im Budget-Tab werden jetzt als **Tree** angezeigt:
  - Parent: `▸` (hat Unterkategorien)
  - Leaf: `•` (keine Unterkategorien)
  - Einrückung zeigt die Tiefe
  - Tooltip zeigt den kompletten Pfad (z.B. `Gesundheit › Krankenkasse › Prämie`)

## Editier-Regel

- **Leaf-Rows (ohne Kinder):**
  - Monatszellen (Jan–Dez) und Total sind wie gewohnt editierbar.

- **Parent-Rows (mit Kindern):**
  - Monatszellen zeigen **Total = Kinder-Summe + Puffer (Eigenbetrag)**.
  - Wenn du eine Monatszelle editierst, wird das als **Puffer/Eigenbetrag** gespeichert.
  - Die **Total-Spalte ist read-only**, weil eine Verteilung über 12 Monate sonst nicht eindeutig wäre.

## Warum so?

Damit du Parent-Kategorien als "Sammelbecken" nutzen kannst (z.B. Sicherheits-Puffer) ohne die Child-Budgets zu zerstören.

## Hinweis zum Footer "TOTAL"

- Der Footer summiert **ohne Doppelzählung**:
  - Leaf-Werte werden direkt summiert
  - Bei Parent-Kategorien wird nur der **Puffer** in die Gesamtsumme eingerechnet (Kinder sind schon in Leafs enthalten)
