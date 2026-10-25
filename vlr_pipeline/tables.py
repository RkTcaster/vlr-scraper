"""Consolidacion csv/<torneo>/*.csv -> tables/table_*.csv (csv_process.ipynb celdas 2-18).

Port mecanico: cada build_* corresponde a una celda del notebook y mantiene
encoding iso-8859-1 en lecturas y escrituras para que la salida sea byte-identica.
"""

import logging
import os
import re
from collections import Counter

import numpy as np
import pandas as pd

from vlr_pipeline.lookups import agent_path_name, map_info, region_id, region_name, team_aliases

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
    for dirpath, dirnames, filenames in os.walk(root_folder):
        # os.walk no garantiza orden (en Linux/GitHub Actions depende del filesystem):
        # ordenamos para que las tablas salgan iguales en Windows y en Actions
        dirnames.sort()
        for file in sorted(filenames):
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


def canonical_teams(tags, team_a, team_b):
    """Tricodes renombrados por vlr -> los de round_info (ver team_aliases en lookups.py).

    Las solapas que se bajan hoy traen el tag actual, pero round_detail se scrapeo cuando el
    equipo se llamaba distinto, y round_info es la fuente de team_map_round_id y del lado.

    El alias se aplica **solo si el tag no es ninguno de los dos equipos de esa ronda**: vlr
    renombro a DRX en KRX a mitad de temporada, asi que las series viejas tienen DRX en
    round_info y las nuevas KRX, y un replace global rompe unas o las otras.
    """
    unknown = tags.notna() & (tags != team_a) & (tags != team_b)
    return tags.mask(unknown, tags.replace(team_aliases))


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
    # el draft guarda un solo lado por serie (sin mirror): un equipo que solo aparece como
    # rival (p.ej. QTD) quedaba fuera de la tabla
    teams = pd.concat([df_draft_concat["team"], df_draft_concat["rival"]]).unique()
    df_team = pd.DataFrame(teams, columns=["team"])

    df_team["team_id"] = df_team["team"]

    df_team = df_team.drop(["team"], axis=1)  # Need to add full name of the team.

    df_team.to_csv(path_or_buf=os.path.join(tables_dir, 'table_teams.csv'), index=False, encoding='iso-8859-1')

    return df_team


def build_players(df_team, csv_dir="csv", tables_dir="tables"):
    """Celda 8: table_players.csv."""
    df_players_stats = concat_csv_from_different_folders(folder=csv_dir, prefix="player_stats")
    # un jugador que cambio de equipo (o su equipo cambio de tag) queda con el equipo de su
    # partido mas reciente; antes quedaba el del primer archivo leido
    df_players = (
        df_players_stats[['player', 'team', 'date']]
        .sort_values('date', kind='stable')
        .drop_duplicates(subset=['player'], keep='last')
        .sort_index()
        .drop(columns=['date'])
        .reset_index(drop=True)
    )
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


ROUND_BUY_KEYS = ["team_map_round_id", "series_id", "map_id", "round", "team_a", "team_b", "side_team_a", "reg_id", "tour_id"]
# campo del csv crudo -> sufijo de la columna ancha ("" = player_k_team_x a secas)
ROUND_BUY_FIELDS = {"player": "", "agent": "_agent", "weapon": "_weapon", "shield": "_shield", "spent": "_spend", "bank": "_bank"}
ROUND_BUY_SLOTS = range(1, 6)


def round_buy_columns():
    columns = list(ROUND_BUY_KEYS)
    for team in ("team_a", "team_b"):
        for slot in ROUND_BUY_SLOTS:
            columns += [f"player_{slot}_{team}{suffix}" for suffix in ROUND_BUY_FIELDS.values()]
    return columns


