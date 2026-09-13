"""Driver de scraping: descubre matches de un evento y los procesa (vlr_scraper.ipynb celdas 3-4)."""

import logging
import random
import re
import time

from vlr_pipeline.fetch import soup_open
from vlr_pipeline.parsers import (
    get_basic_match_info,
    get_picks_bans,
    get_player_performance,
    get_player_stats,
    get_round_detail,
    get_team_economy,
)
from vlr_pipeline.save import (
    normalize_filename,
    save_draft_to_csv,
    save_player_performance_to_csv,
    save_player_stats_to_csv,
    save_team_economy,
)
from vlr_pipeline.tracking import load_log, purge_match_rows, record, save_log, should_skip

logger = logging.getLogger(__name__)


def get_invalid_reason(soup):
    """Why a match can't be processed, or None if it's valid

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup object with the HTML info

    Returns:
        str | None: "showmatch", "not_final" o None si el match es valido
    """
    event_text = soup.find("title").get_text(strip=True)
    regex = r"^([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)$"
    result = re.search(regex, event_text)

    match_notes = soup.find_all("div", {"class": "match-header-vs-note"})
    status = match_notes[0].get_text().strip()

    if result and result.group(3).strip() == "Showmatch":
        return "showmatch"
    if status != "final":
        return "not_final"
    return None


def check_valid_match(soup):
    """Check match validity

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup object with the HTML info

    Returns:
        bool: True for a valid match
    """
    return get_invalid_reason(soup) is None


def linkExtractor(url):
    """extrack the played matches from a vlr tournament match page

    Cada card (a.match-item) trae el estado del match: nos quedamos solo con los
    "Completed", asi los Upcoming/LIVE (incluidos los "tbd-...") no se piden.

    Args:
        url (str): vlr tournament match page

    Returns:
        list: urls de los matches jugados, sin duplicados y en el orden de la pagina
    """
    soup = soup_open(url)

    cards = soup.select("a.match-item[href]")
    if cards:
        links = []
        for card in cards:
            status = card.select_one(".ml-status")
            if status is None or status.get_text(strip=True) != "Completed":
                continue
            links.append(card["href"])
        logger.info(f"{len(cards)} matches en la pagina, {len(links)} completados")
    else:
        # fallback si vlr cambia el layout de la pagina de matches
        logger.warning("no encontre a.match-item; tomo todos los links a matches")
        links = [a["href"] for a in soup.find_all("a", href=True) if re.match(r"^/\d+", a["href"])]

    return list(dict.fromkeys("https://www.vlr.gg" + link for link in links))


def process_match(url, folder="csv", encoding="utf-8"):
    """main fuction to process match url

    No chequea si el match ya se proceso (eso lo hace scrape_event con scrape_log.csv):
    antes de extraer purga las filas que el match tenga en los csv de su torneo, asi que
    llamarlo sobre un match ya scrapeado lo reemplaza en vez de duplicarlo.

    Args:
        url (str): match url from vlr

    Returns:
        dict: status ("ok" / "error" / "skipped" / None si el match todavia no es final),
            error, event, has_performance, has_economy
    """
    result = {"status": None, "error": "", "event": "", "has_performance": "", "has_economy": ""}

    time.sleep(random.randint(1, 2))
    soup = soup_open(url)

    invalid_reason = get_invalid_reason(soup)
    if invalid_reason == "showmatch":
        logger.info(f"showmatch, lo salteo: {url}")
        result["status"] = "skipped"
        result["error"] = "showmatch"
        return result
    if invalid_reason is not None:
        # la card decia Completed pero el match no esta final: no se registra y se
        # vuelve a mirar en la proxima corrida
        logger.info(f"Not valid match ({invalid_reason}): {url}")
        return result

    basic_match_info = get_basic_match_info(soup, url)
    result["event"] = basic_match_info["event"]
    purge_match_rows(normalize_filename(basic_match_info["event"]), url, folder=folder)

    logger.info(f"processing: {url}")
    try:
        # Round detail
        get_round_detail(
            soup=soup,
            basic_match_info=basic_match_info,
            folder=folder,
            encoding=encoding,
        )

        player_stats_dict = get_player_stats(
            soup=soup, basic_match_info=basic_match_info
        )
        save_player_stats_to_csv(
            player_stats_dict, folder=folder, encoding=encoding
        )
        # Player performance
        performance_dict = get_player_performance(
            url=url, basic_match_info=basic_match_info
        )
        save_player_performance_to_csv(
            player_performance_dict=performance_dict,
            folder=folder,
            encoding=encoding,
        )
        result["has_performance"] = bool(performance_dict["event"])

        # Team economy
        team_economy_dict = get_team_economy(
            url, basic_match_info=basic_match_info
        )
        save_team_economy(
            team_economy_dict[0], folder=folder, encoding=encoding
        )
        result["has_economy"] = bool(team_economy_dict[0]["event"])

        draft = get_picks_bans(soup=soup, basic_match_info=basic_match_info)
        save_draft_to_csv(draft, url, folder=folder, encoding=encoding)

    except Exception as e:
        logger.warning(f"error processing {url}: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result

    result["status"] = "ok"
    return result


def scrape_event(event_url, folder="csv", encoding="iso-8859-1", log=None):
    """Scrapea los matches jugados de una pagina de matches de un evento de vlr.

    Los matches ya registrados en scrape_log.csv como ok/skipped (o que agotaron los
    reintentos) se saltean sin pedir su pagina.

    Args:
        log (pd.DataFrame, optional): scrape_log ya cargado; si es None se lee de folder

    Returns:
        int: cantidad de matches que terminaron con status error en esta corrida
    """
    if log is None:
        log = load_log(folder)

    logger.info(f"scraping event: {event_url}")
    match_urls = linkExtractor(event_url)
    pending = [url for url in match_urls if not should_skip(log, url)]
    logger.info(
        f"{len(match_urls)} completados / {len(match_urls) - len(pending)} ya en scrape_log"
        f" / {len(pending)} pendientes"
    )

    error_count = 0
    for match_url in pending:
        result = process_match(match_url, folder=folder, encoding=encoding)
        if result["status"] is None:
            continue
        log = record(
            log,
            match_url,
            status=result["status"],
            event=result["event"],
            error=result["error"],
            has_performance=result["has_performance"],
            has_economy=result["has_economy"],
        )
        # guardar despues de cada match: si la corrida se corta, lo hecho queda registrado
        save_log(log, folder)
        if result["status"] == "error":
            error_count += 1
    return error_count


def scrape_all(events, folder="csv", encoding="iso-8859-1"):
    """Scrapea una lista de eventos (dicts de events.json con name/url).

    Returns:
        int: total de matches con error en todos los eventos
    """
    total_errors = 0
    for event in events:
        logger.info(f"event: {event.get('name', event['url'])}")
        # se relee por evento porque scrape_event guarda el log despues de cada match
        total_errors += scrape_event(event["url"], folder=folder, encoding=encoding)
    return total_errors
