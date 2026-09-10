-- dbt singular test: customer_id not null for recent orders (threshold)
select order_id
from {{ ref('stg_orders') }}
where customer_id is null
  and order_date between '2026-08-01' and '2026-08-11'
