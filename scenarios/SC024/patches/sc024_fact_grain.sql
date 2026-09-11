select
    order_id
from {{ ref('fct_orders') }}
group by order_id
having count(*) > 1