def build_round_buy(df_maps_id, df_round_concat, csv_dir="csv", tables_dir="tables"):
    """table_round_buy.csv: una fila por ronda con la compra de los 10 jugadores.

    Viene de csv/*/round_buy_*.csv (largo, una fila por jugador y ronda). El slot es el orden
    en que vlr muestra a los jugadores del equipo.

    team_map_round_id y team_a/team_b salen de round_info (join por map_id + round), igual que
    en round_events, y no de los tags del csv crudo: si vlr renombro al equipo despues del
    scrape de round_detail (DRX -> KRX en el pacific kickoff), armar el id con los tags nuevos
    deja las filas huerfanas. Lo que si se mantiene es el orden posicional de vlr (su equipo 1
    es teamA en las dos tablas), que es lo que hace que player_N_team_a sea el de teamA.
    """
    path = os.path.join(tables_dir, "table_round_buy.csv")
    file_list = find_files_by_prefix(root_folder=csv_dir, prefix="round_buy")
    if not file_list:
        # antes del backfill no hay round_buy: tabla vacia con headers
        df_empty = pd.DataFrame(columns=round_buy_columns())
        df_empty.to_csv(path_or_buf=path, index=False, encoding="iso-8859-1")
        return df_empty

    df_buy = concat_from_list(file_list)
    df_buy["series_id"] = df_buy["source_url"].apply(match_id_vlr)
    df_buy["map_id"] = df_buy["series_id"] + "-" + df_buy["map"]
    df_buy = pd.merge(df_buy, df_maps_id[["map_id", "reg_id", "tour_id"]], how="left", left_on="map_id", right_on="map_id")

    unknown_team = (df_buy["team"] != df_buy["team_a"]) & (df_buy["team"] != df_buy["team_b"])
    if unknown_team.any():
        logger.warning(f"round_buy: {int(unknown_team.sum())} filas con un tag que no es team_a ni team_b")
    # which se resuelve con los tags del csv crudo (el orden de vlr), el id con los de round_info
    df_buy["which"] = np.where(df_buy["team"] == df_buy["team_a"], "team_a", "team_b")
    df_buy = df_buy.drop(columns=["team_a", "team_b"])
    df_buy = pd.merge(
        df_buy,
        df_round_concat[["map_id", "round", "teamA", "teamB", "team_map_round_id"]].rename(
            columns={"teamA": "team_a", "teamB": "team_b"}
        ),
        how="left",
        on=["map_id", "round"],
    )
    no_round = df_buy["team_map_round_id"].isna()
    if no_round.any():
        logger.warning(f"round_buy: descarto {int(no_round.sum())} filas sin ronda en round_info")
        df_buy = df_buy[~no_round]

    duplicated = df_buy.duplicated(subset=["team_map_round_id", "which", "slot"])
    if duplicated.any():
        logger.warning(f"round_buy: descarto {int(duplicated.sum())} filas con slot repetido")
        df_buy = df_buy[~duplicated]

    df_side = (
        df_buy[df_buy["which"] == "team_a"]
        .drop_duplicates(subset=["team_map_round_id"])[["team_map_round_id", "side"]]
        .rename(columns={"side": "side_team_a"})
    )
    df_keys = df_buy.drop_duplicates(subset=["team_map_round_id"])[
        ["team_map_round_id", "series_id", "map_id", "round", "team_a", "team_b", "reg_id", "tour_id"]
    ]
    df_keys = pd.merge(df_keys, df_side, how="left", on="team_map_round_id")

    # Int64 (nullable): si falta un slot el unstack deja NA y no pasa todo a float ("2400.0")
    df_buy = df_buy.astype({"spent": "Int64", "bank": "Int64"})
    df_wide = df_buy.set_index(["team_map_round_id", "which", "slot"])[list(ROUND_BUY_FIELDS)].unstack(["which", "slot"])
    df_wide.columns = [f"player_{slot}_{which}{ROUND_BUY_FIELDS[field]}" for field, which, slot in df_wide.columns]
    df_wide = df_wide.reset_index()

    df_round_buy = pd.merge(df_keys, df_wide, how="left", on="team_map_round_id")
    # columnas fijas aunque falte algun slot (p.ej. un jugador desconectado toda la ronda)
    df_round_buy = df_round_buy.reindex(columns=round_buy_columns())

    df_round_buy.to_csv(path_or_buf=path, index=False, encoding="iso-8859-1")
    return df_round_buy


