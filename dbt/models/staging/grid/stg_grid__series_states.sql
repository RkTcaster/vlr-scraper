-- Una fila por serie con Series State bajado: el nivel superior del struct `state`.
-- Las series del catalogo sin estado (forfeits, partidos que GRID no siguio) no aparecen aca.

with base as (

    select * from {{ ref('base_grid__series_state') }}

),

renamed as (

    select
        series_id                                           as grid_series_id,
        state.version                                       as state_version,     -- 3.48 / 3.49 / 3.50
        state.format                                        as series_format_name, -- best-of-3
        state.started                                       as is_started,
        state.finished                                      as is_finished,
        state.forfeited                                     as is_forfeited,
        state.valid                                         as is_valid,
        state.startedAt                                     as started_at,
        {{ iso8601_duration_seconds('state.duration') }}    as duration_seconds,
        len(state.games)                                    as map_count,
        len(state.draftActions) > 0                         as has_draft,         -- ~18%: ver analyses/grid_draft_coverage.sql
        state.updatedAt                                     as updated_at,
        fetched_at

    from base

)

select * from renamed
