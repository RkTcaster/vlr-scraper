# Roadmap

Estado del pipeline vlr.gg → `csv/` → `tables/` → Supabase → rktdata.ar.
Última actualización: 2026-11-11.

## Hecho

### Base del pipeline
- Scraper por torneo (`draft_`, `player_stats_`, `player_performance_`, `round_detail_`, `team_economy_`) y
  star schema en `tables/` (`csv_process.ipynb` + paquete `vlr_pipeline/`, lógica en sync).
- GitHub Actions diario (`vlr-pipeline`, 17:00 UTC): scrape de eventos `active` → `process` → `upload` → commit de `csv/`.
- Idempotencia con `csv/scrape_log.csv` (por `series_id`, status ok/error/skipped, 3 intentos, purge antes de re-scrapear).
- Upload incremental a Supabase (`7b42dfb`): dimensiones completas, facts solo de series nuevas o re-scrapeadas,
  `match_id` al final; `--full` para re-subir todo; `csv/upload_log.csv` por corrida.
- Tests con pytest + workflow `tests.yml` (`427d310`): parsers offline con fixtures html, lookups, PKs de todas las tablas.
- Exit codes: fallo parcial del scrape → 0 + `::warning::`; 2 queda solo para argparse.
- Mapa Summit agregado a `lookups.py` / `csv_process.ipynb`.

### 2026-10-08: robustez del fetch
- `fetch.soup_open`: timeout de 30 s y 2 reintentos con backoff ante 429/5xx/errores de red.
- `process_match` entero dentro del `try`; `scrape_all` sigue con el próximo evento si uno falla.
- `tests/test_fetch_errors.py`.

### 2026-10-08: solapa logs (compras por ronda)
- `get_round_logs`: un request `?game=<id>&tab=logs` por mapa jugado (cada página trae todas las rondas).
- CSV crudos nuevos por torneo:
  - `round_buy_`: una fila por jugador y ronda: slot (orden vlr), lado, agente, escudo, arma, `spent`, `bank`.
  - `round_events_`: kills, plant y defuse, con clock, killer/víctima y equipos, arma, sitio, posiciones `pos`/`from`.
- `table_round_buy`: una fila por ronda (`player_{1..5}_team_{a,b}` + `_agent`, `_weapon`, `_shield`, `_spend`, `_bank`),
  PK `team_map_round_id`, join directo con `table_round_info`. Tabla creada en Supabase con `sql/round_buy.sql`.
- `python -m vlr_pipeline backfill-logs [--limit N] [--tournament X]` para matches scrapeados antes (columna `has_logs`
  en scrape_log; no toca status/attempts, actualiza `last_attempt` para que el incremental re-suba).
- Backfill de Champions 2026 hecho (`9b5df45`).
- Fixtures de logs para 753455 y 742481, `tests/test_round_logs.py`; notebooks actualizados.

### 2026-10-09: eventos de ronda (kills, plant, defuse)
- `table_round_events`: una fila por kill/plant/defuse desde `round_events_`, PK `team_map_round_id, ev_index`.
  `t_sec` (segundos desde el inicio de la ronda), `player_id`/`victim_id` de `table_players` (además del nick y el tag),
  lado del jugador, coordenadas `pos`/`from` y flags `is_first_blood`, `is_team_kill` (spike/caída), `is_post_plant`,
  `is_trade`/`is_traded` (ventana de 3 s, `TRADE_WINDOW`).
- `table_round_summary`: una fila por ronda con first blood (`fb_*`), plant (`plant_t`, sitio, jugador), defuse,
  kills y trades por equipo y `last_event_t`.
- DDL en `sql/round_events.sql` (crear en Supabase antes de pushear), `FILES_TO_UPLOAD`, celda en `csv_process.ipynb`
  (salida byte-idéntica al paquete), tests en `test_round_logs.py`.
- Validado con Champions 2026: las kills coinciden 100% con `killsBoth` de vlr; los first bloods, 99,6% con `fkBoth`
  (las diferencias son kills en el mismo segundo: el log no tiene sub-segundos).

### 2026-10-17: nuevo layout de la solapa economy
- vlr cambió la solapa economy (~2026-10-15): la tabla `mod-econ` pasó a ser un grid de divs (`vlr-rounds-row-col`,
  `ecc-c` / `ecr-bank` con `mod-t1`/`mod-t2`). `get_team_economy` fallaba con `list index out of range`
  (754736 y 754742 en error el 2026-10-16).
- `add_economy_rounds_grid` parsea el layout nuevo y se usa si la página lo trae; el parser viejo queda para el html
  de los fixtures. Las columnas del csv no cambian; validado contra lo scrapeado antes de 753451 (bank idéntico,
  gasto ±50 por redondeo).
