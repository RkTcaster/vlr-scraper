# Comandos frecuentes

Todos se corren desde la raíz del repo. Los flags globales (`--log-level`, `--log-file`) van **antes** del
subcomando. En Windows conviene `PYTHONIOENCODING=utf-8` (bash) o `$env:PYTHONIOENCODING="utf-8"` (PowerShell)
para que no se rompan los nombres con acentos.

Antes de correr algo local: `git pull` (el bot commitea `csv/` todos los días).

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
python -m vlr_pipeline all

# igual pero sin subir a Supabase
python -m vlr_pipeline all --skip-upload

# re-subir todo (después de cambiar código de tablas o lookups)
python -m vlr_pipeline all --full
```

## Por pasos

```bash
python -m vlr_pipeline scrape                  # eventos active de events.json
python -m vlr_pipeline scrape --all-events     # también los active=false
python -m vlr_pipeline process                 # csv/ -> tables/
python -m vlr_pipeline upload --dry-run        # valida tables/ sin conectarse
python -m vlr_pipeline upload                  # incremental
python -m vlr_pipeline upload --full           # todo
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

## GitHub Actions

```bash
gh workflow run pipeline.yml                   # corrida manual incremental
gh workflow run pipeline.yml -f full=true      # con --full
gh run list --workflow pipeline.yml --limit 5
gh run watch                                   # seguir la última
```

## Tests

```bash
python -m pytest                               # todo
python -m pytest tests/test_match_format.py    # uno solo
```

## Notebooks headless

```bash
jupyter nbconvert --to notebook --execute --inplace vlr_scraper.ipynb
jupyter nbconvert --to notebook --execute --inplace csv_process.ipynb
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
