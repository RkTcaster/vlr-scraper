# Cambio en `players` y `teams` (vlr-scraper → rktdata.ar)

> Registro para el repo de **rktdata**. Si sos el Claude/dev de ese repo: leé esto, revisá el
> código y la base de Supabase con los pasos de "Qué revisar en rktdata", y completá la sección
> "Respuesta" al final. **No ejecutes los `delete` sin confirmación del usuario.**

Fecha: 2026-09-14. Origen: repo `vlr-scraper` (`vlr_pipeline/tables.py` y `csv_process.ipynb`).

## Contexto: cómo llegan los datos a Supabase

- `vlr-scraper` genera `table_*.csv` y un GitHub Action diario (17:00 UTC) hace **upsert** en las
  tablas de Postgres, igual que `scripts/upload.mjs`: mismo mapeo archivo → tabla → PK, bloques
  de 200 filas, valores como texto.
- `players` usa `on_conflict = player_id`; `teams` usa `on_conflict = team_id`.
- **El upsert nunca borra.** Si una fila cambia de PK, la fila vieja queda en la tabla.

## Qué cambió

### 1. `players`: el equipo de un jugador es el de su partido más reciente

`player_id` se arma como `<team>_<player>` y `team_id` es ese mismo equipo. Hay **una fila por
nick** (`player`).

- **Antes:** se tomaba el equipo del **primer archivo leído**. El orden de lectura no estaba
  garantizado: en Windows era alfabético por carpeta de torneo; en Linux, donde corre el Action,
  es arbitrario. Probado: con órdenes aleatorios cambiaban entre 4 y 17 `player_id` de una
  corrida a otra.
- **Ahora:** se toma el equipo del **partido más reciente** (`date`) y los archivos se leen en
  orden fijo. El resultado es el mismo en cualquier máquina.

### 2. `teams`: incluye equipos que solo aparecían como rival

`teams` salía solo de la columna `team` del draft, que guarda un solo lado por serie. Por eso
**QTD** no existía en `teams` y sus 5 jugadores tenían `team_id` vacío. Ahora `teams` tiene 64
filas (se agrega `QTD`) y ningún jugador queda con `team_id` vacío.

### 3. Orden de subida

En el upload del pipeline, `teams` se sube **antes** que `players` y `tournament_played` (en
`upload.mjs` iba después). Solo importa si hay foreign keys hacia `teams`.

### Lo que NO cambió

- Columnas, nombres de tablas, tipos y PKs: iguales.
- Las otras 11 tablas (`player_stats`, `player_performance`, `round_info`, `team_economy`,
  `draft`, `maps_id`, `match_id`, `tournament`, `tournament_played`, `regions`, `maps_name_ids`)
  son **byte-idénticas** a antes.
- `player_stats` y `player_performance` **no tienen `player_id`**: tienen `player` (nick) y
  `team` (equipo en ese partido).

## Filas afectadas

Con los datos actuales: **25 jugadores cambian de `player_id`** y **5 de QTD pasan de `team_id`
vacío a `QTD`**. En total, 30 filas distintas de 385.

Estos son los 28 jugadores con más de un equipo, los únicos cuyo `player_id` dependía del orden.
La columna "ids viejos posibles" lista todo `player_id` que pudo haberse subido antes para ese
jugador, por el script de node o por el Action:

