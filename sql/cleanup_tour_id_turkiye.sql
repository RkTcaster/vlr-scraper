-- Türkiye Qualifier: borra las filas subidas con el tour_id roto
--   'vct_2027_emea_kickoff_-_tã¼rkiye_qualifier'   (lower() sobre el nombre en forma html, 2026-11-11)
-- El tour_id correcto es 'vct_2027_emea_kickoff_-_türkiye_qualifier'.
--
-- Correr ANTES del upload: al borrar las 48 series de match_id, el upload incremental las ve como
-- pendientes y vuelve a subir sus tablas fact con el tour_id nuevo.
-- El filtro no depende de pegar bien los caracteres rotos y nunca toca las filas con el tour_id correcto,
-- asi que se puede volver a correr sin riesgo.

-- 1. revisar: tiene que listar un solo tour_id (el roto) con estos conteos
--    match_id 48, maps_id 102, round_info 1885, team_economy 1825, player_stats 1011,
--    player_performance 1000, round_buy 1849, round_summary 1849, round_events 14632,
--    tournament_played 95, tournament 1
select 'match_id' t, tour_id, count(*) from match_id
  where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier' group by 2
union all select 'maps_id', tour_id, count(*) from maps_id
  where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier' group by 2
union all select 'round_info', tour_id, count(*) from round_info
  where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier' group by 2
union all select 'team_economy', tour_id, count(*) from team_economy
  where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier' group by 2
union all select 'player_stats', tour_id, count(*) from player_stats
  where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier' group by 2
union all select 'player_performance', tour_id, count(*) from player_performance
  where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier' group by 2
union all select 'round_buy', tour_id, count(*) from round_buy
  where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier' group by 2
union all select 'round_summary', tour_id, count(*) from round_summary
  where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier' group by 2
union all select 'round_events', tour_id, count(*) from round_events
  where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier' group by 2
union all select 'tournament_played', tour_id, count(*) from tournament_played
  where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier' group by 2
union all select 'tournament', tour_id, count(*) from tournament
  where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier' group by 2;

-- 2. borrar (tablas fact primero, tournament al final por si hay FK)
begin;
delete from round_events       where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier';
delete from round_summary      where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier';
delete from round_buy          where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier';
delete from player_performance where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier';
delete from player_stats       where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier';
delete from team_economy       where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier';
delete from round_info         where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier';
delete from draft              where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier';
delete from maps_id            where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier';
delete from match_id           where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier';
delete from tournament_played  where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier';
delete from tournament_slots   where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier';
delete from tournament         where tour_id like 'vct_2027_emea_kickoff_-_t%rkiye_qualifier' and tour_id <> 'vct_2027_emea_kickoff_-_türkiye_qualifier';
commit;

-- 3. despues del upload: un solo tour_id de Türkiye, con subregion 'Türkiye' y match_format 'reduced'
select tour_id, match_format, year, stage, subregion from tournament where tour_id like '%rkiye%';
select count(*) from match_id where tour_id = 'vct_2027_emea_kickoff_-_türkiye_qualifier';   -- 48 o mas
