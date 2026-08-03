# Contrato de ingesta — CSVs que alimentan `main vct Americas.ipynb`

Esta es la instrucción para el Claude que está construyendo el pipeline de
obtención de datos. Tu trabajo es producir 3 CSVs que la notebook consume.
Respetá este contrato **exactamente**: headers, casing y reglas semánticas.
Si rompés cualquier punto, el loader falla en silencio o devuelve resultados
incorrectos en los tiebreakers.

## Dónde escribir

Los 3 archivos viven en la raíz de `intermediate/groups/` del repo
`GroupCalculator/groupcalculator`:

```
intermediate/groups/
  standings.csv
  h2h.csv
  fixture.csv
```

Son **archivos planos globales**: una sola copia de cada uno, con filas para
**todos** los `(tournament, region, group)` que existan. No hay subcarpetas
por grupo.

Podés:
- **Reescribir** los 3 archivos enteros cada corrida (más simple y lo
  recomendado).
- **Appendear** filas nuevas a los existentes. En ese caso, sos vos quien
  garantiza que no haya duplicados según las claves de unicidad (más abajo).

## Convención de slugs

Las 3 columnas de identidad (`tournament`, `region`, `group`) van siempre en
**minúsculas con underscores**:

- `tournament`: `vct_2026_stage_1` (sin la región adentro; misma stage de
  varias regiones comparte tournament).
- `region`: `americas` | `emea` | `pacific` | `china`.
- `group`: `omega` | `alpha`.

> Si tu pipeline usa internamente un slug combinado tipo
> `vct_2026_americas_stage_1`, descomponelo antes de escribir las filas:
> `tournament="vct_2026_stage_1"` y `region="americas"` por separado.

Los **tags de equipo** mantienen la casing oficial (`SEN`, `100T`,
`EG`, etc.). No los pases a lowercase: el resto del notebook compara strings
exactos.

## Archivo 1 — `standings.csv`

Una fila por equipo, con la tabla acumulada al momento del corte.

### Headers (exactos, en este orden)

```
tournament,region,group,name,wins,loss,matchWins,matchLoss,roundWin,roundLoss
```

### Tipos

| columna     | tipo   | descripción |
|-------------|--------|-------------|
| tournament  | string | slug lowercase |
| region      | string | slug lowercase |
| group       | string | slug lowercase |
| name        | string | tag oficial del equipo |
| wins        | int    | partidos ganados (series) |
| loss        | int    | partidos perdidos (series) |
| matchWins   | int    | mapas ganados |
| matchLoss   | int    | mapas perdidos |
| roundWin    | int    | rondas ganadas |
| roundLoss   | int    | rondas perdidas |

### Reglas

1. **Clave de unicidad**: `(tournament, region, group, name)`. No debe haber
   duplicados.
2. **Orden de filas dentro de un `(tournament, region, group)`**: define el
   orden canónico del grupo (1° puesto primero, 6° último). El loader hace
   `reset_index(drop=True)` después de filtrar, así que el orden visible en
   el CSV es el orden que termina siendo `teamNameScores["name"]`.
3. Si tu pipeline no sabe ordenar por tiebreaks, podés ordenar por
   `(wins desc, matchWins-matchLoss desc, roundWin-roundLoss desc)` como
   aproximación — el notebook hace el tiebreaking real con `h2h.csv`.

### Ejemplo

```csv
tournament,region,group,name,wins,loss,matchWins,matchLoss,roundWin,roundLoss
vct_2026_stage_1,americas,omega,KRU,3,0,6,0,78,49
vct_2026_stage_1,americas,omega,SEN,2,1,4,2,75,71
vct_2026_stage_1,americas,omega,FUR,2,1,4,3,78,72
vct_2026_stage_1,americas,omega,100T,1,2,3,4,78,79
vct_2026_stage_1,americas,omega,NRG,1,2,2,5,70,77
vct_2026_stage_1,americas,omega,EG,0,3,1,6,59,90
vct_2026_stage_1,americas,alpha,...
vct_2026_stage_1,emea,omega,...
```

## Archivo 2 — `h2h.csv`

Una fila por matchup jugado, **desde el lado del ganador en mapas**.

### Headers (exactos, en este orden)

```
tournament,region,group,team,opponent,md,rd
```

### Tipos

| columna     | tipo   | descripción |
|-------------|--------|-------------|
| tournament  | string | slug lowercase |
| region      | string | slug lowercase |
| group       | string | slug lowercase |
| team        | string | tag del equipo que **lleva el lado positivo** del matchup |
| opponent    | string | tag del rival |
| md          | int    | map differential desde `team` (siempre > 0) |
| rd          | int    | round differential desde `team` (siempre > 0) |

### Reglas

1. **Clave de unicidad**: `(tournament, region, group, team, opponent)`. Una
   sola fila por par jugado.
2. **Sólo se carga un lado por matchup**, el del ganador en mapas. La
   notebook simetriza automáticamente el lado del perdedor con valores
   negativos (`process_for_round`, líneas 124-135). No escribas las dos filas.
3. **`md` y `rd` siempre positivos**. En series Bo3 los valores típicos son:
   - 2-0 en mapas → `md=2`, `rd=` suma de diff de rondas en los 2 mapas
     (siempre positivo porque ganó los 2).
   - 2-1 en mapas → `md=1`, `rd=` suma de diff de rondas en los 3 mapas
     **desde la perspectiva del ganador de la serie** (puede dar valores
     bajos como 2 o 3 si el mapa perdido fue por mucho).
