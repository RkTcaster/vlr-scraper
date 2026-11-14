-- team_id_vlr, fase 2 (2026-11-13): id de equipo de vlr en las tablas por partido, pedido de rviewer
-- (handoff/VLR_SCRAPER_TEAM_ID_FASE_2.md). Solo se AGREGAN columnas: team_map_round_id y las demas
-- PK de las tablas fact no cambian, salvo:
--   - tournament_played: PK (tour_id, teamA) -> (tour_id, team_id_vlr). Dos equipos con el mismo tag
--     en un torneo (FAKE/FAKE, los THE) eran una sola fila.
--   - team_economy: PK (team_a, team_map_round_id) -> (team_map_round_id). La vieja dejo duplicar las
--     filas espejo (limpiadas con sql/cleanup_huerfanas_2026_11_11.sql).
-- Ademas borra filas que el upload --full no pisa:
--   - player_stats de mapas no jugados (tour_id vacio, 80 filas: el mapa 3 de un 2-0, 787312 Sunset...).
--   - 4 mapas con el nombre equivocado (787286-TBD, 787408-Bind, 788432-Corrode, 788465-Lotus): el mapa
--     anterior no se jugo y round_detail les puso su nombre. Con el parser arreglado son otro map_id.
--
-- Orden:
--   1. Paso A en el SQL editor de Supabase (una transaccion).
--   2. python -m vlr_pipeline upload --full  (llena las columnas nuevas y tournament_played).
--   3. Consultas de verificacion del final.
-- Entre 1 y 2 tournament_played queda vacia (unos minutos) y las columnas nuevas en null.

-- ============================== Paso A ==============================
begin;

-- columnas nuevas (texto, como las de fase 1; tbd_<TAG> = equipo sin pagina en vlr)
alter table public.draft
  add column if not exists "team_id_vlr" text,
  add column if not exists "rival_id_vlr" text;
alter table public.team_economy
  add column if not exists "team_a_id_vlr" text,
  add column if not exists "team_b_id_vlr" text;
alter table public.round_buy
  add column if not exists "team_a_id_vlr" text,
  add column if not exists "team_b_id_vlr" text;
alter table public.round_summary
  add column if not exists "team_a_id_vlr" text,
  add column if not exists "team_b_id_vlr" text,
  add column if not exists "fb_team_id_vlr" text;
alter table public.round_events
  add column if not exists "team_id_vlr" text,
  add column if not exists "victim_team_id_vlr" text;
alter table public.player_performance add column if not exists "team_id_vlr" text;
alter table public.tournament_played add column if not exists "team_id_vlr" text;

-- tournament_played: se vacia y cambia la PK (el upload --full la vuelve a llenar)
delete from public.tournament_played;
do $$
declare
  c text;
begin
  select conname into c from pg_constraint
  where conrelid = 'public.tournament_played'::regclass and contype = 'p';
  if c is not null then
    execute format('alter table public.tournament_played drop constraint %I', c);
  end if;
end $$;
alter table public.tournament_played alter column "team_id_vlr" set not null;
alter table public.tournament_played add primary key ("tour_id", "team_id_vlr");

-- team_economy: PK solo team_map_round_id. Si quedan duplicados, el add primary key falla y la
-- transaccion entera se deshace (revisar con la consulta de abajo antes de reintentar)
do $$
declare
  c text;
begin
  select conname into c from pg_constraint
  where conrelid = 'public.team_economy'::regclass and contype = 'p';
  if c is not null then
    execute format('alter table public.team_economy drop constraint %I', c);
  end if;
end $$;
alter table public.team_economy add primary key ("team_map_round_id");

-- mapas no jugados en player_stats (3d del pedido; 787286-Bind vuelve con el upload --full)
delete from public.player_stats where tour_id is null or tour_id = '';

-- mapas mal nombrados: un mapa no jugado ANTES del jugado le daba su nombre a las rondas del
-- siguiente. El upload --full sube los correctos (787286-Bind, 787408-Corrode, 788432-Sunset,
-- 788465-Abyss); los viejos son otro map_id y el upsert no los pisa
delete from public.round_events where map_id in ('787286-TBD', '787408-Bind', '788432-Corrode', '788465-Lotus');
delete from public.round_summary where map_id in ('787286-TBD', '787408-Bind', '788432-Corrode', '788465-Lotus');
delete from public.round_buy where map_id in ('787286-TBD', '787408-Bind', '788432-Corrode', '788465-Lotus');
delete from public.team_economy where map_id in ('787286-TBD', '787408-Bind', '788432-Corrode', '788465-Lotus');
delete from public.player_stats where map_id in ('787286-TBD', '787408-Bind', '788432-Corrode', '788465-Lotus');
delete from public.player_performance where map_id in ('787286-TBD', '787408-Bind', '788432-Corrode', '788465-Lotus');
delete from public.round_info where map_id in ('787286-TBD', '787408-Bind', '788432-Corrode', '788465-Lotus');
delete from public.maps_id where map_id in ('787286-TBD', '787408-Bind', '788432-Corrode', '788465-Lotus');

-- indices para filtrar por equipo
create index if not exists draft_team_id_vlr_idx on public.draft (team_id_vlr);
create index if not exists draft_rival_id_vlr_idx on public.draft (rival_id_vlr);
create index if not exists team_economy_team_a_id_vlr_idx on public.team_economy (team_a_id_vlr);
create index if not exists team_economy_team_b_id_vlr_idx on public.team_economy (team_b_id_vlr);
create index if not exists round_buy_team_a_id_vlr_idx on public.round_buy (team_a_id_vlr);
create index if not exists round_buy_team_b_id_vlr_idx on public.round_buy (team_b_id_vlr);
create index if not exists round_summary_team_a_id_vlr_idx on public.round_summary (team_a_id_vlr);
create index if not exists round_summary_team_b_id_vlr_idx on public.round_summary (team_b_id_vlr);
create index if not exists round_events_team_id_vlr_idx on public.round_events (team_id_vlr);
create index if not exists player_performance_team_id_vlr_idx on public.player_performance (team_id_vlr);
create index if not exists tournament_played_team_id_vlr_idx on public.tournament_played (team_id_vlr);

commit;

-- Si el add primary key de team_economy falla por duplicados:
-- select team_map_round_id, count(*) from public.team_economy group by 1 having count(*) > 1 limit 20;

-- ============================== Verificacion (despues del upload --full) ==============================
-- Todas tienen que dar 0:
-- select count(*) from public.draft where team_id_vlr is null or rival_id_vlr is null;
-- select count(*) from public.team_economy where team_a_id_vlr is null or team_b_id_vlr is null;
-- select count(*) from public.round_buy where team_a_id_vlr is null or team_b_id_vlr is null;
-- select count(*) from public.round_summary where team_a_id_vlr is null or team_b_id_vlr is null;
-- select count(*) from public.player_performance where team_id_vlr is null;
-- select count(*) from public.player_stats where tour_id is null or tour_id = '';
-- select count(*) from public.round_info where map_id in ('787286-TBD', '787408-Bind', '788432-Corrode', '788465-Lotus');
-- 785082 (FAKE vs FAKE): dos equipos distintos en cada tabla
-- select distinct team_id_vlr from public.round_events where series_id = '785082';
-- select tour_id, team_id_vlr, "teamA" from public.tournament_played where "teamA" = 'FAKE';
