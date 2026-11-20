-- Igual que assert_grid_team_totals_match_players pero por ronda: los contadores del equipo en la ronda son la
-- suma de sus jugadores en esa ronda. Valida el cuarto nivel de unnest (serie > mapa > ronda > equipo > jugador).

with players as (

    select
        round_team_id,
        sum(kills)         as kills,
        sum(deaths)        as deaths,
        sum(damage_dealt)  as damage_dealt
    from {{ ref('stg_grid__round_players') }}
    group by round_team_id

)

select t.round_team_id, t.kills, p.kills as players_kills, t.deaths, p.deaths as players_deaths,
       t.damage_dealt, p.damage_dealt as players_damage_dealt
from {{ ref('stg_grid__round_teams') }} as t
left join players as p using (round_team_id)
where t.kills        is distinct from coalesce(p.kills, 0)
   or t.deaths       is distinct from coalesce(p.deaths, 0)
   or t.damage_dealt is distinct from coalesce(p.damage_dealt, 0)
