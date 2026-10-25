"""Backfill de la solapa logs de vlr para todos los matches ya scrapeados, en tandas y sin apurar a vlr.

Al 2026-10-20 hay 537 matches con status ok y has_logs vacio en csv/scrape_log.csv: son los que
no tienen round_buy_ / round_events_, y por lo tanto quedan afuera de table_round_buy,
table_round_events, table_round_summary y table_round_situations.

Que agrega sobre `python -m vlr_pipeline backfill-logs`:

- **Throttle global de requests.** backfill_logs duerme 1-2 s entre matches, pero get_round_logs
  pide una pagina por mapa jugado (2,56 de promedio) sin pausa entre ellas: son rafagas de 3 o 4
  requests seguidos. Este script envuelve soup_open y garantiza un intervalo minimo entre
  *cualquier* par de requests, con jitter para no quedar en un patron fijo.
- **Tandas con pausa larga.** Procesa --batch matches, para --pause segundos y sigue.
- **Corta si algo anda mal.** Si una tanda no logra marcar ni un match (todos error) o si la tasa
  de error global se dispara, aborta en vez de seguir golpeando a vlr.
- **Reanudable.** backfill_logs guarda scrape_log.csv despues de cada match y toma los pendientes
  de ahi, asi que se puede cortar con Ctrl+C y volver a correr el script tal cual.

Uso:

    # ver el plan, sin tocar la red
    python scripts/backfill_all_logs.py --dry-run

    # correr todo con los defaults (~2 h 30 para los 537 matches)
    python scripts/backfill_all_logs.py

    # mas suave todavia, y solo un torneo
    python scripts/backfill_all_logs.py --min-interval 5 --batch 10 --pause 180 \
        --tournament vct_2026_emea_stage_1

    # una prueba corta antes de largar todo
    python scripts/backfill_all_logs.py --max 5

    # volver a bajar matches cuyo log vlr devolvio incompleto
    python scripts/backfill_all_logs.py --redo 698906 712828 595655

Despues hay que reconstruir las tablas (el script lo hace solo con --process):

    python -m vlr_pipeline process

Y para que Supabase vea las series nuevas: `python -m vlr_pipeline upload --full`
(el incremental no re-envia series ya subidas, ver CLAUDE.md).
"""

import argparse
import glob
import logging
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from vlr_pipeline import config  # noqa: E402
from vlr_pipeline.log import setup_logging  # noqa: E402
from vlr_pipeline.tables import match_id_vlr  # noqa: E402
from vlr_pipeline.tracking import RAW_ENCODING, load_log, save_log  # noqa: E402

logger = logging.getLogger("backfill_all_logs")

# medido sobre table_round_info: 2,56 mapas por serie, mas la pagina principal del match
REQUESTS_PER_MATCH = 1 + 2.56
# si falla mas de esto despues de MIN_SAMPLE matches, algo cambio en vlr (o nos esta cortando)
MAX_ERROR_RATE = 0.3
MIN_SAMPLE = 20


def build_parser():
    parser = argparse.ArgumentParser(
        prog="backfill_all_logs",
        description="Backfill de la solapa logs en tandas, con throttle de requests",
    )
    parser.add_argument("--csv-dir", default=config.DEFAULT_CSV_DIR)
    parser.add_argument("--encoding", default=config.DEFAULT_SCRAPE_ENCODING)
    parser.add_argument("--tournament", default=None,
                        help="solo un torneo (nombre normalizado, p.ej. vct_2026_emea_stage_1)")
    parser.add_argument("--batch", type=int, default=25, help="matches por tanda (default 25)")
    parser.add_argument("--pause", type=float, default=60.0,
                        help="segundos de pausa entre tandas (default 60)")
    parser.add_argument("--min-interval", type=float, default=3.0,
                        help="segundos minimos entre requests, incluidos los de cada mapa (default 3)")
    parser.add_argument("--jitter", type=float, default=1.5,
                        help="segundos aleatorios que se suman al intervalo (default 1.5)")
    parser.add_argument("--max", type=int, default=None,
                        help="tope de matches en esta corrida (default: todos los pendientes)")
    parser.add_argument("--redo", nargs="+", metavar="SERIES_ID", default=None,
                        help="vuelve a bajar los logs de estas series (les borra has_logs en scrape_log); "
                             "para matches cuyo log vlr devolvio incompleto")
    parser.add_argument("--sync-has-logs", action="store_true",
                        help="marca has_logs segun los round_events_ que ya estan en csv/, sin pedir nada a "
                             "vlr; sirve para recuperar scrape_log.csv despues de un conflicto con el bot")
    parser.add_argument("--dry-run", action="store_true",
                        help="muestra el plan y la estimacion, sin pedir nada a vlr")
    parser.add_argument("--process", action="store_true",
                        help="al terminar corre build_all para regenerar tables/")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--log-file", default=os.path.join("logs", "backfill_logs.log"),
                        help="archivo de log (logs/ esta gitignoreado)")
    return parser


