select
    product_id
from {{ ref('dim_products') }}
where unit_price >= 0
