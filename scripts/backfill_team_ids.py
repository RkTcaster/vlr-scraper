"""Backfill del id de equipo de vlr (team_id_vlr) en round_detail_ y player_stats_ ya scrapeados.

El tricode no identifica a un equipo: se repite entre equipos distintos ("THE" en cuatro qualifiers,
FUR = FURIA y un equipo del Brazil Open Qualifier) y hasta en un mismo match (785082, FAKE vs FAKE).
Desde 2026-11-10 el scraper guarda el id de vlr (/team/<id>/ del header del match):
round_detail_ suma team_a_id_vlr, team_b_id_vlr, team_a_name, team_b_name y player_stats_ suma
team_id_vlr (por posicion de la tabla del overview). Este script lo completa para lo viejo.

Pasos:

1. Sin red: agrega las columnas (vacias) a todo round_detail_ / player_stats_ que no las tenga.
2. Por cada serie de round_detail_ sin team_a_id_vlr: pide solo el overview (1 request), llena las
   cuatro columnas en round_detail_ y team_id_vlr en el player_stats_ del mismo torneo, cruzando por
   (map_id_vlr, player_id_vlr), despues por (map_id_vlr, nick) y por ultimo por la posicion de la fila
   en el mapa si la cantidad coincide. Guarda cada --save-every series: cortarlo y volver a
   correrlo retoma donde quedo. Una serie cuenta como hecha cuando tiene team_a_name (el nombre
   siempre viene del <title>); un equipo sin pagina en vlr queda con el id vacio y tables le da
   tbd_<TAG>.

Uso:

    python scripts/backfill_team_ids.py --dry-run       # plan, sin red (igual hace el paso 1)
    python scripts/backfill_team_ids.py --max 5         # prueba corta
    python scripts/backfill_team_ids.py                 # todo (~1 request por serie)
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

logger = logging.getLogger("backfill_team_ids")

ROUND_COLUMNS = ["team_a_id_vlr", "team_b_id_vlr", "team_a_name", "team_b_name"]
STATS_COLUMNS = ["team_id_vlr"]
SERIES_RE = re.compile(r"vlr\.gg/(\d+)")


def read_csv_rows(path):
    with open(path, encoding=RAW_ENCODING, newline="") as f:
        return list(csv.reader(f))


def write_csv_rows(path, rows):
    # mismo writer que save.append_dict_rows (csv.writer, \r\n); latin-1 ida y vuelta deja los
    # bytes tal cual (los textos viajan como utf-8 reinterpretado, ver "Encoding" en CLAUDE.md)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding=RAW_ENCODING, newline="") as f:
        csv.writer(f).writerows(rows)
    os.replace(tmp, path)


def ensure_columns(paths, columns, dry_run=False):
    """Paso 1: agrega las columnas vacias al final donde falten. Devuelve cuantos archivos cambio."""
    changed = 0
    for path in paths:
        rows = read_csv_rows(path)
        if not rows:
            continue
        missing = [column for column in columns if column not in rows[0]]
        if not missing:
            continue
        changed += 1
        if dry_run:
            continue
        rows[0].extend(missing)
        for row in rows[1:]:
            row.extend([""] * len(missing))
        write_csv_rows(path, rows)
    return changed


def series_of(row, i_url):
    match = SERIES_RE.search(row[i_url])
    return match.group(1) if match else None


def pending_series(path):
    """{series_id: source_url} de round_detail_ sin nombre de equipo (nunca backfilleadas)."""
    rows = read_csv_rows(path)
    header = rows[0]
    i_url = header.index("source_url")
    i_name = header.index("team_a_name") if "team_a_name" in header else None  # --dry-run sin paso 1
    done, pending = set(), {}
    for row in rows[1:]:
        series_id = series_of(row, i_url)
        if series_id is None:
            continue
        if i_name is not None and row[i_name]:
            done.add(series_id)
        else:
            pending.setdefault(series_id, row[i_url])
    return {key: url for key, url in pending.items() if key not in done}


def fill_round_detail(rows, series_id, info):
    """Llena las cuatro columnas de equipo en las filas de la serie. Devuelve cuantas filas lleno."""
    header = rows[0]
    i_url = header.index("source_url")
    values = {
        "team_a_id_vlr": info.get("team_a_id_vlr") or "",
        "team_b_id_vlr": info.get("team_b_id_vlr") or "",
        "team_a_name": info.get("team_a") or "",
        "team_b_name": info.get("team_b") or "",
    }
    filled = 0
    for row in rows[1:]:
        if series_of(row, i_url) != series_id:
            continue
        for column, value in values.items():
            row[header.index(column)] = value
        filled += 1
    return filled


def fill_player_stats(rows, series_id, stats):
    """team_id_vlr de las filas de player_stats_ de la serie, con el dict de get_player_stats.

    Devuelve (llenas, sin equipo).
    """
    header = rows[0]
    col = {name: header.index(name) for name in ("player", "map_id_vlr", "source_url", "player_id_vlr", "team_id_vlr")}

    by_player, by_nick, by_game = {}, {}, defaultdict(list)
    for game, player, player_id, team_id in zip(
        stats["map_id_vlr"], stats["player"], stats["player_id_vlr"], stats["team_id_vlr"]
    ):
        game = str(game)
        if player_id:
            by_player[(game, player_id)] = team_id
        by_nick.setdefault((game, player), set()).add(team_id)
        by_game[game].append(team_id)

    series_rows = defaultdict(list)
    for row in rows[1:]:
        if series_of(row, col["source_url"]) == series_id:
            series_rows[row[col["map_id_vlr"]]].append(row)

    filled = missing = 0
    for game, game_rows in series_rows.items():
        page = by_game.get(game, [])
        for position, row in enumerate(game_rows):
            team_id = by_player.get((game, row[col["player_id_vlr"]]), "")
            if not team_id:
                nick_ids = by_nick.get((game, row[col["player"]]), set())
                team_id = next(iter(nick_ids)) if len(nick_ids) == 1 else ""
            if not team_id and len(page) == len(game_rows):
                team_id = page[position]
            if team_id:
                row[col["team_id_vlr"]] = team_id
                filled += 1
            else:
                missing += 1
    return filled, missing


def build_parser():
    parser = argparse.ArgumentParser(prog="backfill_team_ids", description=__doc__.splitlines()[0])
    parser.add_argument("--csv-dir", default=config.DEFAULT_CSV_DIR)
    parser.add_argument("--min-interval", type=float, default=3.0, help="segundos minimos entre requests")
    parser.add_argument("--jitter", type=float, default=1.5, help="segundos aleatorios extra entre requests")
    parser.add_argument("--save-every", type=int, default=10, help="series entre guardados")
    parser.add_argument("--max", type=int, default=None, help="tope de series en esta corrida")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--log-file", default=os.path.join("logs", "backfill_team_ids.log"))
    return parser


def run(args):
    round_paths = sorted(glob.glob(os.path.join(args.csv_dir, "*", "round_detail_*.csv")))
    stats_paths = sorted(glob.glob(os.path.join(args.csv_dir, "*", "player_stats_*.csv")))
    changed = ensure_columns(round_paths, ROUND_COLUMNS, dry_run=args.dry_run)
    changed += ensure_columns(stats_paths, STATS_COLUMNS, dry_run=args.dry_run)
    logger.info(f"paso 1: columnas agregadas en {changed} archivos")

    pending = {path: pending_series(path) for path in round_paths}
    pending = {path: series for path, series in pending.items() if series}
    total = sum(len(series) for series in pending.values())
    target = total if args.max is None else min(total, args.max)
    logger.info(f"paso 2: {total} series sin equipo en {len(pending)} torneos; voy a procesar {target}")
    if args.dry_run or not target:
        return 0

    from scripts.backfill_all_logs import install_throttle
    import vlr_pipeline.parsers as parsers

    throttle = install_throttle(args.min_interval, args.jitter)

    started = time.monotonic()
    done = errors = no_id = stats_missing = 0
    for round_path, series in pending.items():
        if done >= target:
            break
        folder = os.path.dirname(round_path)
        stats_path = os.path.join(folder, os.path.basename(round_path).replace("round_detail_", "player_stats_", 1))
        round_rows = read_csv_rows(round_path)
        stats_rows = read_csv_rows(stats_path) if os.path.exists(stats_path) else None
        unsaved = 0

        def save():
            write_csv_rows(round_path, round_rows)
            if stats_rows is not None:
                write_csv_rows(stats_path, stats_rows)

        for series_id, url in series.items():
            if done >= target:
                break
            done += 1
            try:
                soup = parsers.soup_open(url)
                info = parsers.get_basic_match_info(soup, url)
                stats = parsers.get_player_stats(soup, info)
            except Exception as exc:  # un match roto no corta el resto
                errors += 1
                logger.warning(f"{series_id}: no pude leer el overview ({exc})")
                continue
            if not info.get("team_a_id_vlr") or not info.get("team_b_id_vlr"):
                no_id += 1
                logger.info(f"{series_id}: equipo sin pagina en vlr ({info.get('team_a')} / {info.get('team_b')})")
            fill_round_detail(round_rows, series_id, info)
            if stats_rows is not None:
                _, missing = fill_player_stats(stats_rows, series_id, stats)
                if missing:
                    stats_missing += missing
                    logger.warning(f"{series_id}: {missing} filas de player_stats sin team_id_vlr")
            unsaved += 1
            if unsaved >= args.save_every:
                save()
                unsaved = 0
                logger.info(f"{done}/{target} series, {format_elapsed(started)}")
        if unsaved:
            save()
        logger.info(f"{os.path.basename(folder)} listo ({done}/{target})")

    logger.info(
        f"fin: {done} series, {no_id} con algun equipo sin id, {stats_missing} filas de player_stats sin "
        f"equipo, {errors} errores, {throttle['requests']} requests en {format_elapsed(started)}"
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