# una kill es trade si mata al que mato a un companero hace <= TRADE_WINDOW segundos
TRADE_WINDOW = 3
ROUND_EVENTS_COLUMNS = [
    "team_map_round_id", "ev_index", "series_id", "map_id", "map", "round", "reg_id", "tour_id",
    "t_sec", "type", "player", "player_id", "team", "side", "victim", "victim_id", "victim_team",
    "weapon", "site", "pos_x", "pos_y", "from_x", "from_y",
    "is_first_blood", "is_team_kill", "is_post_plant", "is_trade", "is_traded",
]
ROUND_SUMMARY_COLUMNS = [
    "team_map_round_id", "series_id", "map_id", "round", "reg_id", "tour_id", "team_a", "team_b", "side_team_a",
    "fb_player_id", "fb_team", "fb_victim_id", "fb_t",
    "plant_t", "plant_site", "plant_player_id", "defuse_t", "defuse_player_id",
    "kills_team_a", "kills_team_b", "trades_team_a", "trades_team_b", "last_event_t",
]


def clock_to_seconds(clock):
    "'1:25' (tiempo desde el inicio de la ronda) -> 85"
    minutes, seconds = str(clock).split(":")
    return int(minutes) * 60 + int(seconds)


def mark_trades(df_events):
    """Columnas is_trade / is_traded de las kills de df_events (ordenado por ronda y ev_index).

    is_trade: la kill mata a alguien que mato a un companero del killer hace <= TRADE_WINDOW s.
    is_traded: esa muerte del companero fue tradeada. Las team kills (spike, caida) no cuentan.
    """
    is_trade = pd.Series(False, index=df_events.index)
    is_traded = pd.Series(False, index=df_events.index)
    kills = df_events[(df_events["type"] == "kill") & ~df_events["is_team_kill"]]
    for _, round_kills in kills.groupby("team_map_round_id", sort=False):
        previous = []
        for index, kill in round_kills.iterrows():
            for prev_index, prev in previous:
                if (
                    prev["player"] == kill["victim"]
                    and prev["victim_team"] == kill["team"]
                    and kill["t_sec"] - prev["t_sec"] <= TRADE_WINDOW
                ):
                    is_trade[index] = True
                    is_traded[prev_index] = True
            previous.append((index, kill))
    return is_trade, is_traded


