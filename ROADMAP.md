# Roadmap

Estado del pipeline vlr.gg → `csv/` → `tables/` → Supabase → rktdata.ar.
Última actualización: 2026-10-25.

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

## Pendiente

### Logs incompletos: es un hueco de vlr, no del scraper
- Re-scrapeados con `--redo` el 2026-10-20 y vuelven **idénticos**: 698906-Ascent tiene eventos en 6 de 18 rondas,
  712828-Sunset en 17 de 23, y 595655-Abyss ronda 14 solo las 4 muertes por caída (faltan las 5 kills con las que
  FS ganó). vlr no tiene esos eventos. Impacto total: 1 ronda `elim` de 17 806 termina sin un equipo barrido.
- `has_logs` en `scrape_log.csv`: 506 `True` (con compras y eventos en disco), 65 `False` (matches sin solapa logs
  en vlr) y 78 vacíos (los de status error).

### csv de logs fuera de git (temporal, 2026-10-20)
- `csv/*/round_buy_*.csv` y `csv/*/round_events_*.csv` están en `.gitignore` (~55 MB) hasta decidir si las tablas
  de logs van a Supabase. Mientras siga así, **`csv/scrape_log.csv` tampoco se commitea**: con `has_logs=True` y
  los csv ausentes, Actions cree que los logs están en el repo y no los baja.
- Si el commit diario del bot pisa el log: `python scripts/backfill_all_logs.py --sync-has-logs` lo reconstruye
  leyendo los csv de disco, sin pedir nada a vlr (recupera 472 de 537; los 65 sin solapa logs se re-intentan solos).
- Para sacarlo de ignore: borrar esas líneas del `.gitignore` y commitear `csv/` junto con `scrape_log.csv`.

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
- [ ] Re-scrapear China Kickoff y Stage 1 (78 series en error heredadas del bootstrap) con `--event-url`.
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
