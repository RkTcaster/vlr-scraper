-- Staging de tournament_played: un equipo por torneo en el que jugo.
-- team_tag = el tag mas reciente del equipo en ese torneo (en Supabase la columna se llama teamA).

with source as (

    select * from {{ source('vlr', 'tournament_played') }}

)

select
    tour_id || '-' || team_id_vlr   as tournament_team_id,    -- PK en Supabase: (tour_id, team_id_vlr)
    tour_id                         as tournament_id,
    team_id_vlr,
    teamA                           as team_tag,
    event                           as event_name,
    reg_id                          as region_id
from source