def build_round_events(df_round_concat, df_players_id, csv_dir="csv", tables_dir="tables"):
    """table_round_events.csv (una fila por kill/plant/defuse) y table_round_summary.csv (una por ronda).

    Vienen de csv/*/round_events_*.csv. team_map_round_id, reg_id/tour_id y el lado salen de
    round_info (join por map_id + round). player_id/victim_id son los de table_players (equipo
    mas reciente del jugador); team/victim_team son los tags de ese match.
    """
    events_path = os.path.join(tables_dir, "table_round_events.csv")
    summary_path = os.path.join(tables_dir, "table_round_summary.csv")
    file_list = find_files_by_prefix(root_folder=csv_dir, prefix="round_events")
    if not file_list:
        # antes del backfill no hay round_events: tablas vacias con headers
        df_empty_events = pd.DataFrame(columns=ROUND_EVENTS_COLUMNS)
        df_empty_summary = pd.DataFrame(columns=ROUND_SUMMARY_COLUMNS)
        df_empty_events.to_csv(path_or_buf=events_path, index=False, encoding="iso-8859-1")
        df_empty_summary.to_csv(path_or_buf=summary_path, index=False, encoding="iso-8859-1")
        return df_empty_events, df_empty_summary

    df_events = concat_from_list(file_list)
    df_events["series_id"] = df_events["source_url"].apply(match_id_vlr)
    df_events["map_id"] = df_events["series_id"] + "-" + df_events["map"]
    df_events = pd.merge(
        df_events,
        df_round_concat[["map_id", "round", "teamA", "teamB", "side", "team_map_round_id", "reg_id", "tour_id"]],
        how="left",
        on=["map_id", "round"],
    )
    no_round = df_events["team_map_round_id"].isna()
    if no_round.any():
        logger.warning(f"round_events: descarto {int(no_round.sum())} eventos sin ronda en round_info")
        df_events = df_events[~no_round]
    df_events = df_events.sort_values(["team_map_round_id", "ev_index"], kind="stable").reset_index(drop=True)

    df_events = df_events.rename(columns={"by_player": "player", "by_team": "team", "side": "side_team_a"})
    for column in ("team", "victim_team"):
        df_events[column] = canonical_teams(df_events[column], df_events["teamA"], df_events["teamB"])
    unknown_team = df_events["team"].notna() & (df_events["team"] != df_events["teamA"]) & (df_events["team"] != df_events["teamB"])
    if unknown_team.any():
        tags = sorted(set(df_events.loc[unknown_team, "team"]))
        logger.warning(
            f"round_events: {int(unknown_team.sum())} eventos con un tag que no esta en round_info "
            f"{tags}: agregarlo a team_aliases en lookups.py (el side y las kills por equipo salen mal)"
        )
    df_events["t_sec"] = df_events["clock"].apply(clock_to_seconds)
    df_events["side"] = np.where(
        df_events["team"] == df_events["teamA"],
        df_events["side_team_a"],
        np.where(df_events["side_team_a"] == "atk", "def", "atk"),
    )

    player_ids = df_players_id.set_index("player")["player_id"]
    df_events["player_id"] = df_events["player"].map(player_ids)
    df_events["victim_id"] = df_events["victim"].map(player_ids)
    no_id = df_events["player_id"].isna() | (df_events["victim"].notna() & df_events["victim_id"].isna())
    if no_id.any():
        logger.warning(f"round_events: {int(no_id.sum())} eventos con un jugador que no esta en table_players")

    is_kill = df_events["type"] == "kill"
    df_events["is_team_kill"] = is_kill & (df_events["team"] == df_events["victim_team"])
    valid_kill = is_kill & ~df_events["is_team_kill"]
    df_events["is_first_blood"] = valid_kill & (valid_kill.astype(int).groupby(df_events["team_map_round_id"]).cumsum() == 1)

    plant_index = (
        df_events.loc[df_events["type"] == "plant"].groupby("team_map_round_id")["ev_index"].min()
    )
    df_events["is_post_plant"] = df_events["ev_index"] > df_events["team_map_round_id"].map(plant_index).fillna(np.inf)
    df_events["is_trade"], df_events["is_traded"] = mark_trades(df_events)

    df_events[ROUND_EVENTS_COLUMNS].to_csv(path_or_buf=events_path, index=False, encoding="iso-8859-1")

    # resumen por ronda
    df_summary = df_events.drop_duplicates(subset=["team_map_round_id"])[
        ["team_map_round_id", "series_id", "map_id", "round", "reg_id", "tour_id", "teamA", "teamB", "side_team_a"]
    ].rename(columns={"teamA": "team_a", "teamB": "team_b"})

    first_blood = df_events[df_events["is_first_blood"]].set_index("team_map_round_id")
    df_summary = df_summary.join(
        first_blood[["player_id", "team", "victim_id", "t_sec"]].rename(
            columns={"player_id": "fb_player_id", "team": "fb_team", "victim_id": "fb_victim_id", "t_sec": "fb_t"}
        ),
        on="team_map_round_id",
    )
    plant = df_events[df_events["type"] == "plant"].drop_duplicates(subset=["team_map_round_id"]).set_index("team_map_round_id")
    df_summary = df_summary.join(
        plant[["t_sec", "site", "player_id"]].rename(
            columns={"t_sec": "plant_t", "site": "plant_site", "player_id": "plant_player_id"}
        ),
        on="team_map_round_id",
    )
    defuse = df_events[df_events["type"] == "defuse"].drop_duplicates(subset=["team_map_round_id"]).set_index("team_map_round_id")
    df_summary = df_summary.join(
        defuse[["t_sec", "player_id"]].rename(columns={"t_sec": "defuse_t", "player_id": "defuse_player_id"}),
        on="team_map_round_id",
    )

    df_valid = df_events[valid_kill]
    team_a_kill = df_valid["team"] == df_valid["teamA"]
    counts = pd.DataFrame({
        "kills_team_a": team_a_kill,
        "kills_team_b": ~team_a_kill,
        "trades_team_a": team_a_kill & df_valid["is_trade"],
        "trades_team_b": ~team_a_kill & df_valid["is_trade"],
    }).groupby(df_valid["team_map_round_id"]).sum()
    df_summary = df_summary.join(counts, on="team_map_round_id")
    df_summary = df_summary.join(
        df_events.groupby("team_map_round_id")["t_sec"].max().rename("last_event_t"), on="team_map_round_id"
    )

    # Int64 (nullable): una ronda sin plant/defuse/kills deja NA y no "85.0"
    int_columns = ["fb_t", "plant_t", "defuse_t", "kills_team_a", "kills_team_b", "trades_team_a", "trades_team_b"]
    df_summary[int_columns] = df_summary[int_columns].astype("Float64").fillna(
        {column: 0 for column in int_columns if column.startswith(("kills", "trades"))}
    ).astype("Int64")

    df_summary[ROUND_SUMMARY_COLUMNS].to_csv(path_or_buf=summary_path, index=False, encoding="iso-8859-1")
    return df_events, df_summary


