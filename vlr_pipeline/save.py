"""Helpers de rutas y guardado a csv/<torneo>/<prefijo>_<torneo>.csv (vlr_scraper.ipynb celda 1)."""

import csv
import logging
import os
import re

logger = logging.getLogger(__name__)


def get_folder_path(folder_name, normalized_tournament, file_prefix):
    """Create the file path for the csv

    Args:
        folder_name (string): folder name for the csv
        normalized_tournament (string): tournament in the path format
        file_prefix (string): prefix for the file name

    Returns:
        string: string with the path for the save to csv files
    """
    if file_prefix is None:
        logger.warning("Add file sufix")

    folder_path = os.path.join(folder_name, normalized_tournament)
    os.makedirs(folder_path, exist_ok=True)

    file_path = os.path.join(folder_path, f'{file_prefix}_{normalized_tournament}.csv')

    return file_path


def normalize_filename(name):
    """normalize the file name for the path

    Args:
        name (string): string (usually tournamnet name)

    Returns:
        string: normalized tournament name
    """
    name = name.lower()
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'\s+', '_', name)
    return name.strip('_')


def save_draft_to_csv(draft, url, folder="csv", encoding='utf-8'):
    """save the get_picks_bans() dictionary to csv

    Args:
        draft (dict): draft dict from
        url (string): url from a vlr match
        folder (str, optional): name of the default folder for the export. Defaults to "csv".
        encoding (str, optional): encoding for the csv file. Defaults to 'utf-8'.
    """

    tournament_name = draft['team_A'][-1]
    normalized_tournament = normalize_filename(tournament_name)

    file_path = get_folder_path(folder_name=folder, normalized_tournament=normalized_tournament, file_prefix="draft")

    header = draft["header"]
    file_exists = os.path.isfile(file_path)

    with open(file_path, mode='a', newline='', encoding=encoding) as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(header)
        writer.writerow(draft["team_A"])
        #writer.writerow(draft["team_B"]) saco el mirror para team B


def save_round_detail_to_csv(detail_round_dict, folder="csv", encoding='utf-8'):  # stats from the teams
    """save the get_round_detail() dictionary to csv

    Args:
        detail_round_dict (dict): get_round_detail dict
        folder (str, optional): name of the default folder for the export. Defaults to "csv".
        encoding (str, optional): encoding for the csv file. Defaults to 'utf-8'.
    """
    tournament_name = detail_round_dict["event"][0]  # Medio raro esto
    normalized_tournament = normalize_filename(tournament_name)

    file_path = get_folder_path(folder_name=folder, normalized_tournament=normalized_tournament, file_prefix="round_detail")

    header = list(detail_round_dict)
    file_exists = os.path.isfile(file_path)

    with open(file_path, "a", newline="", encoding=encoding) as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(header)

        writer.writerows(zip(*detail_round_dict.values()))


def save_player_performance_to_csv(player_performance_dict, folder="csv", encoding='utf-8'):
    """save the get_player_performance() dict to csv

    Args:
        player_performance_dict (dict): get_player_performance dict
        folder (str, optional): name of the default folder for the export. Defaults to "csv".
        encoding (str, optional): encoding for the csv file. Defaults to 'utf-8'.
    """
    tournament_name = player_performance_dict["event"][0]
    normalized_tournament = normalize_filename(tournament_name)

    file_path = get_folder_path(folder_name=folder, normalized_tournament=normalized_tournament, file_prefix="player_performance")

    header = player_performance_dict.keys()
    file_exists = os.path.isfile(file_path)

    with open(file_path, "a", newline="", encoding=encoding) as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(header)

        writer.writerows(zip(*player_performance_dict.values()))


def save_team_economy(economy_dict, folder="csv", encoding="utf-8"):
    """save the get_team_economy() dict to csv

    Args:
        economy_dict (dict): get_team_economy dict
        folder (str, optional): name of the default folder for the export. Defaults to "csv".
        encoding (str, optional): encoding for the csv file. Defaults to 'utf-8'.
    """
    tournament_name = economy_dict["event"][0]
    normalized_tournament = normalize_filename(tournament_name)

    file_path = get_folder_path(folder_name=folder, normalized_tournament=normalized_tournament, file_prefix="team_economy")

    header = economy_dict.keys()
    file_exists = os.path.isfile(file_path)

    with open(file_path, "a", newline="", encoding=encoding) as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(header)

        writer.writerows(zip(*economy_dict.values()))


def save_player_stats_to_csv(player_stats_dict, folder="csv", encoding='utf-8'):
    """save the get_player_stats() dict to csv

    Args:
        player_stats_dict (dict): get_player_stats() dict
        folder (str, optional): name of the default folder for the export. Defaults to "csv".
        encoding (str, optional): encoding for the csv file. Defaults to 'utf-8'.
    """
    tournament_name = player_stats_dict["event"][0]
    normalized_tournament = normalize_filename(tournament_name)

    file_path = get_folder_path(folder_name=folder, normalized_tournament=normalized_tournament, file_prefix="player_stats")

    header = player_stats_dict.keys()
    file_exists = os.path.isfile(file_path)

    with open(file_path, "a", newline="", encoding=encoding) as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(header)

        writer.writerows(zip(*player_stats_dict.values()))


def save_match_error(match_error_dict, folder="csv", encoding='utf-8'):
    """save the matchs raising errors

    Args:
        match_error_dict (dict): match error dict
        folder (str, optional): name of the default folder for the export. Defaults to "csv".
        encoding (str, optional): encoding for the csv file. Defaults to 'utf-8'.
    """
    tournament_name = match_error_dict["event"][0]
    normalized_tournament = normalize_filename(tournament_name)

    file_path = get_folder_path(folder_name=folder, normalized_tournament=normalized_tournament, file_prefix="error_match")

    header = match_error_dict.keys()
    file_exists = os.path.isfile(file_path)

    with open(file_path, "a", newline="", encoding=encoding) as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(header)

        writer.writerows(zip(*match_error_dict.values()))
