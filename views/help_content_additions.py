"""Handbuch-Ergänzungen v2.2.35.

Die Hauptdatei ``help_content.py`` enthält die langjährig gewachsenen Themen.
Dieses Modul ergänzt fehlende Funktionsbereiche und korrigiert veraltete
Beschreibungen, ohne Qt oder andere UI-Module zu importieren.
"""

from __future__ import annotations


def _topic(
    topic_id: str,
    icon: str,
    de_title: str,
    en_title: str,
    fr_title: str,
    de: str,
    en: str,
    fr: str,
) -> dict:
    return {
        "id": topic_id,
        "icon": icon,
        "title": {"de": de_title, "en": en_title, "fr": fr_title},
        "body": {"de": de.strip(), "en": en.strip(), "fr": fr.strip()},
    }


def _apply_topic_corrections(by_id: dict[str, dict]) -> None:
    """Korrigiert bestehende Themen mit veralteten oder zu knappen Aussagen."""

    # Korrektur: Der Monatsabschluss setzt nur einen Cockpit-Vermerk. Er sperrt
    # weder Buchungen noch Budgetwerte und besitzt keinen separaten Reopen-Flow.
    by_id["monatsabschluss"]["body"] = {
        "de": """
# Monatsabschluss

Du öffnest ihn im **Cockpit → Monatsabschluss…**. Der Assistent rechnet mit den tatsächlich gebuchten Werten:

**Einnahmen − Ausgaben − Ersparnisse = frei verfügbar**

## Überschuss
Du kannst einen Überschuss bewusst als Ersparnis buchen. Zielkategorie und Betrag bleiben änderbar. BudgetManager bevorzugt ein aktives Sparziel, schreibt aber nichts ohne deine Bestätigung.

## Defizit
Ein Defizit kann durch eine Entnahme aus einer Ersparnis mit vorhandenem Guthaben gedeckt werden. Zusätzlich werden rein informative Hinweise zu flexiblen Budgets des Folgemonats angezeigt. **Fixkosten und wiederkehrende Kategorien werden nie zur Kürzung vorgeschlagen.**

## Was „als abgeschlossen markieren“ wirklich bedeutet
Das Häkchen setzt nur einen **Vermerk für Cockpit und Erinnerungen**. Es friert den Monat nicht ein: Buchungen und Budgets bleiben normal bearbeitbar. Musst du nachträglich etwas ändern, bearbeitest du die Buchung wie gewohnt und öffnest den Monatsabschluss erneut, um die aktualisierte Bilanz zu sehen.

Der Assistent bucht ausschließlich nach einem Klick. Seine Buchungen können über **Rückgängig** widerrufen werden.
""",
        "en": """
# Month-end close

Open it via **Cockpit → Month-end close…**. It calculates from actual transactions:

**Income − expenses − savings = available balance**

A surplus can be booked to a savings category; a deficit can be covered from savings that actually had funds by the end of that month. Suggestions for the following month only mention flexible budgets—fixed and recurring costs are never proposed for cuts.

The **mark month as closed** checkbox is only a reminder flag for the cockpit. It does not lock the month: budgets and transactions remain editable. After a correction, reopen the assistant to see the updated balance.

Nothing is booked automatically and assistant-created transactions can be undone.
""",
        "fr": """
# Clôture du mois

Ouvrez-la via **Cockpit → Clôture du mois…**. Le calcul utilise les opérations réelles :

**Revenus − dépenses − épargne = montant disponible**

Un excédent peut être versé sur une catégorie d’épargne ; un déficit peut être couvert par une épargne qui disposait réellement de fonds à la fin du mois. Les indications pour le mois suivant ne concernent que les budgets flexibles : les charges fixes et récurrentes ne sont jamais proposées à la réduction.

La case **marquer le mois comme clôturé** n’est qu’un repère pour le cockpit. Elle ne verrouille ni budget ni opération. Après une correction, rouvrez l’assistant pour recalculer le solde.

Aucune écriture n’est créée sans clic et les écritures de l’assistant peuvent être annulées.
""",
    }

    # Ausbauen: tägliche Buchungsarbeit und Filter waren bisher zu knapp.
    by_id["buchungen"]["body"] = {
        "de": """
# Buchungen / Tracking

Hier erfasst du echte Geldbewegungen mit **Datum, Typ/Konto, Kategorie, Betrag, Bemerkung und Tags**. Die Kategorieauswahl zeigt nur passende Kategorien des gewählten Typs; bei einer Hauptkategorie im Filter werden ihre Unterkategorien mit berücksichtigt.

## Erfassen und korrigieren
- **Buchung erfassen / Strg+N:** vollständiger Buchungsdialog aus Cockpit, Toolbar und Tracking.
- **Speichern und weitere hinzufügen:** behält sinnvolle letzte Einstellungen wie das Konto bei.
- **Bearbeiten, duplizieren, löschen:** über Knöpfe oder Rechtsklick auf die ausgewählte Zeile.
- **Fix/Wiederkehrend buchen / Strg+Umschalt+F:** zeigt fällige Positionen für einen gewählten Monat und bucht nur deine Auswahl.

## Filter
Filterbar sind Typ/Konto, Kategorie, Tag, Datum bzw. Zeitraum, Betrag und Freitext/Bemerkung. **Filter zurücksetzen** stellt die vollständige Liste wieder her. Je nach Einstellung merkt sich BudgetManager deine Filter.

## Sparziele und Tags
Eine Ersparnisbuchung kann ein verknüpftes Sparziel erhöhen. Bei einer Entnahme wird der Konflikt erklärt und du entscheidest, ob die Buchung als Sparziel-Entnahme gelten soll. Feste Kategorie-Tags werden automatisch ergänzt; manuelle Tags bleiben erhalten.

Jede Änderung wirkt sofort auf Cockpit und Übersicht. Für Fehlbedienungen stehen **Rückgängig/Wiederholen** zur Verfügung.
""",
        "en": """
# Transactions / tracking

Record real money movements with **date, account/type, category, amount, note and tags**. Only categories matching the selected type are offered; selecting a parent in the filter also includes its children.

Use **Add transaction / Ctrl+N** from the cockpit, toolbar or Tracking. **Save and add another** keeps useful choices such as the account. Edit, duplicate or delete the selected row via buttons or its context menu. **Book fixed/recurring / Ctrl+Shift+F** lists due items for a chosen month and books only your selection.

Filters cover account/type, category, tag, date range, amount and free text. Reset restores the full list. Savings transactions can update a linked goal and withdrawals are confirmed explicitly. Fixed category tags are added automatically while manual tags are preserved.
""",
        "fr": """
# Opérations / suivi

Enregistrez les mouvements réels avec **date, compte/type, catégorie, montant, remarque et tags**. Seules les catégories du type choisi sont proposées ; sélectionner une catégorie principale dans le filtre inclut aussi ses sous-catégories.

Utilisez **Ajouter une opération / Ctrl+N** depuis le cockpit, la barre d’actions ou le suivi. **Enregistrer et en ajouter une autre** conserve les choix utiles comme le compte. Les boutons et le menu contextuel permettent modifier, dupliquer ou supprimer. **Saisir les charges fixes/récurrentes / Ctrl+Maj+F** n’enregistre que les lignes sélectionnées pour le mois choisi.

Les filtres couvrent compte/type, catégorie, tag, période, montant et texte libre. Une opération d’épargne peut mettre à jour un objectif lié ; les retraits sont confirmés. Les tags fixes de catégorie sont ajoutés automatiquement, les tags manuels restent conservés.
""",
    }

    by_id["uebersicht"]["body"] = {
        "de": """
# Übersicht

Die Übersicht verbindet **Plan, Ist und Verlauf**. Oben wählst du Jahr, Monat oder einen benutzerdefinierten Zeitraum. Rechts lassen sich Typ/Konto, Kategorie inklusive Unterkategorien, Tags, Bemerkung und Betragsgrenzen kombinieren.

## Was du siehst
- KPI-Karten für Einnahmen, Ausgaben, Ersparnisse und Bilanz.
- Budgettabellen mit Soll, Ist, Rest, Nutzung in Prozent und Überschreitungen.
- Plan/Ist-Donut, Kategorien-Ranking, Kontotyp-Vergleich, Monatsverlauf, Monatsbilanz und Top-Buchungen.
- Gefilterte Buchungsliste und Budgetvorschläge.

Klicks auf KPI oder Diagramme setzen passende Filter. Ein Doppelklick auf eine Budgetzeile öffnet die zugehörige Budgetbearbeitung. Über **Vorschläge** prüfst du Lernbudgets, Erhöhungen oder Senkungen; es wird nichts automatisch übernommen.

Sind Werte unerwartet, zuerst Zeitraum und rechte Filter prüfen und anschließend **F5** drücken.
""",
        "en": """
# Overview

The overview joins **plan, actual and trend**. Choose a year, month or custom range and combine filters for account/type, category including descendants, tags, note and amount limits.

It contains KPI cards, planned/actual tables with remaining amount and percentage, the nested donut, category ranking, type comparison, monthly trends, balance trend, top transactions and a filtered transaction list. Clicking KPI cards or charts applies matching filters; double-clicking a budget row opens its editor. Suggestions are always reviewed before they change a budget.
""",
        "fr": """
# Aperçu

L’aperçu réunit **prévu, réel et évolution**. Choisissez année, mois ou période personnalisée, puis combinez les filtres de compte/type, catégorie avec descendants, tags, remarque et limites de montant.

Il contient cartes KPI, tableaux prévu/réel avec reste et pourcentage, donut, classement des catégories, comparaison des types, évolutions mensuelles, bilan, plus grandes opérations et liste filtrée. Un clic sur une carte ou un graphique applique le filtre correspondant ; un double-clic sur une ligne de budget ouvre sa modification. Toute suggestion doit être validée avant de modifier le budget.
""",
    }

    by_id["backup"]["body"] = {
        "de": """
# Backup & Wiederherstellung

Du findest den Bereich im Reiter **Konto** oder unter **Datei → Einstellungen → Konto & Daten**. Ein BudgetManager-Backup ist normalerweise ein geprüftes **`.bmr`-Restore-Bundle** und kann Datenbank sowie – je nach Paket – Einstellungen und lokale Kontoinformationen enthalten.

## Sicherer Ablauf
1. Vor Reset, Import, Datenumzug oder größerem Update ein frisches Backup erstellen.
2. Wichtige Backups zusätzlich außerhalb des Datenordners aufbewahren.
3. Beim Restore genau prüfen, ob nur die aktive Datenbank oder ein vollständiges Konto wiederhergestellt wird.
4. Bei verschlüsselten Daten kann der **Restore-Key** verlangt werden.

Auto-Backups lassen sich mit Intervall, Anzahl aufzubewahrender Sicherungen und optionaler Bereinigung einstellen. Eine Wiederherstellung ersetzt Daten; BudgetManager legt dafür Sicherheitskopien an, trotzdem bleibt ein eigenes externes Backup Best Practice.

**Nicht verwechseln:** CSV/TXT-Export ist für Auswertung, `.bmr` ist für Wiederherstellung.
""",
        "en": """
# Backup & restore

Open it in the **Account** page or **File → Settings → Account & data**. A BudgetManager backup is normally a verified **`.bmr` restore bundle** and may include the database, settings and local account metadata.

Create a fresh backup before reset, import, data-folder migration or major updates; keep important copies outside the data folder. During restore, check whether only the active database or a complete account is being restored. Encrypted data may require the restore key.

Automatic backup interval, retention count and cleanup are configurable. CSV/TXT export is for analysis; `.bmr` is the recovery format.
""",
        "fr": """
# Sauvegarde et restauration

Ouvrez la fonction dans la page **Compte** ou via **Fichier → Réglages → Compte et données**. Une sauvegarde BudgetManager est normalement un paquet vérifié **`.bmr`** pouvant contenir base de données, réglages et informations locales du compte.

Créez une sauvegarde avant réinitialisation, import, déplacement du dossier de données ou mise à jour importante et conservez une copie hors du dossier de données. Lors de la restauration, vérifiez si vous remplacez seulement la base active ou un compte complet. Les données chiffrées peuvent exiger la clé de restauration.

L’intervalle, la rétention et le nettoyage des sauvegardes automatiques sont réglables. CSV/TXT sert à l’analyse ; `.bmr` sert à restaurer.
""",
    }


