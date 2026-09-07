select
    store_id,
    store_name,
    city,
    country_code,
    store_channel
from {{ ref('stg_stores') }}
