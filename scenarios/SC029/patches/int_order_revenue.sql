with orders_only as (
    select
        o.order_id,
        o.customer_id,
        o.order_date,
        o.order_status
    from {{ ref('stg_orders') }} as o
)
select
    order_id,
    customer_id,
    order_date,
    order_status,
    sum(oi.line_amount) as order_revenue
from orders_only
group by 1, 2, 3, 4
