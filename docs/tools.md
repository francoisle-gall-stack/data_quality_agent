# Tools de construction du contexte d'investigation

## Objectif

Le `Context Agent` construit le contexte transmis à l'`Investigation Agent`.
Il ne cherche pas la cause racine et ne propose pas de correction : il collecte
uniquement les preuves nécessaires à partir du diagnostic dbt.

Le comportement est volontairement sélectif. Le diagnostic est lu par le
pipeline puis transmis au `Context Agent`, qui décide quels autres tools sont
utiles pour l'erreur observée.

> Cette documentation concerne les tools du `Context Agent`, et non les outils
> utilisés ultérieurement par le `Correction Agent`.

## Séquence générale

```text
diagnostic.json + politique de collecte
      │
      ▼
sélection déterministe des tools
      │
      ├── besoin de lineage ?      get_dbt_manifest
      ├── erreur SQL/Jinja ?       get_dbt_compiled_sql
      ├── suspicion de régression ? get_dbt_git_history
      ├── besoin du SQL source ?   get_dbt_models
      └── macro impliquée ?        get_dbt_macros
```

Le contexte final contient `sources_used` et `tool_reasons`. Ils indiquent les
tools effectivement appelés et la justification fondée sur le diagnostic ou
sur un résultat déjà collecté.

## Diagnostic et politique de collecte

Le pipeline lit `dbt/target/diagnostic.json` avant de lancer le `Context Agent`.
Le diagnostic complet est transmis dans son prompt, avec une politique de
collecte calculée à partir de la catégorie et du message d'erreur.
`get_dbt_diagnostic` n'est donc pas rappelé par le Context Agent : cela
dupliquerait le même artefact sans apporter de preuve supplémentaire.

### Règle d'appel

Un tool est appelé uniquement s'il est requis par la politique ou si un résultat
précédent révèle une preuve manquante précise. Les tools non justifiés sont
interdits, et chaque appel est enregistré dans `sources_used` avec sa justification
dans `tool_reasons`.

Par exemple, pour une colonne manquante ou renommée :

- `get_dbt_manifest` est requis pour vérifier la lineage ;
- `get_dbt_compiled_sql` est requis pour confirmer le SQL réellement exécuté ;
- `get_dbt_git_history` est requis pour rechercher une régression ;
- `get_dbt_models` ne charge que le modèle en erreur et les upstream pertinents ;
- `get_dbt_macros` n'est pas appelé, sauf signal explicite Jinja/macro.

### Cas où aucun tool n'est appelé

Le pipeline ne lance pas le `Context Agent` pour les erreurs classées
`infrastructure` ou `config_error`, car elles ne sont pas considérées comme
auto-corrigeables. Le pipeline s'arrête avant la collecte et demande une
intervention humaine.

## Tools conditionnels

### `get_dbt_manifest`

Fichier : [`src/dbt_failure_pipeline/tools/manifest_tool.py`](../src/dbt_failure_pipeline/tools/manifest_tool.py)

À appeler lorsque l'analyse nécessite :

- la lineage amont ou aval ;
- les dépendances transitives ;
- les métadonnées du modèle ;
- les relations avec les sources ;
- l'identification des modèles potentiellement responsables ou impactés.

Le manifest est filtré à partir des nœuds en échec. Il ne renvoie donc pas
l'intégralité du projet dbt, mais les nœuds en échec et leur lineage utile.

Il est généralement pertinent pour :

- une colonne manquante ou renommée ;
- une erreur de dépendance ;
- un problème de relation entre modèles ;
- un test de qualité portant sur une clé ou une relation.

Il peut être omis pour une erreur SQL locale, évidente et indépendante de la
lineage.

### `get_dbt_compiled_sql`

Fichier : [`src/dbt_failure_pipeline/tools/compiled_sql_tool.py`](../src/dbt_failure_pipeline/tools/compiled_sql_tool.py)

À appeler lorsque la comparaison entre le SQL source et le SQL généré est
nécessaire, notamment pour :

- une erreur de compilation ;
- une erreur de syntaxe SQL ;
- une erreur d'exécution SQL ;
- une macro Jinja qui produit du SQL invalide ;
- une différence entre le SQL écrit et le SQL effectivement exécuté.

Le tool renvoie le SQL compilé des nœuds sélectionnés par le manifest. Il peut
être omis pour un simple test de données dont le SQL compilé n'apporte pas
d'information supplémentaire.

### `get_dbt_git_history`

Fichier : [`src/dbt_failure_pipeline/tools/git_history_tool.py`](../src/dbt_failure_pipeline/tools/git_history_tool.py)

À appeler lorsque l'historique du dépôt peut aider à départager les causes :

- régression apparue après une modification récente ;
- changement de nom ou de type de colonne ;
- modification récente d'un modèle ou d'une macro ;
- conflit entre le code courant et le comportement attendu.

