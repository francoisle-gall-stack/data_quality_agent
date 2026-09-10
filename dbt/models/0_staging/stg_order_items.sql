select
    order_item_id,
    order_id,
    product_id,
    quantity,
    unit_price,
    line_amount
from {{ source('raw', 'raw_order_items') }}
