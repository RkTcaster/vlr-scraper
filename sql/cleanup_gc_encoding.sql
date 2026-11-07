-- Filas huerfanas de Game Changers 2026 Championship Sao Paulo con el nombre en mojibake (U+FFFD).
-- Las subio una version vieja de build_region_tournament (antes de json_text, commit befc723);
-- el pipeline actual genera solo 'game_changers_2026_championship_são_paulo' y ninguna fila de
-- tournament_played con tour_id/reg_id vacios. El upsert nunca borra, por eso hay que hacerlo a mano.

-- revisar antes de borrar
select * from public.tournament where tour_id like 'game_changers_2026_championship_s%o_paulo';
select * from public.tournament_played where tour_id = '' or reg_id = '';

-- limpieza
delete from public.tournament_played where tour_id = '' and reg_id = '';
delete from public.tournament
where tour_id like 'game_changers_2026_championship_s%o_paulo'
  and tour_id <> 'game_changers_2026_championship_são_paulo';
