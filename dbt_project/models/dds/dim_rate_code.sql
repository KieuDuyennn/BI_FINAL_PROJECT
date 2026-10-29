-- TODO:
-- Surrogate key is a generated integer starting at 1. UNION ALL one Unknown row
-- with surrogate key 0 and natural key NULL. Do not reuse natural code 0 as the
-- surrogate key.
{{ config(materialized='table', schema='dds') }}

-- TODO: seed-backed code dimension with surrogate key 0 Unknown row.
select cast(null as integer) as rate_code_key, cast(null as integer) as rate_code_natural_key,
       cast(null as varchar) as rate_code_name
where false
