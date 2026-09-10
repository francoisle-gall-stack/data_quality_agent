select
    store_id,
    store_name,
    city,
    country_code,
    channel as store_channel
from {{ source('raw', 'raw_stores') }}