- Cambios de vlr que perdemos: el valor del loadout viene redondeado a 0.1k (antes exacto) y **no se muestran las
  rondas de overtime** (siempre 24 columnas). El bank sí se puede reconstruir sumando `round_buy`, el gasto no
  (incluye habilidades).
- `process_match` borra las filas que alcanzó a guardar si falla: antes el upload subía el match a medias y
  `match_id` lo daba por subido.
- Fixture 753451 (layout nuevo + Summit 19-17) en `test_parsers.py`, test de filas parciales; notebook en sync.

### 2026-10-20: situaciones XvY (ventaja/desventaja numérica)
- La ventana de trade pasó de 5 s a 3 s (`TRADE_WINDOW`): los trades bajaron de 2573 a 2118 (20,4% → 16,8% de las
  kills). Hace falta `upload --full` para rehacer `round_events`/`round_summary` en Supabase.
- `table_round_situations`: una fila por (ronda, segmento, equipo), PK `team_map_round_id, seg_index, team`. Un
  segmento es un tramo con los vivos ya estabilizados: las kills se agrupan en clusters (una kill entra si está a
  <= `SETTLE_WINDOW` de la anterior del cluster) y el estado recién vale `SETTLE_WINDOW` segundos después de la
  última kill, así un trade no genera un 5v4 que nunca se jugó. El segmento 0 es la apertura 5v5.
- Columnas: `alive_own`/`alive_rival`/`diff_alive`/`situation`, tiempos (`t_start`, `t_end`, `duration`), lado,
  contexto de spike (`is_post_plant` por tiempo, `time_since_plant`, `plant_site`, `is_defused_later`), economía de
  `round_buy` en tres juegos (`*_start` del equipo al inicio de ronda, `*_alive` de los vivos, `*_rival_alive` de los
  vivos del rival: bank, spend, Vandal/Phantom/Operator y escudos), etiquetas (`round_win`, `win_con`) y flags de
  calidad (`has_revive`, `has_buy`, `buy_unmatched_own`, `is_t_end_estimated`).
- Los vivos se cuentan con el **set** de muertos por tag (`victim_team`): vlr no loguea las resurrecciones de Sage y
  Clove (52 de 1810 rondas, la víctima muere dos veces), así que la ronda queda marcada con `has_revive` en vez de
  dar conteos imposibles. Las team kills (spike, caída) cuentan como muerte.
- `round_win` sale siempre de `rndA`/`rndB`, nunca de los vivos: **llegar a 0 vivos no decide la ronda**. De 1607
  rondas con un equipo barrido, 34 las gana el barrido (18 por `boom`, el spike explota después del wipe).
- `table_situation_stats` (local, no se sube): win rate por torneo, equipo, lado y situación. Excluye rondas con
  `has_revive` y segmentos con un equipo barrido; `n_wins` cuenta rondas, no segmentos.
- Validado con Champions 2026: 8740 segmentos en 1810 rondas, vivos siempre en [0,5], 1810 aperturas 5v5, y win
  rates simétricos y coherentes (5v4 0,736 / 4v5 0,264; 5v1 1,000; parejos exactamente 0,500).
- Celda en `csv_process.ipynb` (salida byte-idéntica al paquete) y tests en `test_round_situations.py`.

### 2026-10-20: backfill de logs completo (537 matches) y dos bugs que destapó
- `scripts/backfill_all_logs.py`: backfill en tandas con throttle global de requests (get_round_logs pide una
  página por mapa sin pausa propia), corte si una tanda no avanza o si la tasa de error se dispara, y reanudable
  desde `scrape_log.csv`. `--redo <series_id>` vuelve a bajar los logs de series puntuales.
- Cobertura: de 1810 rondas (solo Champions) a **27 438** rondas con logs; `table_round_situations` pasó a
  129 250 segmentos / 258 500 filas. Win rates coherentes: 5v4 0,720 / 4v5 0,280; 5v1 0,999; parejos 0,500.
- **Bug 1, encoding de los nicks del JSON.** `get_round_logs` saca `by_player`/`victim` del JSON de
  `div.lg-map[data-map]`, que `json.loads` devuelve ya decodificado, mientras el resto del scraper trabaja con el
  html decodificado como iso-8859-1. Guardado con iso-8859-1 el csv quedaba en iso-8859-1 puro: `Rosé` (BBL) hacía
  que `table_round_events.csv` no fuera utf-8 válido (el upload lo habría subido con caracteres de reemplazo) y el
  nick no joineaba ni con `round_buy` (economía de vivos sobreestimada) ni con `table_players` (sin `player_id`).
  Fix: `parsers.json_text`; 2139 filas reparadas en 5 csv crudos con `scripts/fix_logs_encoding.py` (idempotente,
  sin volver a pedirle nada a vlr).
