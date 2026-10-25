"""Arregla el encoding de los nicks en los csv/*/round_events_*.csv ya scrapeados.

Corrida unica (idempotente) para los archivos escritos antes del fix de `json_text` en
`vlr_pipeline/parsers.py`. No pide nada a vlr: solo reescribe los csv crudos.

El problema: en round_events_ las columnas `by_player` / `victim` salen del JSON de la solapa
logs (`div.lg-map[data-map]`), que trae la secuencia escapada y `json.loads` devuelve ya
decodificada. Guardado con iso-8859-1, un nick con acento queda como un byte 0xe9 y el archivo
deja de ser utf-8 valido, a diferencia del resto del pipeline (el html se decodifica como
iso-8859-1, asi que los nicks viajan como sus bytes utf-8 reinterpretados y el csv termina en
utf-8; ver la seccion Encoding de CLAUDE.md). Consecuencias:

- `table_round_events.csv` no es utf-8 valido y `upload.read_rows` lo sube con caracteres de
  reemplazo (datos corruptos en Supabase).
- El nick no joinea con `round_buy` (economia de vivos sobreestimada en `round_situations`) ni
  con `table_players` (sin `player_id` / `victim_id`).

Que hace: en los archivos que NO son utf-8 valido, convierte `by_player` y `victim` a la forma
del resto del scraper (bytes utf-8 reinterpretados como iso-8859-1) y los reescribe con el mismo
`csv.writer` y encoding que usa `vlr_pipeline/save.py`, asi que las filas no afectadas quedan
byte-identicas. Los archivos ya validos se saltean, de modo que correrlo dos veces no hace nada.

Uso:

    python scripts/fix_logs_encoding.py --dry-run   # que archivos y que nicks tocaria
    python scripts/fix_logs_encoding.py             # aplica
    python -m vlr_pipeline process                  # regenerar tables/ despues
"""

import argparse
import csv
import glob
import io
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vlr_pipeline import config  # noqa: E402
from vlr_pipeline.log import setup_logging  # noqa: E402
from vlr_pipeline.parsers import json_text  # noqa: E402

logger = logging.getLogger("fix_logs_encoding")

# columnas de round_events_ que salen del JSON (el resto sale del html y ya esta bien)
JSON_COLUMNS = ("by_player", "victim")
RAW_ENCODING = "iso-8859-1"


def is_valid_utf8(path):
    try:
        io.open(path, "rb").read().decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def fix_file(path, dry_run=False):
    """Devuelve (filas_cambiadas, nicks_cambiados) o None si el archivo ya estaba bien."""
    if is_valid_utf8(path):
        return None

    with io.open(path, newline="", encoding=RAW_ENCODING) as handle:
        rows = list(csv.reader(handle))
    if not rows:
        return None

    header = rows[0]
    indexes = [header.index(column) for column in JSON_COLUMNS if column in header]
    if not indexes:
        logger.warning(f"{path}: no tiene las columnas {JSON_COLUMNS}, lo salteo")
        return None

    changed_rows = 0
    changed_nicks = {}
    for row in rows[1:]:
        touched = False
        for index in indexes:
            if index >= len(row) or not row[index]:
                continue
            fixed = json_text(row[index])
            if fixed != row[index]:
                changed_nicks[row[index]] = fixed
                row[index] = fixed
                touched = True
        changed_rows += touched

    if not changed_rows:
        logger.warning(f"{path}: no es utf-8 valido pero no encontre nicks para convertir")
        return 0, {}

    if not dry_run:
        # mismo writer y encoding que vlr_pipeline/save.py, para no tocar las filas sanas
        temporary = path + ".tmp"
        with io.open(temporary, "w", newline="", encoding=RAW_ENCODING) as handle:
            csv.writer(handle).writerows(rows)
        if not is_valid_utf8(temporary):
            os.remove(temporary)
            raise RuntimeError(f"{path}: el archivo reescrito sigue sin ser utf-8 valido")
        os.replace(temporary, path)

    return changed_rows, changed_nicks


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fix_logs_encoding", description=__doc__.splitlines()[0])
    parser.add_argument("--csv-dir", default=config.DEFAULT_CSV_DIR)
    parser.add_argument("--dry-run", action="store_true", help="solo informa, no escribe")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)
    setup_logging(level=args.log_level)

    paths = sorted(glob.glob(os.path.join(args.csv_dir, "*", "round_events_*.csv")))
    logger.info(f"{len(paths)} archivos round_events_ en {args.csv_dir}")

    fixed = total_rows = 0
    all_nicks = {}
    for path in paths:
        result = fix_file(path, dry_run=args.dry_run)
        if result is None:
            continue
        rows, nicks = result
        fixed += 1
        total_rows += rows
        all_nicks.update(nicks)
        verb = "convertiria" if args.dry_run else "converti"
        logger.info(f"{path}: {verb} {rows} filas, nicks {sorted(nicks.values())}")

    if not fixed:
        logger.info("nada para arreglar: todos los archivos ya son utf-8 valido")
        return 0

    logger.info(f"{'(dry-run) ' if args.dry_run else ''}{fixed} archivos, {total_rows} filas, "
                f"{len(all_nicks)} nicks distintos")
    if args.dry_run:
        logger.info("volver a correr sin --dry-run para aplicar")
    else:
        logger.info("siguiente paso: python -m vlr_pipeline process")
    return 0


if __name__ == "__main__":
    sys.exit(main())
