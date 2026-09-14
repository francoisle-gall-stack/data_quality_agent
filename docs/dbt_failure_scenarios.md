# dbt Failure Scenarios

`difficulty_level` is a numeric scenario-complexity indicator. The existing `level` field remains unchanged for compatibility.

- **1 - Simple:** isolated, easy-to-localize failures.
- **2 - Intermediate:** failures requiring upstream/downstream propagation or multiple related checks.
- **3 - Advanced:** multi-step transformation, integration, or data-flow reasoning.
- **4 - Adversarial:** misleading, subtle, or deliberately deceptive failure signals.

## Scenario matrix

| Difficulty | Scenarios | Notes |
| --- | --- | --- |
| 1 | SC003-SC007, SC009 | Simple scenarios |
| 2 | SC008, SC011-SC017 | SC008 is the exception within SC003-SC010 |
| 3 | SC010, SC018-SC030 | SC010 is the exception within SC003-SC010 |
| 4 | SC031-SC036 | Adversarial scenarios |

SC001 and SC002 are legacy-compatible and are intentionally outside the new numeric difficulty assignment.

## Fiche du scénario SC010

| Champ | Valeur |
| --- | --- |
| Nom | Erreur de référence de colonne dans une transformation |
| Difficulté | 3 — Advanced |
| Modèle concerné | `int_order_revenue` |
| Type d'erreur | `schema_change` |
| Cause racine attendue | Référence invalide à `o.order_revenu` |
| Fichier patchable | `dbt/models/1_intermediate/int_order_revenue.sql` |

### Symptôme

Le modèle `int_order_revenue` filtre les commandes avec `o.order_revenu > 0`.
Or `order_revenu` n'est pas une colonne de `stg_orders`. Le chiffre d'affaires
est calculé à partir de `oi.line_amount` et l'alias produit est
`order_revenue`.

La compilation ou l'exécution dbt échoue donc avec une erreur de référence de
colonne (`invalid_column_reference`). Il ne s'agit pas d'un problème de
données manquantes dans la source.

### Correction attendue

La correction doit conserver les statuts valides, notamment `confirmed`, et
remplacer le filtre invalide par une expression cohérente avec l'agrégation,
par exemple :

```sql
having sum(oi.line_amount) > 0
```

Le `having` est nécessaire si le filtre porte sur le montant agrégé. Le filtre
de statut attendu reste :

```sql
where o.order_status in ('completed', 'confirmed', 'shipped')
```

Le patch doit être limité au fichier indiqué dans le manifeste SC010. La
description détaillée de l'anomalie est disponible dans
[`docs/anomalies.md`](anomalies.md).

## Catalogue complet des scénarios

Les fichiers situés dans `scenarios/SCxxx/patches/` représentent l'état
volontairement cassé injecté par chaque scénario. `patch_files` dans le
manifeste liste ces fichiers d'injection ; `expected_fix.file` indique le
fichier que l'agent est censé corriger. Ces deux listes peuvent donc être
différentes lorsque la panne est injectée dans un modèle et doit être corrigée
dans un modèle dépendant.

