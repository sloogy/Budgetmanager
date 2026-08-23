# BudgetManager 3.0.3 – Manuel utilisateur

Ce manuel décrit les fonctions réellement disponibles dans la version 3.0.3. BudgetManager conserve les données localement, ne crée aucune écriture sans validation et sépare **budget (prévision)** et **suivi (opérations réelles)**.

## Premier démarrage en quatre étapes

1. Choisir langue, devise et format numérique.
2. Créer un compte et conserver la clé de restauration séparément.
3. Préparer les catégories par configuration express, import XLSX ou saisie manuelle.
4. Enregistrer la première opération, puis utiliser budget ou mode apprentissage.

## 1. Démarrage rapide

1. Choisir langue, devise et format numérique.
2. Créer un compte Quick, PIN ou mot de passe.
3. Conserver la clé de restauration hors du dossier de l’application.
4. Utiliser la configuration express ou créer les catégories.
5. Saisir des budgets ou commencer avec le mode apprentissage du suivi.
6. Suivre les prochaines étapes du cockpit.

## 2. Zones principales

La barre latérale ouvre Cockpit, Suivi, Budget, Objectifs d’épargne, Aperçu, Catégories optionnelles et Compte. La barre d’actions propose une entrée unique pour opération, charges fixes/récurrentes, catégories, épargne et recherche.

## 3. Catégories

Chaque catégorie appartient aux revenus, dépenses ou épargne et peut être principale ou enfant. Un enfant ne se déplace que dans le même type.

Propriétés : charge fixe, récurrente, jour d’échéance, mode de prévision (Auto, Normal/Flexible, POT/Provision, Incrémentiel), favori et tags fixes. Le renommage se propage dans budgets, suivi, favoris, alertes, récurrences et objectifs. La suppression peut effacer ou réaffecter les données ; sauvegardez d’abord.

Sélectionnez plusieurs lignes dans l’onglet Budget puis faites un clic droit : **⚙️ Modifier N catégories…** ouvre la modification en masse. Charge fixe, récurrence, jour d’échéance et mode de prévision se règlent alors pour toutes les catégories sélectionnées ; les champs que vous laissez tels quels conservent leur valeur d’origine par catégorie.

L’assistant peut importer un modèle XLSX de catégories. La gestion quotidienne utilise **Ctrl+K**.

## 4. Budget

Le budget est une prévision et ne crée pas d’opération. Saisissez un mois, tous les mois ou une plage, éventuellement seulement dans les cellules vides.

**Copier l’année** choisit années source/cible, tous les comptes ou un type, reprise ou non des montants et une liste de contrôle par catégorie. Charges fixes, récurrentes, POT, incrémentielles et apprentissage sont vérifiés. Le bouton **13e salaire** crée un revenu unique dans un seul mois de versement.

Les prévisions utilisent les mois terminés et des modèles stables ; rien n’est appliqué automatiquement.

### Calculer dans les champs de montant

Les champs de montant acceptent aussi un calcul : `23,40 + 12,60` donne 36,00
lorsque vous quittez le champ. Pour saisir un reçu à plusieurs postes, vous le
recopiez au lieu d'additionner de tête.

Les quatre opérations de base, les parenthèses et les signes sont autorisés —
`2 * (3 + 4,50)`. Ce qui n'est pas un calcul reste dans le champ et est
signalé ; cela ne devient jamais un zéro en silence.

Cela vaut dans les boîtes de dialogue comme directement dans les cellules du
tableau budgétaire.

## 5. Prévisions — Modes de prévision et apprentissage

- **Normal/Flexible :** dépenses variables courantes.
- **POT/Provision :** dépenses attendues mais irrégulières, par exemple franchise, réparation ou facture annuelle. Une utilisation partielle ne réduit pas automatiquement le POT ; un dépassement peut produire une alerte.
- **Incrémentiel :** coûts annuels ou trimestriels payés irrégulièrement ou par tranches.
- **Mode apprentissage :** propose un budget initial seulement si aucun budget annuel positif n’existe. Réglage sous **Fichier → Paramètres → Comportement → Aperçu du budget**.
- **Budget zéro souple :** vérifie **revenus − dépenses − épargne ≈ 0 CHF**. Il propose épargne/report en cas d’excédent, puis épargne et dépenses flexibles en cas de déficit. Charges fixes, récurrentes, POT et incrémentielles restent protégées.

Un POT est une provision pour dépense attendue. Un objectif d’épargne possède un montant cible avec versements et retraits.

