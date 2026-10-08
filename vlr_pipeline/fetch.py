import logging
import time

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# urllib sin header suele recibir 403 desde IPs de datacenter (GitHub Actions).
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
# sin timeout una conexion colgada deja el job trabado hasta el limite de Actions (6 h)
TIMEOUT_SECONDS = 30
# reintentos ante fallas transitorias (429, 5xx, timeout/conexion); 404 y demas 4xx no
RETRIES = 2
BACKOFF_SECONDS = 10


def is_transient(error):
    """True si vale la pena reintentar el request"""
    if isinstance(error, HTTPError):
        return error.code == 429 or error.code >= 500
    return isinstance(error, (URLError, TimeoutError, ConnectionError))


def soup_open(url=None, decode="iso-8859-1"):
    """Open an url with BeautifulSoup and return an bs4.BeautifulSoup

    Args:
        url (str, optional): vlr match url. Defaults to None.
        decode (str, optional): decode for the BeautifulSoup. Defaults to "iso-8859-1".

    Returns:
        bs4.BeautifulSoup: BeautifulSoup object with the HTML info
    """
    if url is None:
        logger.warning("Add a url")

    request = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(RETRIES + 1):
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as page:
                html = page.read().decode(decode)
            break
        except Exception as e:
            if attempt == RETRIES or not is_transient(e):
                raise
            wait = BACKOFF_SECONDS * (attempt + 1)
            logger.warning(f"fallo el request a {url} ({e}); reintento en {wait}s")
            time.sleep(wait)

    soup = BeautifulSoup(html, "html.parser")

    return soup
