-- Una fila por jugador, ronda y tipo de objetivo. Aca estan los orbes de definitiva por ronda:
-- objective_type = 'captureUltimateOrb' (como mucho 2 por ronda, 4 en Fracture; test
-- assert_grid_max_orbs_per_round). Tambien plantBomb, defuseBomb, beginDefuseBomb, stopDefuseBomb
-- (defuse cortado), reachDefuseBombCheckpoint (medio defuse) y explodeBomb.
-- No dice en que momento de la ronda ni cual de los dos orbes.

with base as (

    select unnest(state.games) as game from {{ ref('base_grid__series_state') }}

),

rounds as (

    select cast(game.id as varchar) as grid_game_id, unnest(game.segments) as round from base

),

teams as (

    select grid_game_id, round.sequenceNumber as round_number, unnest(round.teams) as team from rounds

),

players as (

    select grid_game_id, round_number, unnest(team.players) as player from teams

),

objectives as (

    select
        grid_game_id,
        round_number,
        player.id                   as grid_player_id,
        unnest(player.objectives)   as objective
    from players

),

renamed as (

    select
        grid_game_id || '-' || round_number || '-' || grid_player_id || '-' || objective.type
                                                                    as round_player_objective_id,
        grid_game_id || '-' || round_number || '-' || grid_player_id as round_player_id,
        objective.type                                              as objective_type,
        objective.completionCount                                   as completions,
        objective.completedFirst                                    as completed_first

    from objectives

)

select * from renamed
