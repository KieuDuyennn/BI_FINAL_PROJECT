-- TODO:
-- Surrogate key is a generated integer starting at 1. UNION ALL one Unknown row
-- with surrogate key 0 and natural key NULL. Do not reuse natural code 0 as the
-- surrogate key.
{{ config(materialized='table', schema='dds') }}

-- TODO: SCD type 1; role-playing pickup and dropoff references use this dimension.
select cast(null as integer) as zone_key, cast(null as integer) as location_id,
       cast(null as varchar) as zone, cast(null as varchar) as borough,
       cast(null as varchar) as service_zone
where false
