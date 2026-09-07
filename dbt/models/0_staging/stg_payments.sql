select
    payment_id,
    order_id,
    payment_method,
    payment_status,
    cast(paid_at as timestamp) as paid_at
from {{ source('raw', 'raw_payments') }}
