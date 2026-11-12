"""Helpers de rutas y guardado a csv/<torneo>/<prefijo>_<torneo>.csv (vlr_scraper.ipynb celda 1)."""

import csv
import logging
import os
import re

logger = logging.getLogger(__name__)


# latin-1 lee y escribe cualquier byte tal cual: sirve para reescribir un csv sin tocar su contenido
# (los csv quedan en utf-8 aunque se escriban con iso-8859-1, ver "Encoding" en CLAUDE.md)
BYTE_SAFE_ENCODING = "iso-8859-1"


def append_dict_rows(file_path, data, encoding="utf-8"):
    """Agrega las filas de un dict de listas al csv, alineadas al header del archivo.

    Si el archivo existe con otro header (un parser sumo una columna, p.ej. player_id_vlr o
    agent el 2026-11-07), primero lo reescribe agregando las columnas nuevas vacias al final;
    sin esto las filas nuevas quedarian corridas respecto del header viejo. Una columna que el
    archivo tiene y el dict no, queda vacia en las filas nuevas.
    """
    columns = list(data.keys())
    if os.path.isfile(file_path):
        with open(file_path, encoding=BYTE_SAFE_ENCODING, newline="") as f:
            existing = next(csv.reader(f), [])
        missing = [column for column in columns if column not in existing]
        if missing:
            add_csv_columns(file_path, missing)
            existing = existing + missing
            logger.info(f"{os.path.basename(file_path)}: agrego columnas {missing}")
        header = existing
        write_header = False
    else:
        header = columns
        write_header = True

    n_rows = len(data[columns[0]]) if columns else 0
    empty = [""] * n_rows
    ordered = [data.get(column, empty) for column in header]
    with open(file_path, "a", newline="", encoding=encoding) as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(header)
        writer.writerows(zip(*ordered))


def add_csv_columns(file_path, new_columns):
    """Reescribe el csv agregando columnas vacias al final, sin tocar los bytes del resto."""
    with open(file_path, encoding=BYTE_SAFE_ENCODING, newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return
    rows[0] = rows[0] + list(new_columns)
    for row in rows[1:]:
        row.extend([""] * len(new_columns))
    tmp = file_path + ".tmp"
    with open(tmp, "w", encoding=BYTE_SAFE_ENCODING, newline="") as f:
        csv.writer(f).writerows(rows)
    os.replace(tmp, file_path)


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
    # el nombre llega en forma html (utf-8 leido como latin-1, ver "Encoding" en CLAUDE.md) y lower()
    # sobre eso rompe los bytes: "TÃ¼rkiye" daba "tã¼rkiye" ("SÃ£o" salia bien solo porque el regex
    # borraba el "£"). Se decodifica primero; un nombre ya decodificado no es utf-8 valido y pasa igual
    try:
        name = name.encode("iso-8859-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    name = name.lower()
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'\s+', '_', name)
    return name.strip('_')


def tournament_from_rows(data, file_prefix):
    """get the normalized tournament name from a extractor dict, or None if it has no rows

    Hay matches donde vlr no publica una pestaña (p.ej. performance/economy en China):
    el extractor devuelve el dict con todas las listas vacias y no hay torneo del que
    sacar el path. En ese caso no hay nada que guardar.

    Args:
        data (dict): dict de un extractor, con la key "event"
        file_prefix (string): prefijo del csv, solo para el log

    Returns:
        string | None: tournament normalizado, o None si el dict viene vacio
    """
    rows = data.get("event") or []
    if not rows:
        logger.info("sin filas para %s; no escribo csv", file_prefix)
        return None
    return normalize_filename(rows[0])


def save_draft_to_csv(draft, url, folder="csv", encoding='utf-8'):
    """save the get_picks_bans() dictionary to csv

    Args:
        draft (dict): draft dict from
        url (string): url from a vlr match
        folder (str, optional): name of the default folder for the export. Defaults to "csv".
        encoding (str, optional): encoding for the csv file. Defaults to 'utf-8'.
    """

    if not draft:
        logger.info("sin draft para %s; no escribo csv", url)
        return

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
    normalized_tournament = tournament_from_rows(detail_round_dict, "round_detail")
    if normalized_tournament is None:
        return

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
    normalized_tournament = tournament_from_rows(player_performance_dict, "player_performance")
    if normalized_tournament is None:
        return

    file_path = get_folder_path(folder_name=folder, normalized_tournament=normalized_tournament, file_prefix="player_performance")

    append_dict_rows(file_path, player_performance_dict, encoding=encoding)


def save_team_economy(economy_dict, folder="csv", encoding="utf-8"):
    """save the get_team_economy() dict to csv

    Args:
        economy_dict (dict): get_team_economy dict
        folder (str, optional): name of the default folder for the export. Defaults to "csv".
        encoding (str, optional): encoding for the csv file. Defaults to 'utf-8'.
    """
    normalized_tournament = tournament_from_rows(economy_dict, "team_economy")
    if normalized_tournament is None:
        return

    file_path = get_folder_path(folder_name=folder, normalized_tournament=normalized_tournament, file_prefix="team_economy")

    append_dict_rows(file_path, economy_dict, encoding=encoding)


def save_player_stats_to_csv(player_stats_dict, folder="csv", encoding='utf-8'):
    """save the get_player_stats() dict to csv

    Args:
        player_stats_dict (dict): get_player_stats() dict
        folder (str, optional): name of the default folder for the export. Defaults to "csv".
        encoding (str, optional): encoding for the csv file. Defaults to 'utf-8'.
    """
    normalized_tournament = tournament_from_rows(player_stats_dict, "player_stats")
    if normalized_tournament is None:
        return

    file_path = get_folder_path(folder_name=folder, normalized_tournament=normalized_tournament, file_prefix="player_stats")

    append_dict_rows(file_path, player_stats_dict, encoding=encoding)


def save_round_buy_to_csv(buy_dict, folder="csv", encoding="utf-8"):
    """save the buy rows of get_round_logs() to csv

    Args:
        buy_dict (dict): primer dict de get_round_logs()
        folder (str, optional): name of the default folder for the export. Defaults to "csv".
        encoding (str, optional): encoding for the csv file. Defaults to 'utf-8'.
    """
    normalized_tournament = tournament_from_rows(buy_dict, "round_buy")
    if normalized_tournament is None:
        return

    file_path = get_folder_path(folder_name=folder, normalized_tournament=normalized_tournament, file_prefix="round_buy")

    append_dict_rows(file_path, buy_dict, encoding=encoding)


def save_round_events_to_csv(events_dict, folder="csv", encoding="utf-8"):
    """save the event rows of get_round_logs() to csv

    Args:
        events_dict (dict): segundo dict de get_round_logs()
        folder (str, optional): name of the default folder for the export. Defaults to "csv".
        encoding (str, optional): encoding for the csv file. Defaults to 'utf-8'.
    """
    normalized_tournament = tournament_from_rows(events_dict, "round_events")
    if normalized_tournament is None:
        return

    file_path = get_folder_path(folder_name=folder, normalized_tournament=normalized_tournament, file_prefix="round_events")

    append_dict_rows(file_path, events_dict, encoding=encoding)
