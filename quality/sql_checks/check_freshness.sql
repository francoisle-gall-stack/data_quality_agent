-- Contrôle la fraîcheur des données en comparant le dernier timestamp
-- de commande à la date minimale attendue de disponibilité.
select
    cast(max(order_timestamp) as date) as metric_date,
    epoch(max(order_timestamp)) as observed_value,
    epoch(cast('2026-08-30' as timestamp)) as expected_value
from main.raw_orders
having max(order_timestamp) < cast('2026-08-30' as timestamp)
