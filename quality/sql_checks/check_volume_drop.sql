-- Compare le nombre quotidien de commandes à la moyenne mobile des
-- sept jours précédents et détecte une baisse supérieure à 40 %.
with daily as (
    select
        cast(order_date as date) as metric_date,
        count(*) as observed_value
    from main.raw_orders
    group by 1
),
with_avg as (
    select
        metric_date,
        observed_value,
        avg(observed_value) over (
            order by metric_date rows between 7 preceding and 1 preceding
        ) as expected_value
    from daily
)
select metric_date, observed_value, expected_value
from with_avg
where observed_value < expected_value * 0.6
  and expected_value is not null