4. **Empate de mapas (1-1, posible en formatos sin tiebreaker)**: si llega a
   ocurrir, define una regla determinística (ej. el primer equipo
   alfabéticamente queda como `team`) y documentala. `md` queda 0 y `rd` se
   carga con el round differential del lado elegido. Hoy no se espera este
   caso en VCT (Bo3 garantiza ganador), pero dejalo previsto.
5. **Sólo matchups ya jugados**. Partidos pendientes van a `fixture.csv`, no
   acá.

### Ejemplo

```csv
tournament,region,group,team,opponent,md,rd
vct_2026_stage_1,americas,omega,KRU,SEN,2,6
vct_2026_stage_1,americas,omega,KRU,NRG,2,10
vct_2026_stage_1,americas,omega,KRU,FUR,2,4
vct_2026_stage_1,americas,omega,SEN,100T,2,5
vct_2026_stage_1,americas,omega,SEN,EG,1,3
vct_2026_stage_1,americas,omega,FUR,NRG,2,7
vct_2026_stage_1,americas,omega,FUR,EG,2,6
vct_2026_stage_1,americas,omega,100T,EG,2,3
vct_2026_stage_1,americas,omega,NRG,100T,1,2
```

Lectura: KRU le ganó a SEN con +2 mapas (2-0) y +6 rondas; SEN le ganó a EG
con +1 mapa (2-1) y +3 rondas; etc.

## Archivo 3 — `fixture.csv`

Una fila por **partido pendiente** (todavía no jugado), agrupado por semana.

### Headers (exactos, en este orden)

```
tournament,region,group,week,teamA,teamB
```

### Tipos

| columna     | tipo   | descripción |
|-------------|--------|-------------|
| tournament  | string | slug lowercase |
| region      | string | slug lowercase |
| group       | string | slug lowercase |
| week        | string | etiqueta de semana, ej. `week4`, `week5` |
| teamA       | string | uno de los equipos (orden no importa para resultado, pero ver nota) |
| teamB       | string | el otro equipo |

### Reglas

1. **Clave de unicidad**: `(tournament, region, group, week, teamA, teamB)`.
2. **Sólo partidos pendientes**. En cuanto un partido se juega, **eliminá la
   fila de `fixture.csv`** y agregá la fila correspondiente en `h2h.csv`
   (más actualizar el `standings.csv` del grupo).
3. **Orden de filas dentro de un `(tournament, region, group, week)`** se
   respeta (el loader usa `groupby("week", sort=False)`). Mantené el orden de
   transmisión de los partidos para que la notebook reporte resultados con la
   misma secuencia que el espectador.
4. **`week` debe ordenar lexicográficamente igual que cronológicamente**. Usá
   `week4`, `week5`, …, `week10` (no `week_4`) — si llegás a `week10`, la
   notebook ya las trata como strings opacos así que no importa el zero-pad,
   pero mantené consistencia con cómo ya vienen las semanas previas.

### Ejemplo

```csv
tournament,region,group,week,teamA,teamB
vct_2026_stage_1,americas,omega,week4,EG,NRG
vct_2026_stage_1,americas,omega,week4,KRU,100T
vct_2026_stage_1,americas,omega,week4,FUR,SEN
vct_2026_stage_1,americas,omega,week5,KRU,EG
vct_2026_stage_1,americas,omega,week5,FUR,100T
vct_2026_stage_1,americas,omega,week5,SEN,NRG
```

## Consistencia cruzada (chequear antes de escribir)

Antes de guardar los 3 archivos, validá:

1. **Suma de h2h ↔ standings**: para cada equipo en un grupo, el número de
   filas donde aparece como `team` u `opponent` en `h2h.csv` debe coincidir
   con `wins + loss` en `standings.csv`.
2. **matchWins/matchLoss vs h2h**: para cada equipo, la suma de `md` en las
   filas donde aparece como `team` menos la suma de `md` donde aparece como
   `opponent` debe igualar `matchWins - matchLoss`.
3. **roundWin/roundLoss vs h2h**: idem con `rd` debe igualar
   `roundWin - roundLoss`.
4. **Sin equipos huérfanos en `fixture.csv`**: los `teamA`/`teamB` deben
   existir como `name` en `standings.csv` para el mismo
   `(tournament, region, group)`.
5. **Sin matchup duplicado entre h2h y fixture**: si `(team, opponent)`
   aparece en `h2h.csv` para un grupo, no debe aparecer en `fixture.csv` en
   ese grupo (un partido es o jugado o pendiente, no ambos).

Si cualquiera de estos chequeos falla, abortá la escritura y reportá qué
fila/equipo no cuadra.

## Cómo se consume después

La notebook hace:

```python
TOURNAMENT, REGION, GROUP = "vct_2026_stage_1", "americas", "omega"
teamNameScores, roundMatches = load_group(TOURNAMENT, REGION, GROUP)
```

El loader filtra los 3 CSVs por ese triplete. Cambiando esas 3 strings, la
notebook procesa otro grupo sin tocar nada más. Por eso es **crítico** que
las 3 columnas de identidad estén siempre en lowercase y consistentes entre
los 3 archivos.

Los resultados de simulación se acumulan en `simulations.csv` (raíz del
repo), con append-or-replace por la misma terna `(group, region, tournament)`
— así que correr el notebook dos veces sobre el mismo grupo no duplica
filas, las reemplaza.
