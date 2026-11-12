-- Limpieza de filas huerfanas en Supabase (revision 2026-11-11, Supabase vs tables/).
-- El upsert nunca borra: son filas de reglas viejas que el csv ya no tiene.
-- Correr en orden, de a un bloque: primero el select (tiene que dar el numero esperado), despues el delete.
-- Los bloques 1 y 2 se apoyan en round_info, por eso van antes de borrar las DRX de round_info (bloque 3).

-- 1. team_economy: filas espejo (mismo team_map_round_id, team_a invertido) en americas / emea / pacific
--    kickoff 2026 y masters santiago. La buena es la que coincide con round_info."teamA".
select count(*) from team_economy e join round_info r on r.team_map_round_id = e.team_map_round_id
where e.team_a <> r."teamA";                                              -- esperado: 6304

delete from team_economy e using round_info r
where e.team_map_round_id = r.team_map_round_id and e.team_a <> r."teamA";

-- 2. round_events: NA Open Qualifier con tags en minuscula en team_map_round_id (ARR-help-...), 23 series
select count(*) from round_events e
where e.tour_id = 'vct_2027_america_kickoff_-_north_america_open_qualifier'
  and not exists (select 1 from round_info r where r.team_map_round_id = e.team_map_round_id);  -- esperado: 8150

delete from round_events e
where e.tour_id = 'vct_2027_america_kickoff_-_north_america_open_qualifier'
  and not exists (select 1 from round_info r where r.team_map_round_id = e.team_map_round_id);

-- 3. DRX -> KRX: series 644656 y 644659 (Pacific Stage 1) con el tag viejo
select count(*) from team_economy
where team_map_round_id like 'DRX-%-644656-%' or team_map_round_id like 'DRX-%-644659-%';   -- esperado: 121
select count(*) from round_info
where team_map_round_id like 'DRX-%-644656-%' or team_map_round_id like 'DRX-%-644659-%';   -- esperado: 121

delete from team_economy
where team_map_round_id like 'DRX-%-644656-%' or team_map_round_id like 'DRX-%-644659-%';
delete from round_info
where team_map_round_id like 'DRX-%-644656-%' or team_map_round_id like 'DRX-%-644659-%';

delete from tournament_played
where "teamA" = 'DRX' and tour_id = 'vct_2026_pacific_stage_1';           -- 1 fila

-- 4. draft: serie 701037 (XLG vs TEC, China Stage 2), no esta en el csv. Mirarla antes de borrar.
select * from draft where series_id = 701037;
-- delete from draft where series_id = 701037;

-- Conteos finales esperados (= tables/ del 2026-11-11)
select 'round_info' t, count(*) from round_info               -- 71290
union all select 'team_economy', count(*) from team_economy   -- 62973
union all select 'round_events', count(*) from round_events   -- 503462
union all select 'tournament_played', count(*) from tournament_played  -- 1102
union all select 'draft', count(*) from draft;                -- 738 (739 si no se borra 701037)
