{#
    Normaliza un nick para comparar GRID contra vlr:
      'TenZ '      -> 'tenz'
      'Rosé'       -> 'rose'        (sin acentos)
      'Toura だ'   -> 'touraだ'     (a diferencia de normalize_team_name, conserva letras de cualquier alfabeto)
      'm a x'      -> 'max'         (vlr a veces guarda espacios dobles; se saca todo lo que no sea letra o numero)
    Solo para texto real (utf-8 decodificado), no para la "forma html" de vlr (ver CLAUDE.md, Encoding).
#}
{% macro normalize_player_name(column) -%}
    nullif(regexp_replace(lower(strip_accents({{ column }})), '[^\p{L}\p{N}]', '', 'g'), '')
{%- endmacro %}
