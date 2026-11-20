-- Staging de player_performance: pestana performance de vlr, una fila por jugador y mapa.
--   multikills_Nk  rondas con N kills (2K..5K)
--   clutches_1vN   clutches ganados 1 contra N
--   econ_rating    rating de economia de vlr (dano por cada 1000 creditos gastados)
-- Bo1/Bo2 de algunos torneos no tienen esta pestana en vlr (China Stage 2): faltan filas, no son ceros.

with source as (

    select * from {{ source('vlr', 'player_performance') }}

)

select
    map_id || '-' || player_id_vlr      as map_player_id,       -- PK en Supabase: (map_id, player_id_vlr)
    map_id                              as vlr_map_id,
    series_id                           as vlr_series_id,
    player_id_vlr,
    team_id_vlr,
    player                              as player_name,
    team                                as team_tag,
    cast("2K" as integer)               as multikills_2k,
    cast("3K" as integer)               as multikills_3k,
    cast("4K" as integer)               as multikills_4k,
    cast("5K" as integer)               as multikills_5k,
    cast("1v1" as integer)              as clutches_1v1,
    cast("1v2" as integer)              as clutches_1v2,
    cast("1v3" as integer)              as clutches_1v3,
    cast("1v4" as integer)              as clutches_1v4,
    cast("1v5" as integer)              as clutches_1v5,
    cast(ECON as integer)               as econ_rating,
    cast(PL as integer)                 as plants,
    cast(DE as integer)                 as defuses,
    map                                 as map_name,
    {{ vlr_timestamp_utc('date') }}     as scheduled_at,
    source_url,
    event                               as event_name,
    reg_id                              as region_id,
    tour_id                             as tournament_id
from source
