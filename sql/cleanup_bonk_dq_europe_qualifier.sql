-- 2026-11-09: BONK descalificado en el VCT 2027 EMEA Kickoff - Europe Qualifier.
-- vlr hizo rollback de sus partidos desde el ro32:
--   784786 BONK vs Aurora (ro32)       -> ahora "forfeited by BONK": queda skipped, sin filas
--   784798 BONK vs Project 100K (ro16) -> ahora Aurora vs Project 100K (otros mapas y jugadores)
--   784804 BONK vs ycatble (ro8)       -> ahora Aurora vs ycatble
-- Los csv ya estan re-scrapeados. El upsert nunca borra y las filas viejas tienen otra PK (tricode BONK
-- en team_map_round_id, otros map_id / player_id_vlr), asi que hay que borrarlas a mano.
-- Correr ANTES del proximo upload: sin la fila en match_id, el incremental vuelve a mandar 784798 y
-- 784804 completos; 784786 ya no esta en tables/ y no vuelve.
-- Las 3 series anteriores de BONK (784618, 784714, 784762: ro256-ro64) no cambiaron en vlr.

begin;

delete from public.round_summary      where series_id::text in ('784786', '784798', '784804');
delete from public.round_events       where series_id::text in ('784786', '784798', '784804');
delete from public.round_buy          where series_id::text in ('784786', '784798', '784804');
delete from public.player_performance where series_id::text in ('784786', '784798', '784804');
delete from public.player_stats       where series_id::text in ('784786', '784798', '784804');
delete from public.team_economy       where series_id::text in ('784786', '784798', '784804');
delete from public.round_info         where series_id::text in ('784786', '784798', '784804');
delete from public.draft              where series_id::text in ('784786', '784798', '784804');
delete from public.maps_id            where series_id::text in ('784786', '784798', '784804');
delete from public.match_id           where series_id::text in ('784786', '784798', '784804');

commit;