## 5.1 Choisir un mode de prévision

Utilisez Normal/Flexible pour les dépenses courantes, POT/Provision pour les coûts attendus mais irréguliers, Incrémentiel pour les coûts annuels par étapes et l’apprentissage uniquement sans budget annuel positif.

## 6. Opérations / suivi

Une opération contient date, compte/type, catégorie, montant, remarque et tags. **Ctrl+N** ouvre le même dialogue complet depuis cockpit, barre d’actions et suivi. Enregistrer puis ajouter conserve les choix utiles comme le compte.

Les boutons/menu contextuel permettent modifier, dupliquer ou supprimer. **Ctrl+Maj+F** liste les charges fixes, récurrentes et attendues du mois choisi et n’enregistre que les lignes cochées.

Les filtres combinent type/compte, catégorie avec descendants, tags, période, montant et texte. Réinitialiser réaffiche tout. Les opérations d’épargne peuvent mettre à jour un objectif lié ; les retraits sont confirmés.

Une **Charge fixe** est protégée des conseils de réduction flexible.

### 6.6 Reprendre des paiements d'autres programmes

D'autres programmes de la suite — FPM par exemple — déposent des dépenses
comme propositions dans un dossier commun. BudgetManager n'ouvre jamais leur
base de données ; il lit les propositions dans une boîte de réception que vous
vérifiez avant toute écriture.

La liste affiche la date, la description, la contrepartie, le montant, la
devise et la catégorie proposée. Sous le tableau, vous choisissez le type et
la catégorie — avec le même champ de recherche et la même liste filtrée que
dans la saisie rapide — puis vous les appliquez à toutes les propositions
sélectionnées avec **Attribuer la catégorie**. Pour vingt paiements
similaires, c'est une étape au lieu de vingt.

**Modifier** permet de changer date, type, catégorie, montant et description
d'une proposition. C'est le seul endroit où une catégorie manquante est
créée, et seulement après votre confirmation explicite.

**Accepter** enregistre l'écriture, **Rejeter** masque la proposition jusqu'à
ce que la source la modifie. Les propositions déjà reprises restent
inchangées : leur écriture existe et ne suivrait pas une modification
ultérieure.

Si la devise source diffère de celle de votre compte, BudgetManager demande
une confirmation explicite avant de reprendre le montant.

### 6.7 Messages dans LifePlanner

Lorsque BudgetManager fonctionne comme module de LifePlanner, il signale ce qui
demande votre attention : budgets dépassés, objectifs d'épargne proches de leur
échéance ou dépassés, et objectifs atteints. LifePlanner les affiche sur sa page
d'aperçu, au-dessus des tuiles de modules — vous les voyez donc sans ouvrir
BudgetManager.

Seul le message fini est transmis : une ligne de texte et son degré d'urgence.
Montants, écritures et noms de catégories restent dans votre base de données.
L'état est écrit à la fermeture et entièrement remplacé la fois suivante ; ce
qui est réglé disparaît de lui-même.

Sans LifePlanner, rien ne se passe ici.

### 6.8 Ce qui est transmis à FPM

La passerelle fonctionne dans les deux sens : FPM propose des dépenses, et en
retour BudgetManager met à disposition des noms de catégories et des objectifs
d'épargne — afin que FPM puisse rattacher ses dépenses à vos catégories et
afficher la progression d'un souhait.

Depuis la version 2.5.0, vous en décidez entrée par entrée.
**Extras → Partage vers FPM** présente les catégories de dépenses, les catégories d'épargne et
les objectifs d'épargne, chacun avec une case à cocher. Seul ce qui est coché
figure dans le fichier de la passerelle ; le reste demeure dans votre base de
données. Des catégories, seul le nom sort — ni montant budgété, ni écriture ;
d'un objectif d'épargne, le nom, le montant et l'échéance.

Il n'y a pas de bouton OK : chaque case agit immédiatement, et les fichiers de
la passerelle sont réécrits à la fermeture de la boîte de dialogue. **Tout dans
l'onglet** et **Rien dans l'onglet** ne valent que pour l'onglet affiché.
**Envoyer à FPM maintenant** réécrit les fichiers sur-le-champ et indique le
dossier où ils se trouvent.

Lors de la mise à jour vers 2.5.0, tout ce qui était déjà transmis reste
partagé — sinon FPM se retrouverait subitement sans catégories. En revanche,
les catégories et objectifs d'épargne créés ensuite ne sont pas partagés
d'office. Une exception : un objectif d'épargne issu d'un souhait FPM est
répercuté afin que la progression y soit visible ; vous pouvez le retirer dans
la même boîte de dialogue.