def _handbook_additions() -> list[dict]:
    """Liefert die in v2.2.35 ergänzten dreisprachigen Themen."""
    return [
        _topic(
            "lernmodus",
            "🧠",
            "Tracking-Lernmodus",
            "Tracking learning mode",
            "Mode apprentissage du suivi",
            """
# Tracking-Lernmodus

Der Lernmodus ist für Kategorien gedacht, die im ausgewählten Jahr **noch kein Budget** haben. Du kannst zuerst echte Buchungen sammeln; nach der eingestellten Beobachtungszeit erscheint ein Vorschlag für ein Startbudget.

**Pfad:** **Datei → Einstellungen → Verhalten → Budgetübersicht**. Dort stellst du Aktivierung, erste Vorschlagsmonate, benötigte stabile Monate, Hochrechnung des laufenden Monats, Anzeige im Bericht und automatisches Ende ein.

Im Vorschlagsdialog kannst du **übernehmen**, **weiter beobachten**, **ignorieren**, als **unregelmäßig/POT** markieren oder den Lernstatus zurücksetzen. Beim Übernehmen bestätigst du die Budgetart. Sobald ein positives Jahresbudget existiert, arbeitet für diese Kategorie die normale Forecast-Logik.

Der Lernmodus bucht nie und verändert Budgets nie ohne Bestätigung. Automatisch erzeugte Fixkostenbuchungen sollen das Lernmuster nicht verzerren.
""",
            """
# Tracking learning mode

Learning mode is for categories with **no budget yet** in the selected year. Record real transactions first; after the configured observation period the app offers a starting budget.

Configure it under **File → Settings → Behaviour → Budget overview**: enablement, first proposal, required stable months, current-month projection, report visibility and automatic ending.

In the suggestion dialog you can accept, keep observing, ignore, mark as irregular/pot or reset the learning state. Acceptance requires confirming the budget kind. Once a positive annual budget exists, normal forecasting takes over. Nothing is booked or changed without confirmation.
""",
            """
# Mode apprentissage du suivi

Ce mode concerne les catégories **sans budget** dans l’année choisie. Enregistrez d’abord les opérations réelles ; après la période d’observation réglée, l’application propose un budget initial.

Réglage : **Fichier → Réglages → Comportement → Aperçu du budget**. Vous y choisissez activation, premier délai, mois stables, projection du mois courant, présence dans le rapport et fin automatique.

Dans les suggestions, vous pouvez accepter, continuer à observer, ignorer, classer en irrégulier/POT ou réinitialiser l’apprentissage. Aucun budget ni aucune écriture n’est modifié sans validation.
""",
        ),
        _topic(
            "pot-rueckstellung",
            "🪣",
            "POT / Rückstellung",
            "Pot / reserve",
            "POT / provision",
            """
# POT / Rückstellung

Ein POT ist für **erwartete, aber unregelmäßige Ausgaben** gedacht, zum Beispiel Franchise, Selbstbehalt, Reparaturen oder eine Jahresrechnung. Er ist kein Sparziel.

## Einrichten
Im Kategorie-Manager den Forecast-Modus **POT / Rückstellung** wählen. Im Modus **Auto** wird *Fix ohne Wiederkehrend* standardmäßig als POT behandelt. Du planst Monatsbeträge oder einen Jahresbetrag; die Übersicht und das Cockpit zeigen Budget, Verbrauch und verbleibende Rückstellung.

## Verhalten
Teil-Verbrauch senkt nicht automatisch das künftige Monatsbudget. Erst wenn der verfügbare Topf überschritten wird, entsteht eine Erhöhungswarnung. 0-Monate gelten nicht als Beweis, dass der POT unnötig ist.

## Unterschied zum Sparziel
POT = reserviertes Budget für eine erwartete Ausgabe. Sparziel = fester Zielbetrag mit Einzahlungen, Freigabe und Entnahmen, zum Beispiel Hochzeit oder Reise.
""",
            """
# Pot / reserve

A pot is for **expected but irregular expenses**, such as a deductible, co-payment, repair or annual invoice. It is not a savings goal.

Choose forecast mode **Pot / reserve** in the category manager. In Auto mode, *fixed but not recurring* defaults to a pot. Plan monthly amounts or an annual amount; the cockpit and overview show planned amount, usage and remaining reserve.

Partial use does not automatically reduce future budgets. An increase warning appears when the available pot is exceeded, and zero months do not prove that the reserve is unnecessary. A savings goal instead has a fixed target with contributions and withdrawals.
""",
            """
# POT / provision

Un POT sert aux **dépenses attendues mais irrégulières** : franchise, quote-part, réparation ou facture annuelle. Ce n’est pas un objectif d’épargne.

Choisissez le mode de prévision **POT / provision** dans le gestionnaire de catégories. En mode Auto, *fixe mais non récurrent* devient normalement un POT. Le cockpit et l’aperçu montrent montant planifié, consommation et provision restante.

Une utilisation partielle ne réduit pas automatiquement les budgets futurs. Une alerte d’augmentation apparaît seulement si le POT disponible est dépassé. Un objectif d’épargne possède au contraire un montant cible avec versements et retraits.
""",
        ),
        _topic(
            "jahreswechsel",
            "🗓️",
            "Jahreswechsel & 13. Monatslohn",
            "Year change & 13th salary",
            "Changement d’année et 13e salaire",
            """
# Jahreswechsel & 13. Monatslohn

## Jahr kopieren
Im Budget-Tab öffnet **Jahr kopieren** eine Prüfliste. Du wählst Quell- und Zieljahr, Kontotyp oder alle Typen und ob Beträge übernommen werden. Pro Kategorie kannst du die Übernahme abwählen oder einen neuen Jahresbetrag setzen. Fixkosten, Wiederholungen, POTs, inkrementelle Kategorien und Tracking-Lernvorschläge werden sichtbar geprüft.

## 13. Monatslohn
Der Knopf **13. Lohn** im Budget-Tab trägt ein einmaliges Einnahmenbudget in genau einem Auszahlungsmonat ein. Verwende eine eigene Kategorie, damit normaler Lohn und Forecast nicht verfälscht werden.

## Übertrag
Die Einstellungen zur Übertrag-Kumulation bestimmen den Startmonat bzw. das Startjahr für die Anzeige. Ein Übertrag ist eine Budget-/Auswertungshilfe und keine automatisch erzeugte Bankbuchung.
""",
            """
# Year change & 13th salary

**Copy year** in the Budget page opens a review list. Choose source and target year, all accounts or one type, whether amounts are copied, and then include/exclude each category or set a new annual amount. Fixed, recurring, pot, incremental and learning items are reviewed explicitly.

The **13th salary** button creates one income budget in exactly one payout month. Keep it in a separate category so normal salary and forecasts remain clean. Carryover settings control where accumulated display starts; carryover is not an automatic bank transaction.
""",
            """
# Changement d’année et 13e salaire

**Copier l’année** dans le budget ouvre une liste de contrôle. Choisissez années source/cible, tous les comptes ou un type, reprise des montants, puis incluez/excluez chaque catégorie ou adaptez son montant annuel. Charges fixes, récurrentes, POT, incrémentielles et propositions d’apprentissage sont vérifiées.

Le bouton **13e salaire** crée un budget de revenu unique dans un seul mois de versement. Utilisez une catégorie séparée pour ne pas fausser salaire normal et prévisions. Le report est une aide d’affichage/budget, pas une opération bancaire automatique.
""",
        ),
        _topic(
            "suche-filter",
            "🔎",
            "Suche & Filter",
            "Search & filters",
            "Recherche et filtres",
            """
# Suche & Filter

## Globale Suche
**Extras → Suche** oder **Strg+F** durchsucht Buchungen, Budgets und Kategorien. Mindestens zwei Zeichen eingeben. Ein Doppelklick springt zum passenden Bereich.

## Tracking-Filter
Kombinierbar sind Typ/Konto, Kategorie, Tags, Datum/Zeitraum, Betrag und Bemerkung. Bei einer Parent-Kategorie werden ihre Children einbezogen. **Zurücksetzen** entfernt alle Filter.

## Übersicht-Filter
Jahr/Monat oder benutzerdefinierter Zeitraum oben; Typ, Kategorie, Tags, Text und Betrag rechts. Diagramm- und KPI-Klicks können Filter setzen. Prüfe bei scheinbar fehlenden Daten immer zuerst den Zeitraum.

Die Einstellung **Filter merken** bewahrt die letzte Auswahl. Schalte sie aus, wenn du bei jedem Start eine neutrale Ansicht möchtest.
""",
            """
# Search & filters

Use **Extras → Search** or **Ctrl+F** to search transactions, budgets and categories; enter at least two characters and double-click a result to navigate.

Tracking filters can combine account/type, category, tags, date range, amount and note. Selecting a parent includes its children. The overview adds year/month or a custom range and chart/KPI clicks can apply filters. If data seems missing, check the period first. **Remember filters** keeps the last selection.
""",
            """
# Recherche et filtres

**Extras → Recherche** ou **Ctrl+F** recherche opérations, budgets et catégories. Saisissez au moins deux caractères et double-cliquez pour ouvrir la zone correspondante.

Les filtres du suivi combinent compte/type, catégorie, tags, période, montant et remarque. Une catégorie principale inclut ses enfants. L’aperçu ajoute année/mois ou période personnalisée ; un clic sur KPI ou graphique peut appliquer un filtre. Si des données semblent absentes, contrôlez d’abord la période. **Mémoriser les filtres** conserve la dernière sélection.
""",
        ),
        _topic(
            "export-druck",
            "📤",
            "Export, PDF & Drucken",
            "Export, PDF & printing",
            "Export, PDF et impression",
            """
# Export, PDF & Drucken

**Extras → Export / Strg+E** exportiert Tracking, Budget und optional Kategorien für ein Jahr oder den gesamten Zeitraum.

Verfügbare Formate:
- **CSV** mit optionalem UTF-8-BOM für Excel/LibreOffice,
- **TXT** als tabulatorgetrennte Textdatei,
- **XLSX** mit getrennten Tabellenblättern für Tracking, Budget und Kategorien,
- **PDF** als schwarzweiss-tauglicher A4-Bericht.

Der Zeitraum wird vor dem Export ausgewählt. XLSX enthält Filter und fixierte Kopfzeilen; PDF ist für Weitergabe und Ausdruck optimiert. Eine interaktive Druckvorschau ist nicht Teil des Exportdialogs.

Der Export ist kein vollständiges Backup und lässt sich nicht als Wiederherstellung einlesen. Verwende dafür `.bmr`.
""",
            """
# Export, PDF & printing

Use **Extras → Export / Ctrl+E** to export tracking, budget and optionally categories for one year or all years. Available formats are **CSV** (optional UTF-8 BOM), tab-separated **TXT**, **XLSX** with separate worksheets and a print-friendly A4 **PDF** report.

Choose the period before exporting. XLSX includes filters and frozen headers; PDF is optimized for sharing and black-and-white printing. An interactive print preview is not part of the export dialog. Export is not a restorable backup; use `.bmr` for recovery.
""",
            """
# Export, PDF et impression

**Extras → Export / Ctrl+E** exporte suivi, budget et éventuellement catégories pour une année ou toute la période. Formats disponibles : **CSV** avec BOM UTF-8 optionnel, **TXT** tabulé, **XLSX** avec feuilles séparées et rapport **PDF** A4 prêt à imprimer.

Choisissez la période avant l’export. XLSX contient filtres et en-têtes figés ; PDF est optimisé pour le partage et l’impression en noir et blanc. L’aperçu interactif avant impression ne fait pas partie du dialogue. Un export n’est pas une sauvegarde restaurable ; utilisez `.bmr`.
""",
        ),
        _topic(
            "einstellungen-design",
            "⚙️",
            "Einstellungen, Design & GNOME",
            "Settings, appearance & GNOME",
            "Réglages, apparence et GNOME",
            """
# Einstellungen, Design & GNOME

Unter **Ansicht → Bedienmodus** schaltest du zwischen **Einfach** (ruhige Kernoberfläche) und **Erweitert** (alle Hauptreiter) um. Manuelle Sichtbarkeitsänderungen werden als **Benutzerdefiniert** erkannt; es werden keine Daten gelöscht.

**Datei → Einstellungen / Strg+,** ist in Seiten gegliedert:
- **Allgemein:** Sprache, Währung, Zahlenformat, Onboarding und Startverhalten.
- **Verhalten:** Auto-Speichern, Warnungen, Tracking-Zeitraum, Standard-Fälligkeitstag, Lernmodus, Soft-0-Budget, Übertrag und Budget-Drag-&-Drop.
- **Darstellung:** hell/dunkel, Designprofil, Schriftgröße, Tabellendichte und Fixkosten-Markierung.
- **Tastenkürzel:** alle Kürzel ändern oder zurücksetzen.
- **Konto & Daten:** Datenordner, Backup und Datenbankverwaltung.

BudgetManager verwendet eigene Designprofile. Seit v2.2.33 bekommt auch die Seitenleiste ihre Farbe aus dem App-Profil; ein dunkles GNOME-Systemtheme darf ein helles BudgetManager-Profil nicht mehr überschreiben. Nach einem Themewechsel werden Tabellen und Diagramme neu geladen.

Bei zu großer Schrift oder kleinem Bildschirm sind Einstellungsseiten scrollbar. Eine Sprachänderung wird vollständig nach dem nächsten Neustart wirksam.
""",
            """
# Settings, appearance & GNOME

Open **File → Settings / Ctrl+,** for general locale/start options, workflow and learning rules, appearance, shortcuts, and account/data management.

BudgetManager uses its own design profiles. Since v2.2.33 the sidebar also takes its background from the application profile, so a dark GNOME system theme must not override a light BudgetManager profile. Settings pages scroll on small screens or with large fonts. A language change is fully applied after restart.
""",
            """
# Réglages, apparence et GNOME

**Fichier → Réglages / Ctrl+,** regroupe langue et démarrage, comportement et apprentissage, apparence, raccourcis, compte et données.

BudgetManager utilise ses propres profils. Depuis v2.2.33, la barre latérale prend elle aussi sa couleur dans le profil de l’application : un thème GNOME sombre ne doit plus remplacer un profil BudgetManager clair. Les pages défilent sur petit écran ou avec grande police. Le changement de langue est complet après redémarrage.
""",
        ),
        _topic(
            "tastenkurzel",
            "⌨️",
            "Tastenkürzel",
            "Keyboard shortcuts",
            "Raccourcis clavier",
            """
# Tastenkürzel

Die vollständige Liste findest du unter **Hilfe → Tastenkürzel** und zum Bearbeiten unter **Datei → Einstellungen → Tastenkürzel**.

Wichtige Standards:
- **F1** Handbuch, **Strg+F1** Kürzelübersicht
- **Strg+N** Buchung, **Strg+F** Suche, **Strg+S** Speichern
- **Strg+K** Kategorien, **Strg+T** Tags, **Strg+E** Export
- **Strg+0…5** Cockpit/Budget/Kategorien/Tracking/Übersicht/Sparziele
- **Strg+Z / Strg+Umschalt+Z** Rückgängig/Wiederholen
- **F2 / Entf / Einfg** Bearbeiten/Löschen/Neu
- **F5** aktualisieren, **F10/F11** maximieren/Vollbild

Eigene Kürzel werden als Abweichung vom Standard gespeichert. **Alle zurücksetzen** stellt die Werkseinstellungen wieder her.
""",
            """
# Keyboard shortcuts

Open **Help → Keyboard shortcuts** for the complete list and **File → Settings → Shortcuts** to edit it. Key defaults include F1 help, Ctrl+N transaction, Ctrl+F search, Ctrl+S save, Ctrl+K categories, Ctrl+T tags, Ctrl+E export, Ctrl+0…5 navigation, Ctrl+Z/Ctrl+Shift+Z undo/redo, F5 refresh and F10/F11 maximise/full screen. Reset all restores defaults.
""",
            """
# Raccourcis clavier

La liste complète se trouve sous **Aide → Raccourcis** et se modifie via **Fichier → Réglages → Raccourcis**. Principaux réglages : F1 aide, Ctrl+N opération, Ctrl+F recherche, Ctrl+S enregistrer, Ctrl+K catégories, Ctrl+T tags, Ctrl+E export, Ctrl+0…5 navigation, Ctrl+Z/Ctrl+Maj+Z annuler/rétablir, F5 actualiser, F10/F11 agrandir/plein écran. La réinitialisation restaure les valeurs d’usine.
""",
        ),
        _topic(
            "datenverwaltung",
            "🗄️",
            "Datenordner & Datenbankverwaltung",
            "Data folder & database management",
            "Dossier de données et gestion de la base",
            """
# Datenordner & Datenbankverwaltung

Öffne den Reiter **Konto** oder **Datei → Einstellungen → Konto & Daten**.

## Datenordner
Dort siehst du den wirksamen Speicherort, kannst ihn im Dateimanager öffnen oder einen neuen Ort wählen. Enthält der alte Ordner Daten und das Ziel ist leer, bietet BudgetManager eine kontrollierte Übernahme mit Sicherheits-Backup an. Der neue Ort wird nach einem Neustart vollständig aktiv.

## Datenbankverwaltung
Sie zeigt Statistiken und Migrationsstand, kann technische Altlasten bereinigen und die Datenbank zurücksetzen. Reset ist absichtlich nur hier erreichbar, verlangt bei geschütztem Konto eine erneute Authentifizierung und löscht Nutzdaten. Vorher Backup erstellen.

Die Statusleiste zeigt aktives Konto und Datenbankpfad. Mehrere portable Programmordner können daher getrennte Datenbestände besitzen.
""",
            """
# Data folder & database management

Open the **Account** page or **File → Settings → Account & data**. It shows the effective storage path, opens it in the file manager and can move data to a new folder. If the old folder contains data and the target is empty, a controlled migration with safety backup is offered; restart activates the new path fully.

Database management shows statistics and migration status, cleans technical leftovers and performs the only normal database reset. Reset requires reauthentication for protected accounts and deletes user data—create a backup first. The status bar shows the active account and database path.
""",
            """
# Dossier de données et gestion de la base

Ouvrez la page **Compte** ou **Fichier → Réglages → Compte et données**. Vous voyez le chemin actif, pouvez l’ouvrir ou déplacer les données. Si l’ancien dossier contient des données et la cible est vide, une migration contrôlée avec sauvegarde de sécurité est proposée ; le redémarrage active complètement le nouveau chemin.

La gestion de la base affiche statistiques et migrations, nettoie les résidus techniques et contient l’unique réinitialisation normale. Celle-ci exige une nouvelle authentification pour un compte protégé et supprime les données : sauvegardez d’abord. La barre d’état indique compte et chemin actifs.
""",
        ),
        _topic(
            "diagnose",
            "🧰",
            "Fehlerdiagnose & Protokolle",
            "Diagnostics & logs",
            "Diagnostic et journaux",
            """
# Fehlerdiagnose & Protokolle

Unter **Hilfe** findest du:
- **Anwendungsprotokoll anzeigen**,
- **Crash-Protokoll anzeigen**,
- **Diagnoseordner öffnen**,
- **Diagnosebericht erstellen**.

Der Diagnosebericht ist ein ZIP für die Fehlersuche. Er enthält Protokolle und technische Laufzeitinformationen, aber bewusst **keine Datenbank und keine Backups**. Prüfe den Inhalt trotzdem vor dem Weitergeben.

Nach einem unsauberen Ende erscheint beim nächsten Start ein Hinweis. Du kannst dann das Log öffnen oder direkt einen Diagnosebericht erstellen. Für reproduzierbare Fehler notiere zusätzlich Handlung, gewählten Reiter/Filter und den genauen Zeitpunkt.
""",
            """
# Diagnostics & logs

The **Help** menu opens the application log, crash log, diagnostics folder and creates a diagnostics ZIP. The report contains logs and technical runtime information but deliberately excludes the database and backups; still review it before sharing.

After an unclean shutdown the next launch offers to open the log or create a report. For reproducible bugs also note the exact action, active page/filter and time.
""",
            """
# Diagnostic et journaux

Le menu **Aide** permet d’afficher journal de l’application, journal de crash, dossier de diagnostic et de créer un ZIP de diagnostic. Il contient journaux et informations techniques mais volontairement **ni base de données ni sauvegardes** ; vérifiez-le néanmoins avant partage.

Après une fermeture incorrecte, le prochain démarrage propose d’ouvrir le journal ou de créer un rapport. Pour un défaut reproductible, notez aussi l’action, la page/le filtre et l’heure exacte.
""",
        ),
    ]