- **Bug 2, tricode renombrado (DRX -> KRX).** `round_buy` armaba `team_map_round_id` con sus propios tags: 339
  filas huérfanas. Peor, en `round_events` el tag nuevo no matcheaba `teamA`/`teamB`, así que en 322 rondas el
  `side` salía mal, `kills_team_a` quedaba en 0 (231 rondas) y `round_situations` perdía 1102 muertes (el equipo
  renombrado nunca bajaba de 5 vivos). Fix: `round_buy` toma el id y los tags de `round_info` como ya hacía
  `round_events`, y `canonical_teams` + `lookups.team_aliases` mapean el tag solo cuando no es ninguno de los dos
  de esa ronda (el renombre fue a mitad de temporada). Un tag sin mapear ahora avisa por warning.
- `tracking.save_log` escribe con `lineterminator` fijo: `to_csv` usaba `os.linesep`, así que `scrape_log.csv`
  salía con LF en Actions y CRLF en Windows y el archivo entero aparecía como cambiado (el resto de los csv los
  escribe `csv.writer`, siempre CRLF).
- Tests nuevos en `test_round_logs.py` (`json_text`, `canonical_teams`); fixtures sin cambios y celdas 17-19 del
  notebook byte-idénticas al paquete.

### 2026-10-25: Game Changers Championship y `teams.team_path`
- Evento activo: Game Changers 2026 Championship São Paulo (Champions 2026 pasó a inactivo, terminado).
- `table_teams` genera `team_path = teams/<team_id sin puntos>.png`: los tricodes de GC traen punto
  (`GEN.GC`, `MIBR.GC`, `NOVA.GC`) y los logos de rviewer se guardaron sin él. El `team_id` no cambia.
  Antes se completaba a mano en Supabase; ahora lo pisa el upsert de dimensiones (ver `handoff/SCRAPER_TEAM_PATH.md`).

### 2026-11-06: torneos de formato reducido (qualifiers sin draft)
- `events.json` acepta `"format": "reduced"` (default `full`; `--format` para `scrape --event-url`). Primer evento:
  VCT 2027 EMEA Kickoff - Europe Qualifier, donde vlr no carga picks/bans ni el mapa decider.
- `scrape_log` tiene la columna `match_format`; `scrape_event` la sincroniza sin requests, así que alcanza con
  cambiar el `format` del evento en `events.json` para re-marcar lo ya scrapeado.
- `table_match_id.match_format` (full/reduced) y `table_tournament.match_format` (full/reduced/mixed).
  En Supabase: `sql/match_format.sql`. Aviso a rktdata: `handoff/RKTDATA_MATCH_FORMAT.md`.
- `table_teams` suma los equipos de `round_detail`, porque los partidos sin draft no aparecían. Con los torneos
  actuales es el mismo conjunto: la tabla no cambia.
- Forfeits (`forfeited by X`, todos los mapas N/A): ahora quedan `skipped`/`forfeit`. Antes eran `not_final` y
  se volvían a pedir en cada corrida.
- La solapa logs de equipos chicos trae el tag con otra capitalización (`Rvan` frente a `RVAN` en round_detail):
  `same_team_case` lo corrige (también con no-ASCII: `Mörk`/`MÖRK`, comparando el texto real) antes de `team_aliases` en `round_buy`, `round_events` y `round_situations`.
- Primer upload del qualifier, bugs que destapó:
  - Nicks y tags con espacios (`VRX Velcro` de `FL R`, y de antes `lovers rock`): performance partía la celda por
    espacios, duplicaba la PK `(map_id, player)` y rechazaba la tabla entera. `performance_player_cell` lee nick y
    `div.team-tag` por separado. Se re-scrapeó performance de 80 series (12 torneos viejos incluidos) y las 68 filas
    huérfanas en Supabase (`player='lovers'`) se borran con `sql/cleanup_player_performance_split_nicks.sql`.
  - Economía con rondas que no existen en round_info (784646 Sunset, 10-13 en 0): dejaban `win_A` vacío, la columna
    pasaba a float (`"0.0"`) y el upsert smallint fallaba. Se descartan con un warning.
  - Agente nuevo `Hush` en `lookups.py` y `csv_process.ipynb` (falta `agents/hush.png` en rviewer).
  - En la solapa performance vlr trunca el tag a 4 caracteres (`Cava`, `GEN.`): no rompe nada (no es PK), queda así.

