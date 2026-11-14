"""team_id_vlr: el id de equipo de vlr es la identidad del equipo, no el tricode (2026-11-10).

El tag se repite entre equipos distintos (THE en cuatro qualifiers, FUR = FURIA y un equipo del
Brazil Open Qualifier) y hasta en un mismo match (785082, FAKE vs FAKE).
"""

import gzip
import os

import pandas as pd
from bs4 import BeautifulSoup

from scripts.backfill_team_ids import fill_player_stats, fill_round_detail
from tests.conftest import HTML_DIR
from vlr_pipeline.parsers import get_basic_match_info, get_player_stats, get_round_detail, get_team_ids
from vlr_pipeline.tables import (
    build_players, build_teams, draft_team_ids, player_team_ids, resolve_team_ids, side_team_ids, team_keys,
)


def fixture_soup(series_id):
    with gzip.open(os.path.join(HTML_DIR, series_id, "match.html.gz")) as f:
        return BeautifulSoup(f.read().decode("iso-8859-1"), "html.parser")


def test_team_ids_from_match_header():
    soup = fixture_soup("753451")
    assert get_team_ids(soup) == ("2059", "6961")
    info = get_basic_match_info(soup, "https://www.vlr.gg/753451/team-vitality-vs-loud")
    assert (info["team_a"], info["team_a_id_vlr"], info["team_b_id_vlr"]) == ("Team Vitality", "2059", "6961")


def test_team_without_vlr_page_gives_empty_id():
    soup = BeautifulSoup(
        '<a class="match-header-link mod-1" href="/team/123/x"></a><a class="match-header-link mod-2"></a>',
        "html.parser",
    )
    assert get_team_ids(soup) == ("123", "")


OVERVIEW_SAME_TAG = """
<div class="vm-stats-game" data-game-id="1">
  <div class="map"><span>Bind</span></div>
  <div class="ovw-table">
    <div class="ovw-row"><div class="ovw-player-name">a1</div><div class="ovw-player-tag">FAKE</div></div>
  </div>
  <div class="ovw-table">
    <div class="ovw-row"><div class="ovw-player-name">b1</div><div class="ovw-player-tag">FAKE</div></div>
  </div>
</div>
"""


def test_player_stats_team_by_table_position_not_tag():
    """785082 (FAKE vs FAKE): la primera ovw-table de cada mapa es team_a."""
    info = {"date": "d", "event": "e", "source_url": "u", "team_a_id_vlr": "10", "team_b_id_vlr": "20"}
    stats = get_player_stats(BeautifulSoup(OVERVIEW_SAME_TAG, "html.parser"), info)
    assert list(zip(stats["player"], stats["team"], stats["team_id_vlr"])) == [
        ("a1", "FAKE", "10"), ("b1", "FAKE", "20"),
    ]


def round_rows(series_id, tag_a, tag_b, id_a, id_b, name_a="", name_b="", date="2026-11-01"):
    return {
        "teamA": tag_a, "teamB": tag_b, "map": "Bind", "date": date,
        "source_url": f"https://www.vlr.gg/{series_id}/x",
        "team_a_id_vlr": id_a, "team_b_id_vlr": id_b, "team_a_name": name_a, "team_b_name": name_b,
    }


def test_team_keys_and_resolution():
    df_round = pd.DataFrame([
        round_rows("1", "FUR", "LOUD", 2406, 6961, "FURIA", "LOUD"),
        round_rows("2", "FUR", "XYZ", 99999, None, "Furious", "Xyz"),
        round_rows("3", "FAKE", "FAKE", 11, 12),
    ])
    keys = team_keys(df_round)
    # ids como texto aunque read_csv los traiga numericos; sin id -> tbd_<TAG>
    assert set(keys["team_id_vlr"]) == {"2406", "6961", "99999", "tbd_XYZ", "11", "12"}

    df = pd.DataFrame({
        "series_id": ["1", "2", "2", "3", "3", "3"],
        "team": ["FUR", "FUR", "XYZ", "FAKE", "FAKE", "NEW"],
        "team_id_vlr": [None, None, None, "12", None, None],
    })
    got = resolve_team_ids(df, keys, "team", raw_col="team_id_vlr").tolist()
    # mismo tag en dos series = dos equipos; FAKE vs FAKE solo con el crudo; sin nada -> tbd_
    assert got == ["2406", "99999", "tbd_XYZ", "12", "tbd_FAKE", "tbd_NEW"]


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8")


