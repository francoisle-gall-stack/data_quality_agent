-- Compte les doublons de order_id par jour et signale les journées
-- où leur volume dépasse 3 % du nombre total de commandes.
select
    cast(order_date as date) as metric_date,
    count(*) - count(distinct order_id) as observed_value,
    count(*) * 0.03 as expected_value
from main.raw_orders
group by 1
having observed_value > expected_value
