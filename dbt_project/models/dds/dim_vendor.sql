{{ config(materialized='table', schema='dds') }}

-- TODO: seed-backed code dimension with surrogate key 0 Unknown row.
select cast(null as integer) as vendor_key, cast(null as integer) as vendor_natural_key,
       cast(null as varchar) as vendor_name
where false
