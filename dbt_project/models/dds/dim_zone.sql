{{ config(materialized='table', schema='dds') }}

-- TODO: SCD type 1; role-playing pickup and dropoff references use this dimension.
select cast(null as integer) as zone_key, cast(null as integer) as location_id,
       cast(null as varchar) as zone, cast(null as varchar) as borough,
       cast(null as varchar) as service_zone
where false
