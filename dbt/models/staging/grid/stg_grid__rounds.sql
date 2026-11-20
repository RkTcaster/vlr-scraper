-- Una fila por ronda: el grano con el que despues se cruza contra round_info de vlr (map_id + round).
-- El ganador y su win_type salen del equipo con won = true de la lista de equipos de la ronda.

with base as (

    select unnest(state.games) as game, series_id from {{ ref('base_grid__series_state') }}

),

rounds as (

    select
        series_id,
        cast(game.id as varchar)  as grid_game_id,
        unnest(game.segments)     as round
    from base

),

renamed as (

    select
        grid_game_id || '-' || round.sequenceNumber            as grid_round_id,
        grid_game_id,
        series_id                                              as grid_series_id,
        round.sequenceNumber                                   as round_number,  -- 1..24, despues overtime
        round.finished                                         as is_finished,
        round.startedAt                                        as started_at,
        -- la ronda 1 incluye la previa del mapa (puede durar 18 min)
        {{ iso8601_duration_seconds('round.duration') }}       as duration_seconds,
        -- list_filter deja los equipos que ganaron; [1] toma el primero (deberia haber exactamente uno)
        list_filter(round.teams, lambda t: t.won)[1].id        as winner_grid_team_id,
        list_filter(round.teams, lambda t: t.won)[1].side      as winner_side,
        list_filter(round.teams, lambda t: t.won)[1].winType   as win_type,
        len(list_filter(round.teams, lambda t: t.won))         as winner_count   -- test: tiene que ser 1

    from rounds

)

select * from renamed
