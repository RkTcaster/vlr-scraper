{#
    Normaliza un nombre o tag de equipo para comparar GRID contra vlr:
      'Gentle Mates (2)' -> 'gentlemates'    (GRID numera equipos con el mismo nombre: se saca el sufijo)
      'KRÜ Esports'      -> 'kruesports'     (sin acentos ni dieresis)
      ' VIL'             -> 'vil'            (solo letras y numeros, en minuscula)
    Solo para texto real (utf-8 decodificado). No usar con texto en "forma html" de vlr (ver CLAUDE.md, Encoding).
#}
{% macro normalize_team_name(column) -%}
    nullif(
        regexp_replace(
            lower(strip_accents(regexp_replace({{ column }}, '\s*\(\d+\)\s*$', ''))),
            '[^a-z0-9]', '', 'g'
        ),
        ''
    )
{%- endmacro %}
