-- Una fila por jugador, mapa y arma: kills con cada arma en el mapa.
-- Solo armas: las kills con habilidad (tour-de-force, showstopper...) no aparecen en weaponKills
-- (pendiente en GRID_NOTES.md comparar sum(kills) contra game_players.kills).

with base as (

    select unnest(state.games) as game from {{ ref('base_grid__series_state') }}

),

teams as (

    select cast(game.id as varchar) as grid_game_id, unnest(game.teams) as team from base

),

players as (

    select grid_game_id, unnest(team.players) as player from teams

),

-- Tercer unnest: una fila por elemento de la lista weaponKills de cada jugador
weapon_kills as (

    select
        grid_game_id,
        player.id                   as grid_player_id,
        unnest(player.weaponKills)  as weapon_kill
    from players

),

renamed as (

    select
        grid_game_id || '-' || grid_player_id || '-' || weapon_kill.weaponName  as game_player_weapon_id,
        grid_game_id || '-' || grid_player_id                                   as game_player_id,
        weapon_kill.weaponName                                                  as weapon_name,
        coalesce(weapon_kill.count, 0)                                          as kills  -- count es nullable en el schema

    from weapon_kills

)

select * from renamed
