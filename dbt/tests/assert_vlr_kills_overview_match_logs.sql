-- Las kills de un jugador en un mapa tienen que ser las mismas en dos pestanas de vlr scrapeadas por separado:
-- el overview (player_stats) y el log de la ronda (round_events, kills que no son team kills: el overview no
-- cuenta las team kills; con ellas solo coincide el 90 %).
-- Solo mapas que tienen log. Un jugador del overview sin kills en el log cuenta como 0.
--
-- warn: al 2026-11-20 difieren 70 de 57 768 jugador-mapa (99.88 % iguales), en dos patrones:
--   - log incompleto: todo el mapa con menos kills en el log (790238 / 790417 / 712828 Sunset, 790219 Lotus,
--     698906 Ascent).
--   - jugador faltante en el overview: en qualifiers LATAM, player_stats crudo tiene 4 jugadores de un equipo
--     (CARN, RADI, ZENI) y las kills del quinto quedan en el log asignadas al jugador con el mismo nick
--     (Charlslol, Splotza, ley0r: log >> overview). Bug del parser del overview, ver ROADMAP.
-- Una suba en la cantidad = pestana logs u overview que cambio, o un problema nuevo de identidad de jugador.

{{ config(severity = 'warn') }}

with maps_with_logs as (

    select distinct vlr_map_id
    from {{ ref('stg_vlr__round_events') }}

),

log_kills as (

    select vlr_map_id, player_id_vlr, count(*) as kills
    from {{ ref('stg_vlr__round_events') }}
    where event_type = 'kill'
      and not is_team_kill
    group by vlr_map_id, player_id_vlr

)

select
    p.vlr_map_id,
    p.player_id_vlr,
    p.player_name,
    p.team_tag,
    p.kills                         as kills_overview,
    coalesce(l.kills, 0)            as kills_log,
    coalesce(l.kills, 0) - p.kills  as diff
from {{ ref('stg_vlr__player_stats') }} as p
join maps_with_logs using (vlr_map_id)
left join log_kills as l using (vlr_map_id, player_id_vlr)
where p.kills <> coalesce(l.kills, 0)