def test_build_teams_one_row_per_vlr_team(tmp_path):
    csv_dir, tables_dir = tmp_path / "csv", tmp_path / "tables"
    tables_dir.mkdir()
    write_csv(str(csv_dir / "t1" / "round_detail_t1.csv"), [
        round_rows("1", "FUR", "LOUD", "2406", "6961", "FURIA", "LOUD", date="2026-06-01"),
        round_rows("2", "FUR", "LOUD", "2406", "6961", "FURIA Esports", "LOUD", date="2026-07-01"),
        round_rows("3", "FUR", "ZZZ", "99999", "", "Furious", "Zzz", date="2026-11-01"),
    ])
    write_csv(str(csv_dir / "t1" / "draft_t1.csv"), [{"team": "FUR", "rival": "LOUD", "source_url": "u"}])
    write_csv(str(csv_dir / "t1" / "player_stats_t1.csv"), [
        {"team": "FUR", "player": "p1", "date": "2026-07-01", "source_url": "https://www.vlr.gg/2/x",
         "map": "Bind", "player_id_vlr": "1", "team_id_vlr": "2406"},
        {"team": "FUR", "player": "p2", "date": "2026-11-01", "source_url": "https://www.vlr.gg/3/x",
         "map": "Bind", "player_id_vlr": "2", "team_id_vlr": ""},
    ])

    df_team = build_teams(str(csv_dir), str(tables_dir))
    assert df_team.columns.tolist() == ["team_id", "team_path", "team_id_vlr", "name"]
    rows = df_team.set_index("team_id_vlr")
    assert rows.loc["2406", "name"] == "FURIA Esports"  # el nombre del partido mas reciente
    assert rows.loc["99999", "team_id"] == "FUR"
    assert rows.loc["tbd_ZZZ", "team_path"] == "teams/ZZZ.png"
    assert df_team["team_id_vlr"].is_unique and (df_team["team_id"] == "FUR").sum() == 2

    # players no se duplica por el tag repetido en teams
    df_players = build_players(df_team, str(csv_dir), str(tables_dir))
    assert df_players.set_index("player_id_vlr")["team_id_vlr"].to_dict() == {"1": "2406", "2": "99999"}
    assert df_players["team_id"].tolist() == ["FUR", "FUR"]


def test_backfill_fills_round_detail_and_player_stats():
    url = "https://www.vlr.gg/785082/x"
    round_csv = [["teamA", "teamB", "source_url", "team_a_id_vlr", "team_b_id_vlr", "team_a_name", "team_b_name"],
                 ["FAKE", "FAKE", url, "", "", "", ""],
                 ["X", "Y", "https://www.vlr.gg/1/y", "", "", "", ""]]
    assert fill_round_detail(round_csv, "785082", {
        "team_a_id_vlr": "10", "team_b_id_vlr": "20", "team_a": "Counterfeit", "team_b": "Faker Rex"}) == 1
    assert round_csv[1][3:] == ["10", "20", "Counterfeit", "Faker Rex"]
    assert round_csv[2][3:] == ["", "", "", ""]

    stats_csv = [["player", "map_id_vlr", "source_url", "player_id_vlr", "team_id_vlr"],
                 ["a1", "1", url, "501", ""],
                 ["b1", "1", url, "", ""]]  # sin perfil en vlr: cae al nick
    page = {"map_id_vlr": ["1", "1"], "player": ["a1", "b1"], "player_id_vlr": ["501", ""],
            "team_id_vlr": ["10", "20"]}
    assert fill_player_stats(stats_csv, "785082", page) == (2, 0)
    assert [row[4] for row in stats_csv[1:]] == ["10", "20"]


