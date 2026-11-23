-- Torneos que GRID cubre (al menos una serie cruzada) con el cruce por debajo de los umbrales: pocas series con par
-- o pocas rondas que coinciden. Si aparece uno: GRID cambio algo (ids, nombres de equipos, horarios), falta un
-- override en seeds/grid_team_overrides.csv, o `grid sync` no corrio despues del scrape. Devuelve los torneos
-- que fallan (un test singular pasa cuando devuelve 0 filas).

{{ config(severity = 'warn') }}

select
    tournament_id,
    vlr_series,
    matched_series,
    pct_series,
    pct_rounds_matching
from {{ ref('mart_tournament_coverage') }}
where is_grid_covered
  and (
        pct_series < {{ var('min_series_coverage_pct') }}
     or pct_rounds_matching < {{ var('min_round_match_pct') }}
  )
