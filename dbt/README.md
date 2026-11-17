# dbt: capa analítica

Proyecto dbt (`vlr_analytics`) que lee `tables/table_*.csv` como *sources* y construye modelos SQL encima.
No reemplaza `vlr_pipeline/tables.py`. Plan y avance en `ROADMAP.md`.

## Preparar el entorno (una vez)

```powershell
python -m venv .venv-dbt
.venv-dbt\Scripts\python -m pip install -r requirements-dbt.txt
```

## Correr

Siempre desde la carpeta `dbt/` (ahí están `dbt_project.yml` y `profiles.yml`), con `tables/` ya generado
(`python -m vlr_pipeline logs pull` + `process`).

```powershell
cd dbt
..\.venv-dbt\Scripts\dbt debug                      # valida proyecto, profile y conexión
..\.venv-dbt\Scripts\dbt run                        # construye todos los modelos
..\.venv-dbt\Scripts\dbt run -s stg_teams           # solo uno
..\.venv-dbt\Scripts\dbt show -s stg_teams --limit 5   # muestra filas sin construir nada
```

El SQL que dbt ejecutó de verdad (con `source()` / `ref()` ya resueltos) queda en `target/compiled/`.

## Conceptos por paso

| Paso | Concepto | Archivo |
| --- | --- | --- |
| 0 | proyecto, profile, target, adapter | `dbt_project.yml`, `profiles.yml` |
| 1 | sources, `source()`, modelo = un `SELECT`, materialización `view` | `models/staging/_sources.yml`, `stg_teams.sql`, `stg_tournaments.sql` |
