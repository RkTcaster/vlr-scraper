-- Comparacion GRID vs vlr: una fila por jugador-mapa y metrica (formato largo).
--
-- Grano: los pares de int_player_crosswalk. Para cada metrica: vlr_value, grid_value, diff (grid - vlr) y
-- is_equal. Resumir por metrica es un group by (ver analyses/source_comparison_summary.sql).
--
-- Como se arma cada metrica del lado de GRID, para que mida lo mismo que vlr:
--   kills, deaths, assists  contadores del mapa (stg_grid__game_players).
--   first_kills             rondas con firstKill = true (a nivel mapa el campo es un booleano, no un conteo).
--   adr                     damage_dealt / rondas. Ya se sabe que da ~0.79 del de vlr (overkill, GRID_NOTES).
--   headshot_pct            impactos en la cabeza / impactos de bala (head + body + leg), como vlr. El campo
--                           headshots de GRID son impactos, no kills.
-- El agente no es numerico: va como columnas de contexto (vlr_agent, grid_agent) en todas las filas del par.

with crosswalk as (

    select * from {{ ref('int_player_crosswalk') }}

),

vlr as (

    select * from {{ ref('stg_vlr__player_stats') }}

),

grid_map as (

    select * from {{ ref('stg_grid__game_players') }}

),

grid_rounds as (

    select
        game_player_id,
        count(*)                                    as rounds_played,
        count(*) filter (where first_kill)          as first_kills
    from {{ ref('stg_grid__round_players') }}
    group by game_player_id

),

grid_hits as (

    select
        r.game_player_id,
        sum(z.hits) filter (where z.zone = 'head')                          as head_hits,
        sum(z.hits) filter (where z.zone in ('head', 'body', 'leg'))        as bullet_hits
    from {{ ref('stg_grid__round_player_damage_zones') }} as z
    join {{ ref('stg_grid__round_players') }} as r using (round_player_id)
    group by r.game_player_id

),

pairs as (

    select
        c.map_player_id,
        c.game_player_id,
        v.vlr_map_id,
        v.player_id_vlr,
        v.team_id_vlr,
        v.tournament_id,
        v.player_name,
        c.vlr_agent,
        c.grid_agent,
        c.agent_matches,
        c.match_method,

        v.kills         as vlr_kills,       g.kills         as grid_kills,
        v.deaths        as vlr_deaths,      g.deaths        as grid_deaths,
        v.assists       as vlr_assists,     g.assists       as grid_assists,
        v.first_kills   as vlr_first_kills, r.first_kills   as grid_first_kills,
        v.adr           as vlr_adr,
        round(g.damage_dealt / nullif(r.rounds_played, 0))                  as grid_adr,
        v.headshot_pct  as vlr_headshot_pct,
        round(100.0 * h.head_hits / nullif(h.bullet_hits, 0))               as grid_headshot_pct

    from crosswalk as c
    join vlr as v using (map_player_id)
    join grid_map as g using (game_player_id)
    left join grid_rounds as r using (game_player_id)
    left join grid_hits as h using (game_player_id)

),

-- De ancho a largo: una fila por metrica. unpivot de DuckDB arma (metric, value) para cada columna; se hace dos
-- veces (vlr y grid) y se juntan por el nombre de la metrica. Todo como double: unpivot pide un solo tipo.
long_vlr as (

    unpivot (select map_player_id,
                    vlr_kills::double as kills, vlr_deaths::double as deaths, vlr_assists::double as assists,
                    vlr_first_kills::double as first_kills, vlr_adr::double as adr,
                    vlr_headshot_pct::double as headshot_pct
             from pairs)
    on kills, deaths, assists, first_kills, adr, headshot_pct
    into name metric value vlr_value

),

long_grid as (

    unpivot (select map_player_id,
                    grid_kills::double as kills, grid_deaths::double as deaths, grid_assists::double as assists,
                    grid_first_kills::double as first_kills, grid_adr::double as adr,
                    grid_headshot_pct::double as headshot_pct
             from pairs)
    on kills, deaths, assists, first_kills, adr, headshot_pct
    into name metric value grid_value

)

select
    p.map_player_id || '-' || l.metric          as comparison_id,
    p.map_player_id,
    p.game_player_id,
    p.vlr_map_id,
    p.player_id_vlr,
    p.team_id_vlr,
    p.tournament_id,
    p.player_name,
    l.metric,
    l.vlr_value,
    g.grid_value,
    g.grid_value - l.vlr_value                  as diff,
    g.grid_value = l.vlr_value                  as is_equal,
    p.vlr_agent,
    p.grid_agent,
    p.agent_matches,
    p.match_method
from long_vlr as l
join long_grid as g using (map_player_id, metric)
join pairs as p using (map_player_id)
