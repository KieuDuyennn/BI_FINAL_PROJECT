{{ config(materialized='table', schema='dds') }}

-- TODO: seed-backed code dimension with surrogate key 0 Unknown row.
select cast(null as integer) as payment_type_key, cast(null as integer) as payment_type_natural_key,
       cast(null as varchar) as payment_type_name
where false