def test_team_path_by_id_only_for_shared_tags(tmp_path):
    """Fase 2: con el tag repetido, el logo por tag queda para el equipo con mas series."""
    csv_dir, tables_dir = tmp_path / "csv", tmp_path / "tables"
    tables_dir.mkdir()
    write_csv(str(csv_dir / "t1" / "round_detail_t1.csv"), [
        round_rows("1", "MIBR", "LOUD", "7386", "6961", date="2026-06-01"),
        round_rows("2", "MIBR", "LOUD", "7386", "6961", date="2026-07-01"),
        round_rows("3", "MIBR", "GEN.GC", "16255", "21858", date="2026-11-01"),
    ])
    write_csv(str(csv_dir / "t1" / "draft_t1.csv"), [{"team": "MIBR", "rival": "LOUD", "source_url": "u"}])
    paths = build_teams(str(csv_dir), str(tables_dir)).set_index("team_id_vlr")["team_path"].to_dict()
    assert paths == {
        "7386": "teams/MIBR.png", "6961": "teams/LOUD.png", "16255": "teams/16255.png", "21858": "teams/GENGC.png",
    }


def test_draft_ids_when_the_draft_has_the_name_not_the_tag():
    """NA Open Qualifier: algunos drafts traen el nombre ("ARCHAIC") en vez del tag ("ARCH")."""
    keys = team_keys(pd.DataFrame([
        round_rows("785006", "MC", "ARCH", "23878", "23567"),
        round_rows("785082", "FAKE", "FAKE", "23815", "21068"),
    ]))
    draft = pd.DataFrame({"series_id": ["785006", "785006", "785082"],
                          "team": ["MC", "ARCHAIC", "FAKE"], "rival": ["ARCHAIC", "MC", "FAKE"]})
    team, rival = draft_team_ids(draft, keys)
    assert team.tolist() == ["23878", "23567", "tbd_FAKE"]
    assert rival.tolist() == ["23567", "23878", "tbd_FAKE"]


def test_player_team_ids_before_tag():
    """El equipo de un jugador sale del overview (por posicion), el tag es el ultimo recurso."""
    keys = pd.DataFrame({"map_id": ["1-Bind", "1-Bind"], "player": ["a", "b"], "agent_key": ["jett", "sova"],
                         "player_id_vlr": ["501", "502"], "team_id_vlr": ["10", "20"]})
    df = pd.DataFrame({"map_id": ["1-Bind", "1-Bind", "1-Bind"], "player_id_vlr": ["502", "999", None]})
    assert player_team_ids(df, keys).fillna("-").tolist() == ["20", "-", "-"]

    tags = pd.Series(["FAKE", "XYZ", None])
    got = side_team_ids(tags, pd.Series(["FAKE"] * 3), pd.Series(["FAKE"] * 3),
                        pd.Series(["10"] * 3), pd.Series(["20"] * 3))
    assert got.fillna("-").tolist() == ["10", "tbd_XYZ", "-"]


ROUND_GRID_UNPLAYED_FIRST = """
<div class="vm-stats-game" data-game-id="1">
  <div class="map"><span style="position: relative;">TBD</span></div>
  <div class="vlr-rounds-row-col"><div class="rnd-num">1</div><div class="rnd-sq"></div><div class="rnd-sq"></div></div>
</div>
<div class="vm-stats-game" data-game-id="2">
  <div class="map"><span style="position: relative;">Bind</span></div>
  <div class="vlr-rounds-row-col">
    <div class="rnd-num">1</div><div class="rnd-sq mod-win mod-ct"><img src="/img/vlr/game/round/elim.webp"></div>
    <div class="rnd-sq"></div>
  </div>
  <div class="ovw-table"><div class="ovw-row"><div class="ovw-player-name">a1</div></div></div>
</div>
"""


def test_unplayed_map_is_skipped(tmp_path):
    """787286: el mapa 1 no se jugo (grilla sin rondas ganadas) y le daba su nombre a Bind."""
    soup = BeautifulSoup(ROUND_GRID_UNPLAYED_FIRST, "html.parser")
    info = {"date": "d", "event": "e", "source_url": "https://www.vlr.gg/787286/x", "team_a_tricode": "A",
            "team_b_tricode": "B", "team_a": "A", "team_b": "B"}
    stats = get_player_stats(soup, info)
    assert stats["map"] == ["Bind"]
    rounds = get_round_detail(soup, info, folder=str(tmp_path))
    assert rounds["map"] == "Bind"
