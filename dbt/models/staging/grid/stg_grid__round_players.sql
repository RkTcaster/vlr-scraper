-- Una fila por jugador y ronda (~950k filas): contadores de la ronda y como termino el jugador.
--
-- end_alive / end_health / end_armor: estado al final de ESA ronda (foto por ronda, a diferencia de la foto del
-- final del mapa en stg_grid__game_players).
-- Fuera de esta etapa (decision del 2026-11-19): dano por fuente, dano por zona del cuerpo, la lista de quien
-- asistio a quien y weaponKills por ronda. El conteo de asistencias (assists) si esta.

with base as (

    select unnest(state.games) as game, series_id from {{ ref('base_grid__series_state') }}

),

rounds as (

    select series_id, cast(game.id as varchar) as grid_game_id, unnest(game.segments) as round from base

),

teams as (

    select series_id, grid_game_id, round.sequenceNumber as round_number, unnest(round.teams) as team
    from rounds

),

players as (

    select series_id, grid_game_id, round_number, team.id as grid_team_id, unnest(team.players) as player
    from teams

),

renamed as (

    select
        grid_game_id || '-' || round_number || '-' || player.id    as round_player_id,
        grid_game_id || '-' || round_number || '-' || grid_team_id as round_team_id,
        grid_game_id || '-' || round_number                        as grid_round_id,
        grid_game_id || '-' || player.id                           as game_player_id,
        grid_game_id,
        series_id                                                  as grid_series_id,
        round_number,
        grid_team_id,
        player.id                                                  as grid_player_id,
        player.name                                                as player_name,
        player.participationStatus                                 as participation_status,

        player.kills,
        player.deaths,
        player.killAssistsGiven                                    as assists,
        player.headshots,
        player.firstKill                                           as first_kill,
        player.teamkills                                           as team_kills,
        player.selfkills                                           as self_kills,
        player.damageDealt                                         as damage_dealt,
        player.damageTaken                                         as damage_taken,
        player.teamdamageDealt                                     as team_damage_dealt,

        player.alive                                               as end_alive,
        cast(player.currentHealth as integer)                      as end_health,
        player.currentArmor                                        as end_armor

    from players

)

select * from renamed