# situaciones XvY: el estado de una pelea solo es valido cuando se cerro la ventana de trade.
# Si siguen cayendo jugadores dentro de SETTLE_WINDOW es la misma pelea y el XvY no quedo firme.
# Constante aparte de TRADE_WINDOW para poder tunear una sin tocar la otra.
SETTLE_WINDOW = TRADE_WINDOW
# arma / escudo de round_buy -> sufijo de la columna agregada
SITUATION_WEAPONS = {"Vandal": "vandal", "Phantom": "phantom", "Operator": "oper"}
SITUATION_SHIELDS = {"Heavy": "heavy", "Light": "light", "Regen": "regen"}
ECONOMY_FIELDS = ["bank", "spend"] + list(SITUATION_WEAPONS.values()) + list(SITUATION_SHIELDS.values())

ROUND_SITUATIONS_COLUMNS = (
    [
        "team_map_round_id", "seg_index", "team", "which", "rival_team",
        "series_id", "map_id", "map", "round", "reg_id", "tour_id", "side",
        "alive_own", "alive_rival", "diff_alive", "situation", "roster_own", "roster_rival",
        "t_start", "t_end", "duration", "deaths_own_cluster", "deaths_rival_cluster",
        "is_opening", "is_last", "is_wiped_own", "is_wiped_rival", "is_t_end_estimated",
        "is_post_plant", "time_since_plant", "plant_site", "is_defused_later",
    ]
    + [f"{field}_start" for field in ECONOMY_FIELDS]
    + [f"{field}_alive" for field in ECONOMY_FIELDS]
    + [f"{field}_rival_alive" for field in ECONOMY_FIELDS]
    + ["round_win", "win_con", "has_revive", "has_buy", "buy_unmatched_own"]
)
# nullables: la ronda puede no tener plant y la economia puede no estar en round_buy
SITUATION_INT_COLUMNS = ["time_since_plant"] + [
    f"{field}{suffix}" for suffix in ("_start", "_alive", "_rival_alive") for field in ECONOMY_FIELDS
]

SITUATION_STATS_COLUMNS = [
    "tour_id", "event", "team", "side", "situation", "alive_own", "alive_rival", "diff_alive",
    "n_segments", "n_rounds", "n_wins", "win_rate", "avg_duration", "post_plant_share",
]


def round_buy_long(df_round_buy):
    """round_buy ancho -> largo: una fila por (ronda, which, slot) con nombre, arma, escudo, spend, bank.

    Usa ROUND_BUY_SLOTS y los sufijos de ROUND_BUY_FIELDS, asi que no puede desincronizarse
    del layout ancho de round_buy_columns().
    """
    frames = []
    for which in ("team_a", "team_b"):
        for slot in ROUND_BUY_SLOTS:
            base = f"player_{slot}_{which}"
            frames.append(pd.DataFrame({
                "team_map_round_id": df_round_buy["team_map_round_id"],
                "which": which,
                "player": df_round_buy[base],
                "weapon": df_round_buy[f"{base}_weapon"],
                "shield": df_round_buy[f"{base}_shield"],
                "spend": df_round_buy[f"{base}_spend"],
                "bank": df_round_buy[f"{base}_bank"],
            }))
    df_long = pd.concat(frames, ignore_index=True)
    return df_long[df_long["player"].notna()]


def situation_economy(records, dead=frozenset()):
    """bank/spend y conteo de armas y escudos de un equipo, salteando a los jugadores muertos.

    Sin filas en round_buy (records vacio) devuelve NA en todo: no es un equipo sin plata, es un
    equipo del que no sabemos la compra. Un equipo entero muerto si devuelve 0 en todo.
    """
    if not records:
        return {field: pd.NA for field in ECONOMY_FIELDS}

    alive = [record for record in records if record["player"] not in dead]
    economy = {
        "bank": sum(record["bank"] for record in alive if not pd.isna(record["bank"])),
        "spend": sum(record["spend"] for record in alive if not pd.isna(record["spend"])),
    }
    for weapon, field in SITUATION_WEAPONS.items():
        economy[field] = sum(1 for record in alive if record["weapon"] == weapon)
    for shield, field in SITUATION_SHIELDS.items():
        economy[field] = sum(1 for record in alive if record["shield"] == shield)
    return economy