### 6.9 Import bancaire depuis PDF et CSV

**Import → Relevé bancaire PDF/CSV…** lit un relevé de compte ou un relevé de
carte de crédit. La lecture se fait sur votre ordinateur ; aucune ligne n'est
transmise à un service tiers.

Chaque ligne reconnue est affichée avec sa date, son type, son montant, son
texte, sa catégorie, ses étiquettes et une case à cocher. **Seules les lignes
cochées sont enregistrées.** Les propositions de type et de catégorie
proviennent de la mémoire locale, qui ne propose que des catégories et des
étiquettes existantes.

Sélectionnez plusieurs lignes avec **Ctrl+clic**, **Maj+clic** ou **Ctrl+A**.
Les listes déroulantes au-dessus du tableau appliquent le type, la catégorie,
les étiquettes et l'état de sélection à toutes les lignes marquées.

Les étiquettes obligatoires de la catégorie choisie sont posées et le restent ;
d'autres étiquettes existantes peuvent être cochées dans la liste déroulante.

Ouvrir deux fois le même fichier ne crée pas de doublons : chaque ligne porte
un identifiant composé de la date, du montant et du texte. L'import se
déroule d'un seul tenant — il aboutit entièrement ou pas du tout.

L'apprentissage a lieu **après** l'import et uniquement à partir de ce que vous
avez confirmé. Une proposition modifiée ou décochée n'est pas apprise.

**Les entrées TWINT ne sont pas enregistrées comme revenus.** Un montant TWINT
positif est le plus souvent le remboursement d'une dépense déjà présente dans
vos chiffres ; enregistré comme revenu, le mois serait faux deux fois. Ces
lignes reçoivent le type **TWINT (KI)** : vous leur attribuez une vraie
catégorie, le programme retient l'attribution, et l'écriture elle-même a un
effet de 0.00 sur votre budget.

## 7. Aperçu

Choisissez année, mois ou période personnalisée et combinez compte/type, catégorie avec enfants, tags, remarque et montant. L’aperçu contient KPI, tableaux prévu/réel, reste, pourcentage, dépassements, opérations filtrées et suggestions à valider.

### Explication des graphiques

Graphiques : donut prévu/réel, classement, comparaison des types, évolution mensuelle, bilan et principales opérations. Un clic applique des filtres ; un double-clic sur une ligne de budget ouvre sa modification.

## 8. Objectifs d’épargne

Un objectif est un flux de projet. L’application sépare **cible**, **versé**, **utilisé/retiré**, **solde actuel** et **reste à verser**. Exemple : cible `50 000`, versé `30 000`, utilisé `15 000` donne un solde de `15 000` et `20 000` encore à verser. Une opération négative est par défaut un **retrait**. Choisissez explicitement **correction** pour une erreur afin qu’elle ne compte pas comme utilisation. Une **libération partielle** rend disponible un montant choisi sans fermer l’objectif.

Si FPM fait partie de la suite, les stylos souhaités peuvent arriver ici comme objectifs d'épargne. Dans la boîte de dialogue des objectifs, **Souhaits de FPM…** affiche les propositions ouvertes et demande pour chacune séparément. Une catégorie qui n'existe pas ici n'est **pas créée** — l'objectif est créé sans catégorie et vous l'affectez vous-même ; un autre programme ne doit pas modifier votre arborescence.

## 9. Cockpit

Le cockpit montre feu, prochaines étapes, KPI, échéances, alertes, restes de POT, favoris, objectifs et opérations récentes. Vous pouvez choisir l’ordre et la visibilité des cartes.

### 9.1 Indicateurs et tendance

Les quatre tuiles du haut affichent recettes, dépenses, épargne et montant libre. En bas à droite de chaque tuile, une flèche et un montant comparent au mois précédent. La couleur suit le sens et non le signe : plus de recettes est vert, plus de dépenses est rouge. Le premier mois, sans données antérieures, la flèche reste masquée.

### 9.2 Analyse

La section **Analyse** contient deux graphiques. L'anneau montre les dépenses du mois par catégorie avec le total au centre ; au-delà de cinq catégories, le reste est regroupé. Le graphique en aires affiche les dépenses cumulées du mois et révèle si elles se concentrent en début ou en fin de mois.

### 9.3 Disposition automatique ou figée

Par défaut, le mode **automatique** est actif : les sections sans contenu se réduisent à leur en-tête et descendent sous les sections remplies. Dès qu'une section retrouve du contenu, elle revient à sa position enregistrée.

