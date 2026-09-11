select
    order_id,
    customer_id,
    store_id,
    order_timestamp,
    order_date,
    order_status,
    channel,
    country_code,
    order_revenue,
    total_quantity
from {{ ref('int_order_revenue') }}
union all
select
    order_id,
    customer_id,
    store_id,
    order_timestamp,
    order_date,
    order_status,
    channel,
    country_code,
    order_revenue,
    total_quantity
from {{ ref('int_order_revenue') }}
