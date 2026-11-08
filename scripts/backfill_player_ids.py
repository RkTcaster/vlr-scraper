"""Backfill de player_id_vlr (id de jugador de vlr) en los player_stats_*.csv ya scrapeados.

vlr identifica a cada jugador por /player/<id>/; el pipeline lo hacia por nick, y dos jugadores con
el mismo nick en el mismo equipo (785988: dos "Splotza" en RADI) rompen las PK (map_id, player).
Desde 2026-11-07 get_player_stats guarda player_id_vlr; este script lo completa para lo viejo.

Pasos:

1. Sin red: agrega la columna player_id_vlr (vacia) a todo player_stats_*.csv que no la tenga.
   Hace falta antes de cualquier scrape nuevo: save_player_stats_to_csv agrega filas con el header
   del dict, y en un csv sin la columna quedarian corridas.
2. Por cada match sin ningun id (scrapeado antes de la columna): pide solo el overview (1 request)
   y llena el id cruzando por
   (map_id_vlr, player, agent). Si vlr renombro al jugador desde el scrape, cae a la posicion de
   la fila dentro del mapa (el orden del csv es el de la pagina) cuando la cantidad coincide.
   Guarda cada --save-every matches: cortarlo y volver a correrlo retoma donde quedo.
   Un match con algunos ids y otros vacios ya se proceso: los vacios son jugadores sin perfil en vlr
   (nick con mod-tbd, sin link) y no hay nada que bajar; tables.raw_player_ids les da un id. Con
   --recheck se vuelven a pedir igual (por si vlr les creo perfil).

Uso:

    python scripts/backfill_player_ids.py --dry-run       # plan, sin red (igual hace el paso 1)
    python scripts/backfill_player_ids.py --max 5         # prueba corta
    python scripts/backfill_player_ids.py                 # todo (~1 request por match)
    python scripts/backfill_player_ids.py --recheck       # tambien los matches con jugadores sin perfil
"""

import argparse
import csv
import glob
import logging
import os
import re
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vlr_pipeline import config  # noqa: E402
from vlr_pipeline.log import setup_logging  # noqa: E402
from vlr_pipeline.tracking import RAW_ENCODING  # noqa: E402

logger = logging.getLogger("backfill_player_ids")

ID_COLUMN = "player_id_vlr"
SERIES_RE = re.compile(r"vlr\.gg/(\d+)")


def read_csv_rows(path):
    with open(path, encoding=RAW_ENCODING, newline="") as f:
        return list(csv.reader(f))


def write_csv_rows(path, rows):
    # mismo writer que save_player_stats_to_csv (csv.writer, \r\n); latin-1 ida y vuelta deja
    # los bytes tal cual (los nicks viajan como utf-8 reinterpretado, ver CLAUDE.md)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding=RAW_ENCODING, newline="") as f:
        csv.writer(f).writerows(rows)
    os.replace(tmp, path)


def ensure_id_column(paths, dry_run=False):
    """Paso 1: agrega player_id_vlr vacia donde falte. Devuelve cuantos archivos cambio."""
    changed = 0
    for path in paths:
        rows = read_csv_rows(path)
        if not rows or ID_COLUMN in rows[0]:
            continue
        changed += 1
        if dry_run:
            continue
        rows[0].append(ID_COLUMN)
        for row in rows[1:]:
            row.append("")
        write_csv_rows(path, rows)
    return changed


def pending_by_file(paths, recheck=False):
    """{path: {series_id: source_url}} de las series sin ningun id (con recheck: con alguna fila sin id)."""
    pending = {}
    for path in paths:
        rows = read_csv_rows(path)
        header = rows[0]
        if ID_COLUMN not in header:
            continue
        i_id, i_url = header.index(ID_COLUMN), header.index("source_url")
        series, with_id = {}, set()
        for row in rows[1:]:
            match = SERIES_RE.search(row[i_url])
            if not match:
                continue
            if row[i_id]:
                with_id.add(match.group(1))
            else:
                series.setdefault(match.group(1), row[i_url])
        if not recheck:
            series = {key: url for key, url in series.items() if key not in with_id}
        if series:
            pending[path] = series
    return pending


