-- Rondas cruzadas que coinciden (ganador y forma de ganar), sumando todos los torneos. Al 2026-11-23: 99.57 %.
-- Una caida general (no de un torneo) apunta a un cambio en la API de GRID o en el staging. Devuelve una fila si
-- esta debajo del umbral.

{{ config(severity = 'warn') }}

select
    sum(rounds_compared)                                            as rounds_compared,
    round(100.0 * sum(rounds_matching) / sum(rounds_compared), 2)   as pct_rounds_matching
from {{ ref('mart_tournament_coverage') }}
having 100.0 * sum(rounds_matching) / sum(rounds_compared) < {{ var('min_total_round_match_pct') }}