| player | equipos (cronológico) | player_id nuevo | ids viejos posibles |
|---|---|---|---|
| Abo | TEC → TE | `TE_Abo` | `TEC_Abo` |
| Akeman | DRG → KBG | `KBG_Akeman` | `DRG_Akeman` |
| BeYN | DRX → KRX | `KRX_BeYN` | `DRX_BeYN` |
| BerLIN | FPX → JDG | `JDG_BerLIN` | `FPX_BerLIN` |
| C0M | EG → FUR | `FUR_C0M` | `EG_C0M` |
| Cloud | GX → FNC | `FNC_Cloud` | `GX_Cloud` |
| ComeBack | TH → NAVI | `NAVI_ComeBack` | `TH_ComeBack` |
| CyvOph | FNC → NAVI | `NAVI_CyvOph` | `FNC_CyvOph` |
| Demon1 | C9 → ENVY | `ENVY_Demon1` | `C9_Demon1` |
| Favian | ULF → EF | `EF_Favian` | `ULF_Favian` |
| Foxy9 | GEN → VL | `VL_Foxy9` | `GEN_Foxy9` |
| GLYPH | M8 → ENVY | `ENVY_GLYPH` | `M8_GLYPH` |
| HYUNMIN | DRX → KRX | `KRX_HYUNMIN` | `DRX_HYUNMIN` |
| Hermes | DRX → KRX → ONG | `ONG_Hermes` | `DRX_Hermes`, `KRX_Hermes` |
| Kyu | SEN → M80 | `M80_Kyu` | `SEN_Kyu` |
| Life | FPX → DRG | `DRG_Life` | `FPX_Life` |
| MaKo | DRX → KRX | `KRX_MaKo` | `DRX_MaKo` |
| N4RRATE | SEN → KC | `KC_N4RRATE` | `SEN_N4RRATE` |
| SiuFatBB | WOL → TYL | `TYL_SiuFatBB` | `WOL_SiuFatBB` |
| UNFAKE | VIT → JL | `JL_UNFAKE` | `VIT_UNFAKE` |
| Xlele | TE → FPX | `FPX_Xlele` | `TE_Xlele` |
| audaz | ULF → EF | `EF_audaz` | `ULF_audaz` |
| cb | EDG → NOVA | `NOVA_cb` | `EDG_cb` |
| coconut | JDG → FPX | `FPX_coconut` | `JDG_coconut` |
| free1ng | DRX → KRX | `KRX_free1ng` | `DRX_free1ng` |
| nekky | ULF → EF | `EF_nekky` | `ULF_nekky` |
| qiutiaN | WOL → NOVA | `NOVA_qiutiaN` | `WOL_qiutiaN` |
| sociablEE | NAVI → FUT | `FUT_sociablEE` | `NAVI_sociablEE` |

Jugadores de QTD (solo cambia `team_id`, el `player_id` es el mismo): `QTD_Pkm`, `QTD_margaret`,
`QTD_Misaya`, `QTD_yuran`, `QTD_Kippei`.

Varios casos son **cambios de tag del mismo equipo**, no transferencias: `DRX → KRX`,
`ULF → EF`, `TEC → TE`. Con la regla nueva quedan con el tag actual.

## Estado probable de Supabase hoy

Como el upsert no borra, es muy posible que `players` tenga **más de una fila por nick** para
algunos de esos 28 jugadores: la vieja de `upload.mjs`, la que subió el Action del 2026-09-13 con
orden arbitrario y, desde la próxima corrida, la nueva.

## Qué revisar en rktdata

1. **Uso de `players` en el código.** Buscar `players`, `player_id` y `team_id`:
   - ¿Se busca un jugador por `player` (nick) esperando **una sola fila** (`.single()`,
     `.maybeSingle()`, `[0]`)? Con filas duplicadas puede fallar o traer el equipo viejo.
   - ¿Se usa `player_id` en **URLs o rutas** (por ejemplo `/player/EG_C0M`)? Los ids que cambian
     rompen links guardados, favoritos o páginas generadas estáticamente.
   - ¿Se muestra el equipo del jugador desde `players.team_id`? Ahora es el equipo actual (último
     partido), no el primero.
   - ¿Se une `player_stats` / `player_performance` con `players`? ¿Por `player`, o armando
     `team + "_" + player`? Si se arma con el `team` del partido, un jugador transferido no
     coincide con su `player_id` actual (esto ya pasaba antes).
