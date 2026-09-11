select
    store_id,
    store_name,
    country_code
from {{ source('raw', env_var('SC030_SOURCE')) }}
