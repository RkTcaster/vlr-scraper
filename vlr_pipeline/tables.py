"""Consolidacion csv/<torneo>/*.csv -> tables/table_*.csv (csv_process.ipynb celdas 2-18).

Port mecanico: cada build_* corresponde a una celda del notebook y mantiene
encoding iso-8859-1 en lecturas y escrituras para que la salida sea byte-identica.
"""

import logging
import os
import re

import numpy as np
import pandas as pd

from vlr_pipeline.lookups import agent_path_name, map_info, region_id, region_name

logger = logging.getLogger(__name__)


def convert_k(valor):
    "remove k in money columns and change the format to int"
    try:
        if type(valor) == str:
            if 'k' in valor:
                return int(float(valor.replace('k', '')) * 1000)
        else:
            return int(valor)

    except:
        return int(valor)


def find_files_by_prefix(root_folder, prefix):
    matched_files = []
    for dirpath, _, filenames in os.walk(root_folder):
        for file in filenames:
            if file.startswith(prefix):
                full_path = os.path.join(dirpath, file)
                matched_files.append(full_path)
    return matched_files


def concat_from_list(file_list, encoding='iso-8859-1'):
    dataframes = []
    for file in file_list:
        try:
            df = pd.read_csv(file, encoding=encoding)
            if not df.empty:
                dataframes.append(df)
            else:
                logger.warning(f"empty file: {file}")
        except Exception as e:
            logger.warning(f"Error reading {file}: {e}")

    if dataframes:
        return pd.concat(dataframes, ignore_index=True)
    else:
        logger.warning("Load file fail")
        return pd.DataFrame()


def concat_csv_from_different_folders(folder="csv", prefix=None):
    if prefix is None:
        logger.warning("Add a prefix")

    file_list = find_files_by_prefix(root_folder=folder, prefix=prefix)
    df_concat = concat_from_list(file_list)
    return df_concat


def text_to_index(df, name, number=0, extra_id=""):
    name_id = name + '_id'
    df[name_id] = df.index + number
    df[name_id] = name + "_" + df[name_id].astype(str) + extra_id
    return df


def tournament_names(folder='csv'):
    tournament_list = []
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if os.path.isdir(path):
            tournament_list.append(name)
    return tournament_list


def region_by_id(touranment_name, region):
    for _, row in region.iterrows():
        if row['region'].lower() in touranment_name.lower():
            return row['reg_id']
    return "reg_4"


def sort_teams(team_string):
    split_teams = team_string.split("-", 2)
    map_info = split_teams[-1]
    sorted_teams = sorted(split_teams[0:2], key=str.lower)
    return "-".join(sorted_teams) + "-" + map_info


def match_id_vlr(url):
    match = re.search(r"vlr\.gg/(\d+)", url)
    if match:
        vlr_id = match.group(1)
        return vlr_id


def build_region_tournament(csv_dir="csv", tables_dir="tables"):
    """Celdas 4-5: table_region.csv y table_tournament.csv."""
    region_data = {"region": region_name, "reg_id": region_id}

    df_region = pd.DataFrame(data=region_data)

    tournaments = tournament_names(csv_dir)
    df_tournaments = pd.DataFrame(data=tournaments, columns=["tournament_name"])

    df_tournaments["event"] = df_tournaments["tournament_name"].apply(lambda x: x.replace("_", " "))

    df_tournaments['reg_id'] = df_tournaments['event'].apply(lambda x: region_by_id(x, df_region))

    df_tournaments['tour_id'] = df_tournaments['tournament_name']

    df_tournaments = df_tournaments.drop(["tournament_name"], axis=1)

    df_region.to_csv(path_or_buf=os.path.join(tables_dir, 'table_region.csv'), index=False, encoding='iso-8859-1')
    df_tournaments.to_csv(path_or_buf=os.path.join(tables_dir, 'table_tournament.csv'), index=False, encoding='iso-8859-1')

    return df_region, df_tournaments


def build_teams(csv_dir="csv", tables_dir="tables"):
    """Celda 7: table_teams.csv."""
    df_draft_concat = concat_csv_from_different_folders(folder=csv_dir, prefix="draft_")
    df_team = pd.DataFrame(df_draft_concat["team"].unique(), columns=["team"])

    df_team["team_id"] = df_team["team"]

    df_team = df_team.drop(["team"], axis=1)  # Need to add full name of the team.

    df_team.to_csv(path_or_buf=os.path.join(tables_dir, 'table_teams.csv'), index=False, encoding='iso-8859-1')

    return df_team


