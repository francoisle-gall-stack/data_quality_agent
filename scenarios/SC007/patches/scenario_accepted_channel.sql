select channel

from {{ ref('stg_orders') }}

where channel not in ('web', 'mobile', 'store')

   or channel is null

