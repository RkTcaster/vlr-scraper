-- Jugador-mapa de GRID <-> jugador-mapa de vlr, dentro de un mapa ya emparejado (int_map_crosswalk) y del mismo
-- equipo (int_team_crosswalk). Dos pasadas:
--   1. nick   nick normalizado igual (macro normalize_player_name).
--   2. agent  entre los que quedaron sin par en ese mapa y equipo, el mismo agente (un agente no se repite dentro
--             de un equipo en un mapa, asi que alcanza para los nicks que cambiaron o se escriben distinto).
-- En las dos pasadas un par vale solo si es unico de los dos lados: dos "Splotza" en el mismo equipo y mapa
-- (785988) no se emparejan por nick y caen al agente.
-- Solo jugadores activos de GRID: los inactive son suplentes que no jugaron y no estan en vlr.
-- El agente se compara sin lo que no sea letra o numero: GRID escribe 'kay/o' y vlr 'Kayo' (242 pares).

with grid_players as (

    select
        p.game_player_id,
        p.grid_game_id,
        p.grid_player_id,
        p.player_name,
        p.agent,
        regexp_replace(lower(p.agent), '[^a-z0-9]', '', 'g')    as agent_key,
        m.vlr_map_id,
        t.team_id_vlr,
        {{ normalize_player_name('p.player_name') }}   as nick_key
    from {{ ref('stg_grid__game_players') }} as p
    join {{ ref('int_map_crosswalk') }} as m using (grid_game_id)
    join {{ ref('int_team_crosswalk') }} as t using (grid_team_id)
    where p.participation_status = 'active'

),

vlr_players as (

    select
        map_player_id,
        vlr_map_id,
        player_id_vlr,
        team_id_vlr,
        player_name,
        lower(agent)                                    as agent,
        regexp_replace(lower(agent), '[^a-z0-9]', '', 'g')      as agent_key,
        {{ normalize_player_name('player_name') }}     as nick_key
    from {{ ref('stg_vlr__player_stats') }}
    where vlr_map_id in (select vlr_map_id from {{ ref('int_map_crosswalk') }})

),

by_nick as (

    select g.game_player_id, v.map_player_id, 'nick' as match_method
    from grid_players as g
    join vlr_players as v
      on v.vlr_map_id = g.vlr_map_id
     and v.team_id_vlr = g.team_id_vlr
     and v.nick_key = g.nick_key
    qualify count(*) over (partition by g.game_player_id) = 1
        and count(*) over (partition by v.map_player_id) = 1

),

by_agent as (

    select g.game_player_id, v.map_player_id, 'agent' as match_method
    from grid_players as g
    join vlr_players as v
      on v.vlr_map_id = g.vlr_map_id
     and v.team_id_vlr = g.team_id_vlr
     and v.agent_key = g.agent_key
    where g.game_player_id not in (select game_player_id from by_nick)
      and v.map_player_id not in (select map_player_id from by_nick)
    qualify count(*) over (partition by g.game_player_id) = 1
        and count(*) over (partition by v.map_player_id) = 1

),

matched as (

    select * from by_nick
    union all
    select * from by_agent

)

select
    m.game_player_id,
    m.map_player_id,
    g.grid_game_id,
    g.grid_player_id,
    v.vlr_map_id,
    v.player_id_vlr,
    v.team_id_vlr,
    m.match_method,
    g.player_name           as grid_player_name,
    v.player_name           as vlr_player_name,
    g.agent                 as grid_agent,
    v.agent                 as vlr_agent,
    g.agent_key = v.agent_key   as agent_matches
from matched as m
join grid_players as g using (game_player_id)
join vlr_players as v using (map_player_id)
