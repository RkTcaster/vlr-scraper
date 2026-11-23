# Comandos frecuentes

Todos se corren desde la raíz del repo. Los flags globales (`--log-level`, `--log-file`) van **antes** del
subcomando. En Windows conviene `PYTHONIOENCODING=utf-8` (bash) o `$env:PYTHONIOENCODING="utf-8"` (PowerShell)
para que no se rompan los nombres con acentos.

Antes de correr algo local: `git pull` (el bot commitea `csv/` todos los días) **y después
`python -m vlr_pipeline logs pull`** (los csv de logs no están en git, ver abajo). Después de scrapear en local:
`logs push` y commitear `csv/logs_manifest.json` junto con `csv/scrape_log.csv`.

## Archivo de logs en Supabase Storage

`round_buy_*.csv` y `round_events_*.csv` viven en el bucket privado `vlr-logs`, no en git (desde 2026-11-15).
En disco siguen en `csv/<torneo>/`, así que el resto de los comandos no cambia.

```bash
python -m vlr_pipeline logs status        # sin red: qué hay para bajar / subir / en conflicto
python -m vlr_pipeline logs pull          # baja lo que esté desactualizado (Actions lo hace al empezar)
python -m vlr_pipeline logs push          # sube lo que cambió y actualiza csv/logs_manifest.json
python -m vlr_pipeline logs prune --dry-run --keep 3   # versiones viejas en el bucket (borrar: sin --dry-run)
python -m vlr_pipeline logs init          # crea el bucket privado vlr-logs (ya hecho el 2026-11-15; solo si se recrea)
```

Conflicto = el archivo cambió en local y en el remoto desde la última sincronización (por ejemplo, scrapeaste en
local mientras corría Actions). No se pisa nada: `logs pull --force` se queda con el remoto (y los matches locales
se re-scrapean si se saca su fila de `scrape_log.csv`), `logs push --force` se queda con el local. Un clon nuevo
arranca con `git pull` + `logs pull`.

## Merge de `csv/` con el bot (una vez por clon)

```bash
git config merge.vlr-csv.name "merge de csv/ por serie"
git config merge.vlr-csv.driver "python scripts/merge_csv.py %O %A %B %P"
```

Con esto, `git pull` combina los csv de `csv/` por serie, así que no hay conflictos aunque el bot y vos hayan
tocado el mismo archivo. Si los dos cambiaron la misma serie, gana la versión local y lo avisa en la salida. Si un
merge ya quedó en conflicto (por ejemplo, desde un clon sin el driver configurado):

```bash
python scripts/merge_csv.py --resolve     # todos los csv/ en conflicto; despues git add y git commit
```

## Pipeline completo

```bash
# scrape de los eventos active de events.json + process + upload incremental (lo mismo que Actions)
python -m vlr_pipeline logs pull
python -m vlr_pipeline all
python -m vlr_pipeline logs push          # y commitear csv/ (manifest + scrape_log)

# igual pero sin subir a Supabase
python -m vlr_pipeline all --skip-upload

# re-subir todo (después de cambiar código de tablas o lookups)
python -m vlr_pipeline all --full
```

## Por pasos

```bash
python -m vlr_pipeline logs pull               # primero: baja los csv de logs del bucket
python -m vlr_pipeline scrape                  # eventos active de events.json
python -m vlr_pipeline scrape --all-events     # también los active=false
python -m vlr_pipeline process                 # csv/ -> tables/
python -m vlr_pipeline upload --dry-run        # valida tables/ sin conectarse
python -m vlr_pipeline upload                  # incremental
python -m vlr_pipeline upload --full           # todo
python -m vlr_pipeline logs push               # al final, si se scrapeo algo
```

Para subir a Supabase, el CLI lee las credenciales de `.env.local` en la raíz (gitignoreado). Acepta los
nombres de rktdata (`NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`) o los del pipeline (`SUPABASE_URL`,
`SUPABASE_SERVICE_KEY`). La key tiene que ser la **service_role**: la anon no se usa. Lo que ya esté definido en el
entorno gana sobre el archivo (en Actions mandan los secrets). Para usar otro archivo: `VLR_ENV_FILE=ruta`.

Si no encuentra nada, `all` avisa `Sin SUPABASE_URL/SUPABASE_SERVICE_KEY en el entorno; salto el upload` y solo
hace scrape + process.

## Torneos de formato reducido (qualifiers sin draft)

`sql/match_format.sql` ya está aplicado en Supabase (2026-11-06).

Opción 1, dejarlo en `events.json` (lo levanta Actions todos los días):

