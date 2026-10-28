{{ config(materialized='table', schema='dds') }}

-- TODO: seed-backed code dimension with surrogate key 0 Unknown row.
select cast(null as integer) as rate_code_key, cast(null as integer) as rate_code_natural_key,
       cast(null as varchar) as rate_code_name
where false
