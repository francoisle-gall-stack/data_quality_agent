{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge'
) }}

{% if is_incremental() and execute %}
    {% set duplicate_check %}
        select count(*) as duplicate_order_count
        from (
            select o.order_id
            from {{ ref('int_order_revenue') }} as o
            left join {{ ref('dim_customers') }} as c
                on o.customer_id = c.customer_id
                and o.order_date >= c.valid_from
                and o.order_date <= c.valid_to
            where o.order_date >= cast('{{ var("dbt_demo_recent_start_date", "2026-08-15") }}' as date)
            group by o.order_id
            having count(*) > 1
        ) as duplicate_orders
    {% endset %}
    {% set duplicate_result = run_query(duplicate_check) %}
    {% if duplicate_result and duplicate_result.rows[0][0] > 0 %}
        {{ exceptions.raise_compiler_error(
            "MERGE failed on fct_orders: duplicate key order_id detected in the incremental source ("
            ~ duplicate_result.rows[0][0] ~ " recent orders are multiplied by overlapping dim_customers SCD2 versions)."
        ) }}
    {% endif %}
{% endif %}

with order_source as (
    select *
    from {{ ref('int_order_revenue') }}
    {% if is_incremental() %}
    where order_date >= cast('{{ var("dbt_demo_recent_start_date", "2026-08-15") }}' as date)
    {% endif %}
),

joined_orders as (
    select
        o.order_id,
        o.customer_id,
        o.store_id,
        o.order_timestamp,
        o.order_date,
        o.order_status,
        o.channel,
        o.country_code,
        o.order_revenue,
        o.total_quantity,
        row_number() over (
            partition by o.order_id
            order by c.valid_from desc
        ) as customer_version_rank
    from order_source as o
    left join {{ ref('dim_customers') }} as c
        on o.customer_id = c.customer_id
        and o.order_date >= c.valid_from
        and o.order_date <= c.valid_to
)

select
    order_id,
    customer_id,
    store_id,
    order_timestamp,
    order_date,
    order_status,
    channel,
    country_code,
    order_revenue,
    total_quantity
from joined_orders
{% if not is_incremental() %}
where customer_version_rank = 1
{% endif %}
