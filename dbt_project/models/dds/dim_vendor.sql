-- TODO:
-- Surrogate key is a generated integer starting at 1. UNION ALL one Unknown row
-- with surrogate key 0 and natural key NULL. Do not reuse natural code 0 as the
-- surrogate key.
{{ config(materialized='table', schema='dds') }}

-- TODO: seed-backed code dimension with surrogate key 0 Unknown row.
select cast(null as integer) as vendor_key, cast(null as integer) as vendor_natural_key,
       cast(null as varchar) as vendor_name
where false
