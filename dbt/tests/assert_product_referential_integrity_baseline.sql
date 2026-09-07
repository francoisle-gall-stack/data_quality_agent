-- dbt singular test: order_items product_id exists in products
select oi.order_item_id
from {{ ref('stg_order_items') }} oi
left join {{ ref('stg_products') }} p on oi.product_id = p.product_id
where p.product_id is null
  and oi.order_id in (
      select order_id from {{ ref('stg_orders') }}
      where order_date between '2026-08-01' and '2026-08-17'
  )