### 2026-11-07: W.O. con mapas TBD, Americas Kickoff y `player_id_vlr`
- W.O. que vlr marca `final 2:0` sin jugar (784758: todos los mapas `TBD`, stats en 0): `get_invalid_reason` los
  da `forfeit`. Un W.O. de un solo mapa (784752) se procesa, pero `get_player_stats` saltea el mapa `TBD`.
- Eventos nuevos (`reduced`): Americas Kickoff NA Open Qualifier y LATAM South/North Open Qualifier. La región se
  busca en el nombre y vlr dice "America" en singular: `region_by_id` lo normaliza a `americas`.
- **Identidad del jugador = id de vlr.** Dos jugadores con el mismo nick en el mismo equipo (785988: dos "Splotza"
  en RADI) duplicaban las PK `(map_id, player)` y `players.player_id`. Ahora:
  - `player_stats_` guarda `player_id_vlr` (link `/player/<id>/` del overview); performance y round_events guardan
    el agente (`agent`, `by_agent`, `victim_agent`) para desempatar nicks repetidos al armar las tablas.
  - `table_players` es una fila por `player_id_vlr` (PK); `player_id` queda como columna legacy no única.
  - PK en Supabase: `players (player_id_vlr)`, `player_stats` / `player_performance (map_id, player_id_vlr)`.
    Columnas `*_id_vlr` en round_events / round_summary y `player_N_team_x_id` en round_buy. `sql/player_id_vlr.sql`.
  - `round_situations` cuenta los muertos por id (con el nick, los dos Splotza eran uno).
  - `scripts/backfill_player_ids.py` completó el id en todos los `player_stats_` viejos (1238 series, 77 min,
    0 errores). Quedaron 97 filas por mapa sin id: jugadores de qualifiers sin perfil en vlr (nick con `mod-tbd`
    y sin link). `tables.raw_player_ids` les da el id real del mismo `(team, nick)` si vlr le creó perfil después
    y hay uno solo; si no, `tbd_<team>_<nick>` (34 jugadores).
  - `parsers.html_words`: el nick de performance se partía con `str.split()`, que toma como espacio el byte
    `\xa0` de un carácter utf-8 leído como latin-1 ("Toura だ#TG8" quedaba en utf-8 inválido). Los nicks se cruzan
    con `match_nick` (todo espacio colapsado). Re-scrapeadas 785877/785907 (ese nick) y 785988/786010/786021
    (Splotza: su performance era de antes de la columna `agent`).
  - `csv_process.ipynb` celda 16: `drop(columns=..., axis=1)` fallaba con pandas nuevo. Celda 8 define
    `match_id_vlr` (la usa antes de la celda 9). Tablas del notebook = package byte a byte.
  - **Tricodes siempre en mayúsculas** (`tables.upper_tag`, aplicado al leer el crudo en
    `concat_csv_from_different_folders` y en round_buy / round_events; los csv crudos no cambian). vlr mezcla:
    en qualifiers el overview trae `Risi` y round_detail `RISI`, y `players.team_id` quedaba vacío en 1449
    jugadores (ahora 0). Hay equipos con el tricode en mixto (`Sun`, `Ortx`, `eOSU`): 23 `team_id` cambian
    (`boom` y `BOOM` se unifican) y con ellos ~1045 `team_map_round_id`; el paso 0b de `sql/player_id_vlr.sql`
    borra esas filas viejas en Supabase antes del `upload --full`. `team_path` también pasa a mayúsculas
    (`teams/SUN.png`). Los tags no-ASCII se decodifican antes del `upper()` (`MÃ¶rk` -> `MÖRK`).
  - `save.append_dict_rows`: un parser que suma una columna ya no deja filas corridas bajo el header viejo.
  - Aviso a rktdata: `handoff/RKTDATA_PLAYER_ID_VLR.md`.
- rktdata reportó de nuevo la fila de Game Changers en mojibake (`s�o_paulo` en `tournament`, 10 filas con
  `tour_id = ''` en `tournament_played`) y Hush faltante en `agent_info`. El pipeline ya no los genera: eran
  `sql/cleanup_gc_encoding.sql` y `sql/agent_hush.sql`, que nunca se corrieron. Quedaron como paso 0 de
  `sql/player_id_vlr.sql`. `agent_info` sigue cargándose a mano (rktdata mantiene la columna `rol`).

