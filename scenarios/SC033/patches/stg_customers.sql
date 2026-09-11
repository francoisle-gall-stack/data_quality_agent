select
    customer_id,
    first_name,
    last_name,
    email,
    country_code,
    cast(signup_date as date) as signup_date
from {{ source('raw', 'raw_customers') }}
