-- Las rondas que GRID cuenta para un jugador tienen que ser las rondas del mapa en vlr. Si no coinciden, el
-- mapa tiene rondas de mas o de menos en una fuente y las tasas por ronda (survival_rate, adr_grid) quedan
-- sesgadas. warn: hay mapas conocidos con rondas corridas (ver assert_grid_vlr_rounds_agree).

{{ config(severity = 'warn') }}

select f.map_player_id, f.rounds_played, m.vlr_round_count
from {{ ref('fct_player_map') }} as f
join {{ ref('int_map_crosswalk') }} as m using (vlr_map_id)
where f.rounds_played <> m.vlr_round_count
