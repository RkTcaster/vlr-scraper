"""Situaciones XvY: table_round_situations (una fila por ronda, segmento y equipo) y table_situation_stats."""

import os

import pandas as pd
import pytest

from tests.conftest import EXPECTED_DIR
from vlr_pipeline.tables import (
    ROUND_SITUATIONS_COLUMNS,
    SETTLE_WINDOW,
    SITUATION_STATS_COLUMNS,
    build_round_situations,
    build_situation_stats,
    round_buy_columns,
)
from vlr_pipeline.tables import ROUND_EVENTS_COLUMNS, ROUND_SUMMARY_COLUMNS, build_all

SEGMENT = ["team_map_round_id", "seg_index"]
ECONOMY = ["bank", "spend", "vandal", "phantom", "oper", "heavy", "light", "regen"]


@pytest.fixture(scope="module")
def expected_tables(tmp_path_factory):
    """tables/ construido desde los csv esperados de los fixtures."""
    path = tmp_path_factory.mktemp("tables")
    build_all(csv_dir=EXPECTED_DIR, tables_dir=str(path))
    return str(path)


def read_table(tables_path, name):
    # iso-8859-1 a la escritura pero los bytes son utf-8 validos (ver build_maps_and_round_info)
    return pd.read_csv(os.path.join(tables_path, f"table_{name}.csv"), encoding="utf-8", low_memory=False)


@pytest.fixture(scope="module")
def situations(expected_tables):
    return read_table(expected_tables, "round_situations")


def test_columns_and_primary_key(situations):
    assert list(situations.columns) == ROUND_SITUATIONS_COLUMNS
    assert not situations.duplicated(["team_map_round_id", "seg_index", "team"]).any()
    assert situations[["team_map_round_id", "seg_index", "team"]].notna().all().all()
    for column in ("seg_index", "alive_own", "alive_rival", "diff_alive", "t_start", "t_end", "duration", "round_win"):
        assert pd.api.types.is_integer_dtype(situations[column]), column


def test_rounds_exist_in_round_info(situations, expected_tables):
    round_info = read_table(expected_tables, "round_info")
    assert situations["team_map_round_id"].isin(set(round_info["team_map_round_id"])).all()
    assert situations["series_id"].notna().all()


def test_two_mirrored_rows_per_segment(situations):
    assert (situations.groupby(SEGMENT).size() == 2).all()
    assert (situations.groupby(SEGMENT)["side"].nunique() == 2).all()
    assert (situations.groupby(SEGMENT)["round_win"].sum() == 1).all()

    # comparacion explicita por which: groupby.first() saltea los NaN de la economia
    # (una ronda sin round_buy deja las columnas en NA) y daria un falso positivo
    team_a = situations[situations["which"] == "team_a"].set_index(SEGMENT)
    team_b = situations[situations["which"] == "team_b"].set_index(SEGMENT)
    assert team_a.index.equals(team_b.index)
    assert (team_a["alive_own"] == team_b["alive_rival"]).all()
    for field in ECONOMY:
        left, right = team_a[f"{field}_alive"], team_b[f"{field}_rival_alive"]
        assert ((left == right) | (left.isna() & right.isna())).all(), field


def test_alive_counts_are_possible(situations):
    assert situations["alive_own"].between(0, 5).all()
    assert situations["alive_rival"].between(0, 5).all()
    assert (situations["diff_alive"] == situations["alive_own"] - situations["alive_rival"]).all()
    assert (situations["situation"] == situations["alive_own"].astype(str) + "v" + situations["alive_rival"].astype(str)).all()

    # sin resurrecciones los vivos solo pueden bajar dentro de la ronda
    monotonic = situations[~situations["has_revive"]].sort_values(["team_map_round_id", "which", "seg_index"])
    assert monotonic.groupby(["team_map_round_id", "which"])["alive_own"].apply(
        lambda alive: alive.diff().dropna().le(0).all()
    ).all()


