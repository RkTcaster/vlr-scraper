-- Cada ronda de mart_team_round_orbs tiene que tener exactamente los dos equipos de esa ronda en vlr
-- (round_info): si el cruce de equipos GRID -> vlr manda un equipo a otro id, la fila queda con team_tag null
-- o la ronda con menos de dos equipos.

select team_map_round_id, count(*) as n_teams, count(team_tag) as n_teams_in_vlr
from {{ ref('mart_team_round_orbs') }}
group by team_map_round_id
having count(*) <> 2 or count(team_tag) <> 2 or count(distinct team_id_vlr) <> 2
