-- Una fila por equipo y ronda (GRID llama "segment" a la ronda).
--
-- A nivel ronda los contadores son de esa ronda sola, y `side` es el lado que el equipo jugo EN esa ronda (a
-- diferencia de stg_grid__game_teams.final_side, que es la foto del final del mapa).
-- win_type solo es relevante en el equipo que gano: opponentEliminated / bombExploded / bombDefused /
-- timeExpired, el equivalente 1 a 1 de round_info.winCon de vlr (elim / boom / defus / tim).

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

teams as (

    select
        series_id,
        grid_game_id,
        round.sequenceNumber      as round_number,
        unnest(round.teams)       as team
    from rounds

),

renamed as (

    select
        grid_game_id || '-' || round_number || '-' || team.id  as round_team_id,
        grid_game_id || '-' || round_number                    as grid_round_id,
        grid_game_id || '-' || team.id                         as game_team_id,
        grid_game_id,
        series_id                                              as grid_series_id,
        round_number,
        team.id                                                as grid_team_id,
        nullif(team.side, 'none')                              as side,          -- attacker / defender
        team.won                                               as won_round,
        team.winType                                           as win_type,
        team.kills,
        team.deaths,
        team.headshots,
        team.firstKill                                         as first_kill,    -- el equipo hizo la primera kill
        team.damageDealt                                       as damage_dealt,
        team.damageTaken                                       as damage_taken

    from teams

)

select * from renamed