### 2026-11-09: `year` / `stage` / `subregion` en `tournament`
- Pedido de rviewer (`handoff/VLR_SCRAPER_TOURNAMENT_HIERARCHY.md`) para el filtro Año → Región → Subregión →
  Torneo. `tables.tournament_hierarchy` los saca del `tour_id`: `year` = temporada del nombre (los qualifiers del
  Kickoff 2027 son 2027), `stage` con `STAGE_PATTERNS` (qualifiers antes que kickoff, game changers antes que
  champions; "Europe Qualifier" sin open/closed = `open_qualifier`), `subregion` solo en qualifiers, con el texto
  exacto del chip en `lookups.subregion_names`. Etapa desconocida -> `null` y subregión nueva -> Title Case,
  ambas con warning: agregarlas y avisar a rviewer. Mismo código en `csv_process.ipynb` (celda de torneos).
- `tournament` entra en `upload.EMPTY_AS_NULL`, así los `null` llegan como NULL y no como `""`. El csv ahora es
  el dueño de las tres columnas: lo cargado a mano el 2026-11-08 se pisa con lo mismo (test con esa tabla).

### 2026-11-09: BONK descalificado en el Europe Qualifier
- vlr hizo rollback desde el ro32: 784786 (BONK vs Aurora) pasó a `forfeited by BONK` y en 784798 / 784804
  (ro16 / ro8, mismos `series_id`) ahora juega Aurora. Se borraron del `scrape_log` y se re-scrapearon; los
  tres partidos anteriores de BONK no cambiaron.
- Bug: un match ya scrapeado que después pasa a forfeit/showmatch quedaba `skipped` pero con sus filas viejas en
  `csv/` (la rama skipped volvía antes de purgar, y `get_basic_match_info` falla sin tricodes). Ahora purga con el
  evento del `<title>` (`scraper.title_event`; también en `vlr_scraper.ipynb`).
- Supabase: `sql/cleanup_bonk_dq_europe_qualifier.sql` borra las tres series de las tablas fact y de
  `match_id` (las filas viejas tienen otra PK y el upsert no las pisa). Correrlo antes del próximo upload.

### 2026-11-09: MENA Qualifier y Brazil Open Qualifier
- Eventos nuevos (`reduced`) en `events.json`: VCT 2027 EMEA Kickoff - MENA Qualifier (3167, todavía sin jugar)
  y VCT 2027 Americas Kickoff - Brazil Open Qualifier (3187). Subregiones nuevas en `lookups.subregion_names`:
  `MENA` y `Brazil` (aviso a rviewer: `handoff/RVIEWER_SUBREGIONES_NUEVAS.md`).
- Brazil: 19 partidos quedaron en `live` en vlr con rondas posteriores ya jugadas (algunos con 1-2 mapas
  cargados). No se registran en scrape_log y se vuelven a mirar en cada corrida sin requests: entran solos si
  vlr los cierra. Si no los cierra nunca, esas series faltan: no se fuerzan (ver "Partidos sin terminar").
- Primer scrape de Brazil (local): 163 ok, 24 forfeit. 787313 falló porque vlr mostró un ACS CT de `1,079`
  con separador de miles; `parse_stat_value` (overview, también en `vlr_scraper.ipynb`) ahora saca las comas.

### 2026-11-09: plazas por evento (`slots` / `relevant_teams`)
- `events.json` acepta `"slots": N` y `"relevant_teams"` (tricodes a mano, en orden, hasta N). `process` (y
  `csv_process.ipynb`) generan `table_tournament_slots` (`tour_id, slot, team_id`), que se sube como dimensión a
  la tabla nueva `tournament_slots` (`sql/tournament_slots.sql`). No toca `teams.relevant`. Ver `COMMANDS.md`.

### 2026-11-09: `end_date` en eventos
- `events.json` acepta `"end_date": "YYYY-MM-DD"`: el evento se deja de scrapear `end_date` + 3 días después, sin
  reescribir el archivo (`config.is_active`). Fechas cargadas desde "Dates" de vlr: Americas Open Qualifiers (NA,
  Brazil, LATAM South/North) 2026-11-16, Europe Qualifier 2026-12-05, MENA Qualifier 2026-12-06.

### 2026-11-10: id de equipo de vlr (`team_id_vlr`, fase 1)
- El tricode no identifica al equipo: 20 tags compartidos por equipos sin relación (`THE` en cuatro qualifiers,
  `LOS` en tres, `FUR` = FURIA y un equipo del Brazil Open Qualifier, `NOVA`, `TS`, `MIBR`) y 785082 es
  `FAKE` vs `FAKE`. En `teams` se mezclaban en una fila y `players.team_id` apuntaba a cualquiera.
