"""Upsert de tables/table_*.csv en tablas de Postgres de Supabase (las que usa rktdata.ar).

Port de scripts/upload.mjs del repo de rktdata: mismo mapeo archivo -> tabla -> PK, bloques de
200 filas y upsert con onConflict. Los valores viajan como texto, igual que csv-parser en node.

Requiere las variables de entorno SUPABASE_URL y SUPABASE_SERVICE_KEY (service role key;
en GitHub Actions se cargan como secrets).

Modos:
- incremental (default): dimensiones completas; tablas de hechos solo con los series_id que no
  estan en la tabla match_id de Supabase o que se re-scrapearon despues del ultimo upload ok.
  match_id se sube al final y solo con los series_id cuyos hechos subieron sin error, asi un
  bloque fallido se reintenta en la proxima corrida.
- full (--full, manual): todas las filas de todas las tablas. Usarlo cuando cambia el codigo o
  los lookups (cambian filas de partidos ya subidos) o si se borro algo en Supabase.

Cada corrida (salvo dry-run) agrega una fila por tabla a csv/upload_log.csv: historial persistente
de lo subido y de los errores, que Actions commitea junto con csv/.
"""

import csv
import logging
import os
import time
from collections import Counter
from datetime import datetime, timezone

from vlr_pipeline.tracking import LOG_FILENAME as SCRAPE_LOG_FILENAME, RAW_ENCODING

logger = logging.getLogger(__name__)

CHUNK_SIZE = 200
# PostgREST devuelve como maximo 1000 filas por request (max-rows por defecto de Supabase)
FETCH_PAGE_SIZE = 1000

UPLOAD_LOG_FILENAME = "upload_log.csv"
UPLOAD_LOG_COLUMNS = [
    "run_at",
    "run_id",
    "mode",
    "table",
    "file",
    "rows",
    "series",
    "failed_rows",
    "status",
    "error",
    "duration_s",
]
# largo maximo del mensaje de error guardado (los de Postgres pueden traer el detalle entero)
MAX_ERROR_LENGTH = 500

# Tipo de tabla en el modo incremental:
DIMENSION = "dimension"  # se sube siempre completa (pocas filas)
FACT = "fact"  # se filtra por series_id
MARKER = "marker"  # match_id: marca que un series_id ya esta subido entero; va ultima

# (archivo, tabla, pk para on_conflict, tipo). Agregar aca las tablas nuevas.
FILES_TO_UPLOAD = [
    ("table_region.csv", "regions", "reg_id", DIMENSION),
    ("table_tournament.csv", "tournament", "tour_id", DIMENSION),
    # teams antes que players / tournament_played: si hay FK a teams, un equipo nuevo tiene
    # que existir antes (en upload.mjs teams iba despues de players)
    ("table_teams.csv", "teams", "team_id", DIMENSION),
    ("table_tournament_played.csv", "tournament_played", "tour_id, teamA", DIMENSION),
    ("table_players.csv", "players", "player_id", DIMENSION),
    ("table_maps_name_id.csv", "maps_name_ids", "map_id", DIMENSION),
    ("table_maps_id.csv", "maps_id", "map_id", FACT),
    ("table_draft.csv", "draft", "series_id", FACT),
    ("table_round_info.csv", "round_info", "team_map_round_id", FACT),
    ("table_team_economy.csv", "team_economy", "team_a, team_map_round_id", FACT),
    ("table_player_stats.csv", "player_stats", "map_id, player", FACT),
    ("table_player_performance.csv", "player_performance", "map_id, player", FACT),
    # ultima: en incremental los series_id que no esten aca se consideran pendientes
    ("table_match_id.csv", "match_id", "series_id", MARKER),
]


def has_credentials():
    return bool(os.environ.get("SUPABASE_URL")) and bool(os.environ.get("SUPABASE_SERVICE_KEY"))


def read_rows(path):
    """Lee un table_*.csv como lista de dicts de strings.

    Las tablas se escriben con iso-8859-1 pero sus bytes son utf-8 valido (ver CLAUDE.md),
    asi que se leen como utf-8, igual que csv-parser en upload.mjs.
    """
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def validate_rows(rows, pk, file):
    """Chequeos previos al upsert. Devuelve lista de problemas (vacia si esta ok).

    Una PK duplicada dentro de un mismo bloque hace fallar el bloque entero en Postgres
    ("ON CONFLICT DO UPDATE command cannot affect row a second time").
    """
    if not rows:
        return []
    pk_columns = [column.strip() for column in pk.split(",")]
    missing = [column for column in pk_columns if column not in rows[0]]
    if missing:
        return [f"{file}: faltan columnas de la PK {missing}"]

    counts = Counter(tuple(row[column] for column in pk_columns) for row in rows)
    duplicated = [key for key, count in counts.items() if count > 1]
    if duplicated:
        return [f"{file}: {len(duplicated)} claves {pk_columns} duplicadas, ej. {duplicated[:3]}"]
    return []


