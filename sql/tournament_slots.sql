-- Tabla tournament_slots de Supabase (la llena vlr_pipeline/upload.py desde tables/table_tournament_slots.csv).
-- Una fila por plaza de un evento: "slots" de events.json da la cantidad (slot 1..N) y
-- "relevant_teams" (a mano, en orden) los equipos que las ocupan. team_id NULL = plaza todavia sin
-- definir. No toca teams.relevant (columna manual de rviewer).
-- Correr una vez en el SQL editor de Supabase ANTES de la primera corrida con algun evento con "slots"
-- (mientras la tabla sale vacia el upload no la toca).
-- El upsert no borra: si se bajan los slots de un evento (3 -> 2) la fila del slot 3 queda; borrarla a mano.
create table if not exists public.tournament_slots (
  "tour_id" text not null,
  "slot" smallint not null,
  "team_id" text,
  primary key ("tour_id", "slot")
);
