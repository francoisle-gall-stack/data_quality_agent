select 1
where (select count(*) from {{ ref('int_order_revenue') }}) = 0
