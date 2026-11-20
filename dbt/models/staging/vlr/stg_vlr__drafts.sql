-- Staging de draft: el veto de mapas de una serie, desde el equipo que vetea primero (team).
--
-- team_veto_N / rival_veto_N = la N-esima eleccion de cada equipo, alternadas: team_veto_1, rival_veto_1,
-- team_veto_2, ... Que es ban o pick depende del formato (best_of):
--   Bo3: veto 1 = ban, veto 2 = pick, veto 3 = ban, y decider_map.
--   Bo5: veto 1 = ban, vetos 2 y 3 = pick, y decider_map.
-- 'NA' = paso del veto que no existio (series con menos elecciones) -> null.
-- Las series de formato reduced (qualifiers sin veto) no estan.
-- match_instance sale del final de la url y vlr corta los slugs largos: hay basura ('ing', 'pen'), ver ROADMAP.

with source as (

    select * from {{ source('vlr', 'draft') }}

)

select
    series_id                           as vlr_series_id,
    team_id_vlr,
    rival_id_vlr,
    team                                as team_tag,
    rival                               as rival_tag,
    nullif(team_1_select_1, 'NA')       as team_veto_1,
    nullif(team_2_select_1, 'NA')       as rival_veto_1,
    nullif(team_1_select_2, 'NA')       as team_veto_2,
    nullif(team_2_select_2, 'NA')       as rival_veto_2,
    nullif(team_1_select_3, 'NA')       as team_veto_3,
    nullif(team_2_select_3, 'NA')       as rival_veto_3,
    nullif(decider, 'NA')               as decider_map,
    cast(bo as integer)                 as best_of,
    {{ vlr_timestamp_utc('date') }}     as scheduled_at,
    source_url,
    event                               as event_name,
    match_instance,
    reg_id                              as region_id,
    tour_id                             as tournament_id
from source