Pour créer votre propre disposition, activez **Affichage → Disposition du cockpit → Organiser librement les tuiles** ou le bouton correspondant en haut du cockpit. **Tout l’en-tête** de chaque tuile devient alors une zone de glisser-déposer ; la poignée `≡` reste également disponible. Les colonnes gauche et droite sont des piles indépendantes : une tuile à droite peut donc monter tout en haut sans dépendre de la hauteur des tuiles à gauche. Un **emplacement de dépôt** mis en évidence montre la position exacte pendant le déplacement. L’ordre et la colonne sont enregistrés dès que la tuile est déposée. Les tableaux, boutons et graphiques restent utilisables car le contenu de la tuile n’est pas une zone de déplacement. **Affichage → Disposition du cockpit → Réinitialiser** rétablit le mode automatique, l’ordre et les colonnes par défaut.

Les deux à la fois sont volontairement exclus : le tri automatique écraserait une disposition faite à la main au prochain rafraîchissement.

### 9.4 Une ou deux colonnes

En mode automatique, le cockpit passe à deux colonnes à partir d’environ 1180 pixels. En mode manuel, deux colonnes cibles de largeur égale sont disponibles dès 720 pixels afin de déplacer librement les tuiles entre gauche et droite avec une fenêtre normale. Avec une largeur encore plus faible, la vue peut défiler horizontalement tout en conservant la disposition enregistrée.

### 9.5 Apparence

Les couleurs et la forme des tuiles proviennent entièrement du profil de design actif. **Paramètres → Apparence** propose 26 profils et permet d'en créer. **Minuit – Violet** correspond au rendu des tableaux de bord modernes : fond presque noir, tuiles détachées, accent violet.

## 10. Tags

Les tags ajoutent un contexte aux catégories. Les tags fixes sont ajoutés automatiquement ; les tags manuels restent lors d’un changement de catégorie.

## 11. Comptes

BudgetManager conserve toujours les trois types de comptes **Revenus**, **Dépenses** et **Épargne**. Des comptes supplémentaires peuvent être créés, colorés et fermés dans la gestion des comptes/catégories, tandis que les types de base restent disponibles.

Le compte décrit le flux d’argent ; la catégorie décrit son usage. Le choix du compte/type limite les catégories proposées. Les comptes utilisateur pour connexion et chiffrement sont expliqués plus loin.

## 12. Clôture mensuelle

Ouvrez **Cockpit → Clôture du mois…**. Le calcul réel est **revenus − dépenses − épargne**. Un excédent peut être versé à l’épargne, un déficit couvert par une épargne disponible à la fin de ce mois. Seuls les budgets flexibles sont mentionnés pour une éventuelle réduction future.

**Marquer comme clôturé** est seulement un rappel du cockpit. Cela ne verrouille ni budget ni opération. Après correction, rouvrez l’assistant pour recalculer.

## 13. Favoris et recherche

Les favoris sont les catégories contrôlées fréquemment et sont disponibles via le cockpit/tableau F12.

**Extras → Recherche globale / Ctrl+F** recherche opérations, budgets et catégories. Saisissez au moins deux caractères et double-cliquez pour naviguer.

## 14. Export, PDF et impression

**Extras → Exporter / Ctrl+E** exporte le suivi, le budget et éventuellement les catégories pour une année ou toute la période.

Les formats disponibles sont CSV avec BOM UTF-8 optionnel, TXT tabulé, XLSX avec feuilles séparées et un rapport PDF A4 prêt à imprimer. XLSX contient des filtres et des en-têtes figés. L’aperçu interactif avant impression ne fait pas partie du dialogue.

L’export n’est pas une sauvegarde ; utilisez `.bmr` pour la restauration.
## 15. Compte utilisateur, clé et données

Niveaux de sécurité : Quick, PIN et mot de passe. Nom, secret et niveau peuvent être modifiés ; les actions sensibles peuvent exiger une nouvelle authentification.

Conservez la clé de restauration séparément des sauvegardes. Une personne possédant clé et base `.enc` peut déchiffrer les données.

La page **Compte** ou **Fichier → Paramètres → Compte et données** affiche le dossier actif, déplace les données avec sauvegarde de sécurité et ouvre sauvegarde/restauration et gestion de base. Le nouveau chemin est pleinement actif après redémarrage.

