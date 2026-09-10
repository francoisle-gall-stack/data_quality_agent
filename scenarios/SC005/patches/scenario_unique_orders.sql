select order_id, count(*) as cnt
from {{ ref('stg_orders') }}
where order_date = '2026-08-09'
group by 1
having count(*) > 1