- `get_team_ids` saca el id del header del match (`a.match-header-link` mod-1/mod-2). Crudos: `round_detail_`
  suma `team_a_id_vlr`, `team_b_id_vlr`, `team_a_name`, `team_b_name`; `player_stats_` suma `team_id_vlr`
  por posición de la `ovw-table` (no por tag, por FAKE vs FAKE).
- Tablas: `teams` una fila por `team_id_vlr` (PK nueva) con `team_id` (tag, ya no único) y `name` del partido más
  reciente; `team_id_vlr` en `players` y `player_stats`, `team_a_id_vlr`/`team_b_id_vlr` en `round_info`. Sin id
  (equipo sin página en vlr): `tbd_<TAG>`. `players.team_id` ya no sale de un merge con `teams` (con tags
  repetidos duplicaba jugadores). Las demás tablas no cambian (verificado contra el build anterior).
- `scripts/backfill_team_ids.py`: 1 request al overview por serie, reanudable; solo agrega columnas (verificado
  byte a byte). SQL: `sql/team_id_vlr.sql`. Notebooks en sync (`vlr_scraper.ipynb` celda 2, `csv_process.ipynb`
  celdas 7, 9, 14 y 16). Tests en `tests/test_team_ids.py`.

### 2026-11-11: nick cortado por `get_text(strip=True)`
- `strip()` de str recorta `\x85` y `\xa0`, que en el html decodificado como latin-1 son el último byte de un
  carácter utf-8: "blong ฅ" (jugador 70389, Brazil Open Qualifier) quedaba sin el `85` en `player_stats_` y
  `round_buy_` y dejaba utf-8 inválido en 5 tablas. Las stats no se perdían (`match_nick` igualaba los dos nicks).
- `parsers.html_text` (strip solo ASCII) en los nicks y tags del overview y de la solapa logs; notebook en sync
  (`vlr_scraper.ipynb` celda 2). Series 787305 y 787378 re-scrapeadas; `csv/` y `tables/` sin líneas no utf-8.
  Quedan con `get_text(strip=True)` los tricodes del header y los tags de economy (sin casos conocidos).

### 2026-11-11: `tour_id` roto de Türkiye
- `normalize_filename` hacía `lower()` sobre el event en forma html: "TÃ¼rkiye" -> "tã¼rkiye" (São Paulo salía
  bien solo porque el regex borraba el "£"). Las 48 series de la corrida del 11/11 12:29 UTC quedaron en la
  carpeta y con el `tour_id` `vct_2027_emea_kickoff_-_tã¼rkiye_qualifier`, `subregion` con carácter de reemplazo
  y `tournament.match_format = full`.
- Tres arreglos (paquete + notebooks): `normalize_filename` decodifica antes de `lower()`; `tournament_hierarchy`
  decodifica el `tour_id` y devuelve la subregion en forma html; `load_match_formats` pasa el `tournament` de
  scrape_log (texto real) a forma html, que es como va el `tour_id`. Carpeta, archivos y scrape_log renombrados
  a `…_türkiye_qualifier`. Tests en `tests/test_tournament_hierarchy.py`.
- [ ] Supabase: correr `sql/cleanup_tour_id_turkiye.sql` y después `upload` (incremental alcanza: al borrar las
  series de `match_id` quedan pendientes).

## Pendiente

### rktdata: migrar a `player_id_vlr` (2026-11-07)
- [ ] rktdata usa `player_id` (`<team>_<nick>`, ya no único) y `player` como identidad: pasar a `player_id_vlr`
  (ver `handoff/RKTDATA_PLAYER_ID_VLR.md`). Cuando esté, evaluar sacar `player_id` legacy de las tablas.
- [ ] `vlr_scraper.ipynb` no tiene `json_text` en `get_round_logs` (el package sí, ver "Encoding" en CLAUDE.md):
  los nicks no-ASCII de los logs quedan distintos si se scrapea con el notebook.

### Cerrado sin hacer (2026-11-10)
- China Kickoff / Stage 1 2026 (78 series en `error` con datos parciales) y Game Changers 2026: temporada
  pasada, no se re-scrapean. Las series quedan como están.

### Partidos sin terminar al cerrar un evento (diseño, prioridad baja)
Caso: Brazil Open Qualifier tiene 19 partidos en `LIVE` en vlr con rondas posteriores ya jugadas. Si vlr no los
cierra antes de `end_date` + 3 días, el evento se cierra igual (`config.is_active`) y esos partidos quedan sin
datos. No se fuerzan ni se procesan a medias. Hoy además no queda registro: `linkExtractor` descarta las cards que
no son `Completed`, así que nada dice que faltan.
- [ ] Registrar los no completados sin pedir la página del match: `linkExtractor` devuelve también las cards
  `LIVE`/`Upcoming` (series_id + estado de la card) y `scrape_event` las escribe en `scrape_log` con status
  `pending` y `error` = estado de la card (`live` / `upcoming`). `pending` no se saltea: se re-mira en cada
  corrida y pasa a `ok` cuando vlr lo cierra (mismo camino que hoy).
