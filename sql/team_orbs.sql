-- Tabla team_orbs de Supabase: orbes de definitiva capturados por equipo y ronda (dos filas por ronda).
-- La arma dbt (models/exports/table_team_orbs.sql) desde la API de GRID: solo rondas del cruce GRID <-> vlr
-- (VCT 2026, internacionales, GC); una ronda sin fila = sin dato. Joinea con round_info por team_map_round_id.
--
-- La carga no la hace el upload diario (Actions no tiene datos de GRID). Primera carga: rktdata (2026-11-20,
-- handoff/RKTDATA_TEAM_ORBS.md). Desde el 2026-11-23, a mano desde este repo: python -m vlr_pipeline upload-grid.
create table if not exists public.team_orbs (
  "team_map_round_id" text not null,
  "team_id_vlr" text not null,
  "series_id" text,
  "map_id" text,
  "map" text,
  "round" integer,
  "team" text,          -- tag del equipo cuando se jugo (el de round_info)
  "side" text,          -- atk / def, lado del equipo en la ronda
  "orbs" integer not null,
  "tour_id" text,
  primary key ("team_map_round_id", "team_id_vlr")
);

create index if not exists team_orbs_series_id_idx on public.team_orbs ("series_id");
create index if not exists team_orbs_map_id_idx on public.team_orbs ("map_id");
