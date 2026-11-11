-- team_id_vlr: id de equipo de vlr (/team/<id>/) como identidad del equipo (2026-11-10, fase 1).
-- Hasta aca teams tenia PK team_id = tricode. El tricode se repite entre equipos distintos (20 tags
-- con rosters disjuntos: THE en cuatro qualifiers, FUR = FURIA y un equipo del Brazil Open
-- Qualifier, NOVA, TS, MIBR...) y hasta en un mismo match (785082, FAKE vs FAKE): esos equipos se
-- mezclaban en una sola fila. team_id sigue como columna (ya no unica) y name pasa a venir lleno.
--
-- Fase 1 (este archivo): teams con PK team_id_vlr, y columnas nuevas nullable en players,
-- player_stats y round_info. Las PK de las tablas fact (team_map_round_id, etc.) NO cambian todavia.
--
-- Orden:
--   1. tables/ regenerado con el backfill completo (scripts/backfill_team_ids.py), si no los equipos
--      salen tbd_<TAG>.
--   2. Paso A en el SQL editor de Supabase.
--   3. python -m vlr_pipeline upload --full
--   4. Paso B (restaura teams.relevant, columna manual de rviewer).
-- Entre 2 y 3 teams queda vacia (unos minutos). Si algun "drop constraint" o el delete fallan por
-- una foreign key de otra tabla hacia teams.team_id, hay que borrar o rehacer esa FK primero: no
-- se usa cascade a proposito.

-- ============================== Paso A ==============================
begin;

-- relevant lo carga rviewer a mano; se guarda por tag para restaurarlo en el paso B
create table if not exists public.teams_relevant_backup as
select team_id, relevant from public.teams;

alter table public.teams add column if not exists "team_id_vlr" text;
alter table public.teams add column if not exists "name" text;

delete from public.teams;

do $$
declare
  c text;
begin
  select conname into c
  from pg_constraint
  where conrelid = 'public.teams'::regclass and contype = 'p';
  if c is not null then
    execute format('alter table public.teams drop constraint %I', c);
  end if;
end $$;

alter table public.teams alter column "team_id_vlr" set not null;
alter table public.teams add primary key ("team_id_vlr");
-- team_id (tricode) deja de ser unico: indice comun para los joins de rktdata/rviewer
create index if not exists teams_team_id_idx on public.teams (team_id);

-- columnas nuevas (el upload --full las llena)
alter table public.players add column if not exists "team_id_vlr" text;
alter table public.player_stats add column if not exists "team_id_vlr" text;
alter table public.round_info
  add column if not exists "team_a_id_vlr" text,
  add column if not exists "team_b_id_vlr" text;

create index if not exists players_team_id_vlr_idx on public.players (team_id_vlr);
create index if not exists player_stats_team_id_vlr_idx on public.player_stats (team_id_vlr);

commit;

-- ============================== Paso B (despues del upload --full) ==============================
-- Tags con un solo equipo: el relevant vuelve tal cual. Tags compartidos: se copia a todos los
-- equipos con ese tag y despues se corrige a mano (consulta de abajo): en general el relevante
-- es el de liga/internacional y el otro es de un qualifier.
-- begin;
-- update public.teams t
-- set relevant = b.relevant
-- from public.teams_relevant_backup b
-- where t.team_id = b.team_id;
-- commit;
--
-- select t.team_id, t.team_id_vlr, t.name, t.relevant
-- from public.teams t
-- where t.team_id in (select team_id from public.teams group by team_id having count(*) > 1)
-- order by t.team_id, t.team_id_vlr;
--
-- Cuando este todo bien: drop table public.teams_relevant_backup;
