"""Solapa logs: round_buy_ / round_events_ crudos, table_round_buy (pivot ancho) y table_round_events / table_round_summary."""

import glob
import os

import pandas as pd
import pytest

from tests.conftest import EXPECTED_DIR
from vlr_pipeline.tables import (
    ROUND_EVENTS_COLUMNS,
    ROUND_SUMMARY_COLUMNS,
    build_all,
    build_round_buy,
    build_round_events,
    mark_trades,
    round_buy_columns,
)
from vlr_pipeline.tracking import LOG_COLUMNS, record, update_fields


def read_expected(prefix):
    files = sorted(glob.glob(os.path.join(EXPECTED_DIR, "*", f"{prefix}_*.csv")))
    return pd.concat([pd.read_csv(file, encoding="iso-8859-1") for file in files], ignore_index=True)


@pytest.fixture(scope="module")
def expected_tables(tmp_path_factory):
    """tables/ construido desde los csv esperados de los fixtures."""
    path = tmp_path_factory.mktemp("tables")
    build_all(csv_dir=EXPECTED_DIR, tables_dir=str(path))
    return str(path)


def test_ten_players_per_round_and_same_rounds_as_round_detail():
    buy = read_expected("round_buy")
    round_detail = read_expected("round_detail")

    assert (buy.groupby(["source_url", "map", "round"]).size() == 10).all()
    assert (buy.groupby(["source_url", "map", "round", "team"]).size() == 5).all()

    buy_rounds = buy.groupby(["source_url", "map"])["round"].nunique()
    detail_rounds = round_detail.groupby(["source_url", "map"])["round"].nunique()
    pd.testing.assert_series_equal(buy_rounds.sort_index(), detail_rounds.sort_index(), check_names=False)


def test_credits_are_non_negative_ints():
    buy = read_expected("round_buy")
    for column in ("spent", "bank"):
        assert pd.api.types.is_integer_dtype(buy[column])
        assert (buy[column] >= 0).all()


def test_events_have_players_and_kill_weapons():
    events = read_expected("round_events")
    assert set(events["type"]) == {"kill", "plant", "defuse"}
    kills = events[events["type"] == "kill"]
    assert kills[["by_player", "by_team", "victim", "victim_team", "weapon"]].notna().all().all()
    assert events.loc[events["type"] != "kill", "site"].notna().all()


def test_round_buy_one_row_per_round_linked_to_round_info(expected_tables):
    round_buy = pd.read_csv(os.path.join(expected_tables, "table_round_buy.csv"), encoding="utf-8")
    round_info = pd.read_csv(os.path.join(expected_tables, "table_round_info.csv"), encoding="utf-8")

    assert list(round_buy.columns) == round_buy_columns()
    assert round_buy["team_map_round_id"].is_unique
    assert set(round_buy["team_map_round_id"]) == set(round_info["team_map_round_id"])
    assert round_buy[["reg_id", "tour_id"]].notna().all().all()
    # cada slot de los dos equipos completo, con enteros (no "2400.0")
    assert round_buy.notna().all().all()
    assert pd.api.types.is_integer_dtype(round_buy["player_1_team_a_spend"])


def test_round_buy_without_raw_files_writes_headers(tmp_path):
    build_round_buy(pd.DataFrame(columns=["map_id", "reg_id", "tour_id"]), csv_dir=str(tmp_path), tables_dir=str(tmp_path))
    table = pd.read_csv(tmp_path / "table_round_buy.csv")
    assert table.empty
    assert list(table.columns) == round_buy_columns()


def test_update_fields_keeps_status_and_attempts():
    url = "https://www.vlr.gg/1/x"
    log = pd.DataFrame(columns=LOG_COLUMNS)
    log = record(log, url, status="ok", event="Evento")
    before = log.iloc[0].copy()

    log = update_fields(log, url, has_logs=True)
    row = log.iloc[0]
    assert row["has_logs"] == "True"
    assert row["status"] == before["status"]
    assert row["attempts"] == before["attempts"]
    assert row["last_attempt"] >= before["last_attempt"]


