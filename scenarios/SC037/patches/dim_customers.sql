with base_customers as (
    select
        customer_id,
        first_name,
        last_name,
        email,
        customer_type,
        country_code,
        signup_date
    from {{ ref('stg_customers') }}
),

stable_versions as (
    select
        customer_id,
        first_name,
        last_name,
        email,
        customer_type,
        country_code,
        signup_date as valid_from,
        cast('9999-12-31' as date) as valid_to,
        true as is_current
    from base_customers
),

overlapping_recent_versions as (
    select
        customer_id,
        first_name,
        last_name,
        email,
        customer_type,
        country_code,
        signup_date + interval '180 days' as valid_from,
        cast('9999-12-31' as date) as valid_to,
        true as is_current
    from base_customers
    where customer_id in (
        select distinct customer_id
        from {{ ref('stg_orders') }}
        where order_date >= cast('{{ var("dbt_demo_recent_start_date", "2026-08-15") }}' as date)
    )
)

select * from stable_versions
union all
select * from overlapping_recent_versions