```json
{
  "name": "VCT 2027 EMEA Kickoff Europe Qualifier",
  "url": "https://www.vlr.gg/event/matches/3175/vct-2027-emea-kickoff-europe-qualifier/?series_id=6092",
  "active": true,
  "format": "reduced"
}
```

```bash
python -m vlr_pipeline scrape      # o `all` para scrape + process + upload
```

Opción 2, un evento suelto sin tocar `events.json`:

```bash
python -m vlr_pipeline scrape --format reduced \
  --event-url "https://www.vlr.gg/event/matches/3175/vct-2027-emea-kickoff-europe-qualifier/?series_id=6092"
python -m vlr_pipeline process
python -m vlr_pipeline upload
```

Si se cambia el `format` de un evento ya scrapeado, el próximo `scrape` re-marca sus partidos sin pedir nada a vlr.
Para que `match_id` en Supabase lo refleje: `upload --full`.

## Fin de un evento (`end_date`)

Un evento puede llevar `"end_date": "YYYY-MM-DD"` (el último día que muestra vlr en "Dates" de la página del
evento). Se sigue scrapeando hasta `end_date` + 3 días (`config.END_DATE_GRACE_DAYS`) y después `scrape` / `all`
lo saltean aunque tenga `"active": true`. El log lo avisa (`end_date ... vencido, no se scrapea`).
`events.json` no se reescribe: para reactivar uno vencido, correr la fecha o sacar el `end_date`.
Sin `end_date`, el evento depende solo de `active`. `scrape --all-events` ignora las dos cosas.

## Equipos relevantes (`teams.relevant`)

Relevantes = los que van a jugar el próximo torneo importante (en qualifiers, los que avanzan). Se editan en
`relevant_teams.json`; cada grupo tiene `teams` (lista manual de `{"id", "name"}`) y/o `event` (url de vlr, toma
los equipos de la página), y `"active": false` lo deja cargado sin aplicar (por ejemplo el kickoff hasta que
empiece).

```bash
python -m vlr_pipeline process                # para que tables/table_teams.csv tenga los equipos nuevos
python scripts/relevant_teams.py              # valida, escribe sql/relevant_teams.sql y muestra entran/salen
python scripts/relevant_teams.py --no-db      # sin consultar Supabase
```

Después pegar `sql/relevant_teams.sql` en el SQL editor de Supabase. Un id que no está en `teams` sale como
warning: el equipo todavía no tiene partidos cargados y el UPDATE no lo marca.

## Plazas de un evento (`slots` / `relevant_teams`)

Antes de usarlo por primera vez, correr `sql/tournament_slots.sql` en el SQL editor de Supabase.

Un evento de `events.json` puede declarar cuántas plazas da (`slots`) y, a mano y en orden, qué equipos las
ocupan (`relevant_teams`, tricodes como en `teams.team_id`; mayúsculas/minúsculas da igual):

```json
{
  "name": "VCT 2027 EMEA Kickoff Europe Qualifier",
  "url": "https://www.vlr.gg/event/matches/3175/vct-2027-emea-kickoff-europe-qualifier/?series_id=6092",
  "active": true,
  "format": "reduced",
  "slots": 2,
  "relevant_teams": ["AURA", "YCAT"]
}
```

- `process` genera `tables/table_tournament_slots.csv` (`tour_id, slot, team_id`): una fila por plaza, `team_id`
  vacío (NULL) mientras falten equipos. Sirve con el evento activo o no.
- `relevant_teams` no puede tener más equipos que `slots`; si un tricode no está en `table_teams` sale un warning.
- No toca `teams.relevant` (columna manual de rviewer).
- El upsert no borra: si se bajan los `slots` de un evento, borrar a mano las filas sobrantes en Supabase.

## Logs (compras / kills por ronda)

```bash
python -m vlr_pipeline backfill-logs --limit 50                            # matches sin has_logs
python -m vlr_pipeline backfill-logs --tournament vct_2026_emea_stage_1
python scripts/backfill_all_logs.py --dry-run                              # plan y estimación
python scripts/backfill_all_logs.py --sync-has-logs                        # rehace has_logs desde csv/, sin requests
python scripts/backfill_all_logs.py --redo 784555 784556                   # re-bajar logs de esas series
python -m vlr_pipeline logs push                                           # siempre despues de tocar logs
```

## Ids de jugador de vlr (`player_id_vlr`)

```bash
python scripts/backfill_player_ids.py --dry-run   # agrega la columna a player_stats_ (sin red) y muestra cuántas series faltan
python scripts/backfill_player_ids.py --max 5     # prueba corta
python scripts/backfill_player_ids.py             # todo lo pendiente (1 request por match, reanudable)
python scripts/backfill_player_ids.py --recheck   # re-pide los matches con jugadores sin perfil en vlr
```

