select

    o.order_id,

    o.customer_id,

    o.order_date,

    o.order_status,

    o.channel,

    invalid_function_xyz(o.order_id) as broken_col

from {{ ref('stg_orders') }} as o

