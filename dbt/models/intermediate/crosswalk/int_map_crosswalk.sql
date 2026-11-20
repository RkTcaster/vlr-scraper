-- Mapa de GRID <-> mapa de vlr, dentro de una serie emparejada. Se empareja por nombre del mapa (GRID en
-- minuscula, vlr con mayuscula) y se guarda si tambien coincide el orden: si no coincide, uno de los dos tiene un
-- mapa de mas o de menos (un mapa no jugado, un remake).

with series as (

    select grid_series_id, vlr_series_id from {{ ref('int_series_crosswalk') }}

),

grid_maps as (

    select grid_game_id, grid_series_id, map_number, map_name, round_count, has_player_stats
    from {{ ref('stg_grid__games') }}

),

vlr_maps as (

    select
        vlr_map_id,
        vlr_series_id,
        any_value(map_number)   as map_number,
        any_value(map_name)     as map_name,
        count(*)                as round_count
    from {{ ref('stg_vlr__rounds') }}
    group by vlr_map_id, vlr_series_id

),

pairs as (

    select
        g.grid_game_id,
        v.vlr_map_id,
        s.grid_series_id,
        s.vlr_series_id,
        g.map_name                          as map_name,
        g.map_number                        as grid_map_number,
        v.map_number                        as vlr_map_number,
        g.map_number = v.map_number         as map_number_matches,
        g.round_count                       as grid_round_count,
        v.round_count                       as vlr_round_count,
        g.has_player_stats
    from series as s
    join grid_maps as g using (grid_series_id)
    join vlr_maps as v
      on v.vlr_series_id = s.vlr_series_id
     and lower(v.map_name) = g.map_name

),

-- El mismo mapa dos veces en una serie: GRID duplico un game en 2914125 (bind 2 y 3, misma duracion y rondas).
-- Gana el que tambien coincide en orden; el otro queda sin par. Mismo criterio desde el lado de GRID.
ranked as (

    select
        *,
        row_number() over (partition by vlr_map_id order by map_number_matches desc, grid_map_number) as rank_vlr,
        row_number() over (partition by grid_game_id order by map_number_matches desc, vlr_map_number) as rank_grid
    from pairs

)

select * exclude (rank_vlr, rank_grid)
from ranked
where rank_vlr = 1
  and rank_grid = 1
