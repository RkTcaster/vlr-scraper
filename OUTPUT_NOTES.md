# Notas para el consumidor (GroupCalculator) — cómo difiere el output del `INPUT_CONTRACT.md`

Este documento es el contrato visto desde el lado productor (este repo `vlr-scraper`). Listo las desviaciones del `INPUT_CONTRACT.md` que tenés que asumir al cargar los CSVs.

## TL;DR de desviaciones

1. **Solo se generan 2 de los 3 archivos**: `standings.csv` y `h2h.csv`. `fixture.csv` lo mantiene el usuario a mano.
2. **`tournament` = slug completo con la región adentro** (no separado).
3. **Team tags preservan diacríticos** (`KRÜ`, no `KRU`).
4. **Encoding de los CSVs**: UTF-8 (no iso-8859-1).
5. **`group` se asigna manualmente** desde un mapping local (`tables/table_groups.csv` en este repo). Si un tournament no tiene mapping, no aparece en el output.

## Detalle por archivo

### `standings.csv`

Headers y orden: idénticos al contrato.
```
tournament,region,group,name,wins,loss,matchWins,matchLoss,roundWin,roundLoss
```

Diferencia: `tournament` viene como **slug completo con region embebida**, ej:

```csv
vct_2026_americas_stage_1,americas,omega,KRÜ,3,0,6,0,78,49
```

en vez del ejemplo del contrato que tiene `vct_2026_stage_1,americas,...`.

`region` sigue siendo columna separada (derivada de `tables/table_region.csv`), así que el filtro por triplete sigue funcionando — solo hay que llamar al loader con el slug entero como `TOURNAMENT`:

```python
TOURNAMENT, REGION, GROUP = "vct_2026_americas_stage_1", "americas", "omega"
teamNameScores, roundMatches = load_group(TOURNAMENT, REGION, GROUP)
```

### `h2h.csv`

Headers y orden: idénticos al contrato.
```
tournament,region,group,team,opponent,md,rd
```

- Solo el lado del ganador en mapas, como pide el contrato.
- `md` y `rd` siempre positivos (asumimos Bo3 con ganador definido; series empatadas en mapas se logean como warning y se omiten).
- Filas de un mismo `(tournament, region, group)` no tienen orden particular garantizado — si te importa el orden, hacé sort en el loader.
- `tournament` con la misma forma de slug que `standings.csv`.

### `fixture.csv`

**No se genera por este pipeline.** El usuario lo mantiene a mano. Si tu loader exige el archivo presente, dejá un stub con solo el header:

```csv
tournament,region,group,week,teamA,teamB
```

Esto es una limitación conocida — no scrapeamos schedule pendiente de vlr.gg todavía.

## Team naming

- Diacríticos preservados: el output usa `KRÜ` (3 chars Unicode, `K`, `R`, `Ü`/`Ü`), **no** `KRU` ASCII.
- Casing oficial mantenida (`SEN`, `100T`, `EG`, etc.).
- Si tu loader hace comparaciones de strings estrictas, asegurate de comparar con UTF-8 normalizado (NFC).

## Encoding

Todos los CSVs se escriben con `utf-8` sin BOM. Si los abrís en pandas:

```python
pd.read_csv("intermediate/groups/standings.csv", encoding="utf-8")
```

## Mapping de grupos

La división `omega` / `alpha` no surge de los datos crudos de vlr — se asigna manualmente vía `tables/table_groups.csv` (en este repo, no en el tuyo) con columnas `tour_id,team,group`. Lo mantiene el usuario.

Consecuencias:
- Si un torneo todavía no tiene mapping cargado, **no aparece en el output** (ni en `standings.csv` ni en `h2h.csv`). No es un bug, es filtrado intencional.
- Masters Santiago (`valorant_masters_santiago_2026`) es single-elim global — queda fuera por diseño.

## Cross-checks que ya corren del lado productor

Antes de escribir los CSVs, el pipeline valida (y aborta si falla):

1. Por cada `(tournament, group, team)`: `count(h2h rows del equipo) == wins + loss`.
2. `sum(md desde team) − sum(md desde opponent) == matchWins − matchLoss`.
3. `sum(rd desde team) − sum(rd desde opponent) == roundWin − roundLoss`.

O sea, si tu loader recibe los archivos, asumí que ya pasaron las invariantes de la sección 5 del `INPUT_CONTRACT.md`.

## Origen

Los CSVs los produce `csv_process.ipynb` en este repo, en la sección final "Export INPUT_CONTRACT". Output va a `intermediate/groups/` (raíz de este repo). El usuario copia los archivos al repo `GroupCalculator/groupcalculator/intermediate/groups/` cuando los quiere consumir.

Estado al momento de escribir esto (2026-05-14): el mapping de grupos está vacío, así que los CSVs salen vacíos (solo headers). Cuando el usuario complete `tables/table_groups.csv` y vuelva a correr la sección, los archivos se poblarán.
