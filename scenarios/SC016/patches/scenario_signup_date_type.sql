select signup_date
from {{ ref('stg_customers') }}
where typeof(signup_date) <> 'DATE'
