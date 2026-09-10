-- Calcule quotidiennement le taux de customer_id NULL et signale
-- les journées où ce taux dépasse 20 %.
select
    cast(order_date as date) as metric_date,
    avg(case when customer_id is null then 1.0 else 0.0 end) as observed_value,
    0.05 as expected_value
from main.raw_orders
group by 1
having observed_value > 0.20
