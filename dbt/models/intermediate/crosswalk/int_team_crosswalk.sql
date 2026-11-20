-- Equipo de GRID -> equipo de vlr (team_id_vlr). Una fila por grid_team_id emparejado.
--
-- No hay id compartido entre las fuentes, asi que se aprende de las series:
--   1. candidatos: un equipo de una serie de GRID y uno de una serie de vlr jugadas a menos de
--      var('grid_vlr_max_hours') horas, con el mismo nombre o el mismo tag normalizados (macro normalize_team_name).
--   2. por cada equipo de GRID gana el equipo de vlr con el que coincide en mas series (n_series).
--   3. el seed grid_team_overrides pisa todo: ahi van a mano los que la regla no resuelve o resuelve mal.
-- Un tag puede coincidir por casualidad (dos equipos "TH" el mismo dia): n_series y n_candidates lo dejan ver,
-- y el cruce de series exige que los DOS equipos coincidan, lo que descarta esas casualidades.

with grid_teams as (

    select
        st.grid_series_id,
        st.grid_team_id,
        st.team_name,
        ct.team_tag,
        s.scheduled_at,
        {{ normalize_team_name('st.team_name') }}  as name_key,
        {{ normalize_team_name('ct.team_tag') }}   as tag_key
    from {{ ref('stg_grid__series_teams') }} as st
    join {{ ref('stg_grid__series') }} as s using (grid_series_id)
    left join {{ ref('stg_grid__catalog_teams') }} as ct using (series_team_id)

),

-- int_vlr__series tiene los dos equipos en columnas (a / b): se pasan a filas con unnest de una lista de structs
vlr_series_teams as (

    select
        vlr_series_id,
        scheduled_at,
        unnest([
            {'team_id_vlr': team_a_id_vlr, 'tag': team_a_tag},
            {'team_id_vlr': team_b_id_vlr, 'tag': team_b_tag}
        ]) as team
    from {{ ref('int_vlr__series') }}

),

vlr_teams as (

    select
        v.vlr_series_id,
        v.scheduled_at,
        v.team.team_id_vlr                          as team_id_vlr,
        t.team_name,
        {{ normalize_team_name('t.team_name') }}    as name_key,
        -- el tag de cuando se jugo (round_info), no el actual: vlr renombra tags (DRX -> KRX)
        {{ normalize_team_name('v.team.tag') }}     as tag_key
    from vlr_series_teams as v
    left join {{ ref('stg_vlr__teams') }} as t on t.team_id_vlr = v.team.team_id_vlr

),

candidates as (

    select
        g.grid_team_id,
        v.team_id_vlr,
        g.grid_series_id,
        g.name_key = v.name_key     as name_match,
        g.tag_key = v.tag_key       as tag_match
    from grid_teams as g
    join vlr_teams as v
      on abs(epoch(g.scheduled_at) - epoch(v.scheduled_at)) <= {{ var('grid_vlr_max_hours') }} * 3600
     and (g.name_key = v.name_key or g.tag_key = v.tag_key)

),

scored as (

    select
        grid_team_id,
        team_id_vlr,
        count(distinct grid_series_id)  as n_series,
        bool_or(name_match)             as any_name_match
    from candidates
    group by grid_team_id, team_id_vlr

),

ranked as (

    select
        *,
        row_number() over (
            partition by grid_team_id
            order by n_series desc, any_name_match desc, team_id_vlr
        )                                               as rank_in_team,
        count(*) over (partition by grid_team_id)       as n_candidates
    from scored

),

overrides as (

    select
        cast(grid_team_id as varchar)   as grid_team_id,
        cast(team_id_vlr as varchar)    as team_id_vlr,
        note
    from {{ ref('grid_team_overrides') }}

),

matched as (

    select grid_team_id, team_id_vlr, 'override' as match_method, null as n_series, null as n_candidates, note
    from overrides

    union all

    select grid_team_id, team_id_vlr,
           case when any_name_match then 'name' else 'tag' end, n_series, n_candidates, null
    from ranked
    where rank_in_team = 1
      and grid_team_id not in (select grid_team_id from overrides)

),

-- nombres para poder revisar el cruce a ojo (el de GRID: el de su serie mas reciente)
grid_names as (

    select grid_team_id, arg_max(team_name, scheduled_at) as grid_team_name
    from grid_teams
    group by grid_team_id

)

select
    m.grid_team_id,
    m.team_id_vlr,
    g.grid_team_name,
    t.team_name                 as vlr_team_name,
    m.match_method,             -- name / tag / override
    m.n_series,
    m.n_candidates,             -- > 1: hubo otro equipo de vlr posible (revisar)
    m.note

from matched as m
left join grid_names as g using (grid_team_id)
left join {{ ref('stg_vlr__teams') }} as t on t.team_id_vlr = m.team_id_vlr
