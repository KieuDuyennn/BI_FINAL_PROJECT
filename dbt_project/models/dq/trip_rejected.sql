{{ config(materialized='table', schema='dq') }}

-- TODO: emit rejected rows only; preserve stage columns plus these firewall columns.
select
    v.*,
    cast(null as varchar) as dq_key,
    cast(null as varchar) as rule_key,
    current_timestamp as dq_timestamp,
    cast(null as varchar) as dq_action,
    cast(null as varchar) as dq_status
from {{ ref('int_trip_validated') }} as v
where false
