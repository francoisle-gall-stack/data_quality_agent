select

    o.order_id,

    o.customer_id,

    o.order_date,

    o.order_status,

    o.channel

from {{ ref('stg_orders') }} as o
