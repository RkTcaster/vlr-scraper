-- GRID y vlr tienen que decir lo mismo de cada ronda emparejada: quien gano y como (winType <-> winCon).
-- severity warn: al 2026-11-19 coinciden ~99.6% de las rondas. Las diferencias se concentran en pocos mapas
-- con rondas corridas o faltantes en una fuente (2882491 corrode, 2917807 fracture) y en win_con
-- bombDefused / elim (rondas con defuse despues de eliminar a los atacantes: cada fuente la clasifica distinto).
-- El detalle esta en int_round_discrepancies. El test avisa si aparecen diferencias nuevas en volumen.

{{ config(severity = 'warn') }}

select *
from {{ ref('int_round_discrepancies') }}
