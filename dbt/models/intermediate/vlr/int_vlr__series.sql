-- Una serie de vlr por fila, armada desde las rondas: fecha, los dos equipos (id y tag de cuando se jugo) y
-- cuantos mapas / rondas tiene. Es intermediate (no staging) porque agrega: el grano cambia de ronda a serie.

with rounds as (

    select * from {{ ref('stg_vlr__rounds') }}

)

select
    vlr_series_id,
    any_value(tournament_id)            as tournament_id,
    any_value(event_name)               as event_name,
    min(scheduled_at)                   as scheduled_at,        -- una sola fecha por serie
    any_value(team_a_id_vlr)            as team_a_id_vlr,
    any_value(team_b_id_vlr)            as team_b_id_vlr,
    any_value(team_a_tag)               as team_a_tag,
    any_value(team_b_tag)               as team_b_tag,
    count(distinct vlr_map_id)          as map_count,
    count(*)                            as round_count

from rounds
group by vlr_series_id