def test_round_events_linked_and_cross_checked_with_player_stats(expected_tables):
    events = pd.read_csv(os.path.join(expected_tables, "table_round_events.csv"), encoding="utf-8")
    round_info = pd.read_csv(os.path.join(expected_tables, "table_round_info.csv"), encoding="utf-8")
    player_stats = pd.read_csv(os.path.join(expected_tables, "table_player_stats.csv"), encoding="utf-8")

    assert list(events.columns) == ROUND_EVENTS_COLUMNS
    assert not events.duplicated(subset=["team_map_round_id", "ev_index"]).any()
    assert set(events["team_map_round_id"]) <= set(round_info["team_map_round_id"])
    assert events[["player_id", "reg_id", "tour_id", "side"]].notna().all().all()
    kills = events[events["type"] == "kill"]
    assert kills["victim_id"].notna().all()

    # kills sin team kills = killsBoth de vlr, jugador por jugador
    valid = kills[~kills["is_team_kill"]]
    from_events = valid.groupby(["map_id", "player"]).size()
    from_stats = player_stats.set_index(["map_id", "player"])["killsBoth"]
    pd.testing.assert_series_equal(
        from_events.reindex(from_stats.index, fill_value=0), from_stats, check_names=False, check_dtype=False
    )

    # a lo sumo un first blood por ronda, y siempre es la primera kill valida
    first_blood = events[events["is_first_blood"]]
    assert first_blood["team_map_round_id"].is_unique
    assert (first_blood.groupby("team_map_round_id")["ev_index"].min()
            == valid.groupby("team_map_round_id")["ev_index"].min().loc[first_blood["team_map_round_id"]]).all()
    assert not events.loc[events["type"] != "kill", ["is_trade", "is_traded"]].any().any()


def test_round_summary_one_row_per_round(expected_tables):
    events = pd.read_csv(os.path.join(expected_tables, "table_round_events.csv"), encoding="utf-8")
    summary = pd.read_csv(os.path.join(expected_tables, "table_round_summary.csv"), encoding="utf-8")

    assert list(summary.columns) == ROUND_SUMMARY_COLUMNS
    assert summary["team_map_round_id"].is_unique
    assert set(summary["team_map_round_id"]) == set(events["team_map_round_id"])
    valid_kills = ((events["type"] == "kill") & ~events["is_team_kill"]).sum()
    assert (summary["kills_team_a"] + summary["kills_team_b"]).sum() == valid_kills
    assert (summary["trades_team_a"] + summary["trades_team_b"]).sum() == events["is_trade"].sum()
    assert summary["plant_t"].notna().sum() == (events["type"] == "plant").sum()
    # defuse siempre despues del plant
    defused = summary[summary["defuse_t"].notna()]
    assert (defused["defuse_t"] >= defused["plant_t"]).all()
    assert pd.api.types.is_integer_dtype(summary["kills_team_a"])


def _event(ev_index, t_sec, player, team, victim, victim_team):
    return {"team_map_round_id": "A-B-1-Ascent-1", "ev_index": ev_index, "t_sec": t_sec, "type": "kill",
            "player": player, "team": team, "victim": victim, "victim_team": victim_team,
            "is_team_kill": team == victim_team}


def test_mark_trades_window():
    events = pd.DataFrame([
        _event(0, 10, "b1", "B", "a1", "A"),  # b1 mata a a1
        _event(1, 14, "a2", "A", "b1", "B"),  # a2 mata a b1 a los 4 s: trade
        _event(2, 20, "b2", "B", "a2", "A"),  # b2 mata a a2
        _event(3, 26, "a3", "A", "b2", "B"),  # 6 s despues: no es trade
        _event(4, 27, "a3", "A", "a3", "A"),  # team kill (spike): se ignora
    ])
    is_trade, is_traded = mark_trades(events)
    assert is_trade.tolist() == [False, True, False, False, False]
    assert is_traded.tolist() == [True, False, False, False, False]


def test_round_events_without_raw_files_writes_headers(tmp_path):
    build_round_events(pd.DataFrame(), pd.DataFrame(), csv_dir=str(tmp_path), tables_dir=str(tmp_path))
    assert list(pd.read_csv(tmp_path / "table_round_events.csv").columns) == ROUND_EVENTS_COLUMNS
    assert list(pd.read_csv(tmp_path / "table_round_summary.csv").columns) == ROUND_SUMMARY_COLUMNS