Que queden filas sin id es normal: son jugadores de qualifiers sin perfil en vlr (41 matches). El script ya no los
toma como pendientes y `process` les da un id (`tbd_<team>_<nick>` o el real si vlr les creó perfil después).

Cambio de esquema en Supabase (una vez): correr `sql/player_id_vlr.sql` en el SQL editor y en seguida
`python -m vlr_pipeline upload --full` (el SQL vacía `players`, `player_stats` y `player_performance`).

## Ids de equipo de vlr (`team_id_vlr`)

```bash
python scripts/backfill_team_ids.py --dry-run   # agrega las columnas a round_detail_ / player_stats_ (sin red) y muestra cuántas series faltan
python scripts/backfill_team_ids.py --max 5     # prueba corta
python scripts/backfill_team_ids.py             # todo lo pendiente (1 request por serie, reanudable)
```

Cambio de esquema en Supabase (una vez, con `tables/` regenerado después del backfill): paso A de
`sql/team_id_vlr.sql`, `python -m vlr_pipeline upload --full` y después el paso B (restaura `teams.relevant`).

## GRID (API de Valorant, Open Access)

Necesita `GRID_API_KEY` en `.env.local`. Baja JSON crudo a `grid/raw/` (gitignored: los datos tienen licencia).
Notas de la API en `handoff/GRID_NOTES.md`; el modelado es de dbt (`handoff/DBT_PLAN.md`).

Documentación de dbt (local, desde `dbt/`): `..\.venv-dbt\Scripts\dbt docs generate` y después
`..\.venv-dbt\Scripts\dbt docs serve` (http://localhost:8080). Más comandos en `dbt/README.md`.

```bash
python -m vlr_pipeline grid sync                       # catálogo + series state, incremental
python -m vlr_pipeline grid catalog --full             # catálogo entero desde --since (default 2026-01-01)
python -m vlr_pipeline grid states --limit 20          # solo las primeras 20 pendientes
python -m vlr_pipeline grid states --series 3003317    # re-baja estas series
python scripts/grid_probe.py --dump grid/raw/grid_probe.json   # introspección del schema
```

`states` re-baja una serie si no terminó, si GRID la modificó (`updatedAt` del catálogo) o si se bajó antes de
3 días desde que empezó (GRID corrige series terminadas).

### Actualizar los orbes en Supabase (`team_orbs`)

Solo local: Actions no tiene los datos de GRID, así que el cron no toca esta tabla. Correrlo cuando se jugaron
partidos de torneos que GRID cubre (ligas VCT, Masters, Champions, GC; no los qualifiers), después de que el
pipeline diario ya los subió (`git pull` + `logs pull` + `process` para tener `tables/` al día).

```bash
python -m vlr_pipeline grid sync                        # 1. series nuevas de GRID
cd dbt && ..\.venv-dbt\Scripts\dbt build && cd ..       # 2. rearma grid/exports/table_team_orbs.csv (y testea)
python -m vlr_pipeline upload-grid --dry-run            #    opcional: valida el csv sin conectarse
python -m vlr_pipeline upload-grid                      # 3. upsert completo en team_orbs (+ fila en upload_log)
```

Sube el csv entero cada vez (~64 mil filas): el upsert es idempotente. Una fila que dejó de existir en el
export no se borra de Supabase.

## GitHub Actions

```bash
gh workflow run pipeline.yml                   # corrida manual incremental
gh workflow run pipeline.yml -f full=true      # con --full
gh run list --workflow pipeline.yml --limit 5
gh run watch                                   # seguir la última
```

El workflow hace `logs pull` → `all` → `logs push` y commitea `csv/` solo si el `logs push` salió bien. Si una
corrida no commiteó nada, mirar primero los pasos "Pull logs archive" / "Push logs archive".

## Tests

```bash
python -m pytest                               # todo
python -m pytest tests/test_match_format.py    # uno solo
```

## Standings / h2h de fase de grupos

Antes era la última sección de `csv_process.ipynb` (las notebooks se borraron el 2026-11-16). Necesita
`tables/table_groups.csv` hecho a mano (`tour_id, team, group`); un torneo sin filas ahí no se exporta.

```bash
python -m vlr_pipeline process
python scripts/export_groups.py                # intermediate/groups/standings.csv y h2h.csv
```

## Entorno

```bash
python -m pip install -r requirements.txt   # pip: bs4, pandas, numpy, supabase (lo que instala Actions)
python -m pip install pytest

# o con conda (spec viejo, Python 3.11; no trae supabase)
conda create --name vlr --file environment.conda.txt
conda activate vlr
python -m pip install "supabase>=2.0" pytest
```
