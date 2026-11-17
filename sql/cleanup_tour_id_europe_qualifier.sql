-- Europe Qualifier: vlr renombro el evento a "Europe Open Qualifier" (2026-11-16), asi que el
-- Qualifier #1 quedo con el tour_id 'vct_2027_emea_kickoff_-_europe_qualifier' y el #2 con
-- 'vct_2027_emea_kickoff_-_europe_open_qualifier'. Se unifico todo en el segundo
-- (scripts/merge_tournament.py); esto borra las filas subidas con el tour_id viejo.
--
-- Correr ANTES del upload: al borrar las series de match_id, el upload incremental las ve como
-- pendientes y vuelve a subir sus tablas fact con el tour_id nuevo.
-- El filtro es por igualdad exacta: nunca toca las filas de europe_open_qualifier.

-- 1. revisar: un solo tour_id (el viejo); match_id tiene que dar 219
select 'match_id' t, tour_id, count(*) from match_id where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier' group by 2
union all select 'maps_id', tour_id, count(*) from maps_id where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier' group by 2
union all select 'round_info', tour_id, count(*) from round_info where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier' group by 2
union all select 'team_economy', tour_id, count(*) from team_economy where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier' group by 2
union all select 'player_stats', tour_id, count(*) from player_stats where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier' group by 2
union all select 'player_performance', tour_id, count(*) from player_performance where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier' group by 2
union all select 'round_buy', tour_id, count(*) from round_buy where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier' group by 2
union all select 'round_summary', tour_id, count(*) from round_summary where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier' group by 2
union all select 'round_events', tour_id, count(*) from round_events where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier' group by 2
union all select 'tournament_played', tour_id, count(*) from tournament_played where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier' group by 2
union all select 'tournament', tour_id, count(*) from tournament where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier' group by 2;

-- 2. borrar (tablas fact primero, tournament al final por si hay FK)
begin;
delete from round_events       where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier';
delete from round_summary      where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier';
delete from round_buy          where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier';
delete from player_performance where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier';
delete from player_stats       where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier';
delete from team_economy       where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier';
delete from round_info         where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier';
delete from draft              where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier';
delete from maps_id            where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier';
delete from match_id           where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier';
delete from tournament_played  where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier';
delete from tournament_slots   where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier';
delete from tournament         where tour_id = 'vct_2027_emea_kickoff_-_europe_qualifier';
commit;

-- 3. despues del upload: un solo tour_id de Europa, con 639 series
select tour_id, match_format, year, stage, subregion from tournament where tour_id like '%europe%qualifier';
select count(*) from match_id where tour_id = 'vct_2027_emea_kickoff_-_europe_open_qualifier';
