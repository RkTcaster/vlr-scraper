-- Una fila por jugador y mapa: agente, contadores del mapa y la foto del final del mapa.
--
-- Contadores (kills, deaths, dano, headshots): total del jugador en el mapa.
-- end_*: foto del ultimo instante de la ultima ronda del mapa (plata, loadout, puntos de definitiva, vida). No son
-- por ronda ni promedios. Ver handoff/GRID_NOTES.md.
-- multikills no se trae: a nivel mapa viene siempre vacio (0 de 45k filas).
--
-- Hay un jugador con nick literal "None": se identifica a los jugadores por grid_player_id, nunca por nombre.

with base as (

    select * from {{ ref('base_grid__series_state') }}

),

games as (

    select series_id, unnest(state.games) as game from base

),

teams as (

    select series_id, cast(game.id as varchar) as grid_game_id, unnest(game.teams) as team from games

),

players as (

    select
        series_id,
        grid_game_id,
        team.id               as grid_team_id,
        unnest(team.players)  as player
    from teams

),

renamed as (

    select
        grid_game_id || '-' || player.id                    as game_player_id,
        grid_game_id || '-' || grid_team_id                 as game_team_id,
        grid_game_id,
        series_id                                           as grid_series_id,
        grid_team_id,
        player.id                                           as grid_player_id,
        player.name                                         as player_name,
        player.character.name                               as agent,             -- en minuscula: chamber, vyse
        player.participationStatus                          as participation_status,

        player.kills,
        player.deaths,
        player.killAssistsGiven                             as assists,
        player.killAssistsReceived                          as assists_received,
        player.headshots,
        player.firstKill                                    as first_kill,
        player.teamkills                                    as team_kills,
        player.selfkills                                    as self_kills,
        player.damageDealt                                  as damage_dealt,
        player.damageTaken                                  as damage_taken,
        player.teamdamageDealt                              as team_damage_dealt,

        player.ultimatePoints                               as end_ultimate_points,
        player.money                                        as end_money,
        player.loadoutValue                                 as end_loadout_value,
        player.netWorth                                     as end_net_worth,
        player.alive                                        as end_alive,
        cast(player.currentHealth as integer)               as end_health          -- read_json lo infiere HUGEINT

    from players

)

select * from renamed
