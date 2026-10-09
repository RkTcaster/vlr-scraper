-- Tablas round_events y round_summary de Supabase (las llena vlr_pipeline/upload.py desde
-- tables/table_round_events.csv y tables/table_round_summary.csv). Joinean con round_info por team_map_round_id.
-- Columnas = vlr_pipeline.tables.ROUND_EVENTS_COLUMNS / ROUND_SUMMARY_COLUMNS: si cambian, actualizar aca.
-- Correr una vez en el SQL editor de Supabase ANTES de la proxima corrida del pipeline que
-- tenga filas de round_events (si la tabla no existe, el upsert falla y la serie no se marca en match_id).

-- Una fila por kill / plant / defuse. t_sec = segundos desde el inicio de la ronda.
-- player/team = killer (o quien planto/defuseo); victim solo en kills.
-- pos_x/pos_y = victima (o spike), from_x/from_y = killer.
-- is_team_kill: victima del mismo equipo (spike, caida); no cuenta para first blood ni trades.
-- is_trade: mata a quien mato a un companero hace <= 5 s; is_traded: esa muerte fue tradeada.
create table if not exists public.round_events (
  "team_map_round_id" text not null,
  "ev_index" integer not null,
  "series_id" text,
  "map_id" text,
  "map" text,
  "round" integer,
  "reg_id" text,
  "tour_id" text,
  "t_sec" integer,
  "type" text,
  "player" text,
  "player_id" text,
  "team" text,
  "side" text,
  "victim" text,
  "victim_id" text,
  "victim_team" text,
  "weapon" text,
  "site" text,
  "pos_x" real,
  "pos_y" real,
  "from_x" real,
  "from_y" real,
  "is_first_blood" boolean,
  "is_team_kill" boolean,
  "is_post_plant" boolean,
  "is_trade" boolean,
  "is_traded" boolean,
  primary key ("team_map_round_id", "ev_index")
);

create index if not exists round_events_series_id_idx on public.round_events (series_id);
create index if not exists round_events_player_id_idx on public.round_events (player_id);

-- Una fila por ronda con eventos. team_a/team_b/side_team_a = teamA/teamB/side de round_info.
-- kills_* / trades_* sin team kills. last_event_t = tiempo del ultimo evento (aprox. de la duracion).
create table if not exists public.round_summary (
  "team_map_round_id" text primary key,
  "series_id" text,
  "map_id" text,
  "round" integer,
  "reg_id" text,
  "tour_id" text,
  "team_a" text,
  "team_b" text,
  "side_team_a" text,
  "fb_player_id" text,
  "fb_team" text,
  "fb_victim_id" text,
  "fb_t" integer,
  "plant_t" integer,
  "plant_site" text,
  "plant_player_id" text,
  "defuse_t" integer,
  "defuse_player_id" text,
  "kills_team_a" integer,
  "kills_team_b" integer,
  "trades_team_a" integer,
  "trades_team_b" integer,
  "last_event_t" integer
);

create index if not exists round_summary_series_id_idx on public.round_summary (series_id);
