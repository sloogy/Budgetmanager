# Kategorie- & Baumstruktur (BudgetManager)

## Baum-Ansicht (Tree Structure)
Kategorien sind hierarchisch organisiert:
- **Root-Ebenen**: Einkommen, Ausgaben, Ersparnisse.
- **Hauptkategorien**: Erste Ebene unter den Root-Typen.
- **Unterkategorien**: Beliebig tiefe Verschachtelung via `parent_id`.

## Anzeige-Regeln im Budget-Tab
- **Blatt-Kategorien (Leafs)**: Direkt editierbar (Jan-Dez).
- **Eltern-Kategorien (Parents)**: 
  - Zeigen die Summe ihrer Kinder + einen optionalen eigenen **Puffer (Eigenbetrag)**.
  - Das Editieren einer Parent-Zelle ändert nur den Puffer dieser Kategorie.
  - Die Total-Spalte bei Parents ist schreibgeschützt (Summenbildung).

## Eigenschaften von Kategorien
- **Fixkosten (📌)**: Markierung für regelmäßige, feste Ausgaben.
- **Wiederkehrend (🔁)**: Kennzeichnung für automatische Buchungsvorschläge.
- **Fälligkeitstag**: Tag des Monats (1-31) für die Buchung.

## Technische Umsetzung
- Intern werden Kategorien über IDs referenziert (v8+).
- In der UI werden Pfade oft als Breadcrumbs dargestellt (z.B. `Wohnen › Miete`).
- **Eindeutigkeit**: Kategorienamen müssen innerhalb eines Typs (Einkommen/Ausgabe/Ersparnis) eindeutig sein.
