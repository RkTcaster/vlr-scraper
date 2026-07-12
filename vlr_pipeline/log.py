import logging
import sys


def setup_logging(level="INFO", log_file=None):
    """Configura logging a stderr y opcionalmente a un archivo (utf-8)."""
    handlers = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )
