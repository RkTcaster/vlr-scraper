-- Una fila por equipo y mapa. Los contadores (kills, dano, headshots) son el total del equipo en el mapa y
-- coinciden con la suma de sus 5 jugadores (test assert_grid_team_totals_match_players).
--
-- `side` NO es el lado inicial: a nivel mapa GRID guarda la foto del final del mapa, asi que es el lado que el
-- equipo jugo en la ultima ronda. Por eso se llama final_side. El lado inicial sale de las rondas (mas adelante).

with base as (

    select * from {{ ref('base_grid__series_state') }}

),

games as (

    select series_id, unnest(state.games) as game from base

),

teams as (

    select
        series_id,
        cast(game.id as varchar) as grid_game_id,
        unnest(game.teams)       as team
    from games

),

renamed as (

    select
        grid_game_id || '-' || team.id                      as game_team_id,
        grid_game_id,
        series_id                                           as grid_series_id,
        team.id                                             as grid_team_id,
        team.name                                           as team_name,
        nullif(team.side, 'none')                           as final_side,        -- attacker / defender; 'none' en mapas sin stats
        team.won                                            as won_map,
        team.score                                          as rounds_won,
        team.kills,
        team.deaths,
        team.killAssistsGiven                               as assists,
        team.headshots,
        team.firstKill                                      as first_kill,        -- foto final: first kill de la ultima ronda
        team.teamkills                                      as team_kills,
        team.selfkills                                      as self_kills,
        team.damageDealt                                    as damage_dealt,
        team.damageTaken                                    as damage_taken

    from teams

)

select * from renamed
