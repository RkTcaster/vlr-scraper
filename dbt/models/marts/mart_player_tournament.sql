-- Una fila por jugador y torneo: stats de vlr y de GRID agregadas sobre los mismos mapas (fct_player_map).
--
-- Base: solo mapas del cruce GRID <-> vlr, asi las columnas de las dos fuentes salen de los mismos mapas. Los
-- torneos que GRID no cubre (qualifiers) no estan.
-- Ponderacion: las tasas de vlr (rating, acs, adr, kast, hs%) se ponderan por las rondas del mapa en vlr, como
-- las stats de evento de vlr: un 13-11 pesa mas que un 13-3. Las de GRID se recalculan desde los totales
-- (sobrevividas / rondas de GRID). Los conteos se suman y las tasas por ronda se dividen por las rondas totales.
-- Sin minimo de mapas: filtrar con where maps >= N al consultar.
-- Equipo: el de la serie mas reciente del jugador en el torneo (los series_id de vlr crecen con el tiempo);
-- n_teams > 1 = cambio de equipo dentro del torneo.

with player_maps as (

    select * from {{ ref('fct_player_map') }}

),

agent_counts as (

    select tournament_id, player_id_vlr, agent, count(*) as maps_on_agent
    from player_maps
    group by all

),

agents as (

    select
        tournament_id,
        player_id_vlr,
        arg_max(agent, maps_on_agent)                           as main_agent,
        string_agg(agent || ' ' || maps_on_agent, ', ' order by maps_on_agent desc, agent)
                                                                as agent_pool,     -- 'Jett 5, Raze 2'
        count(*)                                                as n_agents
    from agent_counts
    group by all

),

aggregated as (

    select
        tournament_id,
        player_id_vlr,
        arg_max(player_name, cast(vlr_series_id as integer))    as player_name,
        arg_max(team_id_vlr, cast(vlr_series_id as integer))    as team_id_vlr,
        arg_max(team_tag, cast(vlr_series_id as integer))       as team_tag,
        count(distinct team_id_vlr)                             as n_teams,

        count(*)                                                as maps,
        count(distinct vlr_series_id)                           as series,
        sum(vlr_rounds)                                         as rounds,

        -- vlr: tasas ponderadas por rondas
        round(sum(rating * vlr_rounds) / sum(vlr_rounds), 2)        as rating,
        round(sum(acs * vlr_rounds) / sum(vlr_rounds), 1)           as acs,
        round(sum(adr * vlr_rounds) / sum(vlr_rounds), 1)           as adr,
        round(sum(kast_pct * vlr_rounds) / sum(vlr_rounds), 1)      as kast_pct,
        round(sum(headshot_pct * vlr_rounds) / sum(vlr_rounds), 1)  as headshot_pct,

        -- vlr: conteos y por ronda
        sum(kills)                                              as kills,
        sum(deaths)                                             as deaths,
        sum(assists)                                            as assists,
        sum(first_kills)                                        as first_kills,
        sum(first_deaths)                                       as first_deaths,
        round(sum(kills) / sum(vlr_rounds), 3)                  as kills_per_round,
        round(sum(deaths) / sum(vlr_rounds), 3)                 as deaths_per_round,
        round(sum(assists) / sum(vlr_rounds), 3)                as assists_per_round,
        round(sum(first_kills) / sum(vlr_rounds), 3)            as first_kills_per_round,
        round(sum(first_deaths) / sum(vlr_rounds), 3)           as first_deaths_per_round,

        -- GRID: desde los totales, por las rondas de GRID
        sum(rounds_played)                                      as grid_rounds,
        sum(rounds_survived)                                    as rounds_survived,
        round(sum(rounds_survived) / sum(rounds_played), 3)     as survival_rate,
        round(sum(damage_dealt) / sum(rounds_played), 1)        as adr_grid,
        round(sum(damage_taken) / sum(rounds_played), 1)        as damage_taken_per_round,
        sum(assists_received)                                   as assists_received,
        sum(orbs_captured)                                      as orbs_captured,
        round(100.0 * sum(orbs_captured) / sum(rounds_played), 1)   as orbs_per_100_rounds,
        sum(plants)                                             as plants,
        sum(defuses)                                            as defuses

    from player_maps
    group by tournament_id, player_id_vlr

)

select
    a.tournament_id || '-' || a.player_id_vlr                   as tournament_player_id,
    a.tournament_id,
    t.tournament_name,
    t.season_year,
    a.player_id_vlr,
    a.player_name,
    a.team_id_vlr,
    a.team_tag,
    a.n_teams,
    g.main_agent,
    g.agent_pool,
    g.n_agents,
    a.* exclude (tournament_id, player_id_vlr, player_name, team_id_vlr, team_tag, n_teams)
from aggregated as a
join agents as g using (tournament_id, player_id_vlr)
left join {{ ref('stg_vlr__tournaments') }} as t using (tournament_id)
