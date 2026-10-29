{{ config(materialized='table', schema='dds') }}

-- Grain: one row per valid taxi trip. TODO: delete + insert each load_month increment.
-- dim_date and dim_time are role-playing for pickup and dropoff.
select
    cast(null as varchar) as trip_id,
    cast(null as integer) as pickup_date_key,
    cast(null as integer) as pickup_time_key,
    cast(null as integer) as dropoff_date_key,
    cast(null as integer) as dropoff_time_key,
    cast(null as integer) as pickup_zone_key,
    cast(null as integer) as dropoff_zone_key,
    cast(null as integer) as vendor_key,
    cast(null as integer) as payment_type_key,
    cast(null as integer) as rate_code_key,
    cast(null as decimal(18,2)) as fare_amount,
    cast(null as decimal(18,2)) as extra,
    cast(null as decimal(18,2)) as mta_tax,
    cast(null as decimal(18,2)) as tip_amount,
    cast(null as decimal(18,2)) as tolls_amount,
    cast(null as decimal(18,2)) as improvement_surcharge,
    cast(null as decimal(18,2)) as congestion_surcharge,
    cast(null as decimal(18,2)) as airport_fee,
    cast(null as decimal(18,2)) as cbd_congestion_fee,
    cast(null as decimal(18,2)) as total_amount,
    cast(null as decimal(18,2)) as trip_distance,
    cast(null as decimal(18,2)) as passenger_count,
    cast(null as decimal(18,2)) as trip_duration_min,
    cast(null as varchar) as etl_run_id
where false
