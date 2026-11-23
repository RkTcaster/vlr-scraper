-- Serie de GRID <-> serie de vlr. Dos series son la misma si sus dos equipos se corresponden (int_team_crosswalk)
-- y se jugaron a menos de var('grid_vlr_max_hours') horas. Si hay mas de un candidato (un mismo cruce de equipos
-- dos veces en pocas horas) gana el mas cercano en el tiempo, de los dos lados: el resultado es 1 a 1.
--
-- Dos decisiones del desempate (al 2026-11-23 ninguna se usa: 598 candidatos, 2 series de vlr con mas de uno y
-- ningun empate de hours_diff):
--   - A igual distancia gana el id mas bajo, comparado como texto. Es deterministico, no tiene significado: solo
--     evita que el resultado cambie entre corridas.
--   - No reasigna: un par entra si es el primero de los DOS lados. Si el mejor candidato de una serie ya es el
--     mejor de otra, esa serie queda sin par aunque tenga un segundo candidato libre (no es un emparejamiento
--     optimo). Se veria como una serie menos en mart_tournament_coverage.

with grid_series as (

    select
        s.grid_series_id,
        s.scheduled_at,
        s.event_name                                    as grid_event_name,
        list_sort(list(x.team_id_vlr))                  as team_key,
        count(x.team_id_vlr)                            as mapped_teams
    from {{ ref('stg_grid__series') }} as s
    join {{ ref('stg_grid__series_teams') }} as st using (grid_series_id)
    left join {{ ref('int_team_crosswalk') }} as x using (grid_team_id)
    group by all
    having count(x.team_id_vlr) = 2             -- los dos equipos tienen par en vlr

),

vlr_series as (

    select
        vlr_series_id,
        scheduled_at,
        tournament_id,
        list_sort([team_a_id_vlr, team_b_id_vlr])       as team_key,
        map_count
    from {{ ref('int_vlr__series') }}

),

pairs as (

    select
        g.grid_series_id,
        v.vlr_series_id,
        g.grid_event_name,
        v.tournament_id,
        round((epoch(g.scheduled_at) - epoch(v.scheduled_at)) / 3600, 2) as hours_diff,
        v.map_count                                     as vlr_map_count
    from grid_series as g
    join vlr_series as v
      on g.team_key = v.team_key
     and abs(epoch(g.scheduled_at) - epoch(v.scheduled_at)) <= {{ var('grid_vlr_max_hours') }} * 3600

),

ranked as (

    select
        *,
        row_number() over (partition by grid_series_id order by abs(hours_diff), vlr_series_id) as rank_grid,
        row_number() over (partition by vlr_series_id order by abs(hours_diff), grid_series_id) as rank_vlr
    from pairs

)

select
    r.grid_series_id,
    r.vlr_series_id,
    r.grid_event_name,
    r.tournament_id,
    r.hours_diff,               -- GRID - vlr, ya en UTC: deberia estar cerca de 0
    st.map_count                as grid_map_count,
    r.vlr_map_count

from ranked as r
left join {{ ref('stg_grid__series_states') }} as st using (grid_series_id)
where r.rank_grid = 1
  and r.rank_vlr = 1
