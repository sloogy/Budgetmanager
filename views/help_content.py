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
                "# Willkommen bei BudgetManager\n\n"
                "BudgetManager hilft dir, den \u00dcberblick \u00fcber Einnahmen, Ausgaben und "
                "Ersparnisse zu behalten. Er ist **portabel**: Programm und Daten liegen "
                "im selben Ordner (`data/`). Mehrere Kopien = mehrere getrennte Budgets.\n\n"
                "## Womit du startest: das Cockpit\n\n"
                "Beim Start landest du auf dem **Cockpit** \u2013 deiner Startseite. Ganz oben "
                "eine **Ampel** f\u00fcr den Monat:\n\n"
                "- Gr\u00fcn \u2013 alles im Plan.\n"
                "- Gelb \u2013 es wird knapp (nahe am Budget).\n"
                "- Rot \u2013 \u00fcber Plan (Budget \u00fcberschritten oder mehr ausgegeben als eingenommen).\n\n"
                "Darunter steht **N\u00e4chste Schritte** \u2013 konkrete Vorschl\u00e4ge (erste Buchung, "
                "offene Fixkosten, Monatsabschluss). Wenn du nicht weiterwei\u00dft: dort steht, was zu tun ist.\n\n"
                "## Zwei Wege, um loszulegen\n\n"
                "**Weg A \u2013 Sofort tracken (empfohlen f\u00fcr den Anfang):** Nutze die "
                "**Express-Einrichtung** im Setup-Assistenten. Sie legt Standard-Kategorien an und "
                "aktiviert den **Lernmodus** \u2013 du buchst deine Ausgaben, das Programm schl\u00e4gt nach "
                "einigen Wochen passende Budgets vor. Kein Budget-Planen n\u00f6tig, bevor du startest.\n\n"
                "**Weg B \u2013 Budgets selbst planen:**\n\n"
                "1. **Kategorien** anlegen oder Vorlage \u00fcbernehmen (**Strg+K** oder im **Budget**-Tab).\n"
                "2. **Budget** je Monat eintragen (Tab *Budget*). Leere Felder bleiben 0.\n"
                "3. **Buchungen** erfassen (Tab *Buchungen*) \u2013 manuell oder \u00fcber *Fixkosten buchen*.\n"
                "4. In der **\u00dcbersicht** Soll/Ist pr\u00fcfen.\n\n"
                "## Am Monatsende\n\n"
                "Der **Monatsabschluss** (Knopf oben rechts im Cockpit) rechnet Einnahmen \u2212 Ausgaben "
                "\u2212 Ersparnisse und hilft, einen \u00dcberschuss zu sichern oder ein Defizit zu decken "
                "\u2013 siehe Thema *Monatsabschluss*.\n\n"
                "Der **Setup-Assistent** (*Hilfe \u2192 Erste Schritte*) f\u00fchrt jederzeit erneut durch "
                "diese Schritte. Tipp: Mit der **Enter-Taste** springst du zur n\u00e4chsten Seite.\n\n"
                "Beim allerersten Start wird dein **Datenbank-/Restore-Key** angezeigt \u2013 gut aufbewahren, "
                "siehe *Datenbank & Schl\u00fcssel*."
            ),
            "en": (
                "# Welcome to BudgetManager\n\n"
                "BudgetManager helps you track income, expenses and savings. It is **portable**: "
                "program and data live in the same folder (`data/`). Several copies = several "
                "separate budgets.\n\n"
                "## Where you start: the cockpit\n\n"
                "On launch you land on the **cockpit** \u2013 your start page. At the top a "
                "**traffic light** rates the month:\n\n"
                "- Green \u2013 on track.\n"
                "- Yellow \u2013 getting tight (close to budget).\n"
                "- Red \u2013 over plan (budget exceeded or spent more than earned).\n\n"
                "Below, **Next steps** suggests what to do (first booking, open fixed costs, "
                "month-end close). Whenever you're unsure, it tells you what's next.\n\n"
                "## Two ways to get going\n\n"
                "**Path A \u2013 Track right away (recommended at first):** use **Express setup** in "
                "the assistant. It creates default categories and enables **learning mode** \u2013 book "
                "your expenses and the app suggests matching budgets after a few weeks. No planning "
                "needed before you start.\n\n"
                "**Path B \u2013 Plan budgets yourself:**\n\n"
                "1. Create **categories** or accept the template (**Ctrl+K** or in the **Budget** tab).\n"
                "2. Enter the **budget** per month (*Budget* tab). Empty fields stay 0.\n"
                "3. Record **transactions** (*Tracking* tab) \u2013 manually or via *Book fixed costs*.\n"
                "4. Check planned/actual in the **Overview**.\n\n"
                "## At month-end\n\n"
                "The **month-end close** (button top right in the cockpit) computes income \u2212 expenses "
                "\u2212 savings and helps secure a surplus or cover a deficit \u2013 see *Month-end close*.\n\n"
                "The **setup assistant** (*Help \u2192 Getting started*) walks you through these steps "
                "again anytime. Tip: press **Enter** to move to the next page.\n\n"
                "On the very first start your **database/restore key** is shown \u2013 keep it safe, see "
                "*Database & key*."
            ),
            "fr": (
                "# Bienvenue dans BudgetManager\n\n"
                "BudgetManager vous aide \u00e0 suivre revenus, d\u00e9penses et \u00e9pargne. Il est "
                "**portable** : programme et donn\u00e9es sont dans le m\u00eame dossier (`data/`). "
                "Plusieurs copies = plusieurs budgets s\u00e9par\u00e9s.\n\n"
                "## Point de d\u00e9part : le cockpit\n\n"
                "Au d\u00e9marrage, vous arrivez sur le **cockpit** \u2013 votre page d'accueil. En haut, "
                "un **feu tricolore** \u00e9value le mois :\n\n"
                "- Vert \u2013 dans le plan.\n"
                "- Jaune \u2013 \u00e7a devient juste (proche du budget).\n"
                "- Rouge \u2013 au-dessus du plan (budget d\u00e9pass\u00e9 ou plus d\u00e9pens\u00e9 que gagn\u00e9).\n\n"
                "En dessous, **Prochaines \u00e9tapes** propose quoi faire (premi\u00e8re \u00e9criture, charges "
                "fixes ouvertes, cl\u00f4ture du mois). En cas de doute, c'est l\u00e0 que \u00e7a se dit.\n\n"
                "## Deux fa\u00e7ons de d\u00e9marrer\n\n"
                "**Voie A \u2013 Suivre tout de suite (conseill\u00e9 au d\u00e9but) :** utilisez la "
                "**configuration express** de l'assistant. Elle cr\u00e9e les cat\u00e9gories standard et "
                "active le **mode apprentissage** \u2013 enregistrez vos d\u00e9penses et l'appli proposera "
                "des budgets adapt\u00e9s apr\u00e8s quelques semaines. Aucune planification avant de commencer.\n\n"
                "**Voie B \u2013 Planifier vous-m\u00eame les budgets :**\n\n"
                "1. Cr\u00e9ez des **cat\u00e9gories** ou reprenez le mod\u00e8le (**Ctrl+K** ou onglet **Budget**).\n"
                "2. Saisissez le **budget** par mois (onglet *Budget*). Champs vides = 0.\n"
                "3. Enregistrez des **op\u00e9rations** (onglet *Suivi*) \u2013 manuellement ou via *Saisir les charges fixes*.\n"
                "4. V\u00e9rifiez pr\u00e9vu/r\u00e9el dans l'**Aper\u00e7u**.\n\n"
                "## En fin de mois\n\n"
                "La **cl\u00f4ture du mois** (bouton en haut \u00e0 droite du cockpit) calcule revenus \u2212 "
                "d\u00e9penses \u2212 \u00e9pargne et aide \u00e0 s\u00e9curiser un exc\u00e9dent ou couvrir un d\u00e9ficit "
                "\u2013 voir *Cl\u00f4ture du mois*.\n\n"
                "L'**assistant** (*Aide \u2192 Premiers pas*) reprend ces \u00e9tapes \u00e0 tout moment. "
                "Astuce : appuyez sur **Entr\u00e9e** pour passer \u00e0 la page suivante.\n\n"
                "Au tout premier d\u00e9marrage, votre **cl\u00e9 de base/restauration** s'affiche \u2013 "
                "conservez-la, voir *Base de donn\u00e9es & cl\u00e9*."
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
                "vorhandenen Kategorien mit einem Klick anlegen. Für die Gesamtplanung aus Einnahmen, "
                "Ausgaben und Ersparnissen siehe **Soft-0-Budget / sanfte Null-Bilanz**."
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
                "empty budget year can be created from existing categories in one click. For whole-plan balancing, "
                "see **Soft Zero Budget / gentle zero balance**."
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
                "catégories existantes. Pour équilibrer le plan global, voir **Budget zéro souple / solde nul**."
            ),
        },
    },
    # ── Soft-0-Budget / sanfte Null-Bilanz ─────────────────────
    {
        "id": "soft-zero-budget",
        "icon": "⚖️",
        "title": {
            "de": "Soft-0-Budget / sanfte Null-Bilanz",
            "en": "Soft Zero Budget / gentle zero balance",
            "fr": "Budget zéro souple / solde nul",
        },
        "body": {
            "de": (
                "# Soft-0-Budget / sanfte Null-Bilanz\n\n"
                "## Wo finde ich die Einstellung?\n\n"
                "**Datei → Einstellungen → Verhalten → Budgetübersicht → "
                "Soft-0-Budget aktivieren**. Direkt daneben öffnet **Erklärung öffnen** dieses Kapitel. "
                "Du findest es in der Hilfe auch über die Suchwörter *Soft 0*, *0-Budget*, "
                "*Nullbudget*, *Null-Bilanz*, *Überschuss* oder *Übertrag*.\n\n"
                "## Was bedeutet Soft-0-Budget?\n\n"
                "Die Regel betrachtet dein geplantes Einkommen als gemeinsamen Topf:\n\n"
                "**Einnahmen − Ausgaben − Ersparnisse = ungefähr 0 CHF**\n\n"
                "Das Ziel ist nicht, alles auszugeben. Auch Geld für Notgroschen, Ferien, Steuern oder "
                "andere Ersparnisse bekommt bewusst eine Aufgabe. *Soft* bedeutet: BudgetManager "
                "berechnet nur Vorschläge. Es wird **nichts automatisch gebucht, verschoben oder geändert**. "
                "Du prüfst und übernimmst jeden Vorschlag selbst.\n\n"
                "> Die Funktion ist mit Zero-Based Budgeting verwandt, aber bewusst weniger streng: "
                "Ein kleiner Rest ist erlaubt, und die App zwingt keinen Monat auf exakt 0 CHF.\n\n"
                "## Welche Daten braucht die Regel?\n\n"
                "- Im ausgewählten Monat muss ein Einnahmenbudget größer als 0 CHF vorhanden sein.\n"
                "- Ausgaben- und Ersparnissebudgets werden dagegen gerechnet.\n"
                "- Zuerst zählt die Planung des Zielmonats. Ist sie bereits nahezu ausgeglichen, kann "
                "ein stabiles Muster aus abgeschlossenen Vormonaten einen Lernvorschlag auslösen.\n"
                "- Kleine Rundungsdifferenzen werden ignoriert.\n\n"
                "## Was passiert bei Überschuss?\n\n"
                "Beispiel: 5’000 CHF Einnahmen, 3’000 CHF Ausgaben und 1’000 CHF Ersparnisse. "
                "Es bleiben 1’000 CHF ohne Aufgabe.\n\n"
                "Unter **Überschuss verwenden für** wählst du:\n\n"
                "1. **Ersparnisse erhöhen:** BudgetManager schlägt eine passende Ersparnisse-Kategorie "
                "vor, bevorzugt z. B. Notgroschen, Reserve oder eine bestehende Spar-Kategorie. "
                "Im Beispiel würde ein Sparbudget von 1’000 CHF auf 2’000 CHF vorgeschlagen.\n"
                "2. **In nächsten Monat übertragen:** Der Überschuss wird als Übertrag-Hinweis gezeigt. "
                "Er wird nicht heimlich gebucht. Startmonat und Startjahr der Übertragskumulation stellst "
                "du darunter ein.\n\n"
                "Existiert keine Ersparnisse-Kategorie, zeigt BudgetManager stattdessen einen Übertrag-Hinweis.\n\n"
                "## Was passiert bei Defizit?\n\n"
                "Beispiel: 5’000 CHF Einnahmen, 4’000 CHF Ausgaben und 1’500 CHF Ersparnisse. "
                "Die Planung liegt 500 CHF im Minus. BudgetManager schlägt zuerst vor, das Sparbudget "
                "von 1’500 CHF auf 1’000 CHF zu reduzieren.\n\n"
                "Reichen Ersparnisse nicht aus, werden danach nur **flexible Ausgaben** als mögliche "
                "Stellschrauben angeboten. Geschützt bleiben:\n\n"
                "- Fixkosten und fixe wiederkehrende Kosten,\n"
                "- POT/Rückstellungen wie Franchise oder Selbstbehalt,\n"
                "- inkrementelle Jahreskosten und andere geschützte Prognosearten.\n\n"
                "Beispiel: Bei 300 CHF Defizit, 800 CHF Sparbudget und 3’500 CHF fixer Miete wird nur "
                "eine Reduktion des Sparbudgets auf 500 CHF vorgeschlagen. Die Miete wird nicht gekürzt.\n\n"
                "## Unterschied zu anderen Funktionen\n\n"
                "- **Tracking-Lernmodus:** lernt ein erstes Budget für Kategorien, die noch kein Budget haben.\n"
                "- **Normale Budgetvorschläge:** vergleichen einzelne Kategorien mit ihren Buchungen.\n"
                "- **Soft-0-Budget:** prüft die Gesamtplanung aus Einnahmen, Ausgaben und Ersparnissen.\n"
                "- **Monatsabschluss:** arbeitet mit dem tatsächlich abgeschlossenen Monat und kann eine "
                "bewusste Buchung in Ersparnisse anbieten. Soft-0-Budget bleibt eine Planungsregel.\n\n"
                "## Wann ist die Funktion sinnvoll?\n\n"
                "Aktiviere sie, wenn du dein gesamtes Einkommen bewusst auf Ausgaben, Rückstellungen und "
                "Ersparnisse verteilen möchtest. Lass sie aus, wenn du absichtlich einen großen freien "
                "Puffer ohne Kategorie stehen lassen willst oder nur einzelne Kategorien beobachten möchtest.\n\n"
                "## Keine Vorschläge sichtbar?\n\n"
                "Prüfe nacheinander:\n\n"
                "1. Ist Soft-0-Budget aktiviert und wurden die Einstellungen mit **OK** oder **Anwenden** gespeichert?\n"
                "2. Gibt es im gewählten Monat ein Einnahmenbudget größer als 0 CHF?\n"
                "3. Ist die Planung bereits ausgeglichen und fehlen noch genügend abgeschlossene Vergleichsmonate?\n"
                "4. Ist die Differenz nur eine kleine Rundung? Dann wird sie absichtlich ignoriert.\n"
                "5. Öffne **Extras → Budgetwarnungen/Vorschläge** oder die Vorschläge in der Übersicht.\n\n"
                "**Merksatz:** Soft-0-Budget gibt jedem geplanten Franken eine Aufgabe – aber nur du "
                "entscheidest, ob ein Vorschlag übernommen wird."
            ),
            "en": (
                "# Soft Zero Budget / gentle zero balance\n\n"
                "## Where is the setting?\n\n"
                "Open **File → Settings → Behaviour → Budget overview → Enable Soft Zero Budget**. "
                "The **Open explanation** button opens this chapter. Search the handbook for *soft zero*, "
                "*zero budget*, *zero balance*, *surplus* or *carryover*.\n\n"
                "## What does it mean?\n\n"
                "The rule treats planned income as one shared pool:\n\n"
                "**Income − expenses − savings = approximately CHF 0**\n\n"
                "Money assigned to savings still has a job; the aim is not to spend everything. *Soft* "
                "means the app creates suggestions only. It never books, moves or changes values automatically. "
                "It is related to zero-based budgeting but deliberately less strict.\n\n"
                "## Requirements and behaviour\n\n"
                "A positive income budget must exist in the selected month. The target month's plan is "
                "checked first; when it is already close to balanced, a stable pattern from completed previous "
                "months may produce a learning suggestion. Tiny rounding differences are ignored.\n\n"
                "For a surplus, choose either **increase savings** or **carry forward to next month**. Example: "
                "CHF 5,000 income − CHF 3,000 expenses − CHF 1,000 savings leaves CHF 1,000. The app can "
                "suggest raising an existing savings budget from CHF 1,000 to CHF 2,000, or show CHF 1,000 as carryover.\n\n"
                "For a deficit, savings are suggested first, then flexible expenses. Fixed/recurring costs, "
                "pots/reserves and incremental annual costs remain protected. Example: CHF 5,000 income, "
                "CHF 4,000 expenses and CHF 1,500 savings results in a CHF 500 suggestion to reduce savings to CHF 1,000.\n\n"
                "## Not the same as\n\n"
                "- Tracking learning creates starting budgets where no budget exists.\n"
                "- Normal suggestions compare individual categories with actual bookings.\n"
                "- Soft Zero Budget checks the total plan across income, expenses and savings.\n"
                "- Month-end close works with the completed actual month; Soft Zero Budget stays a planning rule.\n\n"
                "Use it when you want every planned unit of income assigned deliberately. Leave it off when "
                "you intentionally keep a large uncategorised buffer. If no suggestion appears, verify the setting "
                "was saved, a positive income budget exists, enough completed months exist, and the difference is "
                "not merely rounding.\n\n"
                "**Remember:** the rule gives planned money a job, but you decide whether to accept any suggestion."
            ),
            "fr": (
                "# Budget zéro souple / règle douce de solde nul\n\n"
                "## Où se trouve le réglage ?\n\n"
                "Ouvrez **Fichier → Réglages → Comportement → Aperçu du budget → Activer le budget zéro souple**. "
                "Le bouton **Ouvrir l’explication** ouvre ce chapitre. Recherchez aussi *budget zéro*, "
                "*solde nul*, *excédent* ou *report*.\n\n"
                "## Que signifie cette règle ?\n\n"
                "Elle considère le revenu planifié comme une enveloppe commune :\n\n"
                "**Revenus − dépenses − épargne = environ 0 CHF**\n\n"
                "L'argent attribué à l'épargne a lui aussi une mission ; le but n'est pas de tout dépenser. "
                "Le mot *souple* signifie que l'application ne produit que des suggestions. Elle ne comptabilise, "
                "ne déplace et ne modifie rien automatiquement. Cette approche est proche du budget base zéro, "
                "mais volontairement moins stricte.\n\n"
                "## Conditions et fonctionnement\n\n"
                "Un budget de revenu supérieur à 0 CHF doit exister pour le mois choisi. Le plan du mois cible "
                "est contrôlé en premier ; s'il est déjà presque équilibré, un motif stable des mois précédents "
                "terminés peut déclencher une suggestion. Les petits écarts d'arrondi sont ignorés.\n\n"
                "En cas d'excédent, choisissez **augmenter l'épargne** ou **reporter au mois suivant**. Exemple : "
                "5’000 CHF de revenus − 3’000 CHF de dépenses − 1’000 CHF d'épargne laisse 1’000 CHF. "
                "L'application peut proposer de passer une épargne de 1’000 CHF à 2’000 CHF ou d'afficher 1’000 CHF en report.\n\n"
                "En cas de déficit, l'épargne est proposée en premier, puis les dépenses flexibles. Les charges "
                "fixes/récurrentes, pots/provisions et coûts annuels incrémentiels restent protégés. Exemple : "
                "5’000 CHF de revenus, 4’000 CHF de dépenses et 1’500 CHF d'épargne donnent une suggestion de "
                "réduire l'épargne de 500 CHF à 1’000 CHF.\n\n"
                "## À ne pas confondre\n\n"
                "- Le mode d'apprentissage du suivi crée un premier budget lorsqu'il n'en existe pas.\n"
                "- Les suggestions normales comparent chaque catégorie aux écritures réelles.\n"
                "- Le budget zéro souple vérifie le plan global revenus/dépenses/épargne.\n"
                "- La clôture mensuelle travaille avec le mois réel terminé ; cette règle reste une règle de planification.\n\n"
                "Activez-la pour attribuer consciemment chaque franc planifié. Laissez-la désactivée si vous souhaitez "
                "garder volontairement une grande marge non catégorisée. En l'absence de suggestion, vérifiez que le "
                "réglage est enregistré, qu'un budget de revenu positif existe, que suffisamment de mois sont terminés "
                "et que l'écart n'est pas seulement un arrondi.\n\n"
                "**À retenir :** la règle donne une mission à l'argent planifié, mais vous décidez toujours d'accepter ou non."
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
                "- **Monatsstatus:** Einnahmen, Ausgaben, Ersparnisse und freier Rest im Lohnzyklus. Der Zeitraum beginnt beim tatsächlichen Lohneingang nahe dem hinterlegten Lohntag und endet am Tag vor dem nächsten Lohntag. Beispiel: 25. Januar bis 24. Februar.\n"
                "- **Favoriten:** Kategorien, die du immer im Blick behalten willst. Genau hier machen Favoriten am meisten Sinn.\n"
                "- **Aktive Sparziele:** Fortschritt als Balken; ohne Ziel schrumpft der Bereich auf eine kompakte Hinweiszeile.\n"
                "- **Budget-Ampel:** Budget überschritten, Einnahmen/Sparen noch nicht erreicht oder Ausgaben kaum genutzt.\n"
                "- **Offene Monatsbuchungen:** Fixkosten und wiederkehrende Buchungen, die im aktuellen Monat noch fehlen.\n"
                "- **Letzte 10 Buchungen:** schnelle Plausibilitätskontrolle.\n\n"
                "## Wie bleibt es übersichtlich?\n"
                "Über **⚙ Cockpit gestalten** oder **Ansicht → Anzeigen → Cockpit-Bereiche** blendest du Bereiche ein oder aus.\n"
                "Standardmäßig arbeitet das Cockpit **automatisch**: Leere Abschnitte schrumpfen und wandern nach unten. Über **Ansicht → Cockpit-Layout → Kacheln frei anordnen** wechselst du ins manuelle Layout. Dann kannst du jede Kachel an der gesamten **Kopfzeile** oder am Griff **≡** frei innerhalb und zwischen zwei unabhängigen Zielspalten verschieben. Eine rechte Kachel kann bis ganz nach oben rücken; ein markierter **Ablageplatzhalter** zeigt während des Ziehens die genaue Zielposition. Reihenfolge und Spalte werden sofort gespeichert.\n"
                "Jeder Hauptreiter kann über **Ansicht → Anzeigen → Reiter ein-/ausblenden** verborgen werden. Mindestens ein Reiter bleibt immer sichtbar.\n"
            ),
            "en": "# Cockpit / start page\n\nA compact home tab with KPIs, favorites, active savings goals, budget alerts, missing monthly bookings and recent transactions. The monthly-status KPIs follow the salary cycle from the actual/configured payday to the day before the next payday. Empty sections shrink and move down automatically. Use View → Cockpit layout → Arrange tiles freely, then drag a tile by its full header or the ≡ handle within or between two independent target columns. A highlighted drop placeholder shows the exact destination, and right-hand tiles can move all the way to the top. Panels and main tabs can be hidden via View → Show.",
            "fr": "# Cockpit / accueil\n\nUn onglet d'accueil compact avec indicateurs, favoris, objectifs actifs, alertes budget, écritures mensuelles manquantes et dernières opérations. Les indicateurs mensuels suivent le cycle de salaire, du versement réel/configuré jusqu'à la veille du versement suivant. Les sections vides se réduisent et descendent automatiquement. Utilisez Affichage → Disposition du cockpit → Organiser librement les tuiles, puis déplacez une tuile par tout son en-tête ou la poignée ≡ dans ou entre deux colonnes indépendantes. Un emplacement de dépôt surligné montre la destination exacte et une tuile à droite peut monter tout en haut. Les panneaux et onglets peuvent être masqués via Affichage → Afficher.",
        },
    },
    # \u2500\u2500 Monatsabschluss \u2500\u2500
    {
        "id": "monatsabschluss",
        "icon": "\ud83d\udcc5",
        "title": {
            "de": "Monatsabschluss",
            "en": "Month-end close",
            "fr": "Cl\u00f4ture du mois",
        },
        "body": {
            "de": (
                "# Monatsabschluss\n\n"
                "Der Assistent (Knopf **Monatsabschluss\u2026** oben rechts im Cockpit) schlie\u00dft "
                "einen Monat sauber ab. Er rechnet:\n\n"
                "**Einnahmen \u2212 Ausgaben \u2212 Ersparnisse = frei verf\u00fcgbar**\n\n"
                "## \u00dcberschuss\n"
                "Bleibt Geld \u00fcbrig, schl\u00e4gt der Assistent vor, den Rest in eine **Ersparnis** zu "
                "buchen (bevorzugt das aktivste offene Sparziel). Betrag und Ziel sind \u00e4nderbar. "
                "So verschwindet der \u00dcberschuss nicht unbemerkt im n\u00e4chsten Monat.\n\n"
                "## Defizit\n"
                "Fehlt Geld, kannst du das Loch aus einer **Ersparnis mit Guthaben** decken "
                "(Entnahme). Zus\u00e4tzlich zeigt der Assistent rein informativ, welche **variablen** "
                "Budgets im n\u00e4chsten Monat Spielraum h\u00e4tten.\n\n"
                "> **Wichtig:** Fixkosten und wiederkehrende Kategorien werden **nie** zur K\u00fcrzung "
                "vorgeschlagen \u2013 Miete oder Versicherung k\u00fcrzt man nicht am Monatsende weg.\n\n"
                "## Ampel & N\u00e4chste Schritte\n"
                "Die **Ampel** oben im Cockpit und in der \u00dcbersicht nutzt dieselbe Rechnung: "
                "Rot bei \u00fcberschrittenem Budget oder negativem Rest, Gelb wenn es knapp wird, sonst "
                "Gr\u00fcn. **N\u00e4chste Schritte** erinnert dich ab dem 25. an den Abschluss.\n\n"
                "Es wird nichts automatisch gebucht \u2013 jede Buchung best\u00e4tigst du selbst, und "
                "alles l\u00e4sst sich per **R\u00fcckg\u00e4ngig** widerrufen."
            ),
            "en": (
                "# Month-end close\n\n"
                "The assistant (button **Month-end close\u2026** top right in the cockpit) closes a "
                "month cleanly. It computes:\n\n"
                "**Income \u2212 expenses \u2212 savings = freely available**\n\n"
                "## Surplus\n"
                "If money is left, the assistant suggests booking the remainder into a **savings** "
                "category (preferring the most active open goal). Amount and target are editable, so "
                "the surplus doesn't quietly vanish next month.\n\n"
                "## Deficit\n"
                "If money is missing, you can cover the gap from a **savings category with funds** "
                "(withdrawal). The assistant also shows, for information only, which **variable** "
                "budgets have room next month.\n\n"
                "> **Important:** fixed and recurring categories are **never** suggested for cuts \u2013 "
                "you don't trim rent or insurance at month-end.\n\n"
                "## Traffic light & next steps\n"
                "The **traffic light** in the cockpit and overview uses the same calculation: red for "
                "an exceeded budget or negative remainder, yellow when it gets tight, otherwise green. "
                "**Next steps** reminds you of the close from the 25th.\n\n"
                "Nothing is booked automatically \u2013 you confirm each booking, and everything can be "
                "**undone**."
            ),
            "fr": (
                "# Cl\u00f4ture du mois\n\n"
                "L'assistant (bouton **Cl\u00f4ture du mois\u2026** en haut \u00e0 droite du cockpit) cl\u00f4ture "
                "un mois proprement. Il calcule :\n\n"
                "**Revenus \u2212 d\u00e9penses \u2212 \u00e9pargne = librement disponible**\n\n"
                "## Exc\u00e9dent\n"
                "S'il reste de l'argent, l'assistant propose de verser le reste dans une **\u00e9pargne** "
                "(de pr\u00e9f\u00e9rence l'objectif ouvert le plus actif). Montant et objectif modifiables, "
                "pour que l'exc\u00e9dent ne disparaisse pas le mois suivant.\n\n"
                "## D\u00e9ficit\n"
                "S'il manque de l'argent, vous pouvez combler l'\u00e9cart depuis une **\u00e9pargne avec "
                "des fonds** (retrait). L'assistant montre aussi, \u00e0 titre informatif, quels budgets "
                "**variables** auraient de la marge le mois prochain.\n\n"
                "> **Important :** les cat\u00e9gories fixes et r\u00e9currentes ne sont **jamais** propos\u00e9es "
                "\u00e0 la r\u00e9duction \u2013 on ne rogne pas le loyer ou l'assurance en fin de mois.\n\n"
                "## Feu tricolore & prochaines \u00e9tapes\n"
                "Le **feu tricolore** du cockpit et de l'aper\u00e7u utilise le m\u00eame calcul : rouge si "
                "budget d\u00e9pass\u00e9 ou reste n\u00e9gatif, jaune quand \u00e7a devient juste, sinon vert. "
                "**Prochaines \u00e9tapes** vous rappelle la cl\u00f4ture d\u00e8s le 25.\n\n"
                "Rien n'est comptabilis\u00e9 automatiquement \u2013 vous confirmez chaque \u00e9criture, et tout "
                "peut \u00eatre **annul\u00e9**."
            ),
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
                "- **Diagramme:** Plan/Ist-Donut, Kategorien-Ranking, Konto-Vergleich als Balken, "
                "Monatsverlauf, Monatsbilanz und Top-Buchungen. Der gute Donut bleibt; "
                "verwirrende Nebenkreise werden vermieden.\n"
                "- **Filter/Suche** rechts: Zeitraum, Kategorie, Betragsgrenzen, Freitext.\n\n"
                "Über die Übersicht erreichst du auch das **Verwalten** der Sparziele."
            ),
            "en": (
                "# Overview\n\n"
                "The overview bundles your situation at a glance:\n\n"
                "- **KPIs:** totals for income, expenses, balance.\n"
                "- **Planned/actual per category:** budget vs. actually booked, incl. deviation.\n"
                "- **Savings goals:** progress of your goals (see *Savings goals*).\n"
                "- **Charts:** plan/actual donut, category ranking, account comparison as bars, "
                "monthly trend, monthly balance and top bookings. The useful donut stays; "
                "confusing neighboring pies are avoided.\n"
                "- **Filter/search** on the right: period, category, amount limits, free text.\n\n"
                "From the overview you also reach **Manage** for savings goals."
            ),
            "fr": (
                "# Aperçu\n\n"
                "L'aperçu réunit votre situation d'un coup d'œil :\n\n"
                "- **Indicateurs (KPI) :** totaux revenus, dépenses, solde.\n"
                "- **Prévu/réel par catégorie :** budget vs. saisi, écart inclus.\n"
                "- **Objectifs d'épargne :** progression (voir *Objectifs d'épargne*).\n"
                "- **Graphiques :** donut prévu/réalisé, classement des catégories, comparaison "
                "des comptes en barres, évolution mensuelle, solde mensuel et top écritures. "
                "Le donut utile reste ; les camemberts voisins confus sont évités.\n"
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
                "**Wann nutzen?** Für grosse oder kleine Projekte mit einem festen Zielbetrag, "
                "zum Beispiel Hochzeit, Notgroschen, Urlaub oder ein neues Gerät.\n\n"
                "BudgetManager behandelt ein Sparziel als **Flussbestand** und zeigt getrennt:\n"
                "- **Zielbetrag** des Projekts,\n"
                "- **eingezahlt**,\n"
                "- **verwendet/Bezüge**,\n"
                "- **aktueller Bestand** = eingezahlt minus verwendet,\n"
                "- **noch einzuzahlen** = Zielbetrag minus eingezahlt.\n\n"
                "Beispiel Hochzeit: Ziel `50’000 CHF`, eingezahlt `30’000 CHF`, verwendet "
                "`15’000 CHF`. Damit sind `15’000 CHF` im Projektbestand und `20’000 CHF` "
                "noch einzuzahlen. Der Bezug erhöht den noch einzuzahlenden Betrag nicht erneut.\n\n"
                "**Buchungen:** Eine positive Ersparnisbuchung ist eine Einzahlung. Eine negative "
                "Buchung ist standardmässig ein **Bezug** und wird als Verwendung ausgewiesen. "
                "Nur wenn die negative Buchung eine Fehlbuchung korrigiert, wählst du im "
                "Rückfragedialog ausdrücklich **Korrektur**; dann sinkt der Einzahlungsfortschritt, "
                "ohne dass eine Projektverwendung entsteht.\n\n"
                "Über **Teilfreigabe** kannst du einen wählbaren Betrag freigeben. Das Ziel bleibt "
                "aktiv, wird nicht verloren und kann weiter bespart werden. Bestand und "
                "Einzahlungsfortschritt dürfen nicht negativ werden; Einzahlungen über das Ziel "
                "und Bezüge über den Bestand werden blockiert.\n\n"
                "Sparziele sind über Budget, Tracking, Übersicht, Cockpit und den Verwaltungsdialog "
                "erreichbar. Umbenennungen von Kategorien werden mitgeführt und die Daten sind Teil "
                "des Backups."
            ),
            "en": (
                "# Savings goals – when, how, where\n\n"
                "Use a goal for a project with a fixed target, such as a wedding or emergency fund. "
                "The app separates **target**, **contributed**, **used/withdrawn**, **current stock**, "
                "and **still to contribute**. Example: target `50,000`, contributed `30,000`, used "
                "`15,000` means stock `15,000` and `20,000` still to contribute.\n\n"
                "A positive savings transaction is a deposit. A negative one defaults to "
                "**withdrawal**. Choose **correction** explicitly for an erroneous booking so it "
                "does not count as project use. **Partial release** makes a selected amount "
                "available while the goal stays active and can continue receiving deposits. "
                "Deposits above the target and withdrawals above current stock are blocked."
            ),
            "fr": (
                "# Objectifs d'épargne – quand, comment, où\n\n"
                "Utilisez un objectif pour un projet à montant cible, par exemple un mariage ou "
                "un fonds d'urgence. L'application sépare **cible**, **versé**, **utilisé/retiré**, "
                "**solde actuel** et **reste à verser**. Exemple : cible `50 000`, versé `30 000`, "
                "utilisé `15 000` donne un solde de `15 000` et `20 000` encore à verser.\n\n"
                "Une opération positive est un versement. Une opération négative est par défaut un "
                "**retrait**. Choisissez explicitement **correction** pour une erreur afin qu'elle "
                "ne compte pas comme utilisation. Une **libération partielle** rend disponible un "
                "montant choisi sans fermer l'objectif, qui peut continuer à recevoir des versements. "
                "Les versements au-delà de la cible et les retraits au-delà du solde sont bloqués."
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
                "Löschen von Kategorien korrekt mitgeführt.\n\n"
                "**Abgrenzung zu Tags:** Ein Favorit ist ein Schnellzugriff auf eine Kategorie. "
                "Er ist kein Auswertungs-Schlagwort und wird nicht einzelnen Buchungen zugewiesen."
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
                "renamed/deleted.\n\n"
                "**Difference from tags:** a favorite is a shortcut to a category. It is not an "
                "analysis label and is not assigned to individual transactions."
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
                "est vide. Les favoris suivent les renommages/suppressions.\n\n"
                "**Différence avec les étiquettes :** un favori est un raccourci vers une catégorie. "
                "Ce n’est pas un libellé d’analyse et il n’est pas attribué aux opérations."
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
                "die Kategoriestruktur pressen lassen.\n\n"
                "**Wichtig:** In der App gibt es zusätzlich den **Fälligkeitstag** einer Kategorie "
                "(1–31). Das ist der Buchungstag im Monat und nicht dasselbe wie ein Tag/Label."
            ),
            "en": (
                "# Tags / labels\n\n"
                "**Tags** are an additional, free categorization **across categories** – e.g. "
                "*Holiday2026*, *tax-deductible*, *Project X*.\n\n"
                "- You assign tags to individual transactions.\n"
                "- This lets you analyse spending **by theme, not only by category**.\n"
                "- The tag manager keeps the overview; only tags that have bookings are shown.\n\n"
                "Tags don't replace categories – they complement them for analyses that don't fit the "
                "category tree.\n\n"
                "**Important:** the app also has a category **due day** (1–31). That is the booking "
                "day in the month and is not the same as a tag/label."
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
                "analyses hors de l'arbre.\n\n"
                "**Important :** l’app possède aussi un **jour d’échéance** de catégorie (1–31). "
                "C’est le jour de comptabilisation mensuel, pas une étiquette."
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

# v2.2.35: Funktionsinventar-gestützte Ergänzungen und Korrekturen des Handbuchs.
from views.help_content_additions import apply_handbook_completeness

apply_handbook_completeness(HELP_TOPICS)
