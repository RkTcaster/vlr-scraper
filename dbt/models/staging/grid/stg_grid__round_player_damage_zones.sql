-- Una fila por jugador, ronda y zona del cuerpo: impactos y dano (damageDealtTargets de GRID).
--
-- zone: head / body / leg = impactos de bala en esa zona; general = dano sin zona (habilidades, explosivos).
-- El campo headshots de stg_grid__round_players es el mismo numero que los hits de la zona head: son IMPACTOS en
-- la cabeza, no kills. El headshot % comparable con vlr es head / (head + body + leg).
-- Se agrego el 2026-11-20 para el mart de comparacion con vlr; el dano por fuente (arma/habilidad) sigue afuera.

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

targets as (

    select
        grid_game_id,
        round_number,
        player.id                           as grid_player_id,
        unnest(player.damageDealtTargets)   as target
    from players

),

renamed as (

    select
        grid_game_id || '-' || round_number || '-' || grid_player_id || '-' || target.target.name
                                                                    as round_player_zone_id,
        grid_game_id || '-' || round_number || '-' || grid_player_id as round_player_id,
        target.target.name                                          as zone,
        target.occurrenceCount                                      as hits,
        target.damageAmount                                         as damage

    from targets

)

select * from renamed
