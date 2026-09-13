"""Upsert de tables/table_*.csv en tablas de Postgres de Supabase (las que usa rktdata.ar).

Port de scripts/upload.mjs del repo de rktdata: mismo mapeo archivo -> tabla -> PK, bloques de
200 filas y upsert con onConflict. Los valores viajan como texto, igual que csv-parser en node.

Requiere las variables de entorno SUPABASE_URL y SUPABASE_SERVICE_KEY (service role key;
en GitHub Actions se cargan como secrets).
"""

import csv
import logging
import os
from collections import Counter

logger = logging.getLogger(__name__)

CHUNK_SIZE = 200

# (archivo, tabla, pk para on_conflict). Mismo orden que upload.mjs. Agregar aca las tablas nuevas.
FILES_TO_UPLOAD = [
    ("table_region.csv", "regions", "reg_id"),
    ("table_tournament.csv", "tournament", "tour_id"),
    ("table_tournament_played.csv", "tournament_played", "tour_id, teamA"),
    ("table_players.csv", "players", "player_id"),
    ("table_teams.csv", "teams", "team_id"),
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


def upload_tables(tables_dir="tables", chunk_size=CHUNK_SIZE, dry_run=False):
    """Hace upsert de cada archivo de FILES_TO_UPLOAD en su tabla.

    Como upload.mjs, un bloque que falla se loguea y se sigue con el resto.

    Args:
        dry_run (bool): solo lee y valida los csv, sin conectarse a Supabase

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

    error_count = 0
    for file, table, pk in FILES_TO_UPLOAD:
        path = os.path.join(tables_dir, file)
        if not os.path.exists(path):
            logger.warning("saltando %s: no existe en %s", file, tables_dir)
            continue

        rows = read_rows(path)
        problems = validate_rows(rows, pk, file)
        for problem in problems:
            logger.error(problem)
        if problems:
            error_count += 1
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
        logger.info("finalizado %s: %d/%d filas subidas", table, len(rows) - failed_rows, len(rows))

    return error_count
