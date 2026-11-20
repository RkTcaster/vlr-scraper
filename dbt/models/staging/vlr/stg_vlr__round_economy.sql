-- Staging de team_economy: pestana economy de vlr, una ronda por fila con la economia de los dos equipos.
--   *_loadout_value  valor del equipamiento del equipo en la ronda (vlr lo redondea a 0.1k)
--   *_bank           creditos que le quedan al equipo despues de comprar
-- vlr ya no muestra la economia del overtime (rondas 25+): esas rondas no estan.
-- team_a_side / team_a_won / win_con repiten round_info para tener la ronda completa sin join.

with source as (

    select * from {{ source('vlr', 'team_economy') }}

)

select
    team_map_round_id,
    series_id                               as vlr_series_id,
    map_id                                  as vlr_map_id,
    map                                     as map_name,
    cast(round as integer)                  as round_number,
    team_a                                  as team_a_tag,
    team_b                                  as team_b_tag,
    team_a_id_vlr,
    team_b_id_vlr,
    cast(team_a_economy as integer)         as team_a_loadout_value,
    cast(team_b_economy as integer)         as team_b_loadout_value,
    cast(team_a_bank as integer)            as team_a_bank,
    cast(team_b_bank as integer)            as team_b_bank,
    case side when 'atk' then 'attacker' when 'def' then 'defender' end
                                            as team_a_side,
    win_A = '1'                             as team_a_won,
    winCon                                  as win_con,
    {{ vlr_timestamp_utc('date') }}         as scheduled_at,
    source_url,
    event                                   as event_name,
    reg_id                                  as region_id,
    tour_id                                 as tournament_id
from source