def _cockpit_layout_topic() -> dict:
    """Kapitel zum Cockpit-Layout – Automatik, Fixieren, Spalten, Aussehen."""
    return _topic(
        "cockpit-layout",
        "\u25a6",
        "Cockpit einrichten",
        "Setting up the cockpit",
        "Configurer le cockpit",
        """
# Cockpit einrichten

## Kennzahlen und Trend

Die vier Kacheln oben zeigen Einnahmen, Ausgaben, Ersparnisse und den freien Betrag im **Lohnzyklus**. Dieser beginnt beim tatsächlichen Lohneingang nahe dem hinterlegten wiederkehrenden Lohntag und endet am Tag vor dem nächsten Lohntag. Beispiel bei Lohntag 25: 25. Januar bis 24. Februar. Der Zeitraum steht direkt in der Statuszeile; die Budgetzeile nennt den zugehörigen Budgetmonat. Rechts unten steht der Vergleich zum vorherigen Lohnzyklus als Pfeil mit Betrag. Die Farbe folgt der **Bedeutung, nicht dem Vorzeichen**: mehr Einnahmen sind grün, mehr Ausgaben rot. Ohne erkennbare Lohnkategorie bleibt der Kalendermonat erhalten.

## Auswertung

Der Ring zeigt die Ausgaben des Monats nach Kategorie mit der Summe in der Mitte; ab der sechsten Kategorie wird der Rest zusammengefasst. Der Flächenverlauf daneben zeigt die kumulierten Ausgaben und macht sichtbar, ob sie sich am Monatsanfang oder -ende ballen.

## Automatik oder manuelles Layout

**Automatikmodus (Standard):** Abschnitte ohne Inhalt schrumpfen auf die Kopfzeile und rutschen unter die gefüllten. Bekommt ein Abschnitt wieder Inhalt, kehrt er an seine Position zurück. Oben steht damit immer das, was gerade etwas zu sagen hat.

**Manueller Modus:** `Ansicht → Cockpit-Layout → Kacheln frei anordnen`. Die gesamte **Kopfzeile** und der Griff `≡` sind Drag-Zonen. Kacheln lassen sich nach oben, unten oder in die andere Spalte ziehen; Reihenfolge und Spalte werden sofort gespeichert. Tabellen, Buttons und Diagramme bleiben normal bedienbar.

`Ansicht → Cockpit-Layout → Cockpit-Layout zurücksetzen` stellt Automatik, Standardreihenfolge und Standardspalten wieder her.

Beides gleichzeitig gibt es bewusst nicht: die Automatik würde eine von Hand gezogene Anordnung beim nächsten Aktualisieren überschreiben.

## Ein oder zwei Spalten

Im Automatikmodus entstehen ab etwa 1180 Pixel zwei Spalten. Im manuellen Modus stehen bereits ab 720 Pixel **zwei gleich breite Zielspalten** bereit, damit die Kacheln auch bei normalen Fenstergrössen frei zwischen links und rechts verschoben werden können.

## Aussehen

Farben und Kachelform kommen aus dem Designprofil. Unter `Einstellungen → Erscheinungsbild` stehen 26 Profile bereit, eigene lassen sich erstellen. **Mitternacht – Violett** entspricht der Optik moderner Dashboards.
""",
        """
# Setting up the cockpit

## Key figures and trend

The four tiles show income, expenses, savings and the free amount for the **salary cycle**. It starts with the actual salary receipt near the configured recurring payday and ends on the day before the next payday. The exact period is shown in the status line and the budget line names the matching budget month. Arrows compare against the previous salary cycle. The colour follows **meaning, not sign**: more income is green, more spending red. Without a recognizable salary category, the calendar month remains the fallback.

## Insights

The ring shows this month's spending per category with the total in the centre; beyond five categories the remainder is folded together. The area chart shows cumulative spending across the month.

## Automatic or manual layout

**Automatic (default):** empty sections shrink to their header and drop below the filled ones, returning to their position once they have content again.

**Manual:** `View → Cockpit layout → Arrange tiles freely`. The full **header** and the `≡` handle are drag zones. Move tiles up, down, or into the other column; order and column are saved immediately. Tables, buttons, and charts remain interactive. `Reset cockpit layout` restores the defaults.

Both at once is deliberately impossible — automatic sorting would overwrite a hand-made arrangement.

## One or two columns

Automatic mode uses two columns from roughly 1180 pixels. Manual mode provides **two equal target columns** from 720 pixels so tiles can be moved freely between left and right at normal window sizes.

## Appearance

Colours and tile shapes come from the design profile. `Settings → Appearance` offers 26 profiles; **Midnight – Violet** matches the modern dashboard look.
""",
        """
# Configurer le cockpit

## Indicateurs et tendance

Les quatre tuiles affichent recettes, dépenses, épargne et montant libre pour le **cycle de salaire**. Il commence au versement réel près du jour récurrent configuré et se termine la veille du versement suivant. La période exacte et le mois budgétaire correspondant sont affichés. Les flèches comparent le cycle de salaire précédent. La couleur suit le **sens et non le signe** : plus de recettes est vert, plus de dépenses rouge. Sans catégorie de salaire identifiable, le mois civil reste utilisé.

## Analyse

L'anneau montre les dépenses du mois par catégorie avec le total au centre ; au-delà de cinq catégories le reste est regroupé. Le graphique en aires affiche les dépenses cumulées du mois.

## Disposition automatique ou manuelle

**Automatique (par défaut)** : les sections vides se réduisent à leur en-tête et descendent sous les sections remplies, puis reviennent à leur place dès qu'elles ont du contenu.

**Manuelle** : `Affichage → Disposition du cockpit → Organiser librement les tuiles`. Tout **l’en-tête** et la poignée `≡` servent de zones de déplacement. Les tuiles vont vers le haut, le bas ou l’autre colonne ; l’ordre et la colonne sont enregistrés immédiatement. Les tableaux, boutons et graphiques restent utilisables. `Réinitialiser` rétablit les valeurs par défaut.

Les deux à la fois sont volontairement exclus : le tri automatique écraserait une disposition manuelle.

## Une ou deux colonnes

Le mode automatique utilise deux colonnes à partir d’environ 1180 pixels. Le mode manuel fournit **deux colonnes cibles de même largeur** dès 720 pixels afin de déplacer librement les tuiles entre gauche et droite avec une fenêtre normale.

## Apparence

Les couleurs et la forme des tuiles proviennent du profil de design. `Paramètres → Apparence` propose 26 profils ; **Minuit – Violet** correspond au rendu des tableaux de bord modernes.
""",
    )