def test_segments_cover_the_round(situations):
    opening = situations[situations["is_opening"]]
    assert opening.groupby("team_map_round_id").size().eq(2).all()
    assert (opening["t_start"] == 0).all()
    assert (opening["situation"] == "5v5").all()
    assert (opening["deaths_own_cluster"] == 0).all()

    assert situations[situations["is_last"]].groupby("team_map_round_id").size().eq(2).all()
    assert (situations["is_t_end_estimated"] == situations["is_last"]).all()
    assert (situations["t_end"] >= situations["t_start"]).all()
    assert (situations["duration"] == situations["t_end"] - situations["t_start"]).all()

    # seg_index contiguo desde 0
    index = situations.groupby("team_map_round_id")["seg_index"].agg(["max", "nunique"])
    assert (index["max"] + 1 == index["nunique"]).all()


def test_deaths_match_the_event_log(situations, expected_tables):
    events = read_table(expected_tables, "round_events")
    kills = events[events["type"] == "kill"]
    # team kills incluidas: el muerto igual muere. Victimas distintas, no eventos: vlr no loguea
    # las resurrecciones y una victima puede morir dos veces.
    distinct = kills.groupby(["team_map_round_id", "victim_team"])["victim"].nunique().sum()
    own = situations[situations["which"] == "team_a"]
    assert own[["deaths_own_cluster", "deaths_rival_cluster"]].to_numpy().sum() == distinct


def test_wipe_does_not_decide_the_round(situations, expected_tables):
    """winCon elim => el ultimo segmento tiene un equipo barrido. La inversa no vale: un equipo
    sin vivos gana la ronda si la spike ya estaba plantada y explota."""
    round_info = read_table(expected_tables, "round_info")
    last = situations[situations["is_last"]].merge(round_info[["team_map_round_id", "winCon"]], on="team_map_round_id")
    elim = last[last["winCon"] == "elim"]
    assert (elim["is_wiped_own"] | elim["is_wiped_rival"]).all()
    assert (situations["is_wiped_own"] == (situations["alive_own"] == 0)).all()


def test_spike_context(situations, expected_tables):
    summary = read_table(expected_tables, "round_summary")
    planted = set(summary.loc[summary["plant_t"].notna(), "team_map_round_id"])
    defused = set(summary.loc[summary["defuse_t"].notna(), "team_map_round_id"])

    assert situations.loc[situations["is_post_plant"], "team_map_round_id"].isin(planted).all()
    assert situations.loc[situations["is_defused_later"], "team_map_round_id"].isin(defused).all()
    assert (situations.loc[situations["is_post_plant"], "time_since_plant"] >= 0).all()
    assert situations.loc[~situations["is_post_plant"], "time_since_plant"].isna().all()
    assert situations.loc[situations["plant_site"].notna(), "team_map_round_id"].isin(planted).all()


def test_economy_of_alive_players(situations):
    opening = situations[situations["is_opening"]]
    for field in ECONOMY:
        assert (situations[f"{field}_alive"] <= situations[f"{field}_start"]).all(), field
        # en la apertura no murio nadie: los vivos son el equipo completo
        assert (opening[f"{field}_alive"] == opening[f"{field}_start"]).all(), field

    assert (situations["vandal_start"] + situations["phantom_start"] + situations["oper_start"] <= situations["roster_own"]).all()
    assert (situations["heavy_start"] + situations["light_start"] + situations["regen_start"] <= situations["roster_own"]).all()
    assert (situations.loc[situations["is_wiped_own"], "bank_alive"] == 0).all()
    assert situations["buy_unmatched_own"].sum() == 0
    # has_buy False solo si no hay compra para esa ronda, y entonces la economia va NA entera
    no_buy = situations[~situations["has_buy"]]
    assert no_buy[[f"{field}_start" for field in ECONOMY]].isna().all().all()
    assert situations.loc[situations["has_buy"], "bank_start"].notna().all()


def test_situation_stats(expected_tables):
    stats = read_table(expected_tables, "situation_stats")
    assert list(stats.columns) == SITUATION_STATS_COLUMNS
    assert not stats.duplicated(["tour_id", "team", "side", "situation"]).any()
    assert stats["win_rate"].between(0, 1).all()
    assert (stats["n_wins"] <= stats["n_rounds"]).all()
    assert (stats["n_rounds"] <= stats["n_segments"]).all()
    assert stats["event"].notna().all()
    # los barridos quedan fuera: ninguna situacion con un 0
    assert not stats["situation"].str.contains("0").any()


