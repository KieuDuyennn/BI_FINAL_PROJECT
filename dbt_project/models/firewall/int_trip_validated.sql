{{ config(materialized='view', schema='dq') }}

-- TODO: select every stage column and add one flag column per active dq_rule.
select
    s.*,
    cast(null as varchar) as dq_flags
from {{ source('stage', 'trip') }} as s
