-- Staging de round_events: eventos de una ronda (pestana logs), uno por fila: kill, plant o defuse.
--
-- player = quien hace el evento (el que mata, planta o desactiva); victim = el muerto (solo en kills).
-- target_x / target_y = posicion del muerto o de la spike; killer_x / killer_y = desde donde mato (solo kills,
-- vacio si vlr no lo trae). Coordenadas del minimapa de vlr.
-- side = lado del jugador que hace el evento. is_trade / is_traded: ventana de 3 s (TRADE_WINDOW de tables.py).
-- legacy_*_id = '<tag>_<nick>', identidad vieja; usar *_id_vlr.

with source as (

    select * from {{ source('vlr', 'round_events') }}

)

select
    team_map_round_id || '-' || ev_index        as round_event_id,     -- PK en Supabase: (team_map_round_id, ev_index)
    team_map_round_id,
    cast(ev_index as integer)                   as event_index,
    series_id                                   as vlr_series_id,
    map_id                                      as vlr_map_id,
    map                                         as map_name,
    cast(round as integer)                      as round_number,
    cast(t_sec as integer)                      as event_time_sec,     -- segundos desde el inicio de la ronda
    type                                        as event_type,
    player                                      as player_name,
    player_id_vlr,
    team                                        as team_tag,
    team_id_vlr,
    case side when 'atk' then 'attacker' when 'def' then 'defender' end
                                                as side,
    nullif(victim, '')                          as victim_name,
    nullif(victim_id_vlr, '')                   as victim_id_vlr,
    nullif(victim_team, '')                     as victim_team_tag,
    nullif(victim_team_id_vlr, '')              as victim_team_id_vlr,
    nullif(weapon, '')                          as weapon,
    nullif(site, '')                            as site,
    cast(nullif(pos_x, '') as double)           as target_x,
    cast(nullif(pos_y, '') as double)           as target_y,
    cast(nullif(from_x, '') as double)          as killer_x,
    cast(nullif(from_y, '') as double)          as killer_y,
    is_first_blood = 'True'                     as is_first_blood,
    is_team_kill = 'True'                       as is_team_kill,
    is_post_plant = 'True'                      as is_post_plant,
    is_trade = 'True'                           as is_trade,
    is_traded = 'True'                          as is_traded,
    player_id                                   as legacy_player_id,
    nullif(victim_id, '')                       as legacy_victim_id,
    reg_id                                      as region_id,
    tour_id                                     as tournament_id
from source
