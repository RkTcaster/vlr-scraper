-- Staging de round_buy, en formato largo: una fila por jugador y ronda (la tabla de Supabase es ancha, con 7
-- columnas por cada uno de los 10 jugadores). Es el grano del csv crudo (round_buy_) y el de stg_grid__round_players.
--
-- team = 'a' / 'b' segun la posicion en vlr (team_a de round_info); slot = el orden del jugador en vlr (1-5).
-- side = lado del equipo del jugador en la ronda (attacker / defender).
-- shield: Heavy / Light / Regen / No armor. spend = gasto de la ronda; bank = creditos despues de comprar.
-- Lugares sin jugador (84 al 2026-11-20: rondas con menos de 5 jugadores en el log) se descartan.
-- El unpivot se escribe con un loop de Jinja: un select por (equipo, slot), unidos con union all.

with source as (

    select * from {{ source('vlr', 'round_buy') }}

),

unpivoted as (
{% for team in ['a', 'b'] %}
{%- for slot in range(1, 6) %}
{%- set p = 'player_' ~ slot ~ '_team_' ~ team %}
    {% if not (team == 'a' and slot == 1) %}union all{% endif %}

    select
        team_map_round_id,
        '{{ team }}'                                as team,
        {{ slot }}                                  as slot,
        team_{{ team }}                             as team_tag,
        team_{{ team }}_id_vlr                      as team_id_vlr,
        {%- if team == 'a' %}
        side_team_a                                 as side_raw,
        {%- else %}
        case side_team_a when 'atk' then 'def' when 'def' then 'atk' end
                                                    as side_raw,
        {%- endif %}
        {{ p }}                                     as player_name,
        nullif({{ p }}_id, '')                      as player_id_vlr,
        {{ p }}_agent                               as agent,
        nullif({{ p }}_weapon, '')                  as weapon,
        nullif({{ p }}_shield, '')                  as shield,
        cast(nullif({{ p }}_spend, '') as integer)  as spend,
        cast(nullif({{ p }}_bank, '') as integer)   as bank,
        series_id,
        map_id,
        round,
        reg_id,
        tour_id
    from source
    where {{ p }} <> ''
{% endfor %}
{%- endfor %}
)

select
    team_map_round_id || '-' || team || slot    as round_player_buy_id,
    team_map_round_id,
    series_id                                   as vlr_series_id,
    map_id                                      as vlr_map_id,
    cast(round as integer)                      as round_number,
    team,
    slot,
    team_tag,
    team_id_vlr,
    case side_raw when 'atk' then 'attacker' when 'def' then 'defender' end
                                                as side,
    player_name,
    player_id_vlr,
    agent,
    weapon,
    shield,
    spend,
    bank,
    reg_id                                      as region_id,
    tour_id                                     as tournament_id
from unpivoted
