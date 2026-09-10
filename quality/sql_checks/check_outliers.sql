-- Recherche, pour chaque jour, le montant maximal d'une ligne de commande
-- et signale les valeurs supérieures à 50 000.
select
    cast(o.order_date as date) as metric_date,
    max(oi.line_amount) as observed_value,
    50000.0 as expected_value
from main.raw_order_items oi
join main.raw_orders o on oi.order_id = o.order_id
group by 1
having max(oi.line_amount) > 50000