def build_round_situations(df_events, df_summary, df_round_buy, df_round_concat, tables_dir="tables"):
    """table_round_situations.csv: una fila por (ronda, segmento, equipo) con el estado XvY.

    Un segmento es un tramo de la ronda con el numero de vivos ya estabilizado. Las kills se
    agrupan en clusters (una kill entra al cluster si esta a <= SETTLE_WINDOW de la anterior del
    cluster) y el estado recien vale SETTLE_WINDOW segundos despues de la ultima kill del cluster:
    asi un trade, o una cadena de trades, no genera un 5v4 que nunca se jugo. El segmento 0 es la
    apertura 5v5, de t=0 hasta la primera kill.

    Los vivos se cuentan con el set de muertos por tag (victim_team, nunca victim_id, que lleva el
    equipo mas reciente del jugador). Las team kills cuentan como muerte. vlr no loguea las
    resurrecciones (Sage, Clove): esas rondas quedan marcadas con has_revive y los vivos quedan
    sobreestimados entre la resurreccion y la muerte siguiente.

    La economia sale de round_buy, que es el snapshot de inicio de ronda: *_start es el equipo
    completo y *_alive solo los que siguen vivos en el segmento. round_win, win_con y
    is_defused_later son futuro respecto del segmento: etiquetas, no features.
    """
    path = os.path.join(tables_dir, "table_round_situations.csv")
    kills = df_events[df_events["type"] == "kill"] if not df_events.empty else df_events
    if kills.empty:
        # antes del backfill no hay round_events: tabla vacia con headers
        df_empty = pd.DataFrame(columns=ROUND_SITUATIONS_COLUMNS)
        df_empty.to_csv(path_or_buf=path, index=False, encoding="iso-8859-1")
        return df_empty

    rounds = df_round_concat.drop_duplicates(subset=["team_map_round_id"]).set_index("team_map_round_id")
    summary = df_summary.drop_duplicates(subset=["team_map_round_id"]).set_index("team_map_round_id")
    records_by_round = {
        key: group.to_dict("records")
        for key, group in round_buy_long(df_round_buy).groupby(["team_map_round_id", "which"], sort=False)
    }

    rows = []
    no_round = 0
    unmatched_total = 0
    unknown_tags = Counter()
    for team_map_round_id, round_kills in kills.groupby("team_map_round_id", sort=False):
        if team_map_round_id not in rounds.index:
            no_round += 1
            continue
        info = rounds.loc[team_map_round_id]
        tags = {"team_a": info["teamA"], "team_b": info["teamB"]}
        which_by_tag = {info["teamA"]: "team_a", info["teamB"]: "team_b"}
        # side de round_info es el de teamA; round_win sale de rndA/rndB y nunca de los vivos:
        # un equipo barrido gana la ronda si la spike ya estaba plantada y explota
        sides = {"team_a": info["side"], "team_b": "def" if info["side"] == "atk" else "atk"}
        wins = {"team_a": int(info["rndA"]), "team_b": int(info["rndB"])}

        records = {which: records_by_round.get((team_map_round_id, which), []) for which in tags}
        # sin round_buy asumimos los 5 de siempre; con round_buy puede haber menos (desconexion)
        roster = {which: len(records[which]) or 5 for which in tags}
        has_buy = any(records[which] for which in tags)
        start_economy = {which: situation_economy(records[which]) for which in tags}

        plant_t = summary["plant_t"].get(team_map_round_id, pd.NA)
        plant_site = summary["plant_site"].get(team_map_round_id, pd.NA)
        defuse_t = summary["defuse_t"].get(team_map_round_id, pd.NA)
        last_event_t = summary["last_event_t"].get(team_map_round_id, pd.NA)

        # clusters: ventana deslizante encadenada sobre t_sec (round_kills ya viene por ev_index)
        clusters, current = [], []
        for kill in round_kills.itertuples():
            if current and kill.t_sec - current[-1].t_sec <= SETTLE_WINDOW:
                current.append(kill)
            else:
                if current:
                    clusters.append(current)
                current = [kill]
        clusters.append(current)

        settle_last = int(clusters[-1][-1].t_sec) + SETTLE_WINDOW
        round_end_t = settle_last if pd.isna(last_event_t) else max(int(last_event_t), settle_last)
        has_revive = bool(round_kills["victim"].duplicated().any())

        dead = {which: set() for which in tags}
        unmatched = {which: 0 for which in tags}
        # apertura: 5v5 desde el inicio de la ronda hasta la primera kill
        segments = [{
            "seg_index": 0, "t_start": 0, "t_end": int(clusters[0][0].t_sec),
            "deaths": {which: 0 for which in tags}, "dead": {which: set() for which in tags},
            "unmatched": dict(unmatched), "is_opening": True, "is_last": False,
        }]
        for index, cluster in enumerate(clusters):
            deaths = {which: 0 for which in tags}
            for kill in cluster:
                which = which_by_tag.get(kill.victim_team)
                if which is None:
                    # tag que no es teamA ni teamB: la muerte no se puede atribuir y los vivos
                    # quedarian de mas. Hay que agregar el tag a team_aliases (lookups.py).
                    unknown_tags[kill.victim_team] += 1
                    continue
                if kill.victim not in dead[which]:
                    deaths[which] += 1
                    if records[which] and not any(record["player"] == kill.victim for record in records[which]):
                        unmatched[which] += 1
                dead[which].add(kill.victim)
            settle = int(cluster[-1].t_sec) + SETTLE_WINDOW
            is_last = index + 1 == len(clusters)
            next_t = round_end_t if is_last else int(clusters[index + 1][0].t_sec)
            segments.append({
                "seg_index": index + 1, "t_start": settle, "t_end": max(next_t, settle),
                "deaths": deaths, "dead": {which: set(dead[which]) for which in tags},
                "unmatched": dict(unmatched), "is_opening": False, "is_last": is_last,
            })
        unmatched_total += sum(unmatched.values())

        for segment in segments:
            alive = {which: max(roster[which] - len(segment["dead"][which]), 0) for which in tags}
            alive_economy = {
                which: situation_economy(records[which], segment["dead"][which]) for which in tags
            }
            is_post_plant = not pd.isna(plant_t) and segment["t_start"] >= plant_t
            for own, rival in (("team_a", "team_b"), ("team_b", "team_a")):
                row = {
                    "team_map_round_id": team_map_round_id,
                    "seg_index": segment["seg_index"],
                    "team": tags[own],
                    "which": own,
                    "rival_team": tags[rival],
                    "series_id": info["series_id"],
                    "map_id": info["map_id"],
                    "map": info["map"],
                    "round": info["round"],
                    "reg_id": info["reg_id"],
                    "tour_id": info["tour_id"],
                    "side": sides[own],
                    "alive_own": alive[own],
                    "alive_rival": alive[rival],
                    "diff_alive": alive[own] - alive[rival],
                    "situation": f"{alive[own]}v{alive[rival]}",
                    "roster_own": roster[own],
                    "roster_rival": roster[rival],
                    "t_start": segment["t_start"],
                    "t_end": segment["t_end"],
                    "duration": segment["t_end"] - segment["t_start"],
                    "deaths_own_cluster": segment["deaths"][own],
                    "deaths_rival_cluster": segment["deaths"][rival],
                    "is_opening": segment["is_opening"],
                    "is_last": segment["is_last"],
                    "is_wiped_own": alive[own] == 0,
                    "is_wiped_rival": alive[rival] == 0,
                    "is_t_end_estimated": segment["is_last"],
                    "is_post_plant": is_post_plant,
                    "time_since_plant": segment["t_start"] - plant_t if is_post_plant else pd.NA,
                    "plant_site": plant_site,
                    "is_defused_later": not pd.isna(defuse_t) and defuse_t >= segment["t_start"],
                    "round_win": wins[own],
                    "win_con": info["winCon"],
                    "has_revive": has_revive,
                    "has_buy": has_buy,
                    "buy_unmatched_own": segment["unmatched"][own],
                }
                row.update({f"{field}_start": value for field, value in start_economy[own].items()})
                row.update({f"{field}_alive": value for field, value in alive_economy[own].items()})
                row.update({f"{field}_rival_alive": value for field, value in alive_economy[rival].items()})
                rows.append(row)

    if no_round:
        logger.warning(f"round_situations: descarto {no_round} rondas que no estan en round_info")
    if unmatched_total:
        logger.warning(
            f"round_situations: {unmatched_total} muertes sin slot en round_buy (economia de vivos sobreestimada)"
        )
    if unknown_tags:
        logger.warning(
            f"round_situations: {sum(unknown_tags.values())} muertes con un tag que no esta en round_info "
            f"{dict(unknown_tags)}: los vivos quedan de mas, agregar el tag a team_aliases en lookups.py"
        )

    df_situations = pd.DataFrame(rows).sort_values(
        ["team_map_round_id", "seg_index", "which"], kind="stable"
    ).reset_index(drop=True)
    # Int64 (nullable): una ronda sin plant o sin round_buy deja NA y no "85.0"
    df_situations[SITUATION_INT_COLUMNS] = df_situations[SITUATION_INT_COLUMNS].astype("Float64").astype("Int64")
    df_situations = df_situations.reindex(columns=ROUND_SITUATIONS_COLUMNS)

    df_situations.to_csv(path_or_buf=path, index=False, encoding="iso-8859-1")
    return df_situations


