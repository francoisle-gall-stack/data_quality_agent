select
    c.order_id,
    o.customer_id,
    c.customer_type as customer_segment,
    o.order_date,
    o.order_status,
    o.channel
from {{ ref('stg_orders') }} as o
left join {{ ref('stg_customers') }} as c
    on o.customer_id = c.customer_id
