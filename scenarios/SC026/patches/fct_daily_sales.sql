select
    order_date,
    count(distinct order_id) as order_count,
    count(distinct customer_id) as active_customers,
    sum(order_revenue) as total_revenue,
    avg(order_revenue) as avg_order_value,
    '{{ env_var("SC026_REQUIRED") }}' as execution_environment
from {{ ref('fct_orders') }}
group by 1
