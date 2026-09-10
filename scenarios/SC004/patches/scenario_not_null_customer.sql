select order_id
from {{ ref('stg_orders') }}
where customer_id is null