def _wiki_relationship_topic() -> dict:
    return _topic(
        "wiki-zusammenhaenge",
        "?",
        "Wiki-Audit & Zusammenhänge",
        "Wiki audit & relationships",
        "Audit du wiki et relations",
        """
# Wiki-Audit & grafische Zusammenhänge

Diese Seite erklärt nicht nur einzelne Knöpfe, sondern **wie die Bereiche zusammenarbeiten**.

## Der Hauptablauf

```text
Erststart
  → Konto, Währung und Datenablage
  → Konten und Kategorien
  → Budget planen ODER Lernmodus verwenden
  → echte Buchungen im Tracking erfassen
  → Cockpit und Übersicht vergleichen Plan mit Ist
  → Warnungen/Vorschläge prüfen
  → Monatsabschluss als Erinnerung setzen
  → Jahreswechsel und Backup durchführen
```

## Was beeinflusst was?

- **Konten und Kategorien** bestimmen, welche Kategorie beim Buchen auswählbar ist.
- **Budget** ist der Plan; **Tracking** enthält die echten Geldbewegungen.
- **Cockpit und Übersicht** berechnen ihre Werte aus Budget **und** Tracking.
- Der **Lernmodus** erstellt nur für Kategorien ohne vorhandenes Budget Vorschläge aus Trackingdaten.
- **Soft-0-Budget** gibt freiwillige Ausgleichsvorschläge; Fixkosten und POT/Rückstellungen bleiben geschützt.
- **Monatsabschluss** ist ein Kontrollpunkt und keine Buchungssperre.
- **Backup/Wiederherstellung** schützt Daten und Einstellungen, verändert aber keine Budgetlogik.

Klicke unten auf **Wiki-Grafiken anzeigen**, um die vollständigen Ablauf- und Datenflussgrafiken im lokalen Browser zu öffnen. Die Dateien funktionieren offline und sind Bestandteil der Linux-, Windows- und Source-Version.

## Wo finde ich die Hilfe?

Seit v2.2.37 sitzt ein **?** rechts oben in der Menüleiste, direkt neben Minimieren/Maximieren/Schließen. Ein Klick öffnet dieses Handbuch. Zusätzlich gibt es den Knopf **? Hilfe** unten links in der Seitenleiste sowie das Menü **Hilfe → Handbuch**. Alle drei Wege führen zum selben durchsuchbaren Handbuch.
""",
        """
# Wiki audit & relationships

This topic explains how the parts work together, not only where buttons are.

```text
First start → accounts and categories → budget or learning mode
→ real transactions → cockpit/overview → warnings and review
→ month-end reminder → year change and backup
```

Accounts and categories control valid booking choices. Budget is the plan, Tracking is actual activity, and Cockpit/Overview combine both. Learning mode only proposes budgets for categories without one. Soft Zero Budget is optional, month-end close is a checkpoint rather than a lock, and backup protects data without changing budgeting logic.

Use **Open wiki graphics** below for the offline process and data-flow diagrams.

## Where to find help

Since v2.2.37 a **?** sits at the top right of the menu bar, right next to minimise/maximise/close. Clicking it opens this handbook. The **? Help** button at the bottom of the sidebar and the **Help → Handbook** menu lead to the same place.
""",
        """
# Audit du wiki et relations

Cette rubrique explique comment les parties coopèrent, pas seulement où se trouvent les boutons.

```text
Premier démarrage → comptes et catégories → budget ou apprentissage
→ opérations réelles → cockpit/aperçu → alertes et contrôle
→ repère de fin de mois → changement d’année et sauvegarde
```

Les comptes et catégories déterminent les choix valides. Le budget est le plan, le suivi contient le réel et le cockpit/l’aperçu combinent les deux. L’apprentissage ne propose un budget que lorsqu’il n’en existe pas. Le budget zéro souple reste facultatif, la clôture est un repère et la sauvegarde protège les données sans modifier la logique.

Utilisez **Ouvrir les graphiques du wiki** ci-dessous pour les schémas hors ligne.

## Où trouver l'aide

Depuis la version 2.2.37, un **?** se trouve en haut à droite de la barre de menus, juste à côté de réduire/agrandir/fermer. Un clic ouvre ce manuel. Le bouton **? Aide** en bas de la barre latérale et le menu **Aide → Manuel** mènent au même endroit.
""",
    )


def apply_handbook_completeness(topics: list[dict]) -> None:
    """Ergänzt und aktualisiert das dreisprachige In-App-Handbuch."""
    by_id = {str(t.get("id")): t for t in topics}
    _apply_topic_corrections(by_id)

    existing_ids = set(by_id)
    for item in _handbook_additions():
        if item["id"] not in existing_ids:
            topics.append(item)
            existing_ids.add(item["id"])

    cockpit_topic = _cockpit_layout_topic()
    if cockpit_topic["id"] not in existing_ids:
        topics.append(cockpit_topic)
        existing_ids.add(cockpit_topic["id"])

    wiki_topic = _wiki_relationship_topic()
    if wiki_topic["id"] not in existing_ids:
        topics.append(wiki_topic)
