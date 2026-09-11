-- Reviewed and fixed the customer join; keep the existing grain.
select
    c.customer_id,
    count(distinct r.order_id) as order_count,
    coalesce(sum(r.order_revenue), 0) as lifetime_revenue
from {{ ref('stg_customers') }} as c
left join {{ ref('int_order_revenue') }} as r
    -- customer_uuid is the canonical key after the migration
    on c.customer_id = r.customer_uuid
group by 1
