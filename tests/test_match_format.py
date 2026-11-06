"""Torneos reduced (qualifiers sin draft): format en events.json -> scrape_log -> tablas."""

import json

import pandas as pd
import pytest
from bs4 import BeautifulSoup

from vlr_pipeline import config
from vlr_pipeline.scraper import get_invalid_reason
from vlr_pipeline.tables import canonical_teams, load_match_formats, same_team_case, tournament_format
from vlr_pipeline.tracking import LOG_COLUMNS, record, save_log, sync_match_format

URL_A = "https://www.vlr.gg/784555/rvani-tyz-vs-ronka-e-sports-x"
URL_B = "https://www.vlr.gg/784556/team-protocol-vs-holy-kiwi-x"


def match_soup(status):
    return BeautifulSoup(
        "<html><head><title>A vs. B | Qualifier #1: Round of 256 | x | y | z</title></head><body>"
        f'<div class="match-header-vs-note">{status}</div><div class="match-header-vs-note">Bo3</div>'
        "</body></html>",
        "html.parser",
    )


def test_forfeit_is_skipped_not_retried():
    assert get_invalid_reason(match_soup("forfeited by Les Inconnus")) == "forfeit"
    assert get_invalid_reason(match_soup("final")) is None
    assert get_invalid_reason(match_soup("live")) == "not_final"


def write_events(tmp_path, events):
    path = tmp_path / "events.json"
    path.write_text(json.dumps({"events": events}))
    return str(path)


def test_load_events_defaults_and_validates_format(tmp_path):
    path = write_events(tmp_path, [
        {"name": "full", "url": "u1", "active": True},
        {"name": "qual", "url": "u2", "active": True, "format": "reduced"},
    ])
    assert [event["format"] for event in config.load_events(path)] == ["full", "reduced"]

    bad = write_events(tmp_path, [{"name": "x", "url": "u", "active": True, "format": "qualifier"}])
    with pytest.raises(ValueError, match="format invalido"):
        config.load_events(bad)


def empty_log():
    log = pd.DataFrame(columns=LOG_COLUMNS)
    log["attempts"] = log["attempts"].astype(int)
    return log


def test_match_format_reaches_tables(tmp_path):
    log = record(empty_log(), URL_A, status="ok", event="VCT 2027: EMEA Kickoff - Europe Qualifier",
                 match_format="reduced")
    log = record(log, URL_B, status="ok", event="Otro torneo")
    save_log(log, str(tmp_path))

    formats = load_match_formats(str(tmp_path)).set_index("series_id")["match_format"]
    assert formats.to_dict() == {"784555": "reduced", "784556": "full"}

    # cambiar el format del evento re-marca lo ya scrapeado sin pedir nada a vlr
    assert sync_match_format(log, [URL_B], "reduced") == 1
    assert sync_match_format(log, [URL_B], "reduced") == 0
    assert log.loc[log["series_id"] == "784556", "match_format"].item() == "reduced"


def test_load_match_formats_without_log_or_column(tmp_path):
    assert load_match_formats(str(tmp_path)).empty
    # scrape_log de antes de la columna: todo full
    (tmp_path / "scrape_log.csv").write_text("series_id,tournament,status\n1,t,ok\n")
    assert load_match_formats(str(tmp_path))["match_format"].tolist() == ["full"]


def test_tournament_format():
    assert tournament_format(["reduced", "reduced"]) == "reduced"
    assert tournament_format(["full", "reduced"]) == "mixed"
    assert tournament_format([]) == "full"


def test_logs_tag_case_matches_round_info():
    # la solapa logs de equipos chicos trae "Rvan" y round_detail "RVAN"
    tags = pd.Series(["Rvan", "Ronk", "RVAN", None])
    team_a = pd.Series(["RVAN"] * 4)
    team_b = pd.Series(["RONK"] * 4)
    assert same_team_case(tags, team_a).tolist()[:3] == ["RVAN", "Ronk", "RVAN"]
    assert canonical_teams(tags, team_a, team_b).tolist()[:3] == ["RVAN", "RONK", "RVAN"]


def test_env_file_aliases_without_overriding(tmp_path, monkeypatch):
    path = tmp_path / ".env.local"
    path.write_text(
        '# comentario\nNEXT_PUBLIC_SUPABASE_URL="https://x.supabase.co"\n'
        "NEXT_PUBLIC_SUPABASE_ANON_KEY=anon\nSUPABASE_SERVICE_ROLE_KEY=service",  # sin \n final
        encoding="utf-8",
    )
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "del-entorno")
    for key in ("NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.delenv(key, raising=False)

    added = config.load_env_file(str(path))

    import os
    assert os.environ["SUPABASE_URL"] == "https://x.supabase.co"
    # lo que ya esta en el entorno (secrets de Actions) gana
    assert os.environ["SUPABASE_SERVICE_KEY"] == "del-entorno"
    assert "SUPABASE_SERVICE_KEY" not in added
    assert config.load_env_file("") == []


def test_performance_cell_with_spaces_in_nick_and_tag():
    from vlr_pipeline.parsers import performance_player_cell

    def cell(html):
        return BeautifulSoup(html, "html.parser").div

    # qualifier 784614: nick "VRX Velcro" del equipo "FL R"; antes salia player=VRX, team=Velcro
    assert performance_player_cell(
        cell('<div>\n VRX Velcro\n <div class="team-tag ge-text-faded">\n FL R\n </div>\n</div>')
    ) == ("VRX Velcro", "FL R")
    assert performance_player_cell(
        cell('<div>H1ber<div class="team-tag ge-text-faded">F9</div></div>')
    ) == ("H1ber", "F9")
    # html viejo sin div team-tag: split de siempre
    assert performance_player_cell(cell("<div>Less LOUD</div>")) == ("Less", "LOUD")


def test_tag_case_with_non_ascii_html_form():
    # 784714: round_info "MÖRK", logs "Mörk", ambos en forma html (utf-8 leido como latin-1)
    html = lambda text: text.encode("utf-8").decode("iso-8859-1")
    tags = pd.Series([html("Mörk")])
    assert same_team_case(tags, pd.Series([html("MÖRK")])).tolist() == [html("MÖRK")]
