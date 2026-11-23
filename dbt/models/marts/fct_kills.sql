-- Una fila por kill de vlr (pestana logs), con el contexto de la ronda: mapa, torneo, lado y si el equipo del
-- que mato gano la ronda.
--
-- Materializacion INCREMENTAL (paso 7). La primera corrida (o con --full-refresh) arma la tabla entera; las
-- siguientes solo agregan las series que todavia no estan en la tabla. Que serie es "nueva" lo decide el bloque
-- bloque "if is_incremental()" de abajo (Jinja lee los tags aunque esten en un comentario SQL, por eso no se
-- escriben aca con llaves): is_incremental() es verdadero cuando la tabla ya existe, el modelo es
-- incremental y no se pidio --full-refresh.
--
-- Limite elegido a proposito: una serie que ya esta no se vuelve a procesar aunque se haya re-scrapeado (vlr
-- corrigio datos, backfill de logs, cambio en tables.py). Igual que `upload --full`, en ese caso:
--     dbt build -s fct_kills --full-refresh
--
-- Ojo: el csv se sigue leyendo entero en cada corrida (dbt no puede leer "parte" de un archivo); lo que se
-- ahorra es el join con las rondas y la escritura de ~900 mil filas.

{{
    config(
        materialized = 'incremental',
        incremental_strategy = 'append',
        on_schema_change = 'fail'
    )
}}

with events as (

    select * from {{ ref('stg_vlr__round_events') }}
    where event_type = 'kill'

    {% if is_incremental() %}
        -- this = la tabla fct_kills tal como quedo en la corrida anterior
        and vlr_series_id not in (select distinct vlr_series_id from {{ this }})
    {% endif %}

),

rounds as (

    select * from {{ ref('stg_vlr__rounds') }}

),

kills as (

    select
        events.round_event_id                   as kill_id,
        events.team_map_round_id,
        events.vlr_series_id,
        events.vlr_map_id,
        events.map_name,
        events.round_number,
        events.event_index,
        events.event_time_sec,
        rounds.scheduled_at,
        events.tournament_id,
        events.region_id,

        events.player_id_vlr                    as killer_id_vlr,
        events.player_name                      as killer_name,
        events.team_id_vlr                      as killer_team_id_vlr,
        events.team_tag                         as killer_team_tag,
        events.side                             as killer_side,
        events.victim_id_vlr,
        events.victim_name,
        events.victim_team_id_vlr,
        events.victim_team_tag,
        events.weapon,

        events.is_first_blood,
        events.is_team_kill,
        events.is_post_plant,
        events.is_trade,
        events.is_traded,

        -- el equipo del que mato, ganador de la ronda (null en team kills: el "killer" es la spike o la caida)
        case
            when events.is_team_kill then null
            when events.team_id_vlr = rounds.team_a_id_vlr then rounds.team_a_won
            when events.team_id_vlr = rounds.team_b_id_vlr then not rounds.team_a_won
        end                                     as killer_team_won_round

    from events
    inner join rounds
        on events.team_map_round_id = rounds.team_map_round_id

)

select * from kills
