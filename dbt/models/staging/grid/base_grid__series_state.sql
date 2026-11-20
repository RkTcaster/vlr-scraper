-- Modelo base: lee los ~1800 .json.gz UNA vez por `dbt run` y los deja en una tabla de DuckDB.
--
-- Por que existe: desarmar el JSON hasta ronda leyendo los .gz tarda ~45 s. Si cada staging fuera una view
-- sobre la source, cada consulta volveria a leer y descomprimir todo. Con este modelo materializado como
-- table, los staging (views) leen de una tabla ya cargada y responden en segundos.
--
-- "base_" es la convencion de dbt para un paso previo al staging que no renombra nada: solo trae la source tal
-- cual. El struct `state` queda anidado; cada stg_grid__* desarma el nivel que le toca.

{{ config(materialized = 'table') }}

select
    series_id,
    fetched_at,
    state
from {{ source('grid', 'series_state') }}
