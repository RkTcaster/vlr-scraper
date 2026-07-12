"""Driver de scraping: descubre matches de un evento y los procesa (vlr_scraper.ipynb celdas 3-4)."""

import logging
import os
import random
import re
import time

import pandas as pd

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
    save_match_error,
    save_player_performance_to_csv,
    save_player_stats_to_csv,
    save_team_economy,
)

logger = logging.getLogger(__name__)


def check_valid_match(soup):
    """Check match validity

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup object with the HTML info

    Returns:
        bool: False for a valid match
    """
    event_text = soup.find("title").get_text(strip=True)
    regex = r"^([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)$"
    result = re.search(regex, event_text)

    match_notes = soup.find_all("div", {"class": "match-header-vs-note"})
    status = match_notes[0].get_text().strip()

    if result.group(3).strip() == "Showmatch" or status != "final":
        valid_match = False
    else:
        valid_match = True
    return valid_match


def linkExtractor(url):
    """extrack all the matches from a vlr tournament match page

    Args:
        url (str): vlr tournament match page

    Returns:
        list: list with the url of all the matchs in the matches page
    """
    soup = soup_open(url)

    tempLink = []
    urlLinkExtract = []
    for a in soup.find_all("a", href=True):
        tempLink.append(a["href"])
        filtered_links = [link for link in tempLink if re.match(r"^/\d+", link)]

    for cleanLink in filtered_links:
        urlLinkExtract.append("https://www.vlr.gg" + cleanLink)

    return urlLinkExtract


def get_draft_file_path(basic_match_info, folder="csv"):
    """from basic_match_info dict get the tournament name and create the path using the folder

    Args:
        basic_match_info (dict, optional): basic match info dict. Defaults to None.
        folder (str, optional): folder name. Defaults to "csv".

    Returns:
        str: path with the file name
    """
    normalized_tournament = normalize_filename(basic_match_info["event"])
    folder_path = os.path.join(folder, normalized_tournament)
    os.makedirs(folder_path, exist_ok=True)
    return os.path.join(folder_path, f"draft_{normalized_tournament}.csv")


def was_url_already_processed(file_path, url):
    """check if the url was already process

    Args:
        file_path (str): file path for draft
        url (str): url to verify

    Returns:
        bool: True if ulr is already process
    """
    if not os.path.exists(file_path):
        return False
    df = pd.read_csv(file_path)
    return url in set(df.source_url)


def process_match(url, folder="csv", encoding="utf-8"):
    """main fuction to process match url

    Args:
        url (str): match url from vlr

    Returns:
        bool: True si el match termino en error_match_*.csv
    """
    time.sleep(random.randint(1, 2))
    soup = soup_open(url)
    error_url = {"event": [], "url": [], "error": []}
    if check_valid_match(soup):
        basic_match_info = get_basic_match_info(soup, url)
        path = get_draft_file_path(basic_match_info=basic_match_info, folder=folder)
        # Check if match is processed
        not_processed = not was_url_already_processed(file_path=path, url=url)
        if not_processed:
            logger.info(f"processing: {url}")
            try:
                # Draft
                draft = get_picks_bans(soup=soup, basic_match_info=basic_match_info)
                save_draft_to_csv(draft, url, folder=folder, encoding=encoding)

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

                # Team economy
                team_economy_dict = get_team_economy(
                    url, basic_match_info=basic_match_info
                )
                save_team_economy(
                    team_economy_dict[0], folder=folder, encoding=encoding
                )
                # save_team_economy(
                #     team_economy_dict[1], folder=folder, encoding=encoding
                # )

            except Exception as e:
                logger.warning(f"error processing {url}: {e}")
                error_url["event"].append(basic_match_info["event"])
                error_url["url"].append(url)
                error_url["error"].append(e)
                save_match_error(match_error_dict=error_url, folder=folder, encoding=encoding)
                return True

        else:
            logger.info(f"already processed: {url}")

    else:
        logger.info(f"Not valid match: {url}")

    return False


def scrape_event(event_url, folder="csv", encoding="iso-8859-1"):
    """Scrapea todos los matches de una pagina de matches de un evento de vlr.

    Returns:
        int: cantidad de matches que terminaron en error_match_*.csv
    """
    logger.info(f"scraping event: {event_url}")
    match_urls = linkExtractor(event_url)
    logger.info(f"{len(match_urls)} match links found")

    error_count = 0
    for match_url in match_urls:
        if process_match(match_url, folder=folder, encoding=encoding):
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
        total_errors += scrape_event(event["url"], folder=folder, encoding=encoding)
    return total_errors