def _kill(ev_index, t_sec, player, team, victim, victim_team):
    return {"team_map_round_id": "A-B-1-Ascent-1", "ev_index": ev_index, "t_sec": t_sec, "type": "kill",
            "player": player, "team": team, "victim": victim, "victim_team": victim_team,
            "is_team_kill": team == victim_team}


def _round_info():
    return pd.DataFrame([{
        "team_map_round_id": "A-B-1-Ascent-1", "teamA": "A", "teamB": "B", "side": "atk",
        "rndA": 1, "rndB": 0, "winCon": "elim", "series_id": "1", "map_id": "1-Ascent",
        "map": "Ascent", "round": 1, "reg_id": "reg_1", "tour_id": "torneo", "event": "Torneo",
    }])


def _summary(last_event_t):
    return pd.DataFrame([{
        "team_map_round_id": "A-B-1-Ascent-1", "plant_t": pd.NA, "plant_site": pd.NA,
        "defuse_t": pd.NA, "last_event_t": last_event_t,
    }])


def test_cluster_window_and_revive(tmp_path):
    """Las kills a <= SETTLE_WINDOW son la misma pelea; una victima que muere dos veces cuenta una."""
    events = pd.DataFrame([
        _kill(0, 10, "b1", "B", "a1", "A"),                   # abre el cluster 1
        _kill(1, 10 + SETTLE_WINDOW, "a2", "A", "b1", "B"),   # en el borde: mismo cluster (trade)
        _kill(2, 10 + 2 * SETTLE_WINDOW + 1, "b2", "B", "a2", "A"),  # fuera: cluster 2
        _kill(3, 40, "a3", "A", "a3", "A"),                   # team kill (spike): igual muere
        _kill(4, 50, "b3", "B", "a1", "A"),                   # a1 revivido y muerto otra vez
    ])
    df = build_round_situations(events, _summary(50), pd.DataFrame(columns=round_buy_columns()),
                               _round_info(), tables_dir=str(tmp_path))
    own = df[df["which"] == "team_a"].set_index("seg_index")

    # apertura 5v5 hasta la primera kill
    assert own.loc[0, ["situation", "t_start", "t_end"]].tolist() == ["5v5", 0, 10]
    # cluster 1: cae uno de cada lado y el estado vale en 10 + 2 * SETTLE_WINDOW
    assert own.loc[1, "situation"] == "4v4"
    assert own.loc[1, "t_start"] == 10 + 2 * SETTLE_WINDOW
    assert own.loc[1, ["deaths_own_cluster", "deaths_rival_cluster"]].tolist() == [1, 1]
    # cluster 2: una sola kill
    assert own.loc[2, "situation"] == "3v4"
    # team kill
    assert own.loc[3, "situation"] == "2v4"
    # a1 ya estaba muerta: no baja de nuevo, y la ronda queda marcada
    assert own.loc[4, "situation"] == "2v4"
    assert own.loc[4, "deaths_own_cluster"] == 0
    assert df["has_revive"].all()
    assert own.loc[4, "is_last"] and own.loc[4, "t_end"] == 50 + SETTLE_WINDOW
    # sin round_buy la economia queda en NA, no en 0
    assert own[[f"{field}_start" for field in ECONOMY]].isna().all().all()
    assert not df["has_buy"].any()


def test_empty_input_writes_headers(tmp_path):
    df = build_round_situations(
        pd.DataFrame(columns=ROUND_EVENTS_COLUMNS),
        pd.DataFrame(columns=ROUND_SUMMARY_COLUMNS),
        pd.DataFrame(columns=round_buy_columns()),
        _round_info(),
        tables_dir=str(tmp_path),
    )
    build_situation_stats(df, _round_info(), tables_dir=str(tmp_path))

    situations = pd.read_csv(os.path.join(tmp_path, "table_round_situations.csv"), encoding="utf-8")
    stats = pd.read_csv(os.path.join(tmp_path, "table_situation_stats.csv"), encoding="utf-8")
    assert list(situations.columns) == ROUND_SITUATIONS_COLUMNS and situations.empty
    assert list(stats.columns) == SITUATION_STATS_COLUMNS and stats.empty
