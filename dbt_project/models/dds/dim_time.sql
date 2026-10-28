{{ config(materialized='table', schema='dds') }}

-- TODO: add Unknown row key 0 and hour/time_of_day hierarchy.
select cast(null as integer) as time_key, cast(null as integer) as hour,
       cast(null as varchar) as time_of_day, cast(null as integer) as hour_natural_key
where false