def append_upload_log(entries, log_dir="csv"):
    """Agrega las filas de una corrida a csv/upload_log.csv (lo crea con header si no existe)."""
    if not entries:
        return
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, UPLOAD_LOG_FILENAME)
    file_exists = os.path.isfile(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=UPLOAD_LOG_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(entries)


def _short_error(error):
    text = " ".join(str(error).split())
    return text[:MAX_ERROR_LENGTH]


def _parse_time(value):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def fetch_uploaded_series(client):
    """series_id que ya estan en la tabla match_id de Supabase (paginado)."""
    series = set()
    start = 0
    while True:
        response = (
            client.table("match_id")
            .select("series_id")
            .range(start, start + FETCH_PAGE_SIZE - 1)
            .execute()
        )
        page = response.data or []
        series.update(str(row["series_id"]) for row in page)
        if len(page) < FETCH_PAGE_SIZE:
            return series
        start += FETCH_PAGE_SIZE


def last_ok_upload_at(log_dir="csv"):
    """run_at de la ultima corrida de upload_log.csv con todas sus tablas en ok, o None."""
    path = os.path.join(log_dir, UPLOAD_LOG_FILENAME)
    if not os.path.isfile(path):
        return None
    runs = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            runs.setdefault(row["run_at"], []).append(row.get("status") == "ok")
    ok_runs = [_parse_time(run_at) for run_at, statuses in runs.items() if all(statuses)]
    ok_runs = [run_at for run_at in ok_runs if run_at is not None]
    return max(ok_runs) if ok_runs else None


def rescraped_series(csv_dir="csv", since=None):
    """series_id de csv/scrape_log.csv con last_attempt posterior a since.

    Un match con error deja filas parciales en csv/ y su series_id ya queda en match_id; si
    despues se re-scrapea bien, este criterio hace que se vuelva a subir.
    """
    path = os.path.join(csv_dir, SCRAPE_LOG_FILENAME)
    if since is None or not os.path.isfile(path):
        return set()
    series = set()
    with open(path, newline="", encoding=RAW_ENCODING) as f:
        for row in csv.DictReader(f):
            attempt = _parse_time(row.get("last_attempt"))
            if attempt is not None and attempt > since:
                series.add(row["series_id"])
    return series


def pending_series(all_series, uploaded, rescraped):
    """series_id a subir en modo incremental: los que faltan en Supabase + los re-scrapeados."""
    return {series_id for series_id in all_series if series_id not in uploaded or series_id in rescraped}


def _table_series(tables_dir):
    """Todos los series_id de table_match_id.csv (vacio si no existe)."""
    path = os.path.join(tables_dir, "table_match_id.csv")
    if not os.path.exists(path):
        return set()
    return {row["series_id"] for row in read_rows(path)}


def upload_tables(tables_dir="tables", chunk_size=CHUNK_SIZE, dry_run=False, log_dir="csv",
                  full=False, csv_dir=None):
    """Hace upsert de cada archivo de FILES_TO_UPLOAD en su tabla.

    Como upload.mjs, un bloque que falla se loguea y se sigue con el resto. El resultado de
    cada tabla se agrega a <log_dir>/upload_log.csv (status ok / error / invalid / missing).

    Args:
        dry_run (bool): solo lee y valida los csv, sin conectarse a Supabase ni escribir el log
        log_dir (str): carpeta donde vive upload_log.csv
        full (bool): sube todas las filas; si es False, de las tablas de hechos solo los
            series_id pendientes (ver docstring del modulo)
        csv_dir (str): carpeta de scrape_log.csv (default: log_dir)

    Returns:
        int: cantidad de bloques/archivos con error (0 = todo subido)
    """
    client = None
    returning = None
    if not dry_run:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not supabase_url or not supabase_key:
            raise RuntimeError("Faltan SUPABASE_URL y/o SUPABASE_SERVICE_KEY en el entorno")

        from postgrest.types import ReturnMethod
        from supabase import create_client

        client = create_client(supabase_url, supabase_key)
        returning = ReturnMethod.minimal

    return run_upload(
        client,
        tables_dir=tables_dir,
        chunk_size=chunk_size,
        dry_run=dry_run,
        log_dir=log_dir,
        full=full,
        csv_dir=log_dir if csv_dir is None else csv_dir,
        returning=returning,
    )


def run_upload(client, tables_dir="tables", chunk_size=CHUNK_SIZE, dry_run=False, log_dir="csv",
               full=False, csv_dir="csv", returning=None):
    """Cuerpo de upload_tables con el cliente ya creado (separado para testearlo con un fake)."""
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # en Actions queda el id de la corrida, para ir directo al log completo
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    mode = "full" if full else "incremental"
    entries = []

    # None = sin filtro por series_id (full, o dry-run que no puede consultar Supabase)
    pending = None
    if not full and dry_run:
        logger.info("dry-run: sin conexion no se calculan los series pendientes; se validan todas las filas")
    elif not full:
        since = last_ok_upload_at(log_dir)
        uploaded = fetch_uploaded_series(client)
        rescraped = rescraped_series(csv_dir, since)
        pending = pending_series(_table_series(tables_dir), uploaded, rescraped)
        logger.info(
            "incremental: %d series ya en Supabase, %d re-scrapeadas desde %s -> %d pendientes",
            len(uploaded), len(rescraped), since, len(pending),
        )

    # series_id con algun bloque de hechos fallido: no se marcan en match_id y se reintentan
    failed_series = set()
    error_count = 0
    try:
        for file, table, pk, kind in FILES_TO_UPLOAD:
            started = time.monotonic()
            entry = {
                "run_at": run_at,
                "run_id": run_id,
                "mode": mode,
                "table": table,
                "file": file,
                "rows": 0,
                "series": "",
                "failed_rows": 0,
                "status": "ok",
                "error": "",
                "duration_s": 0,
            }
            entries.append(entry)

            path = os.path.join(tables_dir, file)
            if not os.path.exists(path):
                logger.warning("saltando %s: no existe en %s", file, tables_dir)
                entry.update(status="missing", error=f"no existe en {tables_dir}")
                continue

            rows = read_rows(path)
            # se valida el csv completo, antes de filtrar
            problems = validate_rows(rows, pk, file)
            for problem in problems:
                logger.error(problem)
            if problems:
                error_count += 1
                entry.update(rows=len(rows), status="invalid", failed_rows=len(rows),
                             error=_short_error("; ".join(problems)))
                if kind == FACT:
                    # no se subio nada de esta tabla: ningun series_id queda completo
                    failed_series.update(row.get("series_id") for row in rows)
                continue

            if kind != DIMENSION:
                if pending is not None:
                    rows = [row for row in rows if row["series_id"] in pending]
                if kind == MARKER:
                    rows = [row for row in rows if row["series_id"] not in failed_series]
                entry["series"] = len({row["series_id"] for row in rows})
            entry["rows"] = len(rows)

            if dry_run:
                logger.info("dry-run %s -> %s: %d filas ok", file, table, len(rows))
                continue
            if not rows:
                logger.info("%s: sin filas para subir", table)
                continue

            logger.info("upsert %s -> %s (%d filas)", file, table, len(rows))
            failed_rows = 0
            for start in range(0, len(rows), chunk_size):
                chunk = rows[start:start + chunk_size]
                try:
                    # returning=minimal: no traer las filas de vuelta (upload.mjs tampoco lo hace)
                    client.table(table).upsert(chunk, on_conflict=pk, returning=returning).execute()
                except Exception as e:
                    logger.error("error en %s (filas %d-%d): %s", table, start, start + len(chunk), e)
                    error_count += 1
                    failed_rows += len(chunk)
                    entry.update(status="error", error=_short_error(f"filas {start}-{start + len(chunk)}: {e}"))
                    if kind == FACT:
                        failed_series.update(row["series_id"] for row in chunk)
            entry["failed_rows"] = failed_rows
            entry["duration_s"] = round(time.monotonic() - started, 1)
            logger.info("finalizado %s: %d/%d filas subidas", table, len(rows) - failed_rows, len(rows))
    finally:
        # tambien si algo explota a mitad de camino: queda registrado hasta donde llego
        if not dry_run:
            append_upload_log(entries, log_dir)
    return error_count
