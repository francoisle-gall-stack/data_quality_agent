-- Compare la part quotidienne des commandes du canal mobile à un seuil
-- attendu afin de détecter un changement anormal de distribution.
with daily as (
    select
        cast(order_date as date) as metric_date,
        avg(case when channel = 'mobile' then 1.0 else 0.0 end) as observed_value
    from main.raw_orders
    group by 1
)
select metric_date, observed_value, 0.35 as expected_value
from daily
where observed_value > 0.45
