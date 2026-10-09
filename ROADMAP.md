# Roadmap

Estado del pipeline vlr.gg → `csv/` → `tables/` → Supabase → rktdata.ar.
Última actualización: 2026-10-09.

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

## Pendiente

### Backfill de logs
- [ ] Crear `round_events` y `round_summary` en Supabase con `sql/round_events.sql`.
- [ ] Correr `backfill-logs` para el resto de los torneos (537 series ok sin logs al 2026-10-09, ~1900 requests, ~1 h; en tandas con `--limit`) y commitear `csv/`.
- [ ] Ideas sobre `round_events`: heatmaps por mapa con `pos`/`from`, kills por arma, sitio de plant por mapa, duración real de la ronda.

### Revisión 2026-10-08 (otros puntos)
- [ ] `winCon` truncado por `rstrip(".webp")` (`defus`, `tim`): verificar cómo lo usa rktdata antes de cambiarlo; después hace falta `upload --full`.
- [ ] Re-scrapear China Kickoff y Stage 1 (78 series en error heredadas del bootstrap) con `--event-url`.
- [ ] Request redundante en `get_team_economy`.
- [ ] Bo1/Bo2 sin `player_performance` (vlr no publica datos; China Stage 2).

### Ideas de infraestructura
- [ ] `timeout-minutes` en `pipeline.yml`.
- [ ] Salir temprano si no hay eventos `active`.
- [ ] Test de sync notebook ↔ paquete.
- [ ] Canario contra vlr real (detectar cambios de HTML).
- [ ] actionlint / shellcheck en CI.