- [ ] "Sin terminar" no es un estado guardado, se deriva al armar las tablas: fila `pending` cuyo evento ya no
  está activo (`end_date` vencido o `active: false`). Así no hay que reescribir nada cuando el evento cierra.
- [ ] Flag a nivel evento: `table_tournament.unfinished_series` (cantidad; 0 = completo). El detalle (qué
  series) queda en `scrape_log` (`status=pending`), sin tabla nueva en Supabase salvo que rviewer/rktdata lo pida.
- [ ] `::warning::` en Actions la última corrida antes del cierre (o la primera después) si quedan `pending`.
- Abierto: los `Upcoming` de un evento cerrado probablemente sean cancelados, no "sin terminar"; contarlos aparte
  (`live` vs `upcoming`) o solo contar `live`.

### Identidad de equipo: fase 2 y pendientes de `team_id_vlr`
- [x] 2026-11-11: paso A, `upload --full` (16 tablas ok) y paso B corridos; `teams_relevant_backup` ya borrada.
  Verificado: 972 teams = csv, sin `tbd_`; players / player_stats con `team_id_vlr` en todas las filas.
- [ ] `teams.relevant` en tags compartidos: 8 tags con más de un equipo en `true`. Claros (pasar a false):
  `team_id_vlr in ('24625','24504','16255','23958','24506')` (100Throwers, FURIA GC, Made in Brampton, Timstone,
  solari). A decidir a mano: NOVA 20630 (otro "Nova Esports"), PXL (5548 / 17177), FAKE (21068 / 23815), los 9 THE.
- [ ] Huérfanas en Supabase (previas a esta fase): 644656 y 644659 (Pacific Stage 1) siguen con tag `DRX` en
  `round_info` y `team_economy` (121 filas c/u, `team_map_round_id like 'DRX-%-6446{56,59}-%'`) y una fila
  `tournament_played (DRX, vct_2026_pacific_stage_1)`; el csv ya dice KRX. Borrarlas; `round_info` debe quedar
  en 71290 filas.
- [ ] Más huérfanas (revisión 2026-11-11, Supabase vs csv): `team_economy` 6304 filas espejo en americas / emea /
  pacific kickoff 2026 y masters santiago (mismo `team_map_round_id`, `team_a` invertido; la buena coincide con
  `round_info."teamA"`); `round_events` 8150 del NA Open Qualifier con tags en minúscula (23 series); `draft`
  701037 (no está en el csv). SQL en `handoff/RKTDATA_RESPUESTA_TEAM_ID_Y_DATOS.md`. Deben quedar
  `team_economy` 62973, `round_events` 503462, `draft` 738.
- [ ] PK de `team_economy` a `team_map_round_id` solo (hoy `team_a, team_map_round_id`, que es lo que dejó
  duplicar): constraint en Supabase + `FILES_TO_UPLOAD`. Después de limpiar las filas espejo.
- [ ] `match_instance` del draft sale del final de la url y vlr corta los slugs largos: basura (`ier`, `pen`) en
  los 72 drafts del NA Open Qualifier.
- [ ] Decidir con rviewer si `match_format` pasa a ser por serie (NA Open Qualifier es `reduced` y tiene 72 drafts).
- [ ] Avisar a rktdata/rviewer: `handoff/RKTDATA_TEAM_ID_VLR.md`, `handoff/RKTDATA_RESPUESTA_TEAM_ID_Y_DATOS.md`
  (y Türkiye en `handoff/RVIEWER_SUBREGIONES_NUEVAS.md`).
- [ ] `slots` / `relevant_teams` en `events.json`: ningún evento los usa todavía. Falta saber cuántas plazas dan
  Türkiye, MENA y Europe (vlr no lo muestra).
- [ ] Fase 2, PKs de las tablas fact con id en vez de tag: `team_map_round_id` (round_info, round_buy,
  round_events, round_summary, team_economy, round_situations), `tournament_played (tour_id, teamA)` (hoy dos
  equipos con el mismo tag en un torneo, como FAKE/FAKE en el NA Open Qualifier, colapsan en una fila) y `draft`.
  Con eso `team_aliases` / `canonical_teams` / `same_team_case` dejan de hacer falta. 785082 (FAKE vs FAKE)
  sigue roto en side / kills por equipo / vivos hasta esta fase.