2. **Foreign keys en Supabase** (SQL Editor):
   ```sql
   select conname, conrelid::regclass as tabla, confrelid::regclass as referencia,
          pg_get_constraintdef(oid) as definicion
   from pg_constraint
   where contype = 'f'
     and (conrelid in ('public.players'::regclass, 'public.teams'::regclass)
          or confrelid in ('public.players'::regclass, 'public.teams'::regclass));
   ```
3. **Duplicados actuales por nick:**
   ```sql
   select player, count(*) as filas, array_agg(player_id order by player_id) as ids
   from players
   group by player
   having count(*) > 1
   order by player;
   ```
4. **Filas viejas de los 28 jugadores:**
   ```sql
   select * from players
   where player_id in (
     'C9_Demon1',
  'DRG_Akeman',
  'DRX_BeYN',
  'DRX_HYUNMIN',
  'DRX_Hermes',
  'DRX_MaKo',
  'DRX_free1ng',
  'EDG_cb',
  'EG_C0M',
  'FNC_CyvOph',
  'FPX_BerLIN',
  'FPX_Life',
  'GEN_Foxy9',
  'GX_Cloud',
  'JDG_coconut',
  'KRX_Hermes',
  'M8_GLYPH',
  'NAVI_sociablEE',
  'SEN_Kyu',
  'SEN_N4RRATE',
  'TEC_Abo',
  'TE_Xlele',
  'TH_ComeBack',
  'ULF_Favian',
  'ULF_audaz',
  'ULF_nekky',
  'VIT_UNFAKE',
  'WOL_SiuFatBB',
  'WOL_qiutiaN'
   )
   order by player;
   ```
5. **Caches y datos derivados:** vistas, materialized views, ISR/SSG, JSON exportados o tablas
   propias de rktdata que guarden `player_id` o el equipo del jugador.

## Limpieza propuesta (solo después de revisar lo anterior)

Correr **después** de que el Action haya subido la tabla nueva, para que ya existan los ids
nuevos:

```sql
-- borra los player_id viejos de los 28 jugadores con más de un equipo
delete from players
where player_id in (
  'C9_Demon1',
  'DRG_Akeman',
  'DRX_BeYN',
  'DRX_HYUNMIN',
  'DRX_Hermes',
  'DRX_MaKo',
  'DRX_free1ng',
  'EDG_cb',
  'EG_C0M',
  'FNC_CyvOph',
  'FPX_BerLIN',
  'FPX_Life',
  'GEN_Foxy9',
  'GX_Cloud',
  'JDG_coconut',
  'KRX_Hermes',
  'M8_GLYPH',
  'NAVI_sociablEE',
  'SEN_Kyu',
  'SEN_N4RRATE',
  'TEC_Abo',
  'TE_Xlele',
  'TH_ComeBack',
  'ULF_Favian',
  'ULF_audaz',
  'ULF_nekky',
  'VIT_UNFAKE',
  'WOL_SiuFatBB',
  'WOL_qiutiaN'
);
```

Verificación (tiene que devolver 0 filas):

```sql
select player, count(*) from players
where player in ('Abo', 'Akeman', 'BeYN', 'BerLIN', 'C0M', 'Cloud', 'ComeBack', 'CyvOph', 'Demon1', 'Favian', 'Foxy9', 'GLYPH', 'HYUNMIN', 'Hermes', 'Kyu', 'Life', 'MaKo', 'N4RRATE', 'SiuFatBB', 'UNFAKE', 'Xlele', 'audaz', 'cb', 'coconut', 'free1ng', 'nekky', 'qiutiaN', 'sociablEE')
group by player
having count(*) > 1;
```

Si la consulta 3 muestra duplicados de **otros** jugadores que no están en esta lista, vienen de
cargas anteriores (torneos que ya no están en `csv/`, versiones viejas de las tablas) y hay que
revisarlos aparte.

## Pendiente a futuro (no incluido en este cambio)

