select
    order_id,
    customer_id,
    store_id,
    cast(order_timestamp as timestamp) as order_timestamp,
    cast('not-a-date' as date) as order_date,
    status as order_status,
    channel,
    country_code
from {{ source('raw', 'raw_orders') }}
