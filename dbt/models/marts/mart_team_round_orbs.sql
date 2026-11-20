-- Orbes de definitiva por equipo y ronda, con las claves de vlr (team_map_round_id, team_id_vlr, mapa, serie):
-- dos filas por ronda, una por equipo, aunque el equipo no haya agarrado ninguno (orbs = 0).
--
-- Los orbes salen de GRID (vlr no los publica): solo hay filas para rondas del cruce GRID <-> vlr (VCT 2026,
-- internacionales, GC). Una ronda de vlr sin fila = sin dato, nunca un 0 falso. Las rondas que estan en una
-- sola fuente (int_round_crosswalk.match_status missing_in_*) y los mapas con distinta cantidad de rondas en GRID
-- y en vlr quedan afuera.
--
-- El equipo de GRID se traduce a vlr con int_team_crosswalk; el test assert_team_round_orbs_teams_match_vlr
-- controla que sea uno de los dos equipos de la ronda en round_info.
-- Se exporta a csv con nombres de Supabase en exports/table_team_orbs.

with rounds as (

    select r.grid_game_id, r.round_number, r.team_map_round_id
    from {{ ref('int_round_crosswalk') }} as r
    join {{ ref('int_map_crosswalk') }} as m using (grid_game_id)
    where r.grid_round_id is not null
      and r.team_map_round_id is not null
      -- las rondas se emparejan por numero: si las fuentes no tienen la misma cantidad de rondas en el mapa,
      -- la ronda N de GRID puede no ser la N de vlr y los orbes caerian en otra ronda. Se descarta el mapa.
      and m.grid_round_count = m.vlr_round_count

),

orbs_by_team as (

    select p.round_team_id, sum(o.completions) as orbs
    from {{ ref('stg_grid__round_player_objectives') }} as o
    join {{ ref('stg_grid__round_players') }} as p using (round_player_id)
    where o.objective_type = 'captureUltimateOrb'
    group by p.round_team_id

)

select
    r.team_map_round_id || '-' || x.team_id_vlr     as team_round_id,
    r.team_map_round_id,
    v.vlr_series_id,
    v.vlr_map_id,
    v.map_name,
    v.round_number,
    x.team_id_vlr,
    case x.team_id_vlr
        when v.team_a_id_vlr then v.team_a_tag
        when v.team_b_id_vlr then v.team_b_tag
    end                                             as team_tag,
    t.side,                                         -- lado del equipo en la ronda segun GRID
    coalesce(o.orbs, 0)                             as orbs,
    t.grid_game_id,
    t.grid_team_id,
    v.tournament_id
from rounds as r
join {{ ref('stg_grid__round_teams') }} as t
  on t.grid_game_id = r.grid_game_id
 and t.round_number = r.round_number
join {{ ref('int_team_crosswalk') }} as x on x.grid_team_id = t.grid_team_id
join {{ ref('stg_vlr__rounds') }} as v on v.team_map_round_id = r.team_map_round_id
left join orbs_by_team as o on o.round_team_id = t.round_team_id
