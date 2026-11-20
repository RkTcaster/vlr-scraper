-- Staging de regions: una region de VCT por fila (americas, emea, china, pacific, global).

with source as (

    select * from {{ source('vlr', 'regions') }}

)

select
    reg_id      as region_id,
    region      as region_name
from source
