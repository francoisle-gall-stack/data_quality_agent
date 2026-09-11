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
    group by 1, 2, 3, 4, 5, 6, 7, 8
)
select
    order_id,
    customer_id,
    store_id,
    order_date,
    order_status,
    channel,
    line_amount,
    order_revenue,
    total_quantity
from order_lines
