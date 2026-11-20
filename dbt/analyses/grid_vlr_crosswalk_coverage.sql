-- Cobertura del cruce GRID <-> vlr por torneo de vlr: cuantas series se emparejaron y cuantas rondas coinciden.
-- Correr: dbt show -s grid_vlr_crosswalk_coverage --limit 100
--
-- Al 2026-11-19: todas las ligas VCT 2026, Masters y Champions al 100% salvo China Kickoff (FPX - TYLOO, 598924,
-- no esta en GRID); VCT Pacific Stage 1 no esta en GRID; Esports World Cup no es de Riot; los qualifiers 2027
-- no estan en GRID.

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
    sum(r.rounds_compared)                                          as rounds_compared,
    round(100.0 * sum(r.rounds_matching) / nullif(sum(r.rounds_compared), 0), 2) as pct_rounds_matching

from {{ ref('int_vlr__series') }} as v
left join {{ ref('int_series_crosswalk') }} as x using (vlr_series_id)
left join rounds as r using (vlr_series_id)
group by v.tournament_id
order by matched_series desc, v.tournament_id
