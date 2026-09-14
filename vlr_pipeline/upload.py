"""Upsert de tables/table_*.csv en tablas de Postgres de Supabase (las que usa rktdata.ar).

Port de scripts/upload.mjs del repo de rktdata: mismo mapeo archivo -> tabla -> PK, bloques de
200 filas y upsert con onConflict. Los valores viajan como texto, igual que csv-parser en node.

Requiere las variables de entorno SUPABASE_URL y SUPABASE_SERVICE_KEY (service role key;
en GitHub Actions se cargan como secrets).

Cada corrida (salvo dry-run) agrega una fila por tabla a csv/upload_log.csv: historial persistente
de lo subido y de los errores, que Actions commitea junto con csv/.
"""

import csv
import logging
import os
import time
from collections import Counter
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CHUNK_SIZE = 200

UPLOAD_LOG_FILENAME = "upload_log.csv"
UPLOAD_LOG_COLUMNS = [
    "run_at",
    "run_id",
    "table",
    "file",
    "rows",
    "failed_rows",
    "status",
    "error",
    "duration_s",
]
# largo maximo del mensaje de error guardado (los de Postgres pueden traer el detalle entero)
MAX_ERROR_LENGTH = 500

# (archivo, tabla, pk para on_conflict). Agregar aca las tablas nuevas.
FILES_TO_UPLOAD = [
    ("table_region.csv", "regions", "reg_id"),
    ("table_tournament.csv", "tournament", "tour_id"),
    # teams antes que players / tournament_played: si hay FK a teams, un equipo nuevo tiene
    # que existir antes (en upload.mjs teams iba despues de players)
    ("table_teams.csv", "teams", "team_id"),
    ("table_tournament_played.csv", "tournament_played", "tour_id, teamA"),
    ("table_players.csv", "players", "player_id"),
    ("table_maps_name_id.csv", "maps_name_ids", "map_id"),
    ("table_maps_id.csv", "maps_id", "map_id"),
    ("table_match_id.csv", "match_id", "series_id"),
    ("table_draft.csv", "draft", "series_id"),
    ("table_round_info.csv", "round_info", "team_map_round_id"),
    ("table_team_economy.csv", "team_economy", "team_a, team_map_round_id"),
    ("table_player_stats.csv", "player_stats", "map_id, player"),
    ("table_player_performance.csv", "player_performance", "map_id, player"),
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


def upload_tables(tables_dir="tables", chunk_size=CHUNK_SIZE, dry_run=False, log_dir="csv"):
    """Hace upsert de cada archivo de FILES_TO_UPLOAD en su tabla.

    Como upload.mjs, un bloque que falla se loguea y se sigue con el resto. El resultado de
    cada tabla se agrega a <log_dir>/upload_log.csv (status ok / error / invalid / missing).

    Args:
        dry_run (bool): solo lee y valida los csv, sin conectarse a Supabase ni escribir el log
        log_dir (str): carpeta donde vive upload_log.csv

    Returns:
        int: cantidad de bloques/archivos con error (0 = todo subido)
    """
    client = None
    if not dry_run:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not supabase_url or not supabase_key:
            raise RuntimeError("Faltan SUPABASE_URL y/o SUPABASE_SERVICE_KEY en el entorno")

        from postgrest.types import ReturnMethod
        from supabase import create_client

        client = create_client(supabase_url, supabase_key)

    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # en Actions queda el id de la corrida, para ir directo al log completo
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    entries = []

    error_count = 0
    try:
        for file, table, pk in FILES_TO_UPLOAD:
            started = time.monotonic()
            entry = {
                "run_at": run_at,
                "run_id": run_id,
                "table": table,
                "file": file,
                "rows": 0,
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
            entry["rows"] = len(rows)
            problems = validate_rows(rows, pk, file)
            for problem in problems:
                logger.error(problem)
            if problems:
                error_count += 1
                entry.update(status="invalid", failed_rows=len(rows), error=_short_error("; ".join(problems)))
                continue

            if dry_run:
                logger.info("dry-run %s -> %s: %d filas ok", file, table, len(rows))
                continue

            logger.info("upsert %s -> %s (%d filas)", file, table, len(rows))
            failed_rows = 0
            for start in range(0, len(rows), chunk_size):
                chunk = rows[start:start + chunk_size]
                try:
                    # returning=minimal: no traer las filas de vuelta (upload.mjs tampoco lo hace)
                    client.table(table).upsert(
                        chunk, on_conflict=pk, returning=ReturnMethod.minimal
                    ).execute()
                except Exception as e:
                    logger.error("error en %s (filas %d-%d): %s", table, start, start + len(chunk), e)
                    error_count += 1
                    failed_rows += len(chunk)
                    entry.update(status="error", error=_short_error(f"filas {start}-{start + len(chunk)}: {e}"))
            entry["failed_rows"] = failed_rows
            entry["duration_s"] = round(time.monotonic() - started, 1)
            logger.info("finalizado %s: %d/%d filas subidas", table, len(rows) - failed_rows, len(rows))
    finally:
        # tambien si algo explota a mitad de camino: queda registrado hasta donde llego
        if not dry_run:
            append_upload_log(entries, log_dir)
    return error_count
