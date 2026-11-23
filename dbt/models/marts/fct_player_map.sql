-- Una fila por jugador y mapa, con los ids de vlr y lo que solo tiene GRID.
--
-- Grano: jugador-mapa de vlr que tiene par en GRID (int_player_crosswalk). Los mapas fuera del cruce (qualifiers,
-- torneos que GRID no cubre) no estan: este mart es para las stats que vlr no publica.
--   De vlr:  rating, acs, kills, deaths, assists, kast, adr, hs%, first kills/deaths (lo que muestra la web).
--   De GRID: dano recibido, rondas sobrevividas, orbes, plants, defuses, asistencias recibidas.
-- adr_grid = dano total de GRID / rondas. NO es el mismo numero que adr (vlr): da ~0.79 de adr, constante en
-- todos los torneos. GRID da 147 de dano por kill (tope 150 = vida + armadura) y vlr 182: la hipotesis es que
-- GRID cuenta solo el dano efectivo y vlr/Riot suma el overkill. Comparar jugadores dentro de una misma fuente.

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
        count(*)                                        as rounds_played,
        count(*) filter (where end_alive)               as rounds_survived,
        -- a nivel mapa first_kill es un booleano, no un conteo: se cuentan las rondas
        count(*) filter (where first_kill)              as first_kills
    from {{ ref('stg_grid__round_players') }}
    group by game_player_id

),

-- headshots de GRID son impactos, no kills: hs% = impactos en la cabeza / impactos de bala, como vlr
grid_hits as (

    select
        r.game_player_id,
        sum(z.hits) filter (where z.zone = 'head')                          as head_hits,
        sum(z.hits) filter (where z.zone in ('head', 'body', 'leg'))        as bullet_hits
    from {{ ref('stg_grid__round_player_damage_zones') }} as z
    join {{ ref('stg_grid__round_players') }} as r using (round_player_id)
    group by r.game_player_id

),

grid_objectives as (

    select
        r.game_player_id,
        sum(o.completions) filter (where o.objective_type = 'captureUltimateOrb')  as orbs_captured,
        sum(o.completions) filter (where o.objective_type = 'plantBomb')           as plants,
        sum(o.completions) filter (where o.objective_type = 'defuseBomb')          as defuses
    from {{ ref('stg_grid__round_player_objectives') }} as o
    join {{ ref('stg_grid__round_players') }} as r using (round_player_id)
    group by r.game_player_id

)

select
    -- ids de vlr
    v.map_player_id,
    v.vlr_map_id,
    v.vlr_series_id,
    v.player_id_vlr,
    v.team_id_vlr,
    v.tournament_id,
    v.player_name,
    v.team_tag,
    v.agent,

    -- vlr
    m.vlr_round_count                                              as vlr_rounds,   -- para ponderar las tasas de vlr
    v.rating,
    v.acs,
    v.kills,
    v.deaths,
    v.assists,
    v.kast_pct,
    v.adr,
    v.headshot_pct,
    v.first_kills,
    v.first_deaths,

    -- GRID
    r.rounds_played,
    r.rounds_survived,
    round(r.rounds_survived / nullif(r.rounds_played, 0), 3)       as survival_rate,
    g.damage_dealt,
    g.damage_taken,
    round(g.damage_dealt / nullif(r.rounds_played, 0), 1)          as adr_grid,
    round(g.damage_taken / nullif(r.rounds_played, 0), 1)          as damage_taken_per_round,
    g.assists_received,
    coalesce(o.orbs_captured, 0)                                   as orbs_captured,
    coalesce(o.plants, 0)                                          as plants,
    coalesce(o.defuses, 0)                                         as defuses,

    -- trazabilidad
    c.game_player_id,
    c.grid_player_id,
    c.match_method,

    -- GRID: lo mismo que vlr, contado por GRID (base de mart_player_map_source_comparison)
    g.kills                                                        as kills_grid,
    g.deaths                                                       as deaths_grid,
    g.assists                                                      as assists_grid,
    r.first_kills                                                  as first_kills_grid,
    round(100.0 * h.head_hits / nullif(h.bullet_hits, 0))          as headshot_pct_grid,
    c.grid_agent                                                   as agent_grid,
    c.agent_matches

from crosswalk as c
join vlr as v using (map_player_id)
join grid_map as g using (game_player_id)
left join grid_rounds as r using (game_player_id)
left join grid_objectives as o using (game_player_id)
left join grid_hits as h using (game_player_id)
join {{ ref('int_map_crosswalk') }} as m on m.vlr_map_id = v.vlr_map_id
