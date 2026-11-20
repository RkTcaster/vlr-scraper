-- Staging de maps_id: un mapa jugado por fila.

with source as (

    select * from {{ source('vlr', 'maps_id') }}

)

select
    map_id          as vlr_map_id,          -- <series_id>-<Mapa>
    series_id       as vlr_series_id,
    map             as map_name,
    reg_id          as region_id,
    tour_id         as tournament_id
from source
