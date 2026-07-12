import logging

from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# urllib sin header suele recibir 403 desde IPs de datacenter (GitHub Actions).
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


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
    page = urlopen(request)
    html = page.read().decode(decode)
    soup = BeautifulSoup(html, "html.parser")

    return soup
