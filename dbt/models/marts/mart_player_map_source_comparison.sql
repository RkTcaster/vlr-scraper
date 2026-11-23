-- Comparacion GRID vs vlr: una fila por jugador-mapa y metrica (formato largo).
--
-- Grano: las filas de fct_player_map (pares de int_player_crosswalk). Para cada metrica: vlr_value, grid_value, diff (grid - vlr) y
-- is_equal. Resumir por metrica es un group by (ver analyses/source_comparison_summary.sql).
--
-- Como se arma cada metrica del lado de GRID, para que mida lo mismo que vlr (se calculan en fct_player_map):
--   kills, deaths, assists  contadores del mapa (stg_grid__game_players).
--   first_kills             rondas con firstKill = true (a nivel mapa el campo es un booleano, no un conteo).
--   adr                     damage_dealt / rondas. Ya se sabe que da ~0.79 del de vlr (overkill, GRID_NOTES).
--   headshot_pct            impactos en la cabeza / impactos de bala (head + body + leg), como vlr. El campo
--                           headshots de GRID son impactos, no kills.
-- El agente no es numerico: va como columnas de contexto (vlr_agent, grid_agent) en todas las filas del par.

-- Base: fct_player_map, que ya tiene los dos lados del par (columnas de vlr y *_grid). Antes este mart repetia
-- el cruce y los agregados de GRID; ahora la regla del cruce y como se cuenta cada metrica viven en un solo lugar.

with pairs as (

    select
        map_player_id,
        game_player_id,
        vlr_map_id,
        player_id_vlr,
        team_id_vlr,
        tournament_id,
        player_name,
        agent                   as vlr_agent,
        agent_grid              as grid_agent,
        agent_matches,
        match_method,

        kills                   as vlr_kills,       kills_grid          as grid_kills,
        deaths                  as vlr_deaths,      deaths_grid         as grid_deaths,
        assists                 as vlr_assists,     assists_grid        as grid_assists,
        first_kills             as vlr_first_kills, first_kills_grid    as grid_first_kills,
        adr                     as vlr_adr,
        -- sin redondear a 1 decimal como adr_grid: para comparar con vlr, que publica enteros
        round(damage_dealt / nullif(rounds_played, 0))  as grid_adr,
        headshot_pct            as vlr_headshot_pct,
        headshot_pct_grid       as grid_headshot_pct

    from {{ ref('fct_player_map') }}

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
