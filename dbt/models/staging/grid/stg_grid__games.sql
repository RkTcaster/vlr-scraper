-- Una fila por mapa (GRID lo llama game).

with base as (

    select * from {{ ref('base_grid__series_state') }}

),

games as (

    select
        series_id,
        unnest(state.games) as game
    from base

),

renamed as (

    select
        cast(game.id as varchar)                            as grid_game_id,      -- UUID
        series_id                                           as grid_series_id,
        game.sequenceNumber                                 as map_number,        -- 1, 2, 3...
        game.map.name                                       as map_name,          -- en minuscula: haven, abyss
        game.started                                        as is_started,
        game.finished                                       as is_finished,
        game.forfeited                                      as is_forfeited,
        game.startedAt                                      as started_at,
        {{ iso8601_duration_seconds('game.duration') }}     as duration_seconds,
        len(game.segments)                                  as round_count,
        -- 8 mapas de Challengers traen solo el score: sin jugadores, o con la lista pero todo en 0 y sin agente
        -- (2919966, bind). Se detectan por no tener ninguna kill; final_side viene como 'none'.
        coalesce(list_sum(list_transform(game.teams, lambda t: t.kills)), 0) > 0
                                                            as has_player_stats

    from games

)

select * from renamed
