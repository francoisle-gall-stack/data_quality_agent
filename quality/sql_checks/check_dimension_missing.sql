-- Recherche les journées où l'Allemagne (DE) est absente des commandes
-- alors que plusieurs autres pays sont bien représentés.
with daily_countries as (
    select
        cast(order_date as date) as metric_date,
        count(distinct country_code) as observed_value,
        sum(case when country_code = 'DE' then 1 else 0 end) as de_count
    from main.raw_orders
    group by 1
)
select metric_date, de_count as observed_value, 1.0 as expected_value
from daily_countries
where de_count = 0 and observed_value >= 3
