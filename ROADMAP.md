# Roadmap

Estado del pipeline vlr.gg → `csv/` → `tables/` → Supabase → rktdata.ar.
Última actualización: 2026-10-17.

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
  `is_trade`/`is_traded` (ventana de 5 s, `TRADE_WINDOW`).
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

## Pendiente

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
