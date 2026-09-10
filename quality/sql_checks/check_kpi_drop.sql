-- Compare le chiffre d'affaires quotidien au même jour de la semaine
-- précédente et signale une baisse supérieure à 40 %.
with daily as (
    select order_date as metric_date, total_revenue as observed_value
    from main_marts.fct_daily_sales
),
with_lag as (
    select
        metric_date,
        observed_value,
        lag(observed_value, 7) over (order by metric_date) as expected_value
    from daily
)
select * from with_lag
where expected_value is not null
  and observed_value < expected_value * 0.6
