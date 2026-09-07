# Anomalies injectées — ground truth (évaluation uniquement)

Ce document décrit les **10 anomalies volontairement injectées** dans le dataset e-commerce de démonstration (août 2026).  
Ces informations servent à l'évaluation de l'agent et à la compréhension du dataset. **Elles ne sont pas exposées dans le dashboard métier.**

| ID | Type | Période | Table | Colonne | Cause attendue | Impact attendu |
|---|---|---|---|---|---|---|
| ANO-001 | volume_drop | 2026-08-17 | raw_orders | — | Échec partiel d'ingestion | ~70 % de commandes en moins ce jour |
| ANO-002 | freshness_gap | 2026-08-22 → 2026-08-31 | raw_orders | order_timestamp | Source arrêtée après 14h le 22/08 | Aucune commande après le cutoff |
| ANO-003 | null_rate_spike | 2026-08-12 → 2026-08-14 | raw_orders | customer_id | Sync CRM défaillante | ~35 % de NULL customer_id |
| ANO-004 | duplicates | 2026-08-09 | raw_orders | order_id | Replay Kafka sans dédup | ~8 % de doublons order_id |
| ANO-005 | distribution_shift | 2026-08-19 → 2026-08-21 | raw_orders | channel | Bug app mobile (attribution) | Part mobile ~25 % → ~55 % |
| ANO-006 | kpi_drop | 2026-08-24 | fct_daily_sales | total_revenue | Volume + filtre dbt | CA >50 % sous la semaine précédente |
| ANO-007 | dimension_missing | 2026-08-15 → 2026-08-31 | raw_orders | country_code | DE mal tagué / filtré | Allemagne absente des commandes |
| ANO-008 | outliers | 2026-08-11 | raw_order_items | line_amount | Bug moteur de prix | Montants > 50 000 EUR |
| ANO-009 | referential_integrity | 2026-08-18 → 2026-08-20 | raw_order_items | product_id | Catalogue produit désynchronisé | ~5 % product_id orphelins |
| ANO-010 | dbt_transformation_error | 2026-08-20 → 2026-08-31 | int_order_revenue | order_status | Filtre WHERE trop restrictif dans `int_order_revenue.sql` | Statut `confirmed` exclu en aval |

## Détail par anomalie

### ANO-001 — Chute de volume (2026-08-17)
Le générateur réduit le nombre de commandes à ~30 % de la normale pour cette journée.

### ANO-002 — Fraîcheur (à partir du 2026-08-22 14:00)
Aucune nouvelle commande n'est générée après `2026-08-22 14:00:00`.

### ANO-003 — NULL customer_id (12–14 août)
Environ 35 % des commandes ont `customer_id = NULL` sur cette période.

### ANO-004 — Doublons (2026-08-09)
~8 % des commandes du jour sont dupliquées (même `order_id`).

### ANO-005 — Distribution canal (19–21 août)
La probabilité du canal `mobile` est artificiellement augmentée.

### ANO-006 — Chute de CA (2026-08-24)
Impact combiné possible avec d'autres anomalies ; le 24 août est une journée à surveiller dans les marts.

### ANO-007 — Disparition DE (à partir du 15 août)
Les commandes ne sont plus taguées `DE` ; réattribuées à d'autres pays.

### ANO-008 — Outliers montant (2026-08-11)
~2 % des lignes ont un `line_amount` entre 50 000 et 120 000 EUR.

### ANO-009 — Clés étrangères invalides (18–20 août)
~5 % des lignes référencent un `product_id` inexistant (P9000–P9999).

### ANO-010 — Erreur de transformation dbt (à partir du 20 août)
Dans [`dbt/models/intermediate/int_order_revenue.sql`](../dbt/models/intermediate/int_order_revenue.sql), les commandes `confirmed` à partir du 2026-08-20 sont exclues par :

```sql
and (
    o.order_date < cast('2026-08-20' as date)
    or o.order_status != 'confirmed'
)
```

## Fichiers de référence

- Ground truth JSON : `data/raw/ground_truth_anomalies.json`
- Table DuckDB : `main.ground_truth_anomalies` (réservée à l'évaluation, pas au dashboard métier)
