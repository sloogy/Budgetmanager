"""Inhalte der In-App-Wissensdatenbank (Handbuch).

Reine Daten – KEINE Qt-/UI-Aufrufe. Dadurch wird diese Datei vom i18n-Audit
nicht als "hardcoded UI-String" erfasst und von PyInstaller automatisch
gebündelt (kein zusätzlicher Eintrag in der .spec nötig).

Struktur je Thema:
    {"id": ..., "icon": ...,
     "title": {"de":..., "en":..., "fr":...},
     "body":  {"de": <markdown>, "en":..., "fr":...}}

``body`` ist Markdown und wird via QTextBrowser.setMarkdown() gerendert.
Fehlt eine Sprache, fällt der Dialog auf Deutsch (HELP_FALLBACK_LANG) zurück.
"""

from __future__ import annotations

HELP_FALLBACK_LANG = "de"

# Spezielle Themen-ID, auf die ein "Schlüssel anzeigen"-Button verweisen kann.
HELP_TOPIC_DATABASE = "datenbank"


HELP_TOPICS = [
    # ── Einstieg ────────────────────────────────────────────────
    {
        "id": "einstieg",
        "icon": "🚀",
        "title": {"de": "Einstieg", "en": "Getting started", "fr": "Premiers pas"},
        "body": {
            "de": (
                "# Einstieg\n\n"
                "BudgetManager ist **portabel**: Programm und Daten liegen im selben Ordner "
                "(`data/`). Mehrere Kopien des Ordners = mehrere getrennte Budgets.\n\n"
                "**Empfohlene Reihenfolge:**\n\n"
                "1. **Kategorien** anlegen oder Vorlage übernehmen (Kategorie-Manager via **Strg+K** oder im **Budget**-Tab).\n"
                "2. **Budget** je Monat eintragen (Tab *Budget*). Leere Felder bleiben 0.\n"
                "3. **Buchungen** erfassen (Tab *Buchungen*) – manuell oder über *Fixkosten buchen*.\n"
                "4. In der **Übersicht** Soll/Ist und Auffälligkeiten prüfen.\n\n"
                "Der **Setup-Assistent** (*Hilfe → Erste Schritte*) führt durch diese Schritte. "
                "Beim allerersten Start wird zudem dein **Datenbank-/Restore-Key** angezeigt – "
                "siehe Thema *Datenbank & Schlüssel*."
            ),
            "en": (
                "# Getting started\n\n"
                "BudgetManager is **portable**: program and data live in the same folder "
                "(`data/`). Several copies of the folder = several separate budgets.\n\n"
                "**Recommended order:**\n\n"
                "1. Create **categories** or accept the template (category manager via **Ctrl+K** or in the **Budget** tab).\n"
                "2. Enter the **budget** per month (*Budget* tab). Empty fields stay 0.\n"
                "3. Record **transactions** (*Tracking* tab) – manually or via *Book fixed costs*.\n"
                "4. Check planned/actual and anomalies in the **Overview**.\n\n"
                "The **Setup assistant** (*Help → Getting started*) walks you through these steps. "
                "On the very first start your **database/restore key** is also shown – see "
                "*Database & key*."
            ),
            "fr": (
                "# Premiers pas\n\n"
                "BudgetManager est **portable** : programme et données sont dans le même dossier "
                "(`data/`). Plusieurs copies = plusieurs budgets séparés.\n\n"
                "**Ordre conseillé :**\n\n"
                "1. Créez des **catégories** ou reprenez le modèle (gestionnaire via **Ctrl+K** ou dans l'onglet **Budget**).\n"
                "2. Saisissez le **budget** par mois (onglet *Budget*). Champs vides = 0.\n"
                "3. Enregistrez des **opérations** (onglet *Suivi*) – manuellement ou via *Saisir les charges fixes*.\n"
                "4. Vérifiez prévu/réel et anomalies dans l'**Aperçu**.\n\n"
                "L'**assistant** (*Aide → Premiers pas*) guide ces étapes. Au tout premier "
                "démarrage, votre **clé de base/restauration** s'affiche aussi – voir "
                "*Base de données & clé*."
            ),
        },
    },
    # ── Kategorien ──────────────────────────────────────────────
    {
        "id": "kategorien",
        "icon": "🗂️",
        "title": {
            "de": "Kategorien & Struktur",
            "en": "Categories & structure",
            "fr": "Catégories & structure",
        },
        "body": {
            "de": (
                "# Kategorien & Struktur\n\n"
                "Kategorien haben einen **Typ** (z. B. Einnahmen, Ausgaben, Ersparnisse) und können "
                "**Haupt-** oder **Unterkategorie** sein.\n\n"
                "**Anlegen/Bearbeiten:** über den **Kategorie-Manager** (**Strg+K**) oder direkt im **Budget**-Tab. Pro Kategorie "
                "setzt du die Häkchen *Fixkosten* und *Wiederkehrend* und optional einen Buchungstag.\n\n"
                "**Sicher umbenennen & löschen:**\n\n"
                "- Umbenennen wird über **alle** Tabellen mitgezogen (Budget, Buchungen, Favoriten, "
                "Warnungen, wiederkehrende Buchungen, Sparziele).\n"
                "- Beim Löschen kannst du Buchungen einer **anderen Kategorie zuweisen** (Reassign); "
                "Budgetwerte im selben Monat werden **additiv zusammengeführt**.\n"
                "- Eine Hauptkategorie mit Kindern zu löschen, hebt die Kinder eine Ebene hoch.\n\n"
                "Gibt es keine passende Zielkategorie, ist *Zuweisen* deaktiviert (du kannst dann nur "
                "löschen). Struktur ändern geht per **Drag & Drop** – siehe eigenes Thema."
            ),
            "en": (
                "# Categories & structure\n\n"
                "Categories have a **type** (income, expenses, savings) and can be a **main** or "
                "**sub** category.\n\n"
                "**Create/edit:** via the **category manager** (**Ctrl+K**) or directly in the **Budget** tab. Per category you set "
                "the *Fixed cost* and *Recurring* checkboxes and an optional booking day.\n\n"
                "**Safe rename & delete:**\n\n"
                "- Renaming cascades across **all** tables (budget, tracking, favorites, warnings, "
                "recurring transactions, savings goals).\n"
                "- When deleting you can **reassign** transactions to another category; budget values "
                "in the same month are **merged additively**.\n"
                "- Deleting a main category with children promotes the children one level up.\n\n"
                "If no suitable target exists, *Reassign* is disabled (you can only delete). Re-parent "
                "via **drag & drop** – see its own topic."
            ),
            "fr": (
                "# Catégories & structure\n\n"
                "Les catégories ont un **type** (revenus, dépenses, épargne) et peuvent être "
                "**principale** ou **sous-catégorie**.\n\n"
                "**Créer/modifier :** via le **gestionnaire de catégories** (**Ctrl+K**) ou directement dans l'onglet **Budget**. Par catégorie, vous "
                "cochez *Charge fixe* et *Récurrent* et un jour de saisie éventuel.\n\n"
                "**Renommer et supprimer en sécurité :**\n\n"
                "- Le renommage se propage à **toutes** les tables (budget, suivi, favoris, alertes, "
                "récurrentes, objectifs).\n"
                "- À la suppression, vous pouvez **réaffecter** les opérations ; les budgets du même "
                "mois sont **fusionnés additivement**.\n"
                "- Supprimer une principale avec enfants remonte ceux-ci d'un niveau.\n\n"
                "Sans cible adaptée, *Réaffecter* est désactivé. Réorganisez par **glisser-déposer** – "
                "voir le thème dédié."
            ),
        },
    },
    # ── Drag & Drop ─────────────────────────────────────────────
    {
        "id": "draganddrop",
        "icon": "🖱️",
        "title": {"de": "Drag & Drop", "en": "Drag & drop", "fr": "Glisser-déposer"},
        "body": {
            "de": (
                "# Drag & Drop – wo, wie, was\n\n"
                "**Wo:**\n\n"
                "- **Budget-Tab / Kategorie-Manager**: Einträge im Baum per Maus ziehen.\n"
                "- **Budget-Tabelle** (Tab *Budget*): nur wenn in den Einstellungen aktiviert.\n\n"
                "**Wie:** Eintrag anklicken, gedrückt halten, an die neue Position/auf die neue "
                "Hauptkategorie ziehen, loslassen.\n\n"
                "**Was es bewirkt:**\n\n"
                "- Eine Kategorie unter eine andere ziehen macht sie zur **Unterkategorie**.\n"
                "- Auf die oberste Ebene ziehen macht sie wieder zur **Hauptkategorie**.\n"
                "- Die Zuordnung von Budget und Buchungen bleibt dabei erhalten.\n\n"
                "Ungültige Ziele (z. B. Kategorie in sich selbst, Typ-Mischung) werden abgelehnt. "
                "Lässt sich das Verschieben rückgängig machen? Ja – siehe *Rückgängig / Wiederholen*."
            ),
            "en": (
                "# Drag & drop – where, how, what\n\n"
                "**Where:**\n\n"
                "- **Budget tab / category manager**: drag entries in the tree.\n"
                "- **Budget table** (*Budget* tab): only if enabled in Settings.\n\n"
                "**How:** click an entry, hold, drag onto the new position / new main category, release.\n\n"
                "**What it does:**\n\n"
                "- Dragging a category under another makes it a **sub-category**.\n"
                "- Dragging it to the top level makes it a **main category** again.\n"
                "- Budget and transaction links are preserved.\n\n"
                "Invalid targets (e.g. a category into itself, mixing types) are rejected. Can the move "
                "be undone? Yes – see *Undo / redo*."
            ),
            "fr": (
                "# Glisser-déposer – où, comment, quoi\n\n"
                "**Où :**\n\n"
                "- **Onglet Budget / gestionnaire de catégories** : glissez les entrées dans l'arbre.\n"
                "- **Tableau du budget** (onglet *Budget*) : seulement si activé dans les Réglages.\n\n"
                "**Comment :** cliquez une entrée, maintenez, glissez vers la nouvelle position / "
                "catégorie principale, relâchez.\n\n"
                "**Effet :**\n\n"
                "- Glisser une catégorie sous une autre en fait une **sous-catégorie**.\n"
                "- La glisser au niveau supérieur en refait une **catégorie principale**.\n"
                "- Les liens budget et opérations sont conservés.\n\n"
                "Les cibles invalides (catégorie sur elle-même, mélange de types) sont refusées. "
                "Annulable ? Oui – voir *Annuler / rétablir*."
            ),
        },
    },
    # ── Budget ──────────────────────────────────────────────────
    {
        "id": "budget",
        "icon": "📊",
        "title": {
            "de": "Budget & Vorschläge",
            "en": "Budget & suggestions",
            "fr": "Budget & suggestions",
        },
        "body": {
            "de": (
                "# Budget & Vorschläge\n\n"
                "Im Tab *Budget* trägst du je Kategorie und Monat einen **Sollbetrag** ein. Die App "
                "vergleicht laufend mit den Ist-Buchungen.\n\n"
                "**Budgetvorschläge** (Forecast):\n\n"
                "- Es zählen abgeschlossene Monate (der laufende, unvollständige Monat nicht).\n"
                "- Ein Vorschlag entsteht erst bei einem **stabilen Muster**, nicht bei einem "
                "einzelnen Ausreißer.\n"
                "- **Fixkosten/Wiederkehrende** sind geschützt: 0-Monate senken dort das Budget nie "
                "allein (siehe *Fixkosten*).\n"
                "- Ein budgetierter Betrag bleibt relevant, auch wenn (noch) nichts gebucht wurde "
                "(z. B. Rücklagen).\n\n"
                "**Budgetwarnungen** melden Überschreitungen. Vorschläge sind immer nur Angebote – du "
                "entscheidest, ob du sie übernimmst. Ein leeres Budgetjahr lässt sich aus den "
                "vorhandenen Kategorien mit einem Klick anlegen."
            ),
            "en": (
                "# Budget & suggestions\n\n"
                "In the *Budget* tab you enter a **planned amount** per category and month. The app "
                "continuously compares it with actual bookings.\n\n"
                "**Budget suggestions** (forecast):\n\n"
                "- Completed months count (the current, incomplete month does not).\n"
                "- A suggestion only appears for a **stable pattern**, not a single outlier.\n"
                "- **Fixed/recurring** categories are protected: zero months never lower the budget on "
                "their own (see *Fixed costs*).\n"
                "- A budgeted amount stays relevant even if nothing has been booked yet (e.g. reserves).\n\n"
                "**Budget warnings** flag overruns. Suggestions are always just offers – you decide. An "
                "empty budget year can be created from existing categories in one click."
            ),
            "fr": (
                "# Budget & suggestions\n\n"
                "Dans l'onglet *Budget*, vous saisissez un **montant prévu** par catégorie et par mois. "
                "L'app le compare en continu aux écritures réelles.\n\n"
                "**Suggestions de budget** (prévision) :\n\n"
                "- Seuls les mois terminés comptent (pas le mois courant, incomplet).\n"
                "- Une suggestion n'apparaît que pour un **schéma stable**, pas un mois isolé.\n"
                "- Les catégories **fixes/récurrentes** sont protégées : les mois à zéro n'y baissent "
                "jamais le budget seuls (voir *Charges fixes*).\n"
                "- Un montant budgété reste pertinent même si rien n'a été saisi (p. ex. réserves).\n\n"
                "Les **alertes** signalent les dépassements. Les suggestions ne sont que des "
                "propositions – c'est vous qui décidez. Une année vide se crée d'un clic depuis les "
                "catégories existantes."
            ),
        },
    },
    # ── Cockpit ─────────────────────────────────────────────────
    {
        "id": "cockpit",
        "icon": "🏠",
        "title": {
            "de": "Cockpit / Startseite",
            "en": "Cockpit / start page",
            "fr": "Cockpit / accueil",
        },
        "body": {
            "de": (
                "# Cockpit / Startseite\n\n"
                "Das **Cockpit** ist die ruhige Startseite: Es zeigt nur das Wichtigste und ersetzt nicht die Fachreiter.\n\n"
                "## Was sehe ich dort?\n"
                "- **Monatsstatus:** Einnahmen, Ausgaben, Ersparnisse und ein schneller Restwert.\n"
                "- **Favoriten:** Kategorien, die du immer im Blick behalten willst. Genau hier machen Favoriten am meisten Sinn.\n"
                "- **Aktive Sparziele:** Fortschritt als Balken; der Bereich verschwindet, wenn keine aktiven Ziele existieren.\n"
                "- **Budget-Ampel:** Budget überschritten, Einnahmen/Sparen noch nicht erreicht oder Ausgaben kaum genutzt.\n"
                "- **Offene Monatsbuchungen:** Fixkosten und wiederkehrende Buchungen, die im aktuellen Monat noch fehlen.\n"
                "- **Letzte 10 Buchungen:** schnelle Plausibilitätskontrolle.\n\n"
                "## Wie bleibt es übersichtlich?\n"
                "Über **⚙ Cockpit gestalten** oder **Ansicht → Anzeigen → Cockpit-Bereiche** blendest du Bereiche ein oder aus.\n"
                "Jeder Hauptreiter kann über **Ansicht → Anzeigen → Reiter ein-/ausblenden** verborgen werden. Mindestens ein Reiter bleibt immer sichtbar.\n"
            ),
            "en": "# Cockpit / start page\n\nA compact home tab with KPIs, favorites, active savings goals, budget alerts, missing monthly bookings and recent transactions. Panels and main tabs can be hidden via View → Show.",
            "fr": "# Cockpit / accueil\n\nUn onglet d'accueil compact avec indicateurs, favoris, objectifs actifs, alertes budget, écritures mensuelles manquantes et dernières opérations. Les panneaux et onglets peuvent être masqués via Affichage → Afficher.",
        },
    },
    # ── Buchungen ───────────────────────────────────────────────
    {
        "id": "buchungen",
        "icon": "🧾",
        "title": {
            "de": "Buchungen / Tracking",
            "en": "Transactions / tracking",
            "fr": "Opérations / suivi",
        },
        "body": {
            "de": (
                "# Buchungen / Tracking\n\n"
                "Im Tab *Buchungen* erfasst du tatsächliche Einnahmen und Ausgaben mit Datum, Typ, "
                "Kategorie, Betrag und optionalem Detailtext.\n\n"
                "- **Schnelle Erfassung:** über die Schnell-Hinzufügen-Funktion (Tastenkürzel).\n"
                "- **Filtern & Suchen:** nach Zeitraum, Typ, Kategorie und Freitext.\n"
                "- **Fixkosten/Wiederkehrende buchen:** prüft, was im Monat noch fehlt, und bietet eine "
                "Auswahlliste an (siehe *Fixkosten* und *Wiederkehrende*).\n"
                "- **Tags** lassen sich zusätzlich vergeben (siehe *Tags*).\n\n"
                "Jede Buchung wirkt sofort in der Übersicht (Ist gegen Soll). Fehler lassen sich per "
                "*Rückgängig* korrigieren."
            ),
            "en": (
                "# Transactions / tracking\n\n"
                "In the *Tracking* tab you record actual income and expenses with date, type, category, "
                "amount and an optional detail text.\n\n"
                "- **Quick entry:** via the quick-add function (keyboard shortcut).\n"
                "- **Filter & search:** by period, type, category and free text.\n"
                "- **Book fixed/recurring:** checks what is still missing this month and offers a "
                "selection list (see *Fixed costs* and *Recurring*).\n"
                "- **Tags** can be added too (see *Tags*).\n\n"
                "Every booking takes effect immediately in the overview (actual vs. planned). Mistakes "
                "can be corrected via *Undo*."
            ),
            "fr": (
                "# Opérations / suivi\n\n"
                "Dans l'onglet *Suivi*, vous enregistrez les revenus et dépenses réels avec date, type, "
                "catégorie, montant et un texte de détail facultatif.\n\n"
                "- **Saisie rapide :** via la fonction d'ajout rapide (raccourci).\n"
                "- **Filtrer & rechercher :** par période, type, catégorie et texte libre.\n"
                "- **Saisir fixes/récurrentes :** vérifie ce qui manque ce mois-ci et propose une "
                "liste (voir *Charges fixes* et *Récurrentes*).\n"
                "- Des **étiquettes** peuvent être ajoutées (voir *Étiquettes*).\n\n"
                "Chaque écriture agit immédiatement dans l'aperçu (réel vs. prévu). Les erreurs se "
                "corrigent via *Annuler*."
            ),
        },
    },
    # ── Fixkosten (Flaggschiff) ─────────────────────────────────
    {
        "id": "fixkosten",
        "icon": "📌",
        "title": {
            "de": "Fixkosten (das Häkchen)",
            "en": "Fixed costs (the checkbox)",
            "fr": "Charges fixes (la case)",
        },
        "body": {
            "de": (
                "# Fixkosten – was das Häkchen auslöst\n\n"
                "Das Häkchen **Fixkosten** schützt eine Kategorie in der Budgetlogik. "
                "Zusammen mit **Wiederkehrend** ist es ein echter fixer Monatsbetrag (Miete, Prämie, Abo). "
                "Ohne Wiederkehrend ist es ein variabler Kostenblock/Rückstellung (Franchise, Selbstbehalt). Es ändert drei Dinge:\n\n"
                "## 1. Buchung aus dem Budget\n"
                "Über **Buchungen → Fix/Wiederkehrend buchen** wird eine Buchungsliste vorbereitet.\n\n"
                "- **Fix + Wiederkehrend**: Betrag kommt aus dem Budget, ist gesperrt und wird einmal pro Monat gebucht.\n"
                "- **Fix ohne Wiederkehrend**: Betrag ist editierbar und mit dem offenen Restbetrag vorbelegt. Gut für Franchise/Selbstbehalt.\n"
                "- **Wiederkehrend ohne Fix**: Betrag ist ebenfalls editierbar.\n"
                "- Ist bei echter Fixkosten-Buchung der **Budgetwert 0**, wird übersprungen – es entsteht **keine 0-Buchung**.\n\n"
                "## 2. Schutz in Budgetvorschlägen\n"
                "Bei Fixkosten ist **0 nie allein der Auslöser** für einen Vorschlag. Ein Monat ohne "
                "Buchung heißt *nicht* automatisch „Budget zu hoch“ – die Zahlung kann später, "
                "quartalsweise oder jährlich kommen.\n\n"
                "- Monate ohne Buchung werden für Budgetänderungen **ignoriert**.\n"
                "- Erst **mehrere echte Buchungen** (mindestens drei) können einen Vorschlag auslösen.\n"
                "- So sind **inkrementelle/lumpy** Fixkosten geschützt, während eine echte, wiederholte "
                "Überschreitung weiterhin eine Erhöhung vorschlagen darf.\n\n"
                "## 3. Anzeige\n"
                "Fixkosten werden in der Übersicht **separat ausgewiesen**.\n\n"
                "> **Merksatz:** Nur **Fixkosten + Wiederkehrend** ist eine vollautomatische Monatsbuchung. "
                "Alles mit genau einem Häkchen bleibt im Buchungsdialog editierbar und gilt erst als erledigt, "
                "wenn der Monatsbudgetbetrag erreicht wurde."
            ),
            "en": (
                "# Fixed costs – what the checkbox does\n\n"
                "The **Fixed cost** checkbox protects a category in the budget logic. Combined with **Recurring**, "
                "it is a true fixed monthly amount. Without recurring, it is a variable reserve/cost block. It changes three things:\n\n"
                "## 1. Booking from the budget\n"
                "Via **Tracking → Book fixed/recurring** a booking list is prepared.\n\n"
                "- **Fixed + recurring**: amount comes from the budget and is locked.\n"
                "- **Fixed without recurring**: amount is editable and prefilled with the remaining budget.\n"
                "- **Recurring without fixed**: amount is also editable.\n"
                "- If a true fixed booking has **budget value 0**, it is skipped – **no zero booking**.\n\n"
                "## 2. Protection in budget suggestions\n"
                "For fixed costs, **0 alone never triggers** a suggestion. A month without a booking "
                "does *not* automatically mean “budget too high” – payment may come later, quarterly or "
                "yearly.\n\n"
                "- Months without a booking are **ignored** for budget changes.\n"
                "- Only **several real bookings** (at least three) can trigger a suggestion.\n"
                "- This protects **incremental/lumpy** fixed costs, while a genuine, repeated overrun "
                "may still suggest an increase.\n\n"
                "## 3. Display\n"
                "Fixed costs are shown **separately** in the overview.\n\n"
                "> **Rule of thumb:** Only **fixed + recurring** is a fully automatic monthly booking. "
                "Single-flag categories remain editable and are only done once the monthly budget amount is reached."
            ),
            "fr": (
                "# Charges fixes – ce que déclenche la case\n\n"
                "La case **Charge fixe** marque une catégorie comme un montant fixe et récurrent "
                "(loyer, assurance, abonnement …). Elle change trois choses :\n\n"
                "## 1. Saisie depuis le budget\n"
                "Via **Suivi → Saisir les charges fixes**, le montant est repris **automatiquement "
                "depuis le budget** du mois.\n\n"
                "- Si le **budget vaut 0**, la catégorie est **ignorée** – **aucune écriture à 0**.\n"
                "- Si déjà saisi ce mois-ci, pas de doublon.\n\n"
                "## 2. Protection dans les suggestions\n"
                "Pour les charges fixes, **0 seul ne déclenche jamais** une suggestion. Un mois sans "
                "écriture ne signifie *pas* « budget trop élevé » – le paiement peut être trimestriel "
                "ou annuel.\n\n"
                "- Les mois sans écriture sont **ignorés** pour les changements de budget.\n"
                "- Seules **plusieurs écritures réelles** (au moins trois) peuvent déclencher une "
                "suggestion.\n"
                "- Cela protège les charges **ponctuelles/irrégulières**, tandis qu'un dépassement réel "
                "et répété peut toujours proposer une hausse.\n\n"
                "## 3. Affichage\n"
                "Les charges fixes sont affichées **séparément** dans l'aperçu.\n\n"
                "> **Fixe vs. récurrent :** *Charge fixe* = montant fixe depuis le budget. *Récurrent* = "
                "écriture régulière dont le montant reste ajustable. Les deux cases sont combinables."
            ),
        },
    },
    # ── Wiederkehrend ───────────────────────────────────────────
    {
        "id": "wiederkehrend",
        "icon": "🔁",
        "title": {
            "de": "Wiederkehrende Buchungen",
            "en": "Recurring transactions",
            "fr": "Opérations récurrentes",
        },
        "body": {
            "de": (
                "# Wiederkehrende Buchungen\n\n"
                "Markierst du eine Kategorie als **wiederkehrend**, kannst du je Kategorie einen "
                "**Soll-Buchungstag** setzen. Über **Buchungen → Fixkosten/Wiederkehrende buchen** "
                "prüft die App, ob im aktuellen Monat schon gebucht wurde.\n\n"
                "- Fehlende Buchungen erscheinen in einer **Auswahlliste**; du entscheidest, was "
                "übernommen wird.\n"
                "- Bei rein wiederkehrenden Kategorien (ohne Fix-Häkchen) lässt sich der **Betrag in "
                "der Liste anpassen**. Ein belassener 0-Betrag wird übersprungen.\n\n"
                "So vermeidest du Doppelbuchungen und vergisst keine regelmäßige Zahlung."
            ),
            "en": (
                "# Recurring transactions\n\n"
                "Marking a category as **recurring** lets you set a **target booking day** per "
                "category. Via **Tracking → Book fixed/recurring** the app checks whether the current "
                "month has already been booked.\n\n"
                "- Missing bookings appear in a **selection list**; you decide what to apply.\n"
                "- For purely recurring categories (no fixed-cost flag) the **amount can be adjusted** "
                "in the list. A 0 amount left in is skipped.\n\n"
                "This avoids double bookings and forgotten regular payments."
            ),
            "fr": (
                "# Opérations récurrentes\n\n"
                "En marquant une catégorie comme **récurrente**, vous définissez un **jour de saisie "
                "cible** par catégorie. Via **Suivi → Saisir fixes/récurrentes**, l'app vérifie si le "
                "mois en cours a déjà été saisi.\n\n"
                "- Les écritures manquantes apparaissent dans une **liste** ; vous décidez.\n"
                "- Pour les catégories purement récurrentes (sans case fixe), le **montant est "
                "ajustable** dans la liste. Un 0 laissé est ignoré.\n\n"
                "Cela évite les doublons et les paiements réguliers oubliés."
            ),
        },
    },
    # ── Übersicht ───────────────────────────────────────────────
    {
        "id": "uebersicht",
        "icon": "📈",
        "title": {"de": "Übersicht", "en": "Overview", "fr": "Aperçu"},
        "body": {
            "de": (
                "# Übersicht\n\n"
                "Die Übersicht bündelt deine Lage auf einen Blick:\n\n"
                "- **Kennzahlen (KPI):** Summen für Einnahmen, Ausgaben, Saldo.\n"
                "- **Soll/Ist je Kategorie:** Budget gegen tatsächlich Gebuchtes, inkl. Abweichung.\n"
                "- **Sparziele:** Fortschritt deiner Ziele (siehe *Sparziele*).\n"
                "- **Diagramme:** Verteilung/Verlauf; ohne Daten erscheint ein Hinweis statt leerer "
                "Fläche.\n"
                "- **Filter/Suche** rechts: Zeitraum, Kategorie, Betragsgrenzen, Freitext.\n\n"
                "Über die Übersicht erreichst du auch das **Verwalten** der Sparziele."
            ),
            "en": (
                "# Overview\n\n"
                "The overview bundles your situation at a glance:\n\n"
                "- **KPIs:** totals for income, expenses, balance.\n"
                "- **Planned/actual per category:** budget vs. actually booked, incl. deviation.\n"
                "- **Savings goals:** progress of your goals (see *Savings goals*).\n"
                "- **Charts:** distribution/trend; with no data a hint appears instead of a blank area.\n"
                "- **Filter/search** on the right: period, category, amount limits, free text.\n\n"
                "From the overview you also reach **Manage** for savings goals."
            ),
            "fr": (
                "# Aperçu\n\n"
                "L'aperçu réunit votre situation d'un coup d'œil :\n\n"
                "- **Indicateurs (KPI) :** totaux revenus, dépenses, solde.\n"
                "- **Prévu/réel par catégorie :** budget vs. saisi, écart inclus.\n"
                "- **Objectifs d'épargne :** progression (voir *Objectifs d'épargne*).\n"
                "- **Graphiques :** répartition/évolution ; sans données, une indication s'affiche.\n"
                "- **Filtre/recherche** à droite : période, catégorie, limites de montant, texte libre.\n\n"
                "Depuis l'aperçu, vous accédez aussi à **Gérer** les objectifs."
            ),
        },
    },
    # ── Sparziele ───────────────────────────────────────────────
    {
        "id": "sparziele",
        "icon": "🎯",
        "title": {
            "de": "Sparziele – wann, wie, wo",
            "en": "Savings goals – when, how, where",
            "fr": "Objectifs – quand, comment, où",
        },
        "body": {
            "de": (
                "# Sparziele – wann, wie, wo\n\n"
                "**Wann nutzen?** Für konkrete Sparvorhaben mit Zielbetrag – z. B. Notgroschen, "
                "Urlaub, neues Gerät. So siehst du, wie weit du bist und ob du im Plan liegst.\n\n"
                "**Wo erreichbar, ohne omnipräsent zu sein:**\n\n"
                "- **Budget:** kleiner Button *🎯 Sparziele* neben der Schnelleingabe. Dort planst du Ziele als Teil deines Budgets.\n"
                "- **Tracking/Buchungen:** ein kompakter Bereich *Aktive Sparziele* erscheint nur, wenn Ziele aktiv sind. Doppelklick öffnet direkt das Ziel.\n"
                "- **Übersicht:** zeigt den Gesamtfortschritt und dient zur Kontrolle.\n"
                "- **Extras / Ansicht:** Sparziele bleiben zusätzlich direkt erreichbar.\n\n"
                "**Roter Faden:**\n\n"
                "1. Ziel im Budget-Kontext anlegen, z. B. *Notgroschen 3’000 CHF*.\n"
                "2. Optional mit einer Ersparnisse-Kategorie verknüpfen, z. B. *Notgroschen*.\n"
                "3. Einzahlungen als Tracking-Buchungen unter **Ersparnisse** buchen.\n"
                "4. Fortschritt in Tracking und Übersicht prüfen.\n"
                "5. Bei Erreichen **freigeben**. Dann ist der erreichte Stand eingefroren.\n"
                "6. Geld herausbuchen: im Tracking Typ **Ersparnisse** wählen, die Ziel-Kategorie wählen "
                "und den Betrag **negativ** erfassen, z. B. `-500 CHF`.\n"
                "7. Wenn erledigt: **abschließen**.\n\n"
                "**Ist eine negative Zahl gesperrt?** Nein, nicht für Ersparnisse. Negative Beträge "
                "sind bei **Ersparnisse** erlaubt und bedeuten Entnahme aus Sparziel/Ersparnis. "
                "Bei **Ausgaben** bleiben negative Beträge gesperrt, weil Ausgaben positiv erfasst werden sollen.\n\n"
                "**Nicht verwechseln:** Das Herausbuchen erfolgt über die Ersparnisse-Kategorie des Ziels. "
                "Eine echte Ausgabe kannst du zusätzlich separat buchen, wenn sie in der Ausgabenstatistik erscheinen soll.\n\n"
                "**Grenzen:** Der Sparziel-Stand darf nicht unter 0 fallen und nicht über 100 % steigen. "
                "Wenn du mehr entnehmen willst, als aktuell vorhanden ist, oder mehr einzahlen willst, "
                "als bis zum Zielbetrag noch fehlt, blockiert BudgetManager die Buchung und zeigt eine Meldung. "
                "Beispiele: Stand `300 CHF`, Entnahme `-500 CHF` → blockiert. Ziel `1’000 CHF`, "
                "Stand `900 CHF`, Einzahlung `200 CHF` → blockiert. "
                "Ziele werden beim Umbenennen/Löschen von Kategorien sauber mitgeführt und sind Teil des Backups."
            ),
            "en": (
                "# Savings goals – when, how, where\n\n"
                "**When to use?** For concrete savings plans with a target amount – e.g. emergency "
                "fund, holiday, new device. You see how far along you are and whether you're on track.\n\n"
                "**Where:** the **Overview** has a *Savings goals* panel. Open the dialog via "
                "**‹Manage›**. While no goal exists, the panel shows *“Click ‹Manage› to get started.”*\n\n"
                "**How to create:**\n\n"
                "1. Open *Manage*, add a new goal.\n"
                "2. Enter a **name** and **target amount**, optionally a **target date**.\n"
                "3. Optionally **link a category** (or *None*).\n\n"
                "**Limits:** the savings goal balance cannot fall below 0 and cannot go above 100%. "
                "If you try to withdraw more than currently saved, or deposit more than the remaining target amount, "
                "BudgetManager blocks the booking and shows a message. Goals are carried correctly "
                "when categories are renamed/deleted and are part of the backup."
            ),
            "fr": (
                "# Objectifs d'épargne – quand, comment, où\n\n"
                "**Quand ?** Pour des projets d'épargne concrets avec montant cible – fonds d'urgence, "
                "vacances, nouvel appareil. Vous voyez votre avancement et si vous êtes dans les temps.\n\n"
                "**Où :** l'**Aperçu** a un panneau *Objectifs d'épargne*. Ouvrez la boîte via "
                "**‹Gérer›**. Sans objectif, le panneau indique *« Cliquez sur ‹Gérer› pour commencer. »*\n\n"
                "**Comment créer :**\n\n"
                "1. Ouvrez *Gérer*, ajoutez un objectif.\n"
                "2. Saisissez un **nom** et un **montant cible**, éventuellement une **date**.\n"
                "3. Liez éventuellement une **catégorie** (ou *Aucune*).\n\n"
                "**Limites :** le solde d’un objectif ne peut pas passer sous 0 ni dépasser 100 %. "
                "Si vous tentez de retirer plus que le montant disponible ou de verser plus que le reste à atteindre, "
                "BudgetManager bloque l’écriture et affiche un message. Les objectifs suivent les "
                "renommages/suppressions de catégories et font partie de la sauvegarde."
            ),
        },
    },
    # ── Favoriten ───────────────────────────────────────────────
    {
        "id": "favoriten",
        "icon": "⭐",
        "title": {
            "de": "Favoriten – wofür?",
            "en": "Favorites – what for?",
            "fr": "Favoris – à quoi ?",
        },
        "body": {
            "de": (
                "# Favoriten – wofür ist das gut?\n\n"
                "Mit **Favoriten** pinnst du **häufig genutzte Kategorien** an. Das spart Wege bei "
                "Kategorien, die du oft brauchst.\n\n"
                "**Nutzen:**\n\n"
                "- Schneller **Favoriten-Überblick** mit *Budget gegen Gebucht* für genau diese "
                "Kategorien – ohne durch die ganze Liste zu scrollen.\n"
                "- Ideal, um deine wichtigsten Posten (z. B. Lebensmittel, Sprit, Miete) laufend im "
                "Blick zu behalten.\n\n"
                "**So geht's:** Eine Kategorie als Favorit markieren/lösen (Pin-Aktion). Ist noch "
                "nichts angepinnt, ist der Favoriten-Bereich leer. Favoriten werden beim Umbenennen/"
                "Löschen von Kategorien korrekt mitgeführt."
            ),
            "en": (
                "# Favorites – what are they for?\n\n"
                "With **favorites** you pin **frequently used categories**. This saves clicks for the "
                "categories you need often.\n\n"
                "**Benefit:**\n\n"
                "- A quick **favorites overview** with *budget vs. booked* for exactly those "
                "categories – no scrolling through the whole list.\n"
                "- Ideal for keeping your key items (e.g. groceries, fuel, rent) in view.\n\n"
                "**How:** mark/unmark a category as favorite (pin action). If nothing is pinned, the "
                "favorites area is empty. Favorites are carried correctly when categories are "
                "renamed/deleted."
            ),
            "fr": (
                "# Favoris – à quoi ça sert ?\n\n"
                "Avec les **favoris**, vous épinglez les **catégories fréquentes**. Cela fait gagner "
                "des clics pour celles que vous utilisez souvent.\n\n"
                "**Intérêt :**\n\n"
                "- Un **aperçu des favoris** rapide avec *budget vs. saisi* pour ces seules catégories "
                "– sans faire défiler toute la liste.\n"
                "- Idéal pour garder vos postes clés (courses, carburant, loyer) à l'œil.\n\n"
                "**Comment :** marquez/retirez une catégorie en favori (épingle). Sans favori, la zone "
                "est vide. Les favoris suivent les renommages/suppressions."
            ),
        },
    },
    # ── Tags ────────────────────────────────────────────────────
    {
        "id": "tags",
        "icon": "🏷️",
        "title": {"de": "Tags / Labels", "en": "Tags / labels", "fr": "Étiquettes"},
        "body": {
            "de": (
                "# Tags / Labels\n\n"
                "**Tags** sind eine zusätzliche, freie Kategorisierung **quer zu den Kategorien** – "
                "z. B. *Urlaub2026*, *steuerlich absetzbar*, *Projekt X*.\n\n"
                "- Du vergibst Tags an einzelne Buchungen.\n"
                "- So lassen sich Ausgaben **themen- statt nur kategorienbezogen** auswerten.\n"
                "- Über die Tag-Verwaltung behältst du den Überblick; es werden nur Tags angezeigt, zu "
                "denen es Buchungen gibt.\n\n"
                "Tags ersetzen keine Kategorien – sie ergänzen sie für Auswertungen, die sich nicht in "
                "die Kategoriestruktur pressen lassen."
            ),
            "en": (
                "# Tags / labels\n\n"
                "**Tags** are an additional, free categorization **across categories** – e.g. "
                "*Holiday2026*, *tax-deductible*, *Project X*.\n\n"
                "- You assign tags to individual transactions.\n"
                "- This lets you analyse spending **by theme, not only by category**.\n"
                "- The tag manager keeps the overview; only tags that have bookings are shown.\n\n"
                "Tags don't replace categories – they complement them for analyses that don't fit the "
                "category tree."
            ),
            "fr": (
                "# Étiquettes\n\n"
                "Les **étiquettes** sont une catégorisation libre **transversale aux catégories** – "
                "p. ex. *Vacances2026*, *déductible*, *Projet X*.\n\n"
                "- Vous les attribuez à des opérations individuelles.\n"
                "- Cela permet d'analyser les dépenses **par thème, pas seulement par catégorie**.\n"
                "- Le gestionnaire d'étiquettes garde la vue ; seules celles ayant des écritures "
                "s'affichent.\n\n"
                "Les étiquettes ne remplacent pas les catégories – elles les complètent pour des "
                "analyses hors de l'arbre."
            ),
        },
    },
    # ── Undo/Redo ───────────────────────────────────────────────
    {
        "id": "undoredo",
        "icon": "↩️",
        "title": {
            "de": "Rückgängig / Wiederholen",
            "en": "Undo / redo",
            "fr": "Annuler / rétablir",
        },
        "body": {
            "de": (
                "# Rückgängig / Wiederholen\n\n"
                "Viele Aktionen lassen sich rückgängig machen und wiederholen.\n\n"
                "- **Rückgängig:** `Strg+Z`\n"
                "- **Wiederholen:** `Strg+Y` oder `Strg+Umschalt+Z`\n\n"
                "Das gilt app-weit, auch für komplexe Aktionen wie Kategorie-Umbenennungen: Undo/Redo "
                "setzt dann **alle betroffenen Tabellen** konsistent zurück bzw. wieder vor (Budget, "
                "Buchungen, Favoriten, Warnungen, wiederkehrende Buchungen, Sparziele).\n\n"
                "So kannst du Änderungen gefahrlos ausprobieren."
            ),
            "en": (
                "# Undo / redo\n\n"
                "Many actions can be undone and redone.\n\n"
                "- **Undo:** `Ctrl+Z`\n"
                "- **Redo:** `Ctrl+Y` or `Ctrl+Shift+Z`\n\n"
                "This works application-wide, even for complex actions like category renames: undo/redo "
                "then consistently reverts/re-applies **all affected tables** (budget, tracking, "
                "favorites, warnings, recurring transactions, savings goals).\n\n"
                "So you can try out changes safely."
            ),
            "fr": (
                "# Annuler / rétablir\n\n"
                "De nombreuses actions sont annulables et rétablissables.\n\n"
                "- **Annuler :** `Ctrl+Z`\n"
                "- **Rétablir :** `Ctrl+Y` ou `Ctrl+Maj+Z`\n\n"
                "Cela vaut pour toute l'app, même pour des actions complexes comme le renommage de "
                "catégorie : annuler/rétablir réinitialise/réapplique alors **toutes les tables "
                "concernées** (budget, suivi, favoris, alertes, récurrentes, objectifs).\n\n"
                "Vous pouvez donc tester sans risque."
            ),
        },
    },
    # ── Backup ──────────────────────────────────────────────────
    {
        "id": "backup",
        "icon": "💾",
        "title": {
            "de": "Backup & Wiederherstellung",
            "en": "Backup & restore",
            "fr": "Sauvegarde & restauration",
        },
        "body": {
            "de": (
                "# Backup & Wiederherstellung\n\n"
                "Sichere deine Daten als Paket und stelle sie bei Bedarf wieder her. Vor jedem Update "
                "wird zusätzlich automatisch ein **Rollback-Backup** angelegt.\n\n"
                "**Tipps:**\n\n"
                "- Bewahre Backups **außerhalb** des App-Ordners auf (z. B. externes Laufwerk).\n"
                "- Eine Wiederherstellung **ersetzt** die aktuellen Daten – im Zweifel vorher ein "
                "frisches Backup ziehen.\n"
                "- Du kannst die Datenbank auch auf den **Standard zurücksetzen**, um neu zu starten.\n\n"
                "**Wichtig:** Zum Wiederherstellen einer verschlüsselten Datenbank kann der "
                "**Datenbank-/Restore-Key** nötig sein – siehe *Datenbank & Schlüssel*."
            ),
            "en": (
                "# Backup & restore\n\n"
                "Save your data as a bundle and restore it when needed. Before every update a "
                "**rollback backup** is also created automatically.\n\n"
                "**Tips:**\n\n"
                "- Keep backups **outside** the app folder (e.g. an external drive).\n"
                "- A restore **replaces** the current data – if unsure, make a fresh backup first.\n"
                "- You can also **reset the database to defaults** to start over.\n\n"
                "**Important:** restoring an encrypted database may require the **database/restore "
                "key** – see *Database & key*."
            ),
            "fr": (
                "# Sauvegarde & restauration\n\n"
                "Enregistrez vos données dans un paquet et restaurez-les au besoin. Avant chaque mise "
                "à jour, une **sauvegarde de restauration** est aussi créée automatiquement.\n\n"
                "**Conseils :**\n\n"
                "- Conservez les sauvegardes **hors** du dossier de l'app (disque externe).\n"
                "- Une restauration **remplace** les données – dans le doute, sauvegardez d'abord.\n"
                "- Vous pouvez aussi **réinitialiser la base** par défaut pour repartir de zéro.\n\n"
                "**Important :** restaurer une base chiffrée peut nécessiter la **clé de "
                "base/restauration** – voir *Base de données & clé*."
            ),
        },
    },
    # ── Datenbank & Schlüssel ───────────────────────────────────
    {
        "id": "datenbank",
        "icon": "🔑",
        "title": {
            "de": "Datenbank & Schlüssel",
            "en": "Database & key",
            "fr": "Base de données & clé",
        },
        "body": {
            "de": (
                "# Datenbank & Schlüssel\n\n"
                "Deine Daten liegen **verschlüsselt** in `data/` (Format `.enc`). Jede Datenbank hat "
                "einen zufälligen **Datenbank-Schlüssel**. Daraus ergibt sich ein lesbarer "
                "**Restore-Key** (Gruppen aus Buchstaben/Zahlen).\n\n"
                "**Wozu der Restore-Key?**\n\n"
                "- Er kann deine verschlüsselte Datenbank **wiederherstellen** – auch wenn du dein "
                "Passwort/deine PIN vergisst oder nur die `.enc`-Datei übrig ist.\n"
                "- **Ohne** Restore-Key (und ohne Passwort/PIN bzw. die lokalen Kontodaten) sind die "
                "Daten **nicht wiederherstellbar**.\n\n"
                "**Wo finde ich ihn?**\n\n"
                "- Beim **ersten Start** wird er angezeigt – bitte sicher notieren.\n"
                "- Jederzeit über den Knopf **„DB-Schlüssel / Restore-Key anzeigen“** unten in diesem "
                "Handbuch (zeigt den Schlüssel der aktuell geöffneten Datenbank).\n"
                "- Bei Konten ohne Passwort zusätzlich in der **Kontoverwaltung**.\n\n"
                "**Sicherheit:** Bewahre den Schlüssel getrennt von den Backups an einem sicheren Ort "
                "auf. Wer den Schlüssel und die `.enc`-Datei hat, kann die Daten lesen."
            ),
            "en": (
                "# Database & key\n\n"
                "Your data is stored **encrypted** in `data/` (`.enc` format). Each database has a "
                "random **database key**. From it a readable **restore key** is derived (groups of "
                "letters/numbers).\n\n"
                "**What is the restore key for?**\n\n"
                "- It can **restore** your encrypted database – even if you forget your password/PIN or "
                "only the `.enc` file remains.\n"
                "- **Without** the restore key (and without password/PIN or the local account data) the "
                "data **cannot be recovered**.\n\n"
                "**Where do I find it?**\n\n"
                "- It is shown at the **first start** – please note it down safely.\n"
                "- Any time via the **“Show DB / restore key”** button below in this handbook (shows "
                "the key of the currently open database).\n"
                "- For accounts without a password also in **Account management**.\n\n"
                "**Security:** keep the key in a safe place, separate from the backups. Anyone with the "
                "key and the `.enc` file can read the data."
            ),
            "fr": (
                "# Base de données & clé\n\n"
                "Vos données sont stockées **chiffrées** dans `data/` (format `.enc`). Chaque base a "
                "une **clé de base** aléatoire. Une **clé de restauration** lisible en dérive (groupes "
                "de lettres/chiffres).\n\n"
                "**À quoi sert la clé de restauration ?**\n\n"
                "- Elle peut **restaurer** votre base chiffrée – même si vous oubliez le mot de "
                "passe/PIN ou s'il ne reste que le fichier `.enc`.\n"
                "- **Sans** cette clé (et sans mot de passe/PIN ni données de compte locales), les "
                "données **ne sont pas récupérables**.\n\n"
                "**Où la trouver ?**\n\n"
                "- Elle s'affiche au **premier démarrage** – notez-la en lieu sûr.\n"
                "- À tout moment via le bouton **« Afficher la clé »** en bas de ce manuel (clé de la "
                "base actuellement ouverte).\n"
                "- Pour les comptes sans mot de passe, aussi dans la **gestion des comptes**.\n\n"
                "**Sécurité :** conservez la clé en lieu sûr, séparée des sauvegardes. Quiconque a la "
                "clé et le fichier `.enc` peut lire les données."
            ),
        },
    },
    # ── Konten & Sicherheit ─────────────────────────────────────
    {
        "id": "konten",
        "icon": "👤",
        "title": {
            "de": "Konten & Sicherheit",
            "en": "Accounts & security",
            "fr": "Comptes & sécurité",
        },
        "body": {
            "de": (
                "# Konten & Sicherheit\n\n"
                "Die Datenbank ist **immer verschlüsselt**. Beim Anlegen wählst du eine "
                "Sicherheitsstufe:\n\n"
                "- **Ohne Passwort (Quick)** ⚡ – bequem; der Schlüssel liegt lokal bei den Kontodaten. "
                "Notiere dir trotzdem den Restore-Key (siehe *Datenbank & Schlüssel*).\n"
                "- **PIN** 🔢 – kurze Zahlenfolge.\n"
                "- **Passwort** 🔒 – stärkster Schutz.\n\n"
                "Bei PIN/Passwort wird der Schlüssel daraus abgeleitet; vergisst du das Geheimnis, "
                "hilft nur der **Restore-Key**. Sicherheitsstufe und Name lassen sich in der "
                "**Kontoverwaltung** ändern. Die Statusleiste zeigt immer das aktive Konto."
            ),
            "en": (
                "# Accounts & security\n\n"
                "The database is **always encrypted**. When creating it you pick a security level:\n\n"
                "- **No password (Quick)** ⚡ – convenient; the key is stored locally with the account "
                "data. Still note the restore key (see *Database & key*).\n"
                "- **PIN** 🔢 – short numeric code.\n"
                "- **Password** 🔒 – strongest protection.\n\n"
                "For PIN/password the key is derived from the secret; if you forget it, only the "
                "**restore key** helps. Security level and name can be changed in **Account "
                "management**. The status bar always shows the active account."
            ),
            "fr": (
                "# Comptes & sécurité\n\n"
                "La base est **toujours chiffrée**. À la création, vous choisissez un niveau :\n\n"
                "- **Sans mot de passe (Quick)** ⚡ – pratique ; la clé est stockée localement avec le "
                "compte. Notez tout de même la clé de restauration (voir *Base de données & clé*).\n"
                "- **PIN** 🔢 – court code numérique.\n"
                "- **Mot de passe** 🔒 – protection maximale.\n\n"
                "Pour PIN/mot de passe, la clé en est dérivée ; en cas d'oubli, seule la **clé de "
                "restauration** aide. Niveau et nom se changent dans la **gestion des comptes**. La "
                "barre d'état montre toujours le compte actif."
            ),
        },
    },
    # ── Updates ─────────────────────────────────────────────────
    {
        "id": "update",
        "icon": "⬆️",
        "title": {"de": "Updates", "en": "Updates", "fr": "Mises à jour"},
        "body": {
            "de": (
                "# Updates\n\n"
                "Der Update-Dialog (Menü) prüft automatisch auf eine neue Version, lädt sie herunter "
                "und bereitet sie vor. Ein Klick auf **„Jetzt aktualisieren & neu starten“** wendet "
                "das Update an.\n\n"
                "Unter Windows öffnet sich ein **sichtbares Update-Fenster**, das die laufende Datei "
                "ersetzt und die App neu startet. Deine Daten (`data/`) bleiben unangetastet; "
                "zusätzlich wird vorher ein Rollback-Backup erstellt."
            ),
            "en": (
                "# Updates\n\n"
                "The update dialog (menu) automatically checks for a new version, downloads it and "
                "prepares it. One click on **“Update now & restart”** applies the update.\n\n"
                "On Windows a **visible update window** opens, replaces the running file and restarts "
                "the app. Your data (`data/`) is left untouched; a rollback backup is created "
                "beforehand."
            ),
            "fr": (
                "# Mises à jour\n\n"
                "La boîte de mise à jour (menu) vérifie automatiquement une nouvelle version, la "
                "télécharge et la prépare. Un clic sur **« Mettre à jour et redémarrer »** l'applique.\n\n"
                "Sous Windows, une **fenêtre visible** s'ouvre, remplace le fichier en cours et "
                "redémarre l'app. Vos données (`data/`) restent intactes ; une sauvegarde de "
                "restauration est créée avant."
            ),
        },
    },
    # ── Währung & Zahlenformat ──────────────────────────────────
    {
        "id": "datenformat",
        "icon": "🌍",
        "title": {
            "de": "Währung & Zahlenformat",
            "en": "Currency & number format",
            "fr": "Devise & format des nombres",
        },
        "body": {
            "de": (
                "# Währung & Zahlenformat\n\n"
                "Sprache, Währung und **Zahlenformat** wählst du beim Erststart und später in den "
                "Einstellungen. Das Zahlenformat steuert Tausender- und Dezimaltrennzeichen "
                "(z. B. `1'234.56`, `1.234,56`, `1 234,56`, `1,234.56`).\n\n"
                "Die Eingabefelder passen sich dem Format an, damit Eingabe und Anzeige "
                "zusammenpassen. Die App ist auf Deutsch, Englisch und Französisch verfügbar."
            ),
            "en": (
                "# Currency & number format\n\n"
                "Choose language, currency and **number format** at first start and later in Settings. "
                "The number format controls thousands and decimal separators "
                "(e.g. `1'234.56`, `1.234,56`, `1 234,56`, `1,234.56`).\n\n"
                "Input fields adapt to the format so entry and display agree. The app is available in "
                "German, English and French."
            ),
            "fr": (
                "# Devise & format des nombres\n\n"
                "Choisissez la langue, la devise et le **format des nombres** au premier démarrage "
                "puis dans les Réglages. Le format gère les séparateurs de milliers et décimaux "
                "(p. ex. `1'234.56`, `1.234,56`, `1 234,56`, `1,234.56`).\n\n"
                "Les champs de saisie s'adaptent au format pour que saisie et affichage concordent. "
                "L'app est disponible en allemand, anglais et français."
            ),
        },
    },
]


