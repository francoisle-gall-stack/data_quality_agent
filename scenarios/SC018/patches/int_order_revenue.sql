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
        calculate_order_revenue(oi.line_amount, oi.quantity) as order_revenue,
        sum(oi.quantity) as total_quantity
    from {{ ref('stg_orders') }} as o
    inner join {{ ref('stg_order_items') }} as oi
        on o.order_id = oi.order_id
    where o.order_status in ('completed', 'confirmed', 'shipped')
    group by 1, 2, 3, 4, 5, 6, 7, 8
)

select * from order_lines