def build_situation_stats(df_situations, df_round_concat, tables_dir="tables"):
    """table_situation_stats.csv: win rate por torneo, equipo, lado y situacion XvY.

    Agregado de table_round_situations para ver rapido como le va a un equipo en ventaja o en
    desventaja. No se sube a Supabase: no tiene series_id y una serie nueva cambia filas ya
    existentes, asi que del lado de la base el equivalente es una vista.

    Excluye las rondas con has_revive (vivos sobreestimados) y los segmentos con un equipo
    barrido (ya no son una situacion jugable). n_wins cuenta rondas, no segmentos.
    """
    path = os.path.join(tables_dir, "table_situation_stats.csv")
    keys = ["tour_id", "team", "side", "situation", "alive_own", "alive_rival", "diff_alive"]
    if df_situations.empty:
        pd.DataFrame(columns=SITUATION_STATS_COLUMNS).to_csv(path_or_buf=path, index=False, encoding="iso-8859-1")
        return

    df_valid = df_situations[
        ~df_situations["has_revive"] & ~df_situations["is_wiped_own"] & ~df_situations["is_wiped_rival"]
    ]
    df_stats = df_valid.groupby(keys, sort=True).agg(
        n_segments=("seg_index", "size"),
        n_rounds=("team_map_round_id", "nunique"),
        avg_duration=("duration", "mean"),
        post_plant_share=("is_post_plant", "mean"),
    ).reset_index()

    # una ronda podria aportar dos segmentos a la misma situacion: las victorias se cuentan una vez
    per_round = df_valid.drop_duplicates(subset=keys + ["team_map_round_id"])
    df_stats = df_stats.join(per_round.groupby(keys)["round_win"].sum().rename("n_wins"), on=keys)
    df_stats["win_rate"] = (df_stats["n_wins"] / df_stats["n_rounds"]).round(4)
    df_stats["avg_duration"] = df_stats["avg_duration"].round(2)
    df_stats["post_plant_share"] = df_stats["post_plant_share"].round(4)
    events = df_round_concat.drop_duplicates(subset=["tour_id"]).set_index("tour_id")["event"]
    df_stats["event"] = df_stats["tour_id"].map(events)

    df_stats[SITUATION_STATS_COLUMNS].to_csv(path_or_buf=path, index=False, encoding="iso-8859-1")


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
    df_players_id = build_players(df_team, csv_dir, tables_dir)

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

    logger.info("building table_round_buy")
    df_round_buy = build_round_buy(df_maps_id, df_round_concat, csv_dir, tables_dir)

    logger.info("building table_round_events / table_round_summary")
    df_events, df_summary = build_round_events(df_round_concat, df_players_id, csv_dir, tables_dir)

    logger.info("building table_round_situations")
    df_situations = build_round_situations(df_events, df_summary, df_round_buy, df_round_concat, tables_dir)

    logger.info("building table_situation_stats")
    build_situation_stats(df_situations, df_round_concat, tables_dir)

    logger.info("building table_agent_info")
    build_agent_info(tables_dir)

    logger.info("done: tables written to %s", tables_dir)