def help_topic_title(topic: dict, lang: str) -> str:
    t = topic.get("title", {})
    return t.get(lang) or t.get(HELP_FALLBACK_LANG) or topic.get("id", "")


def help_topic_body(topic: dict, lang: str) -> str:
    b = topic.get("body", {})
    return b.get(lang) or b.get(HELP_FALLBACK_LANG) or ""


def help_topic_haystack(topic: dict, lang: str) -> str:
    """Durchsuchbarer Text (Titel + Body) für die Suche."""
    return (help_topic_title(topic, lang) + "\n" + help_topic_body(topic, lang)).lower()


# Zusätzlicher Laufplan: bewusst als eigenes Thema am Ende ergänzt, damit die
# vorhandene dreisprachige Hilfe stabil bleibt und die Mindmap auffindbar ist.
HELP_TOPICS.append(
    {
        "id": "mindmap",
        "icon": "🧭",
        "title": {
            "de": "Informations-Laufplan / Mindmap",
            "en": "Information flow / mind map",
            "fr": "Parcours d’information / mindmap",
        },
        "body": {
            "de": (
                "# Informations-Laufplan / Mindmap\n\n"
                "Die Mindmap zeigt den sinnvollsten Weg durch das Programm:\n\n"
                "```text\n"
                "BudgetManager\n"
                "├─ Erststart\n"
                "│  ├─ Sprache / Währung / Zahlenformat\n"
                "│  ├─ Benutzerkonto\n"
                "│  ├─ Restore-Key sichern\n"
                "│  └─ Setup-Assistent\n"
                "├─ Kategorien\n"
                "│  ├─ Einnahmen / Ausgaben / Ersparnisse\n"
                "│  ├─ Haupt- und Unterkategorien\n"
                "│  ├─ Fixkosten / Wiederkehrend / Fälligkeitstag\n"
                "│  └─ Drag & Drop\n"
                "├─ Cockpit / Startseite\n"
                "│  ├─ Monatsstatus / Favoriten / Sparziele\n"
                "│  ├─ Budget-Ampel / offene Buchungen / letzte 10\n"
                "│  └─ frei gestaltbar: Bereiche und Reiter ausblendbar\n"
                "├─ Budget\n"
                "│  ├─ Monatswerte planen\n"
                "│  ├─ Jahr kopieren\n"
                "│  └─ Budget ist Plan, keine Buchung\n"
                "├─ Buchungen / Tracking\n"
                "│  ├─ Manuell buchen\n"
                "│  ├─ Schnelleingabe\n"
                "│  └─ Fix/Wiederkehrend buchen\n"
                "├─ Übersicht\n"
                "│  ├─ Plan/Ist\n"
                "│  ├─ Verlauf / Ranking / letzte Buchungen\n"
                "│  └─ Budgetvorschläge\n"
                "├─ Sparziele\n"
                "│  ├─ Anlegen\n"
                "│  ├─ Fortschritt / Sync\n"
                "│  └─ Freigeben / Abschließen\n"
                "└─ Sicherheit\n"
                "   ├─ Datenordner\n"
                "   ├─ Backup .bmr\n"
                "   ├─ Restore-Key anzeigen\n"
                "   └─ Updates\n"
                "```\n\n"
                "Direkt anzeigbare Version: **Hilfe → Informations-Laufplan / Mindmap anzeigen…** "
                "oder im Handbuch unten auf **Mindmap anzeigen** klicken. Die Datei liegt lokal unter "
                "`docs/help/mindmap.html` und funktioniert im Browser ohne Mermaid-Plugin."
            ),
            "en": (
                "# Information flow / mind map\n\n"
                "The mind map shows the recommended path through the app: setup, categories, budget, "
                "tracking, overview, savings goals and backup/restore.\n\n"
                "Open the directly viewable version via **Help → Show information flow / mind map…** "
                "or the **Show mind map** button in this handbook. The local file is "
                "`docs/help/mindmap.html` and works in a browser without a Mermaid plugin."
            ),
            "fr": (
                "# Parcours d’information / mindmap\n\n"
                "La mindmap montre le chemin conseillé dans l’application : démarrage, catégories, "
                "budget, suivi, aperçu, objectifs d’épargne et sauvegarde/restauration.\n\n"
                "Ouvrez la version directement consultable via **Aide → Afficher le parcours / la mindmap…** "
                "ou le bouton **Afficher la mindmap** dans ce manuel. Le fichier local est "
                "`docs/help/mindmap.html` et fonctionne dans un navigateur sans plugin Mermaid."
            ),
        },
    }
)
