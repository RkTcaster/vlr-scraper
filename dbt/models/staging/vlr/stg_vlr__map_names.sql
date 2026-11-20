-- Staging de maps_name_ids: catalogo de los mapas del juego (lista a mano en vlr_pipeline/lookups.py).
-- map_name_id es 'map_N'; no confundir con vlr_map_id (un mapa jugado en una serie).

with source as (

    select * from {{ source('vlr', 'maps_name_ids') }}

)

select
    map_id          as map_name_id,
    map             as map_name,
    image_path
from source
