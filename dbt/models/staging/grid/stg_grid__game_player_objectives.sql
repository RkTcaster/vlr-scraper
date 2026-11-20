-- Una fila por jugador, mapa y tipo de objetivo: cuantas veces lo completo en el mapa.
-- Tipos vistos: plantBomb, defuseBomb, beginDefuseBomb, stopDefuseBomb (defuse cortado),
-- reachDefuseBombCheckpoint (medio defuse), explodeBomb, captureUltimateOrb (orbes de definitiva).

with base as (

    select unnest(state.games) as game from {{ ref('base_grid__series_state') }}

),

teams as (

    select cast(game.id as varchar) as grid_game_id, unnest(game.teams) as team from base

),

players as (

    select grid_game_id, unnest(team.players) as player from teams

),

objectives as (

    select
        grid_game_id,
        player.id                   as grid_player_id,
        unnest(player.objectives)   as objective
    from players

),

renamed as (

    select
        grid_game_id || '-' || grid_player_id || '-' || objective.type  as game_player_objective_id,
        grid_game_id || '-' || grid_player_id                           as game_player_id,
        objective.type                                                  as objective_type,
        objective.completionCount                                       as completions,
        objective.completedFirst                                        as completed_first

    from objectives

)

select * from renamed