Le tool collecte, pour les fichiers pertinents :

- le diff non commité ;
- les commits récents ;
- les patchs récents.

Il peut être omis lorsqu'aucun changement récent n'est suspecté et que l'erreur
est déterministe à partir des artefacts dbt.

### `get_dbt_models`

Fichier : [`src/dbt_failure_pipeline/tools/models_tool.py`](../src/dbt_failure_pipeline/tools/models_tool.py)

À appeler lorsque l'agent a besoin du SQL source complet d'un ou plusieurs
modèles. Les noms doivent être ciblés et séparés par des virgules.

Ce tool est utile pour :

- lire le modèle en échec ;
- inspecter un modèle amont ou aval identifié par le manifest ;
- comparer le SQL source avec le SQL compilé ;
- vérifier une référence de colonne, un alias, un `ref()` ou une jointure.

Il ne doit pas être appelé pour charger automatiquement tous les modèles du
projet. Le `Context Agent` doit demander uniquement les fichiers nécessaires.

### `get_dbt_macros`

Fichier : [`src/dbt_failure_pipeline/tools/macros_tool.py`](../src/dbt_failure_pipeline/tools/macros_tool.py)

À appeler uniquement lorsqu'une macro Jinja ou du SQL généré par une macro est
impliqué :

- macro absente ;
- macro appelée avec un mauvais nom ;
- expression SQL invalide produite par une macro ;
- différence entre le template Jinja et le SQL compilé.

Lorsqu'un nom de macro est connu, il doit être fourni afin de limiter la
collecte. Le mode sans nom est interdit par défaut et ne peut être utilisé que
si la politique de collecte l'autorise explicitement.

## Matrice indicative par type d'erreur

| Type d'erreur | Manifest | SQL compilé | Git | Modèles | Macros |
| --- | :---: | :---: | :---: | :---: | :---: |
| Compilation / syntaxe SQL | Selon lineage | Oui | Selon régression | Oui | Si Jinja |
| Colonne manquante / renommée | Oui | Oui | Oui | Oui | Non, sauf indication |
| Dépendance / upstream | Oui | Selon erreur | Oui | Oui | Non |
| Test `not_null`, `unique`, `accepted_values` | Selon impact | Non | Selon régression | Selon transformation | Non |
| Test de relationships | Oui | Non | Selon régression | Selon modèles concernés | Non |
| Cast ou erreur de type | Selon lineage | Oui | Selon régression | Oui | Si macro impliquée |
| Macro absente ou SQL macro invalide | Selon lineage | Oui | Selon modification | Oui | Oui |
| Configuration / infrastructure | Non | Non | Non | Non | Non |

Cette matrice donne une orientation, pas une règle mécanique. La décision
finale appartient au `Context Agent`, qui peut appeler un tool supplémentaire
si le résultat d'un premier tool révèle un besoin non anticipé.

## Contrat de sortie

Le `Context Agent` retourne un objet JSON compatible avec
`InvestigationContext` :

```json
{
  "diagnostic": {},
  "manifest": {},
  "compiled_sql": {},
  "git": {},
  "models": {},
  "macros": {},
  "lineage": {},
  "sources_used": [],
  "tool_reasons": {}
}
```

Les champs correspondant aux tools non appelés restent vides. Les erreurs
renvoyées par un tool sont conservées dans le champ correspondant afin que
l'`Investigation Agent` sache quelle preuve est indisponible.

## Tools du `Correction Agent`

Ils ne font pas partie de la construction du contexte initial :

- `get_dbt_model` et `get_dbt_macro` relisent le fichier à corriger ;
- `propose_patch` construit une proposition de diff sans appliquer directement
  la modification.

Ces tools sont utilisés après l'investigation, lorsque le correctif doit être
préparé et soumis à l'approbation humaine.

## Mode business du Context Agent

Le dashboard React appelle `POST /api/chat` avec une question et un
`dashboard_context` (graphique, filtres et anomalie sélectionnée). Le routeur
déterministe classe la question en `metric_definition`, `chart_source`,
`lineage`, `anomaly_explanation` ou `data_exploration`.

Le profil business collecte uniquement les preuves correspondantes :
`get_dbt_schema_yml` pour les définitions, le manifest et les modèles pour le
lineage, et les tools DuckDB en lecture seule pour les valeurs et l'historique
des métriques. Le Business Q&A Agent reçoit ce bundle et répond avec les
sources utilisées. Aucune correction n'est proposée depuis le chat.

Routes principales :

- `GET /api/filters`
- `GET /api/kpis`
- `GET /api/charts/daily-trends`
- `GET /api/charts/by-country`
- `GET /api/charts/by-channel`
- `GET /api/anomalies/overlays`
- `POST /api/chat`