- [ ] `tournament_slots` guarda el tag de `relevant_teams`: sumar `team_id_vlr` resuelto con los equipos del torneo.
- [ ] `team_path` sigue por tag (dos equipos con el mismo tag comparten logo): decidir con rviewer si pasa a
  `teams/<team_id_vlr>.png`.
- [ ] Drafts del NA Open Qualifier con el nombre del equipo en vez del tricode (785006: `Archaic`, no `ARCH`):
  antes generaban 8 filas basura en `teams` (ARCHAIC, BABOONS...), ahora solo un warning. Revisar `get_picks_bans`
  para los `reduced` que sí traen draft.

### Logs incompletos: es un hueco de vlr, no del scraper
- Re-scrapeados con `--redo` el 2026-10-20 y vuelven **idénticos**: 698906-Ascent tiene eventos en 6 de 18 rondas,
  712828-Sunset en 17 de 23, y 595655-Abyss ronda 14 solo las 4 muertes por caída (faltan las 5 kills con las que
  FS ganó). vlr no tiene esos eventos. Impacto total: 1 ronda `elim` de 17 806 termina sin un equipo barrido.
- `has_logs` en `scrape_log.csv`: 506 `True` (con compras y eventos en disco), 65 `False` (matches sin solapa logs
  en vlr) y 78 vacíos (los de status error).

### csv de logs en git (2026-11-07)
- [x] `csv/*/round_buy_*.csv` y `csv/*/round_events_*.csv` salieron del `.gitignore` (estuvieron ignorados desde
  2026-10-20). La regla "no commitear `scrape_log.csv`" no se podía cumplir: el bot lo commitea a diario, y 55
  matches scrapeados por Actions (47 del qualifier EMEA 2027, 8 de GC Championship) quedaron con `has_logs=True`
  y sus csv perdidos con el runner. Se re-bajaron con `backfill_all_logs.py --redo` y se commitearon junto con
  `scrape_log.csv`. Peso: ~121 MB en disco, ~9 MB comprimidos en git.

### Situaciones XvY
- [ ] Subir `round_situations` a Supabase: DDL en `sql/round_situations.sql` (todavía no escrito), alta en
  `FILES_TO_UPLOAD` como `FACT` y en `EMPTY_AS_NULL`, y `table_round_situations.csv` en `OPTIONAL_FILES` de
  `test_primary_keys.py`. Se dejó local a propósito hasta validar el esquema (precedente: `table_agent_info`).
- [ ] Hoy la tabla solo cubre Champions 2026 (1810 de 35 256 rondas de `round_info`): crece con el backfill de logs.
- [ ] `revive_t` inferido: un jugador que mata después de haber sido víctima fue revivido, así que se podría
  corregir el conteo en vez de solo marcar `has_revive`.
- [ ] Clases de arma (rifle/smg/sniper/...) en `lookups.py` si Vandal/Phantom/Operator resulta poca señal en eco.
- [ ] `t_end` del último segmento es `last_event_t` (`is_t_end_estimated`): mejora si se deriva la duración real
  de la ronda.

### Backfill de logs
- [ ] Crear `round_events` y `round_summary` en Supabase con `sql/round_events.sql`.
- [ ] Correr `backfill-logs` para el resto de los torneos (537 series ok sin logs al 2026-10-09, ~1900 requests, ~1 h; en tandas con `--limit`) y commitear `csv/`.
- [ ] Ideas sobre `round_events`: heatmaps por mapa con `pos`/`from`, kills por arma, sitio de plant por mapa, duración real de la ronda.

### Revisión 2026-10-08 (otros puntos)
- [ ] `winCon` truncado por `rstrip(".webp")` (`defus`, `tim`): verificar cómo lo usa rktdata antes de cambiarlo; después hace falta `upload --full`.
- [ ] Request redundante en `get_team_economy`.
- [ ] Economy del overtime (rondas 25+): vlr ya no lo muestra. Opción: completar el bank desde `round_buy` y dejar el gasto vacío.
- [ ] `convert_k` trunca (`int(32.3 * 1000)` = 32299): usar `round`.
- [ ] Bo1/Bo2 sin `player_performance` (vlr no publica datos; China Stage 2).

### Ideas de infraestructura
- [ ] `timeout-minutes` en `pipeline.yml`.
- [ ] Salir temprano si no hay eventos `active`.
- [ ] Test de sync notebook ↔ paquete.
- [ ] Canario contra vlr real (detectar cambios de HTML).
- [ ] actionlint / shellcheck en CI.
