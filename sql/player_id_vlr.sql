-- player_id_vlr: id de jugador de vlr (/player/<id>/) como identidad del jugador (2026-11-07).
-- Hasta aca el jugador era su nick: players tenia PK player_id = <team>_<nick> y player_stats /
-- player_performance PK (map_id, player). Dos jugadores con el mismo nick en el mismo equipo
-- (785988, VCT 2027 LATAM South: dos "Splotza" en RADI, /player/69551 y /player/50487) rompian
-- las tres PK y el upload. player_id sigue como columna legacy (ya no unica) para rktdata.
--
-- Correr una vez en el SQL editor de Supabase y en seguida `python -m vlr_pipeline upload --full`
-- (con tables/ ya regenerado con este cambio). Incluye al principio las limpiezas de Game Changers
-- y Hush que reporto rktdata (paso 0) y el borrado de las filas con tricodes en minuscula (paso 0b):
--   * players, player_stats y player_performance se VACIAN: sus filas viejas no tienen
--     player_id_vlr y no pueden quedar en una PK not null. Quedan vacias hasta que termina el
--     upload --full (unos minutos), asi que rktdata no ve jugadores en ese rato.
--   * El resto de las tablas solo suma columnas nullable; el --full las llena.
-- Si algun "drop constraint" falla por una foreign key de otra tabla (p.ej. de rktdata) hacia
-- players.player_id, hay que borrar o rehacer esa FK primero: no se usa cascade a proposito.

begin;

-- 0. limpiezas pendientes del 2026-11-06 que rktdata volvio a reportar el 2026-11-07 ------------
-- (mismo contenido que sql/cleanup_gc_encoding.sql y sql/agent_hush.sql, que no se habian corrido)
-- Game Changers con el nombre en mojibake: 1 fila de mas en tournament y 10 en tournament_played
-- con tour_id/reg_id vacios. El pipeline actual ya no las genera; el upsert nunca borra.
delete from public.tournament_played where tour_id = '' and reg_id = '';
delete from public.tournament
where tour_id like 'game_changers_2026_championship_s%o_paulo'
  and tour_id <> 'game_changers_2026_championship_são_paulo';
-- Hush: agent_info no la sube el pipeline (rktdata mantiene la columna rol a mano), queda con rol vacio
insert into public.agent_info (agent_name, agent_path)
select 'Hush', 'agents/hush.png'
where not exists (select 1 from public.agent_info where agent_name = 'Hush');

-- 0b. tricodes en mayusculas (tables.upper_tag, 2026-11-07) -------------------------------------
-- El pipeline pasa todo tag de equipo a mayusculas ("Sun" -> "SUN", "Risi" -> "RISI"). Cambia la PK
-- de las filas de esos equipos (team_id, (tour_id, teamA), team_map_round_id lleva los tags): las
-- viejas quedarian huerfanas, el upsert nunca borra. Se borran aca y el upload --full las vuelve a
-- subir con el tag nuevo (~23 equipos de qualifiers, ~1045 rondas). round_events no tiene team_a/b:
-- va por los team_map_round_id de round_info, antes de borrar round_info.
delete from public.round_events where team_map_round_id in (
  select team_map_round_id from public.round_info
  where "teamA" <> upper("teamA") or "teamB" <> upper("teamB"));
delete from public.round_summary where team_a <> upper(team_a) or team_b <> upper(team_b);
delete from public.round_buy where team_a <> upper(team_a) or team_b <> upper(team_b);
delete from public.team_economy where team_a <> upper(team_a) or team_b <> upper(team_b);
delete from public.round_info where "teamA" <> upper("teamA") or "teamB" <> upper("teamB");
delete from public.tournament_played where "teamA" <> upper("teamA");
delete from public.teams where team_id <> upper(team_id);

-- 1. columnas nuevas ---------------------------------------------------------------------------
alter table public.players add column if not exists "player_id_vlr" text;
alter table public.player_stats add column if not exists "player_id_vlr" text;
alter table public.player_performance add column if not exists "player_id_vlr" text;

-- round_buy: player_N_team_x_id = id de vlr del jugador de ese slot (tables.ROUND_BUY_FIELDS)
alter table public.round_buy
  add column if not exists "player_1_team_a_id" text,
  add column if not exists "player_2_team_a_id" text,
  add column if not exists "player_3_team_a_id" text,
  add column if not exists "player_4_team_a_id" text,
  add column if not exists "player_5_team_a_id" text,
  add column if not exists "player_1_team_b_id" text,
  add column if not exists "player_2_team_b_id" text,
  add column if not exists "player_3_team_b_id" text,
  add column if not exists "player_4_team_b_id" text,
  add column if not exists "player_5_team_b_id" text;

-- round_events / round_summary (tables.ROUND_EVENTS_COLUMNS / ROUND_SUMMARY_COLUMNS)
alter table public.round_events
  add column if not exists "player_id_vlr" text,
  add column if not exists "victim_id_vlr" text;
alter table public.round_summary
  add column if not exists "fb_player_id_vlr" text,
  add column if not exists "fb_victim_id_vlr" text,
  add column if not exists "plant_player_id_vlr" text,
  add column if not exists "defuse_player_id_vlr" text;

create index if not exists round_events_player_id_vlr_idx on public.round_events (player_id_vlr);
create index if not exists round_events_victim_id_vlr_idx on public.round_events (victim_id_vlr);

-- 2. PK nuevas (las PK viejas se crearon a mano: se buscan por catalogo, no por nombre) --------
delete from public.player_stats;
delete from public.player_performance;
delete from public.players;

do $$
declare
  t text;
  c text;
begin
  foreach t in array array['players', 'player_stats', 'player_performance'] loop
    select conname into c
    from pg_constraint
    where conrelid = format('public.%I', t)::regclass and contype = 'p';
    if c is not null then
      execute format('alter table public.%I drop constraint %I', t, c);
    end if;
  end loop;
end $$;

alter table public.players alter column "player_id_vlr" set not null;
alter table public.players add primary key ("player_id_vlr");

alter table public.player_stats alter column "player_id_vlr" set not null;
alter table public.player_stats add primary key ("map_id", "player_id_vlr");

alter table public.player_performance alter column "player_id_vlr" set not null;
alter table public.player_performance add primary key ("map_id", "player_id_vlr");

-- player_id deja de ser unico (dos jugadores con el mismo nick y equipo): indice comun para rktdata
create index if not exists players_player_id_idx on public.players (player_id);

commit;
