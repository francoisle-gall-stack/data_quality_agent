-- Vérifie l'intégrité référentielle entre les lignes de commande et le
-- catalogue produit, puis signale plus de 2 % d'identifiants orphelins.
with daily as (
    select
        cast(o.order_date as date) as metric_date,
        avg(case when p.product_id is null then 1.0 else 0.0 end) as observed_value
    from main.raw_order_items oi
    join main.raw_orders o on oi.order_id = o.order_id
    left join main.raw_products p on oi.product_id = p.product_id
    group by 1
)
select metric_date, observed_value, 0.02 as expected_value
from daily
where observed_value > 0.02
