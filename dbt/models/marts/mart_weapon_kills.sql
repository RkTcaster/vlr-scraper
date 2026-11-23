-- Kills por arma, mapa y torneo, desde fct_kills.
--
-- Es una table comun (no incremental): agrega ~900 mil filas en menos de un segundo, y recalcular todo evita
-- el problema de que un agregado incremental tenga que "corregir" grupos que ya existian.
-- weapon incluye habilidades (ultis como Showstopper o Blade Storm); las team kills (Spike, Fall...) no entran.

with kills as (

    select * from {{ ref('fct_kills') }}
    where not is_team_kill

),

by_weapon as (

    select
        tournament_id,
        map_name,
        weapon,
        count(*)                                            as kills,
        count(*) filter (where is_first_blood)              as first_bloods,
        count(*) filter (where is_post_plant)               as post_plant_kills,
        -- traded = el que murio fue vengado por su equipo en 3 s
        avg(is_traded::int)                                 as traded_rate,
        avg(killer_team_won_round::int)                     as round_win_rate

    from kills
    group by tournament_id, map_name, weapon

)

select
    *,
    -- parte de las kills de ese torneo y mapa que hizo esta arma
    kills / sum(kills) over (partition by tournament_id, map_name) as kill_share
from by_weapon
