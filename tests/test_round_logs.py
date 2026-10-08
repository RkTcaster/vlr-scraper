"""Solapa logs: round_buy_ / round_events_ crudos y table_round_buy (pivot ancho)."""

import glob
import os

import pandas as pd
import pytest

from tests.conftest import EXPECTED_DIR
from vlr_pipeline.tables import build_all, build_round_buy, round_buy_columns
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
