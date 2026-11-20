# dbt: capa analítica

Proyecto dbt (`vlr_analytics`) con dos fuentes: `tables/table_*.csv` de vlr (lo que arma
`vlr_pipeline process`) y el JSON crudo de la API de GRID en `grid/raw/` (`python -m vlr_pipeline grid sync`).
No reemplaza `vlr_pipeline/tables.py`. Plan y avance en `ROADMAP.md` y `handoff/DBT_PLAN.md`.

## Preparar el entorno (una vez)

```powershell
python -m venv .venv-dbt
.venv-dbt\Scripts\python -m pip install -r requirements-dbt.txt
```

Después, desde `dbt/`, bajar los paquetes (`packages.yml`, versión fijada en `package-lock.yml`):

```powershell
..\.venv-dbt\Scripts\dbt deps
```

## Correr

Siempre desde la carpeta `dbt/` (ahí están `dbt_project.yml` y `profiles.yml`), con `tables/` ya generado
(`python -m vlr_pipeline logs pull` + `process`).

```powershell
cd dbt
..\.venv-dbt\Scripts\dbt debug                      # valida proyecto, profile y conexión
..\.venv-dbt\Scripts\dbt run                        # construye todos los modelos
..\.venv-dbt\Scripts\dbt build                      # modelos + tests, en orden
..\.venv-dbt\Scripts\dbt run -s stg_vlr__teams       # solo uno
..\.venv-dbt\Scripts\dbt run -s staging.grid         # una carpeta
..\.venv-dbt\Scripts\dbt show -s stg_grid__games --limit 5   # muestra filas sin construir nada
..\.venv-dbt\Scripts\dbt show -s grid_draft_coverage --limit 100   # un analysis
..\.venv-dbt\Scripts\dbt show -s grid_vlr_crosswalk_coverage --limit 100   # cobertura del cruce GRID <-> vlr
..\.venv-dbt\Scripts\dbt show -s source_comparison_summary --limit 10      # GRID vs vlr por metrica
```

`dbt show` muestra 5 filas si no se le pasa `--limit`.

## Documentación y linaje

```powershell
cd dbt
..\.venv-dbt\Scripts\dbt docs generate    # escribe target/catalog.json y manifest.json (consulta la base)
..\.venv-dbt\Scripts\dbt docs serve       # sitio local en http://localhost:8080; Ctrl+C para cerrar
```

La portada es el bloque `__overview__` de `models/_docs.md`; ahí también están los doc blocks de las columnas
que se repiten (`{{ doc('player_id_vlr') }}`). El grafo de linaje es el botón de abajo a la derecha del sitio;
termina en la exposure `grid_vs_vlr_player_analysis` (`models/_exposures.yml`). Todo queda local: el sitio no
se publica.

Con `PYTHONIOENCODING=utf-8` (`$env:PYTHONIOENCODING="utf-8"`): sin eso la consola rompe los nombres no ASCII.

El SQL que dbt ejecutó de verdad (con `source()` / `ref()` ya resueltos) queda en `target/compiled/`.

## Conceptos por paso

| Paso | Concepto | Archivo |
| --- | --- | --- |
| 0 | proyecto, profile, target, adapter | `dbt_project.yml`, `profiles.yml` |
| 1 | sources, `source()`, modelo = un `SELECT`, materialización `view` | `models/staging/vlr/` |
| G2 | source sobre JSON (`read_json`), modelo base materializado como `table`, `unnest` de structs anidados, `ref()`, macro (`iso8601_duration_seconds`), tests genéricos y singulares, severidad `warn`, `analyses/` | `models/staging/grid/`, `macros/`, `tests/`, `analyses/` |
| 2 | staging completo, macro reutilizable (`vlr_timestamp_utc`), loop de Jinja (`{% for %}`) para generar SQL repetido (unpivot de `round_buy`), tests `relationships` entre staging | `models/staging/vlr/`, `macros/` |
| 3 | tests sobre sources (contrato del csv), paquetes (`packages.yml`, `dbt deps`, `dbt_utils.unique_combination_of_columns`), test singular entre tablas | `models/staging/vlr/_vlr__sources.yml`, `tests/assert_vlr_kills_overview_match_logs.sql` |
| 4a | intermediate, joins entre fuentes, window functions (`row_number` para 1 a 1), `seeds/`, `var()`, full outer join para no perder filas | `models/intermediate/`, `seeds/grid_team_overrides.csv` |
| 4b | marts materializados como `table`, `qualify`, `unpivot` (ancho → largo), tests singulares de totales | `models/marts/`, `tests/assert_mart_*` |
| 5 | `dbt docs generate` / `serve`, doc blocks y `__overview__`, `exposures`, descripciones de seeds | `models/_docs.md`, `models/_exposures.yml`, `seeds/_seeds.yml` |

Convención de nombres: `stg_<fuente>__<entidad>` (`stg_vlr__teams`, `stg_grid__games`); `base_` para el paso
previo al staging que solo trae la source (`base_grid__series_state`, tabla para no releer los .gz).

DuckDB 2.0: las lambdas son `lambda x: ...` (la flecha `x -> ...` está deprecada).
