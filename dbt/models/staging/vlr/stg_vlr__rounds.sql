-- Staging de round_info: una ronda de vlr por fila.
--
-- Tres cosas del csv que no son obvias:
--   rndA / rndB  1 para el equipo que gano ESA ronda (no es el score acumulado) -> team_a_won
--   side         lado del teamA en la ronda (atk de la 1 a la 12, def desde la 13) -> team_a_side
--   date         hora programada en America/New_York (comparada con GRID: 4 h de diferencia en horario de
--                verano, 5 h en invierno). Se pasa a UTC para que las dos fuentes sean comparables.
-- Los lados se escriben como en GRID (attacker / defender) para poder compararlos sin traducir.

with source as (

    select * from {{ source('vlr', 'round_info') }}

),

renamed as (

    select
        team_map_round_id,
        series_id                                           as vlr_series_id,
        map_id                                              as vlr_map_id,        -- <series_id>-<Mapa>
        map                                                 as map_name,          -- con mayuscula: Breeze
        cast(map_order as integer) + 1                      as map_number,        -- map_order arranca en 0
        cast(round as integer)                              as round_number,
        teamA                                               as team_a_tag,        -- tag de cuando se jugo
        teamB                                               as team_b_tag,
        team_a_id_vlr,
        team_b_id_vlr,
        case side when 'atk' then 'attacker' when 'def' then 'defender' end
                                                            as team_a_side,
        rndA = '1'                                          as team_a_won,
        winCon                                              as win_con,           -- elim / boom / defus / tim
        -- timestamp sin zona -> "esta hora es de Nueva York" -> timestamptz (instante absoluto, se ve en UTC)
        {{ vlr_timestamp_utc('date') }}             as scheduled_at,
        tour_id                                             as tournament_id,
        event                                               as event_name

    from source

)

select * from renamed
