select
    order_date,
    count(distinct order_id) as order_count,
    count(distinct customer_id) as active_customers,
    {{ normalize_currency('sum(order_revenue)', 'EUR') }} as total_revenue,
    avg(order_revenue) as avg_order_value
from {{ ref('fct_orders') }}
group by 1
