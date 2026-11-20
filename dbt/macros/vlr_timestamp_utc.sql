{#
    Fecha de vlr (texto 'YYYY-MM-DD HH:MM:SS', hora de America/New_York, sin zona) -> timestamptz en UTC.
    vlr publica la hora programada de la serie en hora de Nueva York (4 h de diferencia con UTC en horario de
    verano, 5 h en invierno); asi las fechas de vlr se pueden comparar con las de GRID.
#}
{% macro vlr_timestamp_utc(column) -%}
    timezone('America/New_York', cast({{ column }} as timestamp))
{%- endmacro %}
