-- Staging de tournament_slots: las plazas de un torneo (events.json: slots / relevant_teams).
-- team_tag vacio = plaza sin decidir. Al 2026-11-20 ningun evento usa slots: la tabla esta vacia.

with source as (

    select * from {{ source('vlr', 'tournament_slots') }}

)

select
    tour_id || '-' || slot      as tournament_slot_id,      -- PK en Supabase: (tour_id, slot)
    tour_id                     as tournament_id,
    cast(slot as integer)       as slot,
    nullif(team_id, '')         as team_tag
from source