def build_players(df_team, csv_dir="csv", tables_dir="tables"):
    """Celda 8: table_players.csv."""
    df_players_stats = concat_csv_from_different_folders(folder=csv_dir, prefix="player_stats")
    df_players = df_players_stats[['player', 'team']].drop_duplicates(subset=['player'], ignore_index=True)
    df_players["player_id"] = df_players["team"] + "_" + df_players["player"]

    df_players_id = pd.merge(df_players, df_team[["team_id"]], how="left", left_on="team", right_on="team_id")

    df_players_id = df_players_id.drop(["team"], axis=1)

    df_players_id.to_csv(path_or_buf=os.path.join(tables_dir, 'table_players.csv'), index=False, encoding='iso-8859-1')

    return df_players_id


def build_ids(df_tournaments, csv_dir="csv", tables_dir="tables"):
    """Celda 11: table_maps_id.csv, table_match_id.csv y table_tournament_played.csv.

    Devuelve df_maps_id, consumido por casi todas las tablas siguientes.
    """
    df_round_detail = concat_csv_from_different_folders(folder=csv_dir, prefix="round_detail")

    df_filter_map = df_round_detail["map"] != "all"
    df_round_detail_filter = df_round_detail[df_filter_map]
    df_round_detail_filter["event"] = df_round_detail_filter["event"].apply(lambda x: x.replace(":", "").lower())
    df_round_detail_filter["vlr_id"] = df_round_detail_filter["source_url"].apply(
        match_id_vlr
    )
    df_round_detail_filter["vlr_id-map"] = (
        df_round_detail_filter["vlr_id"] + "-" + df_round_detail_filter["map"]
    )

    df_maps_id = pd.DataFrame(
        df_round_detail_filter["vlr_id-map"].unique(), columns=["vlr_id-map"]
    )

    df_maps_id["map_id"] = df_maps_id["vlr_id-map"]

    df_maps_id[["vlr_id", "map"]] = df_maps_id["vlr_id-map"].str.rsplit(
        "-", n=1, expand=True
    )

    df_match_id = pd.DataFrame(data=df_maps_id["vlr_id"].unique(), columns=["vlr_id"])

    df_match_id["series_id"] = df_match_id["vlr_id"]

    df_round_detail_filter = pd.merge(
        df_round_detail_filter,
        df_tournaments[["event", "reg_id", "tour_id"]],
        how="left",
        left_on="event",
        right_on="event",
    )

    df_match_id = pd.merge(
        df_match_id,
        df_round_detail_filter[["vlr_id", "reg_id", "tour_id"]],
        how="left",
        left_on="vlr_id",
        right_on="vlr_id",
    )

    df_match_id.drop_duplicates(inplace=True, ignore_index=True)

    df_maps_id = pd.merge(
        df_maps_id,
        df_match_id,
        how="left",
        left_on="vlr_id",
        right_on="vlr_id",
    )

    df_played_a = df_round_detail_filter[["teamA", "event", "reg_id", "tour_id"]].copy()
    df_played_b = (
        df_round_detail_filter[["teamB", "event", "reg_id", "tour_id"]].copy()
        .rename(columns={"teamB": "teamA"})
    )
    df_tournament_played = pd.concat([df_played_a, df_played_b], ignore_index=True)
    df_tournament_played.drop_duplicates(inplace=True, ignore_index=True)

    df_maps_id = df_maps_id.drop(["vlr_id-map", "vlr_id"], axis=1)

    df_maps_id.to_csv(path_or_buf=os.path.join(tables_dir, 'table_maps_id.csv'), index=False, encoding='iso-8859-1')

    df_match_id = df_match_id.drop(["vlr_id"], axis=1)

    df_match_id.to_csv(path_or_buf=os.path.join(tables_dir, 'table_match_id.csv'), index=False, encoding='iso-8859-1')

    df_tournament_played.to_csv(path_or_buf=os.path.join(tables_dir, 'table_tournament_played.csv'), index=False, encoding='iso-8859-1')

    return df_maps_id


def build_player_performance(df_maps_id, csv_dir="csv", tables_dir="tables"):
    """Celda 12: table_player_performance.csv."""
    df_player_performance = concat_csv_from_different_folders(folder=csv_dir, prefix="player_performance")

    df_filter_map = df_player_performance["map"] != "all"
    df_player_performance = df_player_performance[df_filter_map]
    df_player_performance["series_id"] = df_player_performance["source_url"].apply(
        match_id_vlr
    )
    df_player_performance["map_id"] = (
        df_player_performance["series_id"] + "-" + df_player_performance["map"]
    )

    df_player_performance = pd.merge(df_player_performance, df_maps_id[["map_id", "reg_id", "tour_id"]], how="left", left_on="map_id", right_on="map_id")

    df_player_performance.to_csv(path_or_buf=os.path.join(tables_dir, 'table_player_performance.csv'), index=False, encoding='iso-8859-1')


