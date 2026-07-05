# BudgetManager 2.2.6 – Guide utilisateur

## 1. Idée générale

BudgetManager fonctionne localement sur votre ordinateur. L'application enregistre budgets, opérations, catégories, sauvegardes et paramètres dans le dossier de données. Dans la version portable, ce dossier se trouve à côté du programme sous `data/`.

Flux conseillé :

1. Vérifier ou créer les catégories.
2. Saisir le budget mensuel.
3. Enregistrer les vraies opérations dans le suivi.
4. Contrôler l'aperçu et les graphiques.
5. Créer une sauvegarde avant les grands changements.

## 2. Catégories

Les catégories appartiennent toujours à un type : revenus, dépenses ou épargne. Les sous-catégories ne peuvent être déplacées que dans le même type. Le glisser-déposer permet de placer une catégorie sous une catégorie principale ou de la remettre au niveau principal.

Options :

- **Charge fixe** : coût planifié ou réserve, par exemple loyer, assurance, franchise ou participation médicale.
- **Récurrent** : opération qui revient régulièrement.
- **Fixe + récurrent** : vraie charge mensuelle. Le montant budgété du mois est utilisé à la saisie.
- **Fixe sans récurrence** : réserve variable protégée. Le montant peut être modifié lors de la saisie.
- **Récurrent sans fixe** : opération régulière mais variable. Le montant peut être modifié.

## 3. Budget

Dans l'onglet Budget, vous saisissez le montant prévu par catégorie et par mois. Un budget ne crée pas d'opération. Il représente seulement le plan.

Règles importantes :

- Les cellules vides valent 0.
- Les catégories parentes affichent la somme des enfants plus leur propre marge.
- La ligne de total affiche la somme de la zone visible.
- Une année peut être copiée depuis une année existante, avec ou sans montants.

## 4. Suivi / opérations

Le suivi enregistre les mouvements d'argent réels. Le choix de catégorie n'affiche que les catégories du type sélectionné. Les favoris et les catégories manuelles fréquentes apparaissent en haut ; les saisies automatiques de charges fixes ne faussent pas cet ordre. Les catégories parentes avec sous-catégories ne sont pas affichées comme lignes saisissables ; les sous-catégories restent courtes, p. ex. **Loyer** au lieu de **Logement › Loyer**.

Le bouton **Saisir les charges fixes/récurrentes** crée volontairement les écritures dues pour le mois choisi. Rien n'est saisi en secret en arrière-plan.

## 5. Prévisions / suggestions de budget

Les suggestions sont des recommandations, pas des changements automatiques. L'application analyse uniquement les mois terminés et évite les suggestions basées sur un seul écart.

Logique :

- Un seul mois à zéro ne suffit jamais à réduire un budget.
- Pour les catégories fixes ou récurrentes, les mois à zéro sont ignorés pour les réductions.
- Les charges fixes nécessitent plusieurs vraies écritures avant une suggestion.
- Les catégories flexibles peuvent apprendre de motifs répétés, même si certains mois sont à zéro.
- Des écarts opposés, par exemple 450 CHF puis 350 CHF avec un budget de 400 CHF, ne déclenchent pas de suggestion.

## 6. Aperçu et graphiques

L'aperçu compare les valeurs prévues et réelles.

Explication des graphiques :

- **Donut prévu/réalisé** : anneau extérieur revenus, anneau central dépenses, anneau intérieur épargne. Chaque anneau montre saisi, encore ouvert ou au-dessus du budget. C’est le contrôle mensuel principal.
- **Classement catégories** : affiche les principales catégories de dépenses en barres. C’est plus lisible qu’un grand camembert.
- **Comparaison comptes** : affiche revenus, dépenses et épargne en barres. Cela remplace le camembert voisin confus, car ces valeurs ne sont pas des parts d’un même total.
- **Évolution mensuelle** : montre l'évolution sur plusieurs mois. Utile pour repérer les tendances.
- **Solde mensuel** : montre revenus moins dépenses moins épargne par mois.
- **Top opérations** : regroupe les catégories et trie par montant, afin que les loyers ou salaires répétés ne créent pas de doublons trompeurs.

S'il n'y a pas de données, l'application affiche un message au lieu d'un graphique vide.

## 7. Mises à jour

Utilisez **Extras → Mises à jour…** pour rechercher une nouvelle version. La fenêtre de mise à jour montre chaque étape.

Chemins de mise à jour :

- **Portable Windows/Linux** : télécharge le ZIP portable, remplace les fichiers du programme et conserve `data/` et `updates/`.
- **EXE Windows / binaire Linux direct** : migre les anciens fichiers de démarrage versionnés vers des noms stables.
- **Installateur Windows** : télécharge la nouvelle EXE d'installation, attend la fermeture de l'application et lance l'installateur en mode mise à jour. Le dossier de données choisi est conservé.

## 8. Sauvegarde et clé de restauration

La clé de restauration est importante pour les bases chiffrées et la récupération. Conservez-la hors du dossier BudgetManager, par exemple dans Bitwarden.

Avant les grands changements, créez une sauvegarde. Le dossier de données et `data/backups/` ne sont pas écrasés par les mises à jour.

## 5.1 Mode apprentissage du suivi

Le mode apprentissage aide lorsqu’aucun budget n’a encore été défini. Il utilise uniquement les écritures manuelles du suivi et propose un budget de départ.

Lors du premier démarrage, le mode apprentissage actif permet de continuer sans saisir de valeur de budget. C’est volontaire : vous pouvez d’abord suivre vos écritures, puis laisser l’application proposer des budgets à partir des données réelles. Si le mode apprentissage est désactivé, le premier démarrage exige toujours au moins une valeur de budget.

Le mode apprentissage et la logique normale de suggestion sont séparés :

- Aucun budget dans l’année choisie : le mode apprentissage peut proposer un budget de départ.
- Budget existant dans l’année choisie : le mode apprentissage se termine et la logique normale prend le relais.
- Une suggestion ne modifie jamais les données automatiquement.
- Lors de la reprise, le type de budget doit d’abord être confirmé.

Dans le dialogue des suggestions, un clic droit permet de continuer l’observation, ignorer la suggestion, marquer la catégorie comme irrégulière/réserve ou réinitialiser le statut d’apprentissage. C’est utile pour les frais de santé, franchises, réparations et autres dépenses irrégulières.

Dans le bandeau de l’aperçu, les nouveaux budgets de départ appris utilisent **🆕**. Les vraies alertes de déficit/augmentation gardent **📉**, tandis que les suggestions d’excédent/réduction utilisent **📈**.

## 5.2 Copie annuelle avec mode apprentissage

Lors de la copie d’une année, BudgetManager vérifie aussi les catégories suivies mais jamais budgétées dans l’année source. Elles apparaissent comme budgets de départ possibles pour la nouvelle année et peuvent être reprises ou désélectionnées.
