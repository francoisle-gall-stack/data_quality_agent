-- Vérifie que les commandes confirmées présentes dans le staging sont bien
-- conservées dans int_order_revenue après la date de début du bug dbt.
with staging as (
    select count(*) as cnt
    from main_staging.stg_orders
    where order_status = 'confirmed'
      and order_date >= cast('2026-08-20' as date)
),
intermediate as (
    select count(*) as cnt
    from main_intermediate.int_order_revenue
    where order_status = 'confirmed'
      and order_date >= cast('2026-08-20' as date)
)
select
    cast('2026-08-20' as date) as metric_date,
    i.cnt as observed_value,
    s.cnt as expected_value
from staging s, intermediate i
where i.cnt < s.cnt * 0.9
