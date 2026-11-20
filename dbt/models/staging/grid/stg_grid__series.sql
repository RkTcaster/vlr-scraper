-- Una fila por serie del catalogo de Central Data (incluye las que GRID no tiene con estado: ver
-- stg_grid__series_states). Del catalogo salen torneo, fecha programada, formato e ids de Riot.
--
-- Los nombres de torneo traen la fase entre parentesis: "VCT EMEA - Stage 2 2026 (Play-Ins: Play-Ins)".
-- Se separan en event_name / stage_name para poder mapearlos despues contra los tour_id de vlr.
-- Ojo: Central Data rompe los caracteres no ASCII (Turkiye llega con U+FFFD), no tiene arreglo aca.

with source as (

    select * from {{ source('grid', 'series_catalog') }}

),

renamed as (

    select
        id                                                  as grid_series_id,
        type                                                as series_type,       -- siempre ESPORTS (filtro de la ingesta)
        cast(startTimeScheduled as timestamptz)             as scheduled_at,
        format.nameShortened                                as series_format,     -- Bo1 / Bo3 / Bo5
        tournament.id                                       as grid_tournament_id,
        tournament.name                                     as tournament_full_name,
        regexp_replace(tournament.name, ' \(.*\)$', '')     as event_name,
        nullif(regexp_extract(tournament.name, '\((.*)\)$', 1), '') as stage_name,
        tournament.parent.id                                as grid_parent_tournament_id,
        -- externalLinks es una lista de {dataProvider, externalEntity}; el proveedor VALORANT es el id de Riot.
        -- Las listas de DuckDB arrancan en 1. `lambda l: ...` es la sintaxis de DuckDB 2.0 (la flecha -> se depreco).
        list_filter(externalLinks, lambda l: l.dataProvider.name = 'VALORANT')[1].externalEntity.id
                                                            as riot_series_id,
        cast(updatedAt as timestamptz)                      as updated_at

    from source

)

select * from renamed