def build_player_stats(df_maps_id, csv_dir="csv", tables_dir="tables"):
    """Celda 13: table_player_stats.csv. Los astype(int) fallan si hay NaN (ej. datos faltantes de China)."""
    df_player_stats = concat_csv_from_different_folders(folder=csv_dir, prefix="player_stats")

    df_filter_map = df_player_stats["map"] != "all"
    df_player_stats = df_player_stats[df_filter_map]
    df_player_stats["series_id"] = df_player_stats["source_url"].apply(
        match_id_vlr
    )
    df_player_stats["map_id"] = (
        df_player_stats["series_id"] + "-" + df_player_stats["map"]
    )

    df_player_stats = pd.merge(df_player_stats, df_maps_id[["map_id", "reg_id", "tour_id"]], how="left", left_on="map_id", right_on="map_id")

    df_player_stats_types = df_player_stats.astype(
        {
            "acsBoth": int,
            "acsT": int,
            "acsCT": int,
            "killsBoth": int,
            "killsT": int,
            "killsCT": int,
            "deadBoth": int,
            "deadT": int,
            "deadCT": int,
            "assistsBoth": int,
            "assistsT": int,
            "assistsCT": int,
            "k-dBoth": int,
            "k-dT": int,
            "k-dCT": int,
            "adrBoth": int,
            "adrT": int,
            "adrCT": int,
            "fkBoth": int,
            "fkT": int,
            "fkCT": int,
            "fdBoth": int,
            "fdT": int,
            "fdCT": int,
            "fk-fdBoth": int,
            "fk-fdT": int,
            "fk-fdCT": int,
        }
    )

    df_player_stats_types.to_csv(path_or_buf=os.path.join(tables_dir, 'table_player_stats.csv'), index=False, encoding='iso-8859-1')


def build_draft(df_maps_id, csv_dir="csv", tables_dir="tables"):
    """Celda 14: table_draft.csv."""
    df_draft_concat = concat_csv_from_different_folders(folder=csv_dir, prefix="draft_")
    df_draft_concat["match_instance"] = df_draft_concat["source_url"].apply(
        lambda x: x[-3:].lstrip("-")
    )
    df_draft_concat["series_id"] = df_draft_concat["source_url"].apply(match_id_vlr)

    df_draft_concat = pd.merge(
        df_draft_concat,
        df_maps_id[["series_id", "reg_id", "tour_id"]],
        how="left",
        left_on="series_id",
        right_on="series_id",
    )
    df_draft_concat_filter = df_draft_concat["order"] == "A"
    df_draft_concat = df_draft_concat[df_draft_concat_filter]
    df_draft_concat.drop_duplicates(inplace=True, ignore_index=True)

    df_draft_concat.to_csv(path_or_buf=os.path.join(tables_dir, 'table_draft.csv'), index=False, encoding='iso-8859-1')


def build_maps_and_round_info(df_maps_id, csv_dir="csv", tables_dir="tables"):
    """Celda 15: table_maps_name_id.csv y table_round_info.csv.

    Devuelve df_round_concat, que consume build_team_economy.
    Nota: round_info se escribe "iso-8859-1" pero los bytes en disco quedan utf-8
    validos; el consumidor (standings en la notebook) lo relee como utf-8.
    """
    df_round_concat = concat_csv_from_different_folders(folder=csv_dir, prefix="round_detail")

    df_maps_name_id = pd.DataFrame(map_info)

    text_to_index(df_maps_name_id, "map")

    df_maps_name_id.to_csv(
        path_or_buf=os.path.join(tables_dir, "table_maps_name_id.csv"), index=False, encoding="iso-8859-1"
    )

    df_round_concat["series_id"] = df_round_concat["source_url"].apply(match_id_vlr)
    df_round_concat["map_id"] = df_round_concat["series_id"] + "-" + df_round_concat["map"]

    df_round_concat = pd.merge(
        df_round_concat,
        df_maps_id[["map_id", "reg_id", "tour_id"]],
        how="left",
        left_on="map_id",
        right_on="map_id",
    )

    df_round_concat = df_round_concat.drop_duplicates(subset=["map_id", "round"])

    df_round_concat["team_map_round_id"] = (
        df_round_concat["teamA"]
        + "-"
        + df_round_concat["teamB"]
        + "-"
        + df_round_concat["map_id"]
        + "-"
        + df_round_concat["round"].astype(str)
    )

    df_round_concat["team_map_round_id"] = df_round_concat["team_map_round_id"].apply(
        sort_teams
    )

    df_round_concat.to_csv(
        path_or_buf=os.path.join(tables_dir, "table_round_info.csv"), index=False, encoding="iso-8859-1"
    )

    return df_round_concat