def pending_matches(csv_dir, tournament=None):
    """Matches ok sin logs en scrape_log.csv, el mismo criterio que usa backfill_logs.

    Usa tracking.load_log para leerlo igual que el resto del paquete (iso-8859-1, sin NaN).
    """
    log = load_log(csv_dir)
    pending = log[(log["status"] == "ok") & (log["has_logs"] == "")]
    if tournament:
        pending = pending[pending["tournament"] == tournament]
    return pending


def format_duration(seconds):
    hours, rest = divmod(int(seconds), 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours} h {minutes:02d} min"
    if minutes:
        return f"{minutes} min {seconds:02d} s"
    return f"{seconds} s"


def estimate_seconds(matches, args):
    """Estimacion gruesa: requests * intervalo promedio + las pausas entre tandas."""
    requests = matches * REQUESTS_PER_MATCH
    per_request = args.min_interval + args.jitter / 2
    batches = max((matches + args.batch - 1) // args.batch - 1, 0)
    return requests * per_request + batches * args.pause


def install_throttle(min_interval, jitter):
    """Envuelve soup_open para que nunca haya dos requests a vlr mas cerca que min_interval.

    get_round_logs pide una pagina por mapa sin pausa propia: sin esto son rafagas de 3-4
    requests seguidos. Se parchea el nombre en cada modulo que lo importo (igual que
    tests/conftest.py), no en fetch, porque scraper y parsers ya tienen su referencia.
    """
    import vlr_pipeline.parsers as parsers
    import vlr_pipeline.scraper as scraper

    original = parsers.soup_open
    state = {"last": 0.0, "requests": 0, "waited": 0.0}

    def throttled(url=None, decode="iso-8859-1"):
        wait = state["last"] + min_interval + random.uniform(0, jitter) - time.monotonic()
        if wait > 0:
            time.sleep(wait)
            state["waited"] += wait
        state["last"] = time.monotonic()
        state["requests"] += 1
        return original(url=url, decode=decode)

    parsers.soup_open = throttled
    scraper.soup_open = throttled
    return state


def reset_has_logs(csv_dir, series_ids, dry_run=False):
    """Borra has_logs de esas series para que backfill_logs las vuelva a bajar.

    No toca status ni attempts: el match ya esta ok, lo que se re-scrapea es solo la solapa logs
    (backfill_logs purga round_buy_ / round_events_ del match antes de reescribirlos).
    """
    log = load_log(csv_dir)
    wanted = {str(series) for series in series_ids}
    found = log["series_id"].astype(str).isin(wanted)
    missing = wanted - set(log.loc[found, "series_id"].astype(str))
    if missing:
        logger.warning(f"--redo: estas series no estan en scrape_log: {sorted(missing)}")
    not_ok = log.loc[found & (log["status"] != "ok"), "series_id"].astype(str)
    if len(not_ok):
        logger.warning(f"--redo: estas series no estan en ok, las salteo: {sorted(not_ok)}")

    target = found & (log["status"] == "ok")
    logger.info(f"--redo: reseteo has_logs de {int(target.sum())} series")
    if not dry_run and target.any():
        log.loc[target, "has_logs"] = ""
        save_log(log, csv_dir)
    return int(target.sum())


def sync_has_logs(csv_dir, dry_run=False):
    """Marca has_logs en scrape_log.csv segun los round_events_ que ya estan en csv/, sin red.

    Los csv de la solapa logs estan en .gitignore pero scrape_log.csv no, asi que el commit diario
    del bot puede pisar el has_logs del backfill. Esto lo reconstruye leyendo que series tienen
    filas de eventos en disco, en vez de volver a bajar 537 matches.
    """
    series_on_disk = set()
    for path in sorted(glob.glob(os.path.join(csv_dir, "*", "round_events_*.csv"))):
        urls = pd.read_csv(path, encoding=RAW_ENCODING, usecols=["source_url"], low_memory=False)
        series_on_disk.update(url for url in urls["source_url"].map(match_id_vlr).dropna())
    logger.info(f"--sync-has-logs: {len(series_on_disk)} series con eventos en {csv_dir}")

    log = load_log(csv_dir)
    on_disk = log["series_id"].astype(str).isin(series_on_disk)
    to_mark = on_disk & (log["status"] == "ok") & (log["has_logs"] == "")
    # has_logs == "False" son matches que vlr no tiene con solapa logs: no deberian estar en disco
    stale = ~on_disk & (log["has_logs"] == "True")
    logger.info(f"--sync-has-logs: marco {int(to_mark.sum())} series como has_logs=True")
    if stale.any():
        logger.warning(
            f"--sync-has-logs: {int(stale.sum())} series dicen has_logs pero no tienen eventos en disco "
            "(si se borraron los csv, correr sin --sync-has-logs para volver a bajarlos)"
        )
    if not dry_run and to_mark.any():
        log.loc[to_mark, "has_logs"] = "True"
        save_log(log, csv_dir)
    return int(to_mark.sum())


def run(args):
    if args.sync_has_logs:
        sync_has_logs(args.csv_dir, dry_run=args.dry_run)
        return 0

    if args.redo:
        reset_has_logs(args.csv_dir, args.redo, dry_run=args.dry_run)

    pending = pending_matches(args.csv_dir, args.tournament)
    total = len(pending)
    target = total if args.max is None else min(total, args.max)

    scope = f" de {args.tournament}" if args.tournament else ""
    logger.info(f"{total} matches ok sin logs{scope}; voy a procesar {target}")
    if total:
        counts = pending["tournament"].value_counts()
        logger.info("por torneo: " + ", ".join(f"{name} {count}" for name, count in counts.items()))
    logger.info(
        f"plan: tandas de {args.batch} con {format_duration(args.pause)} de pausa, "
        f"{args.min_interval}-{args.min_interval + args.jitter} s entre requests "
        f"(~{int(target * REQUESTS_PER_MATCH)} requests a vlr)"
    )
    logger.info(f"estimado: {format_duration(estimate_seconds(target, args))}")

    if args.dry_run:
        logger.info("dry-run: no pido nada a vlr")
        return 0
    if not target:
        logger.info("nada que hacer")
        return 0

    from vlr_pipeline.scraper import backfill_logs

    throttle = install_throttle(args.min_interval, args.jitter)
    started = time.monotonic()
    done = errors = batch_number = 0
    interrupted = False

    try:
        while done < target:
            batch_number += 1
            remaining = target - done
            limit = min(args.batch, remaining)
            before = len(pending_matches(args.csv_dir, args.tournament))

            logger.info(f"--- tanda {batch_number}: {limit} matches ({done}/{target} listos) ---")
            errors += backfill_logs(
                folder=args.csv_dir, encoding=args.encoding, limit=limit, tournament=args.tournament
            )

            after = len(pending_matches(args.csv_dir, args.tournament))
            progress = before - after
            done += progress

            if progress == 0:
                logger.error(
                    "la tanda no marco ningun match (todos error): corto para no seguir "
                    "golpeando a vlr. Revisar csv/scrape_log.csv y el log de arriba."
                )
                break
            if done >= MIN_SAMPLE and errors / (done + errors) > MAX_ERROR_RATE:
                logger.error(
                    f"tasa de error {errors / (done + errors):.0%} sobre {done + errors} matches: "
                    "corto. Puede ser un cambio de layout en vlr o un bloqueo por rate limit."
                )
                break

            elapsed = time.monotonic() - started
            if done < target:
                eta = elapsed / done * (target - done) + args.pause
                logger.info(
                    f"{done}/{target} listos en {format_duration(elapsed)} "
                    f"({errors} errores); faltan ~{format_duration(eta)}. "
                    f"Pausa de {format_duration(args.pause)}"
                )
                time.sleep(args.pause)
    except KeyboardInterrupt:
        interrupted = True
        logger.warning("interrumpido con Ctrl+C")

    elapsed = time.monotonic() - started
    logger.info(
        f"fin: {done} matches con logs, {errors} errores, {throttle['requests']} requests "
        f"en {format_duration(elapsed)} (throttle durmio {format_duration(throttle['waited'])})"
    )
    left = len(pending_matches(args.csv_dir, args.tournament))
    if left:
        logger.info(f"quedan {left} pendientes: volver a correr el script para seguir")

    if args.process and done:
        logger.info("regenerando tables/ ...")
        from vlr_pipeline.tables import build_all

        build_all(csv_dir=args.csv_dir, tables_dir=config.DEFAULT_TABLES_DIR)
    elif done:
        logger.info("siguiente paso: python -m vlr_pipeline process")

    if interrupted:
        return 130
    return 1 if errors and not done else 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.log_file:
        os.makedirs(os.path.dirname(args.log_file) or ".", exist_ok=True)
    setup_logging(level=args.log_level, log_file=args.log_file)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
