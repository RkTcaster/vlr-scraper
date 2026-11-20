-- Staging de player_stats: una fila por jugador y mapa jugado en vlr (overview).
--
-- Tres versiones de cada stat: el mapa completo (sin sufijo, columnas *Both), en ataque (_atk, columnas *T) y en
-- defensa (_def, columnas *CT). k-d y fk-fd no se traen: son restas de otras columnas.
-- player_id_vlr es la identidad del jugador (dos jugadores pueden compartir nick, ver CLAUDE.md); el nick se
-- guarda para el cruce con GRID y para revisar a ojo. agent viene con mayuscula (Jett), GRID en minuscula.
-- kast y hs vienen como fraccion (0.71, 0.33) y se pasan a porcentaje.

{%- set sides = [('Both', ''), ('T', '_atk'), ('CT', '_def')] %}

with source as (

    select * from {{ source('vlr', 'player_stats') }}

),

renamed as (

    select
        map_id || '-' || player_id_vlr                      as map_player_id,     -- PK en Supabase: (map_id, player_id_vlr)
        map_id                                              as vlr_map_id,
        series_id                                           as vlr_series_id,
        player_id_vlr,
        team_id_vlr,
        team                                                as team_tag,
        player                                              as player_name,
        agent,
        map                                                 as map_name,
        {%- for col, suffix in sides %}

        -- {{ 'mapa completo' if suffix == '' else ('ataque' if suffix == '_atk' else 'defensa') }}
        cast({{ 'ratingBoth' if col == 'Both' else ('ratingT' if col == 'T' else '"rating-ct"') }} as double)
                                                            as rating{{ suffix }},
        cast(acs{{ col }} as integer)                       as acs{{ suffix }},
        cast(kills{{ col }} as integer)                     as kills{{ suffix }},
        cast(dead{{ col }} as integer)                      as deaths{{ suffix }},
        cast(assists{{ col }} as integer)                   as assists{{ suffix }},
        round(cast(kast{{ col }} as double) * 100)          as kast_pct{{ suffix }},
        cast(adr{{ col }} as integer)                       as adr{{ suffix }},
        round(cast(hs{{ col }} as double) * 100)            as headshot_pct{{ suffix }},  -- impactos en la cabeza / impactos
        cast(fk{{ col }} as integer)                        as first_kills{{ suffix }},
        cast(fd{{ col }} as integer)                        as first_deaths{{ suffix }},
        {%- endfor %}

        -- duracion del mapa: 'mm:ss' (o 'h:mm:ss') -> segundos
        list_reduce(
            list_transform(string_split(map_duration, ':'), lambda x: cast(x as integer)),
            lambda acc, x: acc * 60 + x
        )                                                   as map_duration_sec,
        {{ vlr_timestamp_utc('date') }}                     as scheduled_at,
        source_url,
        event                                               as event_name,
        reg_id                                              as region_id,
        tour_id                                             as tournament_id

    from source

)

select * from renamed
