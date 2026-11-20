-- Resumen de mart_player_map_source_comparison: por metrica, cuantas filas coinciden y cuanto difieren.
-- dbt show -s source_comparison_summary
--   pct_equal       filas con el mismo valor en las dos fuentes
--   pct_within_1    |diff| <= 1 (un kill de mas o de menos, redondeos de porcentaje)
--   mean_diff       sesgo: positivo = GRID da mas que vlr
--   ratio           sum(grid) / sum(vlr)

select
    metric,
    count(*)                                                        as n,
    count(grid_value)                                               as n_with_grid,
    round(100.0 * avg(is_equal::int), 2)                            as pct_equal,
    round(100.0 * avg((abs(diff) <= 1)::int), 2)                    as pct_within_1,
    round(avg(diff), 2)                                             as mean_diff,
    round(avg(abs(diff)), 2)                                        as mean_abs_diff,
    round(sum(grid_value) / nullif(sum(vlr_value), 0), 3)           as ratio,
    round(corr(vlr_value, grid_value), 3)                           as corr
from {{ ref('mart_player_map_source_comparison') }}
group by metric
order by metric