Les sauvegardes `.bmr` peuvent contenir la base, les réglages et le compte utilisateur associé à cette base. Si plusieurs comptes locaux existent, seul le compte correspondant est inclus. Intervalle, rétention et nettoyage automatiques sont réglables. La gestion de base affiche statistiques/migrations, nettoie les résidus et contient l’unique réinitialisation normale, avec nouvelle authentification si le compte est protégé.

Depuis la version 2.2.48, la base, les réglages et les métadonnées du compte possèdent chacun leur propre contrôle SHA-256. Les éléments endommagés ou modifiés sont refusés et une ancienne sauvegarde confirmée peut être convertie en copie entièrement contrôlée. Ces contrôles détectent une corruption mais ne prouvent pas l’origine du fichier ; restaurez une sauvegarde complète de compte uniquement depuis une source fiable. Une sauvegarde de compte Quick peut contenir la clé locale de la base ; traitez donc le fichier `.bmr` comme un mot de passe et ne le déposez pas sans protection dans un dossier cloud public.

Un démarrage source ou portable peut utiliser le dossier standard `data/`. Avec plusieurs dossiers du programme, fiez-vous au chemin affiché dans la barre d’état.

## 16. Réglages et apparence

**Fichier → Paramètres / Ctrl+,** couvre langue/démarrage, comportement, suivi, apprentissage, budget zéro souple, report, apparence, raccourcis et compte/données.

BudgetManager utilise ses propres profils. Depuis v2.2.33, la barre latérale prend sa couleur dans le profil de l’application ; un thème GNOME sombre ne doit pas remplacer un profil clair. Le changement de langue est complet après redémarrage.

### Mode simple et avancé

Utilisez **Affichage → Mode d’utilisation** pour basculer à tout moment :

- **Simple :** cockpit, budget, suivi et aperçu ; catégories et objectifs restent accessibles via les dialogues ou après changement de mode.
- **Avancé :** affiche tous les onglets principaux et le cockpit standard complet.

Les onglets ou panneaux modifiés manuellement sont reconnus comme **Personnalisé**. Aucune donnée ni fonction n’est supprimée.

## 17. Raccourcis importants

F1 aide, Ctrl+F1 liste, Ctrl+N opération, Ctrl+F recherche, Ctrl+S enregistrer, Ctrl+K catégories, Ctrl+T tags, Ctrl+E export, Ctrl+0…5 navigation, Ctrl+Z/Ctrl+Maj+Z annuler/rétablir, Ctrl+Maj+F charges fixes/récurrentes, F5 actualiser, F10/F11 agrandir/plein écran. Tous sont modifiables.

## 18. Mises à jour et diagnostic

**Extras → Mises à jour / Ctrl+U** vérifie manifeste et intégrité, télécharge le paquet adapté et prépare l’installation sans remplacer le dossier de données.

Le menu Aide ouvre journaux, dossier de diagnostic et crée un ZIP. Il exclut volontairement base et sauvegardes ; vérifiez-le avant partage.

## 19. Bonne routine

Chaque jour : saisir les opérations. Chaque semaine : vérifier filtres et aperçu. Chaque mois : saisir les échéances, contrôler clôture et suggestions, créer une sauvegarde. Chaque année : copier l’année, vérifier catégories fixes/POT/incrémentielles et saisir le 13e salaire séparément.

## Relations et schémas graphiques

Ouvrez **Aide → Relations et schémas** pour une page hors ligne avec trois schémas : parcours complet, flux Budget/Suivi et boucle de retour par aperçu, alertes et adaptation. Le **?** en haut à droite de la barre de menus – juste à côté de réduire/agrandir/fermer – ouvre le manuel consultable. Le bouton **? Aide** en bas de la barre latérale fait de même. Les deux utilisent du texte normal plutôt qu'un emoji, afin de rester visibles sous Linux sans police emoji.

Depuis la version 2.2.41, les tuiles vides du cockpit descendent automatiquement en fin de colonne. Pour conserver votre propre disposition, activez **Épingler les tuiles** : l'ordre est alors figé et les tuiles se déplacent à la souris par leur en-tête, y compris d'une colonne à l'autre.

Depuis la version 2.2.38, le menu **Aide** est réparti en cinq groupes : consultation (manuel, base de connaissances, vues d'ensemble visuelles), apprentissage (raccourcis clavier, premiers pas), un sous-menu **Dépannage** (journal de l'application, journal de plantage, dossier de diagnostic, rapport de diagnostic, clé de récupération), version (rechercher des mises à jour, nouveautés) et enfin À propos. La recherche de mises à jour se trouvait auparavant sous Extras.
