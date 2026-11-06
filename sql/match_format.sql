-- Columna match_format en match_id y tournament (la llena vlr_pipeline/upload.py).
-- full: torneo con picks/bans. reduced: qualifiers donde vlr no carga el draft (bans ni
-- mapa decider), marcados con "format": "reduced" en events.json. tournament puede valer
-- tambien mixed si un torneo tiene matches de los dos formatos.
-- Correr una vez en el SQL editor de Supabase ANTES de la proxima corrida del pipeline con
-- este cambio: el upsert manda la columna siempre, y si no existe falla match_id/tournament
-- (y sin match_id las series quedan pendientes y se reintentan cada dia).
-- El default 'full' deja bien marcadas las filas existentes sin tener que correr --full.
alter table public.match_id add column if not exists "match_format" text not null default 'full';
alter table public.tournament add column if not exists "match_format" text not null default 'full';