Un jugador que cambie de equipo más adelante va a volver a cambiar de `player_id` y a dejar su
fila vieja. Opciones, según cómo lo use rktdata:
- `player_id` = solo el nick: estable, pero dos jugadores distintos con el mismo nick chocarían.
- Limpieza automática en el upload: borrar de `players` los ids que ya no están en el CSV.

## Respuesta (completar desde rktdata)

Revisado desde el repo `rviewer` (rktdata) el 2026-09-14.

- [x] **¿rktdata usa `players.player_id`?** No. La tabla `players` no se consulta en ningún lado
  (no hay `.from('players')` en `lib/`) y no hay rutas ni URLs con `player_id`. Las stats de
  jugadores salen de `player_stats` / `player_performance` / `draft`, agrupando por `player` y
  usando el `team` de cada partido. `teams` solo se lee en `lib/data/images.ts`
  (`getTeamLogos`: `team_id, team_path`, descarta filas sin `team_path`).
- [x] **¿Busca jugadores por nick esperando una sola fila?** No. El único `.single()`
  (`lib/data/draft.ts:163`) es sobre `draft`.
- [ ] **¿Hay FKs hacia `players` o `teams`?** Sin verificar: la consulta 2 va contra
  `pg_constraint` y no se puede correr por la API REST. Hay que correrla en el SQL Editor.
- [x] **Consulta 3 (duplicados actuales)**, hecha por API con la service key:
  - `players`: 404 filas, 385 nicks distintos, **19 nicks duplicados** (2 filas cada uno):
    Akeman, audaz, BerLIN, BeYN, coconut, Favian, Foxy9, free1ng, Hermes (`DRX_Hermes`,
    `ONG_Hermes`), HYUNMIN, Life, MaKo, N4RRATE, nekky, qiutiaN, SiuFatBB, sociablEE, Xlele y
    **yong** (`DRX_yong`, `KRX_yong`).
  - **`yong` no está en la lista de 28:** en `player_stats` solo aparece con KRX (33 mapas), así
    que `DRX_yong` es de una carga anterior. Hay que sumarlo a la limpieza.
  - Los 28 ids viejos de la consulta 4 están **todos presentes** (`KRX_Hermes` no existe).
  - De los 28 ids nuevos hay 18; **faltan 10**: `TE_Abo`, `FUR_C0M`, `FNC_Cloud`,
    `NAVI_ComeBack`, `NAVI_CyvOph`, `ENVY_Demon1`, `ENVY_GLYPH`, `M80_Kyu`, `JL_UNFAKE`,
    `NOVA_cb`. Si se limpia antes de la próxima corrida del Action, esos jugadores quedan sin fila.
  - Los 5 de QTD siguen con `team_id` vacío (todavía no corrió la versión nueva).
  - `teams`: 64 filas y `QTD` ya existe con `team_path = teams/QTD.png`.
- [x] **¿Se puede correr la limpieza?** Desde el código de rviewer, sí: no hace falta ningún
  cambio. Condiciones:
  1. Correrla **después** de la próxima corrida del Action, con los 10 ids nuevos que faltan ya
     cargados.
  2. Agregar `'DRX_yong'` al `delete`.
  3. Confirmar antes que la consulta 2 no muestre FKs hacia `players`.
  4. **No volver a correr `scripts/upload.mjs` con los CSV actuales de `rviewer/data/`**
     (2026-09-08, lógica vieja): reinsertaría los `player_id` viejos (`EG_C0M`, `DRX_Hermes`, …)
     y los `team_id` vacíos de QTD. Mejor sacar `players` y `teams` de ese script o dejar de usarlo.
- [x] **Pendiente a futuro:** para rviewer da igual, porque no usa `player_id`. Se prefiere la
  **limpieza automática en el upload** (borrar de `players` los ids que no están en el CSV), que
  evita que se vuelvan a juntar filas viejas sin cambiar el formato del id.
