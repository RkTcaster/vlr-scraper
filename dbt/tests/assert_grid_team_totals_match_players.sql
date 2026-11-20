-- Test singular: un SELECT que devuelve las filas que fallan (0 filas = pasa).
--
-- Los contadores del equipo en un mapa tienen que ser la suma de sus jugadores (verificado a mano en 3003317).
-- Valida dos cosas a la vez: que GRID es consistente y que los unnest del staging no duplican ni pierden
-- jugadores. Los mapas sin datos de jugadores (has_player_stats = false) dan 0 = 0 y pasan.

with players as (

    select
        game_team_id,
        sum(kills)         as kills,
        sum(deaths)        as deaths,
        sum(damage_dealt)  as damage_dealt,
        sum(headshots)     as headshots
    from {{ ref('stg_grid__game_players') }}
    group by game_team_id

)

select
    t.game_team_id,
    t.kills,        p.kills        as players_kills,
    t.deaths,       p.deaths       as players_deaths,
    t.damage_dealt, p.damage_dealt as players_damage_dealt,
    t.headshots,    p.headshots    as players_headshots
from {{ ref('stg_grid__game_teams') }} as t
left join players as p using (game_team_id)
where t.kills        is distinct from coalesce(p.kills, 0)
   or t.deaths       is distinct from coalesce(p.deaths, 0)
   or t.damage_dealt is distinct from coalesce(p.damage_dealt, 0)
   or t.headshots    is distinct from coalesce(p.headshots, 0)
