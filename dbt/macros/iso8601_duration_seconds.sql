{#
    Duracion ISO 8601 de GRID ('PT4H47M43.648S', 'PT2M25.559S') a segundos (double).

    Una macro es una funcion de Jinja que devuelve SQL: dbt la reemplaza al compilar. Esta se usa en serie,
    mapa (y mas adelante ronda), asi la regex vive en un solo lugar. Ver el SQL resultante en target/compiled/.
#}
{% macro iso8601_duration_seconds(column) -%}
    (
        coalesce(try_cast(regexp_extract({{ column }}, '([0-9.]+)H', 1) as double), 0) * 3600
      + coalesce(try_cast(regexp_extract({{ column }}, '([0-9.]+)M', 1) as double), 0) * 60
      + coalesce(try_cast(regexp_extract({{ column }}, '([0-9.]+)S', 1) as double), 0)
    )
{%- endmacro %}
