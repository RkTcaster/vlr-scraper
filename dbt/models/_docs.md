{% docs __overview__ %}
# vlr_analytics

Capa analítica en dbt sobre dos fuentes de estadísticas de Valorant esports:

- **vlr** (`source: vlr`): el star schema que arma `vlr_pipeline` scrapeando [vlr.gg](https://www.vlr.gg)
  (`tables/table_*.csv`, lo mismo que se sube a Supabase y usa rktdata.ar).
- **GRID** (`source: grid`): el JSON crudo de la API de GRID (Open Access de Riot): series, mapas, rondas y
  jugadores con datos que vlr no publica (daño recibido, supervivencia por ronda, orbes, zonas del cuerpo).

## Capas

| Capa | Qué hace | Materialización |
|---|---|---|
| `staging/vlr`, `staging/grid` | Un modelo por entidad: renombra, tipa, desarma el JSON (`unnest`). Sin lógica. | view (la base de GRID, table) |
| `intermediate/crosswalk` | El cruce GRID ↔ vlr por nivel: equipo → serie → mapa → ronda → jugador. Cada nivel es 1 a 1 (tests `unique` de los dos lados). | view |
| `marts` | Lo que se consulta: stats de jugador con ids de vlr y la comparación entre fuentes. | table |

## El cruce, en números (2026-11-20)

- Series: 596 de 597 posibles. Rondas: 99.57 % coinciden en ganador y forma de ganar.
- Jugador-mapa: 14 937 de 14 938 filas de vlr (por nick, y por agente cuando el nick difiere).
- Kills y deaths coinciden en el 99.6 % de los jugador-mapa; el ADR de GRID da ~0.81 del de vlr
  (GRID parece no contar el overkill).

## Marts

- `fct_player_map`: jugador por mapa, stats de vlr + las que solo tiene GRID.
- `mart_player_tournament`: jugador por torneo, tasas ponderadas por rondas.
- `mart_player_map_source_comparison`: GRID vs vlr por jugador-mapa y métrica.

Los tests `warn` marcan datos conocidos de las fuentes (mapas con rondas faltantes, un mapa roto en GRID); un
salto en su cantidad es la señal de revisar.
{% enddocs %}


{% docs player_id_vlr %}
Id del jugador en vlr (`/player/<id>/`). Es la identidad del jugador: dos jugadores pueden compartir nick, incluso
en el mismo equipo. Jugadores de qualifiers sin perfil en vlr llevan `tbd_<team>_<nick>`.
{% enddocs %}

{% docs team_id_vlr %}
Id del equipo en vlr (`/team/<id>/`). Es la identidad del equipo: el tag (tricode) no es único, varios equipos sin
relación comparten tag.
{% enddocs %}

{% docs team_tag %}
Tricode del equipo en vlr, en mayúsculas. No es único entre equipos: para identificar un equipo usar team_id_vlr.
{% enddocs %}

{% docs vlr_series_id %}
Id de la serie (el partido completo, Bo1/Bo3/Bo5) en vlr: el número de la url del match.
{% enddocs %}

{% docs vlr_map_id %}
Mapa de una serie de vlr: `<series_id>-<Mapa>` (`788539-Corrode`).
{% enddocs %}

{% docs map_player_id %}
Jugador en un mapa de vlr: `<vlr_map_id>-<player_id_vlr>`. Es la PK de player_stats en Supabase.
{% enddocs %}

{% docs team_map_round_id %}
Ronda de vlr, PK de round_info: `<tag>-<tag>-<vlr_map_id>-<ronda>` con los tags ordenados (`100T-RRQ-706754-Breeze-1`).
Lleva el tag que tenía el equipo cuando se jugó la serie.
{% enddocs %}

{% docs tournament_id %}
Id del torneo en vlr, derivado del nombre del evento (`vct_2026_americas_stage_1`).
{% enddocs %}

{% docs grid_series_id %}
Id de la serie en GRID.
{% enddocs %}

{% docs grid_game_id %}
Id de un mapa (game) en GRID.
{% enddocs %}

{% docs game_player_id %}
Jugador en un mapa de GRID: `<grid_game_id>-<grid_player_id>`.
{% enddocs %}

{% docs grid_player_id %}
Id del jugador en GRID. Se identifica a los jugadores por id, nunca por nombre (hay un nick literal "None").
{% enddocs %}

{% docs grid_team_id %}
Id del equipo en GRID. Un mismo equipo de vlr puede tener más de un id en GRID.
{% enddocs %}

{% docs has_player_stats %}
false = GRID tiene solo el resultado de ese mapa, sin stats por jugador (8 mapas de Challengers al 2026-11-19).
{% enddocs %}

{% docs player_match_method %}
Cómo se emparejó el jugador: `nick` (nick normalizado igual, dentro del mismo mapa y equipo) o `agent` (nick
distinto, mismo agente: un agente no se repite dentro de un equipo en un mapa).
{% enddocs %}

{% docs agent_matches %}
true = las dos fuentes dicen el mismo agente (comparado sin símbolos: GRID `kay/o`, vlr `Kayo`). false en un par
emparejado por nick indica un dato roto en una fuente.
{% enddocs %}

{% docs adr_grid %}
Daño hecho por ronda según GRID (damageDealt / rondas de GRID). No es el mismo número que el ADR de vlr: da
~0.8 del de vlr en todos los torneos. GRID suma ~147 de daño por kill (tope 150 = vida + armadura) y vlr ~182, así
que GRID parece contar solo el daño efectivo y vlr también el overkill. No mezclar las dos columnas en un ranking.
{% enddocs %}

{% docs survival_rate %}
Rondas en las que el jugador terminó vivo / rondas jugadas (`alive` de GRID al final de cada ronda).
{% enddocs %}

{% docs headshot_pct %}
Impactos en la cabeza / impactos de bala totales, en %. Así lo calcula vlr; del lado de GRID se arma con los
impactos por zona (head / (head + body + leg)).
{% enddocs %}
