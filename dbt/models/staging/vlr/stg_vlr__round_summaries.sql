-- Staging de round_summary: una ronda por fila, resumida desde round_events (lo arma tables.py).
-- first_blood_* = la primera kill de la ronda; plant_* / defuse_* vacios = no hubo. Tiempos en segundos desde el
-- inicio de la ronda. trades: kills que vengan a un companero en 3 s; las team kills no cuentan.
-- legacy_*_id = '<tag>_<nick>', identidad vieja; usar *_id_vlr.

with source as (

    select * from {{ source('vlr', 'round_summary') }}

)

select
    team_map_round_id,
    series_id                                   as vlr_series_id,
    map_id                                      as vlr_map_id,
    cast(round as integer)                      as round_number,
    team_a                                      as team_a_tag,
    team_b                                      as team_b_tag,
    team_a_id_vlr,
    team_b_id_vlr,
    case side_team_a when 'atk' then 'attacker' when 'def' then 'defender' end
                                                as team_a_side,
    nullif(fb_player_id_vlr, '')                as first_blood_player_id_vlr,
    nullif(fb_victim_id_vlr, '')                as first_blood_victim_id_vlr,
    nullif(fb_team, '')                         as first_blood_team_tag,
    nullif(fb_team_id_vlr, '')                  as first_blood_team_id_vlr,
    cast(nullif(fb_t, '') as integer)           as first_blood_time_sec,
    cast(nullif(plant_t, '') as integer)        as plant_time_sec,
    nullif(plant_site, '')                      as plant_site,
    nullif(plant_player_id_vlr, '')             as plant_player_id_vlr,
    cast(nullif(defuse_t, '') as integer)       as defuse_time_sec,
    nullif(defuse_player_id_vlr, '')            as defuse_player_id_vlr,
    cast(kills_team_a as integer)               as kills_team_a,
    cast(kills_team_b as integer)               as kills_team_b,
    cast(trades_team_a as integer)              as trades_team_a,
    cast(trades_team_b as integer)              as trades_team_b,
    cast(last_event_t as integer)               as last_event_time_sec,
    nullif(fb_player_id, '')                    as legacy_first_blood_player_id,
    nullif(fb_victim_id, '')                    as legacy_first_blood_victim_id,
    nullif(plant_player_id, '')                 as legacy_plant_player_id,
    nullif(defuse_player_id, '')                as legacy_defuse_player_id,
    reg_id                                      as region_id,
    tour_id                                     as tournament_id
from source
