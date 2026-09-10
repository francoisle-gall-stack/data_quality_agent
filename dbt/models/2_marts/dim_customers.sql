select
    customer_id,
    first_name,
    last_name,
    email,
    country_code,
    signup_date
from {{ ref('stg_customers') }}
