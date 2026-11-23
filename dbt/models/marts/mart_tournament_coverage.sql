-- Cobertura del cruce GRID <-> vlr por torneo de vlr: cuantas series tienen par en GRID y cuantas rondas
-- coinciden (ganador y forma de ganar). Era analyses/grid_vlr_crosswalk_coverage.sql; como mart se construye en
-- cada build, aparece en el linaje y lo vigilan dos tests:
--   assert_coverage_per_tournament  torneo que GRID cubre con menos de var('min_series_coverage_pct') % de series
--                                   cruzadas o var('min_round_match_pct') % de rondas que coinciden
--   assert_coverage_total           rondas que coinciden en total, debajo de var('min_total_round_match_pct') %
--
-- is_grid_covered = GRID tiene al menos una serie del torneo. Los que no (al 2026-11-23: qualifiers 2027, VCT Pacific
-- Stage 1, Esports World Cup) quedan en 0 % y los tests no los miran: no es un cruce roto, GRID no los tiene.
-- Un torneo en curso puede bajar si `grid sync` no corrio despues del scrape de vlr: por eso los tests son warn.

with rounds as (

    select
        vlr_series_id,
        count(*)                                        as rounds_compared,
        count(*) filter (where match_status = 'match')  as rounds_matching
    from {{ ref('int_round_crosswalk') }}
    group by vlr_series_id

)

select
    v.tournament_id,
    count(*)                                                        as vlr_series,
    count(x.grid_series_id)                                         as matched_series,
    round(100.0 * count(x.grid_series_id) / count(*), 1)            as pct_series,
    count(x.grid_series_id) > 0                                     as is_grid_covered,
    coalesce(sum(r.rounds_compared), 0)                             as rounds_compared,
    coalesce(sum(r.rounds_matching), 0)                             as rounds_matching,
    round(100.0 * sum(r.rounds_matching) / nullif(sum(r.rounds_compared), 0), 2) as pct_rounds_matching

from {{ ref('int_vlr__series') }} as v
left join {{ ref('int_series_crosswalk') }} as x using (vlr_series_id)
left join rounds as r using (vlr_series_id)
group by v.tournament_id
