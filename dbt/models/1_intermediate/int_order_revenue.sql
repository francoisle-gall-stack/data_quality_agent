with order_lines as (
    select
        o.order_id,
        o.customer_id,
        o.store_id,
        o.order_timestamp,
        o.order_date,
        o.order_status,
        o.channel,
        o.country_code,
        sum(oi.line_amount) as order_revenue,
        sum(oi.quantity) as total_quantity
    from {{ ref('stg_orders') }} as o
    inner join {{ ref('stg_order_items') }} as oi
        on o.order_id = oi.order_id
    where
        o.order_status in ('completed', 'confirmed', 'shipped')
        -- INTENTIONAL BUG (ANO-010): from 2026-08-20, 'confirmed' is excluded
        and (
            o.order_date < cast('{{ var("dbt_transformation_bug_start_date") }}' as date)
            or o.order_status != 'confirmed'
        )
    group by 1, 2, 3, 4, 5, 6, 7, 8
)

select * from order_lines
