-- Analysis: SQL que dbt compila (resuelve ref/source) pero NO ejecuta ni materializa. Sirve para consultas que
-- queremos versionar junto al proyecto sin convertirlas en un modelo.
--
-- Correr:  dbt show -s grid_draft_coverage --limit 100
--   (o dbt compile -s grid_draft_coverage y ejecutar el SQL de target/compiled/vlr_analytics/analyses/)
--
-- Que torneos y desde cuando tienen el veto de mapas en GRID. Al 2026-11-19: ~90% en VCT Americas / EMEA,
-- Masters y Champions desde el primer partido del ano; parcial en GC (7/18) y MENA Pulse (5/32); nada en
-- Pacific, CN ni Challengers. Depende de la liga, no de la fecha ni de la version del Series State.

select
    s.event_name,
    count(*)                                                    as series,
    count(*) filter (where st.has_draft)                        as with_draft,
    round(100.0 * count(*) filter (where st.has_draft) / count(*), 0) as pct_draft,
    min(s.scheduled_at)::date                                   as first_series,
    min(s.scheduled_at) filter (where st.has_draft)::date       as first_draft,
    max(s.scheduled_at) filter (where st.has_draft)::date       as last_draft,
    string_agg(distinct st.state_version, ', ' order by st.state_version) as versions

from {{ ref('stg_grid__series') }} as s
join {{ ref('stg_grid__series_states') }} as st using (grid_series_id)
group by s.event_name
order by with_draft desc, series desc