def build_team_economy(df_maps_id, df_round_concat, csv_dir="csv", tables_dir="tables"):
    """Celda 16: table_team_economy.csv. Excluye reg_2 (China): vlr no siempre tiene esa data."""
    df_team_economy = concat_csv_from_different_folders(folder=csv_dir, prefix="team_economy")

    columns_update = ["team_a_economy", "team_b_economy", "team_a_bank", "team_b_bank"]

    for column_name in columns_update:
        df_team_economy[column_name] = df_team_economy[column_name].apply(convert_k)

    df_team_economy["series_id"] = df_team_economy["source_url"].apply(
        match_id_vlr
    )
    df_team_economy["map_id"] = (
        df_team_economy["series_id"] + "-" + df_team_economy["map"]
    )

    df_team_economy = pd.merge(df_team_economy, df_maps_id[["map_id", "reg_id", "tour_id"]], how="left", left_on="map_id", right_on="map_id")

    df_team_economy["team_map_round_id"] = df_team_economy["team_a"] + "-" + df_team_economy["team_b"] + "-" + df_team_economy["map_id"] + "-" + df_team_economy["round"].astype(str)

    df_team_economy["team_map_round_id"] = df_team_economy["team_map_round_id"].apply(sort_teams)

    df_team_economy = df_team_economy[df_team_economy["reg_id"] != "reg_2"]

    df_team_economy = pd.merge(df_team_economy, df_round_concat[["teamA", "teamB", "rndA", "rndB", "team_map_round_id", "winCon", "side"]], how="left", left_on="team_map_round_id", right_on="team_map_round_id")
    df_team_economy["side_b"] = np.where(df_team_economy["side"] == "atk", "def", "atk")
    df_team_economy["eco_side"] = np.where(df_team_economy["team_a"] == df_team_economy["teamA"], df_team_economy["side"], df_team_economy["side_b"])
    df_team_economy["eco_win_A"] = np.where(df_team_economy["team_a"] == df_team_economy["teamA"], df_team_economy["rndA"], df_team_economy["rndB"])
    df_team_economy = df_team_economy.drop(columns=["teamA", "teamB", "rndA", "rndB", "side", "side_b"])
    df_team_economy = df_team_economy.rename(columns={"eco_side": "side", "eco_win_A": "win_A"})

    df_team_economy.to_csv(path_or_buf=os.path.join(tables_dir, 'table_team_economy.csv'), index=False, encoding='iso-8859-1')  # No china, sometimes vlr dont have the data on china


def build_agent_info(tables_dir="tables"):
    """Celda 18: table_agent_info.csv."""
    agent_info = {"agent_name": [], "agent_path": []}

    agent_info["agent_name"] = [f"{agent.split('.')[0].capitalize()}" for agent in agent_path_name]
    agent_info["agent_path"] = [f"agents/{path.lower()}" for path in agent_path_name]

    df_agent_info = pd.DataFrame(agent_info)

    df_agent_info.to_csv(
        path_or_buf=os.path.join(tables_dir, "table_agent_info.csv"), index=False, encoding="iso-8859-1"
    )


def build_all(csv_dir="csv", tables_dir="tables"):
    """Corre todas las tablas en el mismo orden que el notebook."""
    os.makedirs(tables_dir, exist_ok=True)

    logger.info("building table_region / table_tournament")
    df_region, df_tournaments = build_region_tournament(csv_dir, tables_dir)

    logger.info("building table_teams")
    df_team = build_teams(csv_dir, tables_dir)

    logger.info("building table_players")
    build_players(df_team, csv_dir, tables_dir)

    logger.info("building table_maps_id / table_match_id / table_tournament_played")
    df_maps_id = build_ids(df_tournaments, csv_dir, tables_dir)

    logger.info("building table_player_performance")
    build_player_performance(df_maps_id, csv_dir, tables_dir)

    logger.info("building table_player_stats")
    build_player_stats(df_maps_id, csv_dir, tables_dir)

    logger.info("building table_draft")
    build_draft(df_maps_id, csv_dir, tables_dir)

    logger.info("building table_maps_name_id / table_round_info")
    df_round_concat = build_maps_and_round_info(df_maps_id, csv_dir, tables_dir)

    logger.info("building table_team_economy")
    build_team_economy(df_maps_id, df_round_concat, csv_dir, tables_dir)

    logger.info("building table_agent_info")
    build_agent_info(tables_dir)

    logger.info("done: tables written to %s", tables_dir)
