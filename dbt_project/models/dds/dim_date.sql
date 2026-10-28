{{ config(materialized='table', schema='dds') }}

-- TODO: integer surrogate key, alternate natural date key, and Unknown row key 0.
select
    cast(null as integer) as date_key,
    cast(null as date) as date_natural_key,
    cast(null as varchar) as month,
    cast(null as integer) as quarter,
    cast(null as integer) as year,
    cast(null as integer) as day_of_week,
    cast(null as boolean) as is_weekend
where false
