select
    c.customer_id,
    count(distinct r.order_id) as order_count,
    coalesce(sum(r.order_revenue), 0) as lifetime_revenue
from {{ ref('stg_customers') }} as c
left join {{ ref('int_order_revenue') }} as r
    on c.customer_id = r.customer_key
group by 1