def fill_series(rows, series_id, ids):
    """Llena el id de las filas de una serie con el dict de get_player_ids. Devuelve (llenas, sin id)."""
    header = rows[0]
    col = {name: header.index(name) for name in ("player", "agent", "map_id_vlr", "source_url", ID_COLUMN)}

    by_game = defaultdict(list)  # ids de la pagina por mapa, en orden
    for (game, _player, _agent), player_id in ids.items():
        by_game[game].append(player_id)

    series_rows = defaultdict(list)
    for row in rows[1:]:
        match = SERIES_RE.search(row[col["source_url"]])
        if match and match.group(1) == series_id:
            series_rows[row[col["map_id_vlr"]]].append(row)

    filled = missing = 0
    for game, game_rows in series_rows.items():
        page_ids = by_game.get(game, [])
        for position, row in enumerate(game_rows):
            player_id = ids.get((game, row[col["player"]], row[col["agent"]]), "")
            if not player_id and len(page_ids) == len(game_rows):
                player_id = page_ids[position]
            if player_id:
                row[col[ID_COLUMN]] = player_id
                filled += 1
            else:
                missing += 1
    return filled, missing


def build_parser():
    parser = argparse.ArgumentParser(prog="backfill_player_ids", description=__doc__.splitlines()[0])
    parser.add_argument("--csv-dir", default=config.DEFAULT_CSV_DIR)
    parser.add_argument("--min-interval", type=float, default=3.0, help="segundos minimos entre requests")
    parser.add_argument("--jitter", type=float, default=1.5, help="segundos aleatorios extra entre requests")
    parser.add_argument("--save-every", type=int, default=10, help="matches entre guardados")
    parser.add_argument("--max", type=int, default=None, help="tope de matches en esta corrida")
    parser.add_argument("--recheck", action="store_true",
                        help="volver a pedir los matches con jugadores sin perfil en vlr (ids vacios parciales)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--log-file", default=os.path.join("logs", "backfill_player_ids.log"))
    return parser


def run(args):
    paths = sorted(glob.glob(os.path.join(args.csv_dir, "*", "player_stats_*.csv")))
    changed = ensure_id_column(paths, dry_run=args.dry_run)
    logger.info(f"paso 1: columna {ID_COLUMN} agregada a {changed} de {len(paths)} archivos")

    pending = pending_by_file(paths, recheck=args.recheck)
    total = sum(len(series) for series in pending.values())
    target = total if args.max is None else min(total, args.max)
    logger.info(f"paso 2: {total} series sin id en {len(pending)} archivos; voy a procesar {target}")
    if args.dry_run or not target:
        return 0

    from vlr_pipeline.parsers import get_player_ids
    from scripts.backfill_all_logs import install_throttle

    throttle = install_throttle(args.min_interval, args.jitter)
    import vlr_pipeline.parsers as parsers

    started = time.monotonic()
    done = errors = filled_total = missing_total = 0
    for path, series in pending.items():
        if done >= target:
            break
        rows = read_csv_rows(path)
        unsaved = 0
        for series_id, url in series.items():
            if done >= target:
                break
            done += 1
            try:
                ids = get_player_ids(parsers.soup_open(url))
            except Exception as exc:  # un match roto no corta el resto
                errors += 1
                logger.warning(f"{series_id}: no pude leer el overview ({exc})")
                continue
            filled, missing = fill_series(rows, series_id, ids)
            filled_total += filled
            missing_total += missing
            if missing:
                # jugadores sin perfil en vlr (mod-tbd): normal en qualifiers, raw_player_ids los cubre
                logger.info(f"{series_id}: {missing} filas sin perfil en vlr ({url})")
            unsaved += 1
            if unsaved >= args.save_every:
                write_csv_rows(path, rows)
                unsaved = 0
                logger.info(f"{done}/{target} series, {format_elapsed(started)}")
        if unsaved:
            write_csv_rows(path, rows)
        logger.info(f"{os.path.basename(path)} listo ({done}/{target})")

    logger.info(
        f"fin: {done} series, {filled_total} filas con id, {missing_total} sin id, {errors} errores, "
        f"{throttle['requests']} requests en {format_elapsed(started)}"
    )
    return 1 if errors > done * 0.3 else 0


def format_elapsed(started):
    minutes, seconds = divmod(int(time.monotonic() - started), 60)
    return f"{minutes} min {seconds:02d} s"


def main(argv=None):
    args = build_parser().parse_args(argv)
    setup_logging(args.log_level, log_file=args.log_file)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