| ID | Difficulté | Nom | Fichier(s) injecté(s) | Problème observé | Correction attendue |
| --- | ---: | --- | --- | --- | --- |
| SC001 | legacy | Column renamed customer_segment to customer_type | `int_orders.sql` | `int_orders` référence `c.customer_segment`, colonne renommée dans `stg_customers` | Restaurer la référence à `customer_type` ou rétablir un alias compatible |
| SC002 | legacy | Column removed from staging | `stg_customers.sql` | `customer_type` est absent de la projection de staging alors qu'un modèle aval l'attend | Restaurer la colonne attendue ou adapter `dim_customers` |
| SC003 | 1 | Type cast error on customer_type | `int_orders.sql` | Appel à la fonction inexistante `invalid_function_xyz` | Remplacer l'appel par une expression ou une fonction SQL valide |
| SC004 | 1 | not_null test failure on customer_id | `scenario_not_null_customer.sql` | Le test retourne les commandes dont `customer_id` est NULL | Corriger la source ou la logique de traitement des identifiants NULL |
| SC005 | 1 | unique test failure on order_id | `scenario_unique_orders.sql` | Le test détecte les `order_id` dupliqués du 9 août 2026 | Dédupliquer les commandes ou corriger l'ingestion |
| SC006 | 1 | relationships test failure | `scenario_relationships_product.sql` | Des `product_id` de `stg_order_items` n'existent pas dans `stg_products` | Corriger le référentiel produit ou traiter les clés orphelines |
| SC007 | 1 | accepted_values test failure on channel | `scenario_accepted_channel.sql` | Le test détecte un canal hors de `web`, `mobile`, `store` ou NULL | Corriger la valeur source ou la normaliser explicitement |
| SC008 | 2 | Upstream model broken | `stg_orders.sql` | La projection référence `missing_column_xyz` | Restaurer la colonne valide ou supprimer cette référence |
| SC009 | 1 | SQL syntax error | `int_orders.sql` | `SELEC` est un mot-clé SQL invalide | Corriger la syntaxe en `SELECT` |
| SC010 | 3 | Invalid column reference in revenue transformation | `int_order_revenue.sql` | Le filtre référence `o.order_revenu`, colonne inexistante | Utiliser une expression agrégée valide, par exemple `having sum(oi.line_amount) > 0` |
| SC011 | 2 | Customer key removed upstream | `stg_customers.sql` | `customer_id` est supprimé de la projection amont | Restaurer `customer_id` dans le staging |
| SC012 | 2 | Order status renamed upstream | `stg_orders.sql` | `order_status` est remplacé par `status_code` | Conserver l'alias `order_status` attendu en aval |
| SC013 | 2 | Order date cast receives invalid text | `stg_orders.sql` | La valeur littérale `not-a-date` est castée en date | Utiliser la colonne de date source ou un cast tolérant et documenté |
| SC014 | 2 | Revenue arithmetic type mismatch | `int_order_revenue.sql` | `line_amount` est additionné à `quantity` casté en texte | Effectuer une opération numérique avec des types compatibles |
| SC015 | 2 | Product key type changed before relationship test | `stg_products.sql`, `scenario_product_relationship.sql` | `product_id` est casté en texte, ce qui casse la relation avec les clés amont | Harmoniser le type de clé dans les deux relations |
| SC016 | 2 | Customer signup timestamp used as date | `stg_customers.sql`, `scenario_signup_date_type.sql` | `signup_date` est produit comme `TIMESTAMP` alors que le test attend `DATE` | Caster `signup_date` en `DATE` |
| SC017 | 2 | Order line amount removed upstream | `stg_order_items.sql` | `line_amount` est absent de la projection des lignes de commande | Restaurer `line_amount` dans le staging |
| SC018 | 3 | Missing revenue macro | `int_order_revenue.sql` | Appel à la macro/fonction inexistante `calculate_order_revenue` | Utiliser la macro existante ou une expression SQL valide |
| SC019 | 3 | Macro emits invalid SQL | `int_order_revenue.sql`, `order_revenue.sql` | La macro génère une expression terminée par `+` | Corriger la macro pour produire une expression SQL complète |
| SC020 | 3 | Source table reference drift | `stg_products.sql` | La source référence `raw_product` au lieu de la relation déclarée | Utiliser le nom de source déclaré, `raw_products` |
| SC021 | 3 | Alias mismatch in enriched orders | `int_orders.sql` | Le modèle sélectionne `c.customer_segment`, colonne non disponible dans le staging | Référencer `c.customer_type` ou créer explicitement l'alias |
| SC022 | 3 | CTE column escapes its scope | `int_order_revenue.sql` | La requête finale sélectionne `line_amount`, absent de la CTE `order_lines` | Sélectionner une colonne exposée par la CTE ou l'y ajouter |
| SC023 | 3 | Join key renamed upstream | `int_customer_orders.sql` | La jointure utilise `r.customer_key`, clé absente de `int_order_revenue` | Utiliser la clé réellement exposée, `r.customer_id` |
| SC024 | 3 | Fact grain regression | `fct_orders.sql`, `sc024_fact_grain.sql` | `fct_orders` duplique toutes les lignes avec `UNION ALL` | Supprimer la duplication et préserver un grain d'une commande |
| SC025 | 3 | Filter removes every revenue row | `int_order_revenue.sql`, `sc025_revenue_not_empty.sql` | `where 1 = 0` vide entièrement le modèle | Retirer le filtre artificiel et restaurer les conditions métier |
| SC026 | 3 | Required environment setting missing | `fct_daily_sales.sql` | Le modèle exige `SC026_REQUIRED` via `env_var` | Définir la variable ou fournir une valeur par défaut documentée |
| SC027 | 3 | Git branch introduces missing ref | `dim_customers.sql` | Le modèle référence `branch_only_customer_snapshot`, relation inexistante | Pointer vers une relation existante et déclarée |
| SC028 | 3 | Wrong table alias in selected order column | `int_orders.sql` | `c.order_id` est sélectionné alors que `c` désigne les clients | Utiliser `o.order_id` |
| SC029 | 3 | Join references CTE-only relation | `int_order_revenue.sql` | La requête agrège `oi.line_amount` sans joindre `oi` dans la portée finale | Ajouter la jointure nécessaire ou exposer les lignes dans la CTE |
| SC030 | 3 | Environment-controlled relation is absent | `dim_stores.sql` | La source dépend de `SC030_SOURCE`, relation potentiellement absente | Configurer une relation existante et validée |
| SC031 | 4 | Adversarial commented-out join fix | `int_customer_orders.sql` | Un commentaire prétend corriger la jointure, mais le SQL utilise `r.customer_uuid` inexistant | Corriger réellement la clé de jointure ; ignorer les commentaires non exécutables |
| SC032 | 4 | Adversarial safe-looking cast | `int_orders.sql` | Une colonne `nonexistent_column` est sélectionnée malgré des casts valides autour | Supprimer la référence inexistante et utiliser une colonne réelle |
| SC033 | 4 | Adversarial upstream column removal | `stg_customers.sql` | `customer_type` est supprimé, cassant la dépendance de `int_orders` | Restaurer la colonne ou adapter explicitement le modèle aval |
| SC034 | 4 | Adversarial macro substitution | `fct_daily_sales.sql` | Appel à la macro inexistante `normalize_currency` | Utiliser une macro disponible ou une conversion SQL valide |
| SC035 | 4 | Adversarial source spelling change | `stg_products.sql` | La source `raw_product` ne correspond pas à la source déclarée | Corriger le nom de relation source |
| SC036 | 4 | Adversarial inverted data test | `sc036_product_prices.sql` | Le prédicat `unit_price >= 0` retourne les prix valides au lieu des invalides | Inverser le prédicat pour ne retourner que les valeurs en anomalie |

### Vérification des métadonnées

Les manifests et les ground truths ont été comparés aux SQL injectés. Les
corrections nécessaires ont été appliquées à :

- `SC010` : le nom du scénario décrit désormais la référence de colonne
  invalide `o.order_revenu`.
- `SC028` : le nom et la cause racine décrivent désormais la mauvaise
  qualification de `order_id` par l'alias `c`.
