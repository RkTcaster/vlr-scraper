"""slots / relevant_teams de events.json -> table_tournament_slots."""

import json

import pandas as pd
import pytest

from vlr_pipeline.config import load_events
from vlr_pipeline.tables import build_tournament_slots, event_key, event_slug

URL = "https://www.vlr.gg/event/matches/{id}/{slug}/?series_id=all"


def write_events(tmp_path, events):
    path = tmp_path / "events.json"
    path.write_text(json.dumps({"events": events}), encoding="utf-8")
    return str(path)


def event(slug, **extra):
    return {"name": slug, "url": URL.format(id=1, slug=slug), "active": False, **extra}


@pytest.mark.parametrize("extra, message", [
    ({"slots": 0}, "slots invalido"),
    ({"slots": "2"}, "slots invalido"),
    ({"slots": True}, "slots invalido"),
    ({"relevant_teams": ["AURA"]}, "sin slots"),
    ({"slots": 1, "relevant_teams": ["AURA", "YCAT"]}, "2 relevant_teams para 1 slots"),
    ({"slots": 2, "relevant_teams": ["AURA", "aura"]}, "repetidos"),
    ({"slots": 2, "relevant_teams": "AURA"}, "lista de tricodes"),
])
def test_invalid_slots_fail_on_load(tmp_path, extra, message):
    path = write_events(tmp_path, [event("x", **extra)])
    with pytest.raises(ValueError, match=message):
        load_events(path)


def test_event_key_matches_slug_and_tour_id():
    # vlr cambia "ã" por "-" en el slug; el tour_id lo guarda en la forma html
    gc = "game-changers-2026-championship-s-o-paulo"
    assert event_key(gc) == event_key("game_changers_2026_championship_sÃ£o_paulo")
    brazil = event_slug(URL.format(id=3187, slug="vct-2027-america-kickoff-brazil-open-qualifier"))
    assert event_key(brazil) == event_key("vct_2027_america_kickoff_-_brazil_open_qualifier")


def test_build_tournament_slots(tmp_path, caplog):
    path = write_events(tmp_path, [
        event("vct-2027-emea-kickoff-europe-qualifier", slots=3, relevant_teams=["aura", " YCAT ", "MÖRK"]),
        event("vct-2027-america-kickoff-brazil-open-qualifier", slots=2, relevant_teams=["CABO"]),
        event("vct-2026-emea-stage-1"),  # sin slots: no genera filas
        event("vct-2027-pacific-kickoff-sea-qualifier", slots=2),  # sin partidos todavia
    ])
    df_tournaments = pd.DataFrame({"tour_id": [
        "vct_2027_emea_kickoff_-_europe_qualifier",
        "vct_2027_america_kickoff_-_brazil_open_qualifier",
        "vct_2026_emea_stage_1",
    ]})
    # tricodes en la forma html (utf-8 leido como latin-1), como en table_teams
    df_team = pd.DataFrame({"team_id": ["AURA", "YCAT", "MÖRK".encode("utf-8").decode("iso-8859-1")]})

    df = build_tournament_slots(df_tournaments, df_team, path, str(tmp_path))

    europe = "vct_2027_emea_kickoff_-_europe_qualifier"
    brazil = "vct_2027_america_kickoff_-_brazil_open_qualifier"
    assert df.to_dict("records") == [
        {"tour_id": europe, "slot": 1, "team_id": "AURA"},
        {"tour_id": europe, "slot": 2, "team_id": "YCAT"},
        {"tour_id": europe, "slot": 3, "team_id": "MÖRK".encode("utf-8").decode("iso-8859-1")},
        {"tour_id": brazil, "slot": 1, "team_id": "CABO"},
        {"tour_id": brazil, "slot": 2, "team_id": ""},
    ]
    assert "sea-qualifier no tiene tour_id" in caplog.text
    assert "'CABO' no esta en table_teams" in caplog.text
    written = (tmp_path / "table_tournament_slots.csv").read_bytes().decode("utf-8")
    assert written.splitlines()[0] == "tour_id,slot,team_id"
    assert "MÖRK" in written  # el csv queda en utf-8 valido, como el resto de tables/
