-- Las rondas que gano cada equipo, contadas una por una, tienen que dar el score del mapa (rounds_won).
-- Une los dos niveles del JSON (game y segment): si las rondas estuvieran incompletas o duplicadas, no cierra.
-- Los mapas sin stats (has_player_stats = false) pueden traer el score sin rondas: se excluyen.

with counted as (

    select game_team_id, count(*) filter (where won_round) as rounds_won_counted
    from {{ ref('stg_grid__round_teams') }}
    group by game_team_id

)

select t.game_team_id, t.grid_series_id, t.team_name, t.rounds_won, coalesce(c.rounds_won_counted, 0) as counted
from {{ ref('stg_grid__game_teams') }} as t
join {{ ref('stg_grid__games') }} as g using (grid_game_id)
left join counted as c using (game_team_id)
where g.has_player_stats
  and t.rounds_won <> coalesce(c.rounds_won_counted, 0)
