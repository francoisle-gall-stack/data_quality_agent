select
    c.customer_id,
    count(distinct r.order_id) as order_count,
    coalesce(sum(r.order_revenue), 0) as lifetime_revenue,
    min(r.order_date) as first_order_date,
    max(r.order_date) as last_order_date
from {{ ref('stg_customers') }} as c
left join {{ ref('int_order_revenue') }} as r
    on c.customer_id = r.customer_id
group by 1
