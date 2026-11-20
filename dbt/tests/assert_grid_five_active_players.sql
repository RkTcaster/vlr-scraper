-- Cada equipo, en mapas con stats, tiene que tener 5 jugadores activos en el mapa.
-- severity warn: al 2026-11-19 falla en 2 mapas de Trace Esports (serie 2939172, 4 activos: un jugador que
-- jugo figura como inactive). Es un dato de GRID, no un error del modelo.

{{ config(severity = 'warn') }}

with active as (

    select game_team_id, count(*) as active_players
    from {{ ref('stg_grid__game_players') }}
    where participation_status = 'active'
    group by game_team_id

)

select t.game_team_id, t.grid_series_id, t.team_name, coalesce(a.active_players, 0) as active_players
from {{ ref('stg_grid__game_teams') }} as t
join {{ ref('stg_grid__games') }} as g using (grid_game_id)
left join active as a using (game_team_id)
where g.has_player_stats
  and coalesce(a.active_players, 0) <> 5
