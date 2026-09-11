select
    first_name,
    last_name,
    email,
    customer_type,
    country_code,
    cast(signup_date as date) as signup_date
from {{ source('raw', 'raw_customers') }}
