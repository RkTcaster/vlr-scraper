-- Kills y deaths por jugador-mapa tienen que ser iguales en GRID y en vlr: son el control de que el cruce de
-- jugadores empareja a la persona correcta. warn: al 2026-11-20 difieren 118 filas, casi todas en mapas con
-- rondas faltantes en una fuente (712828 Sunset, 645492 Fracture y Pearl, 754736 Summit) y el mapa roto de
-- Trace Esports (659476 Split). Un salto en la cantidad = revisar el cruce o un mapa nuevo con datos rotos.

{{ config(severity = 'warn') }}

select *
from {{ ref('mart_player_map_source_comparison') }}
where metric in ('kills', 'deaths')
  and not is_equal
