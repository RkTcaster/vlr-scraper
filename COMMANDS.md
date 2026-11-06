# Comandos frecuentes

Todos se corren desde la raíz del repo. Los flags globales (`--log-level`, `--log-file`) van **antes** del
subcomando. En Windows conviene `PYTHONIOENCODING=utf-8` (bash) o `$env:PYTHONIOENCODING="utf-8"` (PowerShell)
para que no se rompan los nombres con acentos.

Antes de correr algo local: `git pull` (el bot commitea `csv/` todos los días).

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

## Logs (compras / kills por ronda)

```bash
python -m vlr_pipeline backfill-logs --limit 50                            # matches sin has_logs
python -m vlr_pipeline backfill-logs --tournament vct_2026_emea_stage_1
python scripts/backfill_all_logs.py --dry-run                              # plan y estimación
python scripts/backfill_all_logs.py --sync-has-logs                        # rehace has_logs desde csv/, sin requests
python scripts/backfill_all_logs.py --redo 784555 784556                   # re-bajar logs de esas series
```

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
