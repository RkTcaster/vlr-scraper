-- Export de mart_team_round_orbs a csv, con los nombres de columna de Supabase (como tables/table_*.csv).
--
-- materialized = 'external' (dbt-duckdb): el build escribe el archivo y deja una view encima, asi los tests
-- corren sobre lo mismo que se va a subir.
-- Va a grid/exports/ (gitignoreado), NO a tables/: son datos de GRID y vlr_pipeline/upload.py no los sube.
-- Tabla de Supabase: sql/team_orbs.sql; la carga la hace rktdata (handoff/RKTDATA_TEAM_ORBS.md).

{{ config(
    materialized = 'external',
    location = '../grid/exports/table_team_orbs.csv',
    format = 'csv'
) }}

select
    team_map_round_id,
    team_id_vlr,
    vlr_series_id   as series_id,
    vlr_map_id      as map_id,
    map_name        as map,
    round_number    as round,
    team_tag        as team,
    case side when 'attacker' then 'atk' when 'defender' then 'def' end
                    as side,
    orbs,
    tournament_id   as tour_id
from {{ ref('mart_team_round_orbs') }}
order by series_id, map_id, round, team_id_vlr
