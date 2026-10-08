"""CLI del pipeline: python -m vlr_pipeline {scrape,backfill-logs,process,upload,all}.

Exit codes: 0 ok (incluye scrape con algunos matches en status error: se loguea un warning,
y en GitHub Actions tambien una anotacion ::warning::); 1 error fatal o fallo el upsert a Supabase;
2 lo usa solo argparse (argumentos invalidos).
"""

import argparse
import logging
import os
import sys

from vlr_pipeline import config
from vlr_pipeline.log import setup_logging

logger = logging.getLogger(__name__)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="vlr_pipeline",
        description="Scraping y procesamiento de stats de Valorant desde vlr.gg",
    )
    parser.add_argument("--log-level", default="INFO", help="DEBUG/INFO/WARNING/ERROR")
    parser.add_argument("--log-file", default=None, help="archivo de log opcional")

    sub = parser.add_subparsers(dest="command", required=True)

    p_scrape = sub.add_parser("scrape", help="scrapea los eventos activos de events.json")
    p_scrape.add_argument("--events-file", default=config.DEFAULT_EVENTS_FILE)
    p_scrape.add_argument("--event-url", action="append", default=None,
                          help="url de pagina de matches de un evento; repetible, pisa events.json")
    p_scrape.add_argument("--all-events", action="store_true",
                          help="incluye tambien los eventos con active=false")
    p_scrape.add_argument("--csv-dir", default=config.DEFAULT_CSV_DIR)
    p_scrape.add_argument("--encoding", default=config.DEFAULT_SCRAPE_ENCODING)

    p_backfill = sub.add_parser("backfill-logs",
                                help="agrega la solapa logs (compras/kills) a los matches ya scrapeados")
    p_backfill.add_argument("--csv-dir", default=config.DEFAULT_CSV_DIR)
    p_backfill.add_argument("--encoding", default=config.DEFAULT_SCRAPE_ENCODING)
    p_backfill.add_argument("--limit", type=int, default=None, help="maximo de matches en esta corrida")
    p_backfill.add_argument("--tournament", default=None,
                            help="solo un torneo (nombre normalizado, p.ej. vct_2026_emea_stage_1)")

    p_process = sub.add_parser("process", help="consolida csv/ en tables/table_*.csv")
    p_process.add_argument("--csv-dir", default=config.DEFAULT_CSV_DIR)
    p_process.add_argument("--tables-dir", default=config.DEFAULT_TABLES_DIR)

    p_upload = sub.add_parser("upload", help="upsert de tables/table_*.csv en las tablas de Supabase")
    p_upload.add_argument("--tables-dir", default=config.DEFAULT_TABLES_DIR)
    p_upload.add_argument("--csv-dir", default=config.DEFAULT_CSV_DIR,
                          help="carpeta donde se agrega upload_log.csv")
    p_upload.add_argument("--dry-run", action="store_true",
                          help="solo lee y valida los csv, sin conectarse a Supabase")
    p_upload.add_argument("--full", action="store_true",
                          help="sube todas las filas (default: incremental, solo series nuevas)")

    p_all = sub.add_parser("all", help="scrape + process + upload")
    p_all.add_argument("--events-file", default=config.DEFAULT_EVENTS_FILE)
    p_all.add_argument("--csv-dir", default=config.DEFAULT_CSV_DIR)
    p_all.add_argument("--tables-dir", default=config.DEFAULT_TABLES_DIR)
    p_all.add_argument("--encoding", default=config.DEFAULT_SCRAPE_ENCODING)
    p_all.add_argument("--skip-upload", action="store_true")
    p_all.add_argument("--full", action="store_true",
                       help="upload de todas las filas (default: incremental, solo series nuevas)")

    return parser


def warn_scrape_errors(error_count):
    """Fallo parcial del scrape: no corta el pipeline, lo scrapeado ok se procesa y se sube igual."""
    message = f"{error_count} matches terminaron con error (ver csv/scrape_log.csv)"
    logger.warning(message)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::warning::{message}", flush=True)


def cmd_scrape(args):
    from vlr_pipeline.scraper import scrape_all

    if args.event_url:
        events = [{"name": url, "url": url} for url in args.event_url]
    else:
        events = config.load_events(args.events_file, only_active=not args.all_events)

    if not events:
        logger.warning("No hay eventos activos para scrapear")
        return 0

    error_count = scrape_all(events, folder=args.csv_dir, encoding=args.encoding)
    if error_count:
        warn_scrape_errors(error_count)
    return 0


def cmd_backfill_logs(args):
    from vlr_pipeline.scraper import backfill_logs

    error_count = backfill_logs(
        folder=args.csv_dir, encoding=args.encoding, limit=args.limit, tournament=args.tournament
    )
    if error_count:
        warn_scrape_errors(error_count)
    return 0


def cmd_process(args):
    from vlr_pipeline.tables import build_all

    build_all(csv_dir=args.csv_dir, tables_dir=args.tables_dir)
    return 0


def cmd_upload(args):
    from vlr_pipeline.upload import upload_tables

    error_count = upload_tables(
        tables_dir=args.tables_dir, dry_run=args.dry_run, log_dir=args.csv_dir, full=args.full
    )
    if error_count:
        logger.error("upload con %d errores", error_count)
        return 1
    return 0


def cmd_all(args):
    from vlr_pipeline.tables import build_all
    from vlr_pipeline.upload import has_credentials, upload_tables

    events = config.load_events(args.events_file, only_active=True)
    if events:
        from vlr_pipeline.scraper import scrape_all

        error_count = scrape_all(events, folder=args.csv_dir, encoding=args.encoding)
        if error_count:
            warn_scrape_errors(error_count)
    else:
        logger.warning("No hay eventos activos en %s; salto el scrape", args.events_file)

    build_all(csv_dir=args.csv_dir, tables_dir=args.tables_dir)

    if args.skip_upload:
        logger.info("upload salteado (--skip-upload)")
    elif not has_credentials():
        logger.warning("Sin SUPABASE_URL/SUPABASE_SERVICE_KEY en el entorno; salto el upload")
    else:
        if upload_tables(tables_dir=args.tables_dir, log_dir=args.csv_dir, full=args.full):
            logger.error("upload a Supabase con errores")
            return 1

    return 0


COMMANDS = {
    "scrape": cmd_scrape,
    "backfill-logs": cmd_backfill_logs,
    "process": cmd_process,
    "upload": cmd_upload,
    "all": cmd_all,
}


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(level=args.log_level, log_file=args.log_file)

    try:
        return COMMANDS[args.command](args)
    except Exception:
        logger.exception("fallo el comando '%s'", args.command)
        return 1
