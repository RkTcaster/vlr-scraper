"""CLI del pipeline: python -m vlr_pipeline {scrape,process,upload,all}.

Exit codes: 0 ok; 1 error fatal; 2 = scrape termino pero hubo matches en error_match_*.csv.
"""

import argparse
import logging
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

    p_process = sub.add_parser("process", help="consolida csv/ en tables/table_*.csv")
    p_process.add_argument("--csv-dir", default=config.DEFAULT_CSV_DIR)
    p_process.add_argument("--tables-dir", default=config.DEFAULT_TABLES_DIR)

    p_upload = sub.add_parser("upload", help="sube tables/table_*.csv a Supabase Storage")
    p_upload.add_argument("--tables-dir", default=config.DEFAULT_TABLES_DIR)
    p_upload.add_argument("--bucket", default=config.DEFAULT_BUCKET)

    p_all = sub.add_parser("all", help="scrape + process + upload")
    p_all.add_argument("--events-file", default=config.DEFAULT_EVENTS_FILE)
    p_all.add_argument("--csv-dir", default=config.DEFAULT_CSV_DIR)
    p_all.add_argument("--tables-dir", default=config.DEFAULT_TABLES_DIR)
    p_all.add_argument("--encoding", default=config.DEFAULT_SCRAPE_ENCODING)
    p_all.add_argument("--bucket", default=config.DEFAULT_BUCKET)
    p_all.add_argument("--skip-upload", action="store_true")

    return parser


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
        logger.warning("%d matches terminaron en error_match_*.csv", error_count)
        return 2
    return 0


def cmd_process(args):
    from vlr_pipeline.tables import build_all

    build_all(csv_dir=args.csv_dir, tables_dir=args.tables_dir)
    return 0


def cmd_upload(args):
    from vlr_pipeline.upload import upload_tables

    count = upload_tables(tables_dir=args.tables_dir, bucket=args.bucket)
    logger.info("%d archivos subidos al bucket '%s'", count, args.bucket)
    return 0


def cmd_all(args):
    from vlr_pipeline.tables import build_all
    from vlr_pipeline.upload import has_credentials, upload_tables

    events = config.load_events(args.events_file, only_active=True)
    scrape_exit = 0
    if events:
        from vlr_pipeline.scraper import scrape_all

        error_count = scrape_all(events, folder=args.csv_dir, encoding=args.encoding)
        if error_count:
            logger.warning("%d matches terminaron en error_match_*.csv", error_count)
            scrape_exit = 2
    else:
        logger.warning("No hay eventos activos en %s; salto el scrape", args.events_file)

    build_all(csv_dir=args.csv_dir, tables_dir=args.tables_dir)

    if args.skip_upload:
        logger.info("upload salteado (--skip-upload)")
    elif not has_credentials():
        logger.warning("Sin SUPABASE_URL/SUPABASE_SERVICE_KEY en el entorno; salto el upload")
    else:
        count = upload_tables(tables_dir=args.tables_dir, bucket=args.bucket)
        logger.info("%d archivos subidos al bucket '%s'", count, args.bucket)

    return scrape_exit


COMMANDS = {
    "scrape": cmd_scrape,
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
