-- El agregado no pierde ni duplica mapas: por torneo, la suma de maps / kills / rondas de GRID del mart tiene
-- que ser igual a la de fct_player_map. Falla si un join del mart (agentes, torneos) multiplica o descarta filas.

with mart as (

    select tournament_id, sum(maps) as maps, sum(kills) as kills, sum(grid_rounds) as grid_rounds
    from {{ ref('mart_player_tournament') }}
    group by tournament_id

),

fct as (

    select tournament_id, count(*) as maps, sum(kills) as kills, sum(rounds_played) as grid_rounds
    from {{ ref('fct_player_map') }}
    group by tournament_id

)

select *
from fct
full join mart using (tournament_id)
where fct.maps is distinct from mart.maps
   or fct.kills is distinct from mart.kills
   or fct.grid_rounds is distinct from mart.grid_rounds
