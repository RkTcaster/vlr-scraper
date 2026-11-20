-- Orbes de definitiva capturados por ronda, entre los 10 jugadores: como mucho 2, salvo Fracture que tiene 4
-- (al 2026-11-19: 184 rondas con 3 y 52 con 4, todas en fracture; ningun otro mapa pasa de 2).
-- Si aparece un mapa nuevo con mas orbes, este test lo marca y se agrega aca.

with orbs as (

    select p.grid_round_id, p.grid_game_id, sum(o.completions) as orbs
    from {{ ref('stg_grid__round_player_objectives') }} as o
    join {{ ref('stg_grid__round_players') }} as p using (round_player_id)
    where o.objective_type = 'captureUltimateOrb'
    group by p.grid_round_id, p.grid_game_id

)

select orbs.grid_round_id, g.map_name, orbs.orbs
from orbs
join {{ ref('stg_grid__games') }} as g using (grid_game_id)
where orbs.orbs > case when g.map_name = 'fracture' then 4 else 2 end
