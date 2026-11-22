"""Closed de un qualifier que vlr pone como stage del evento del open (handoff/VLR_SCRAPER_EMEA_PLAYOFFS.md)."""

import pytest
from bs4 import BeautifulSoup

from vlr_pipeline.parsers import stage_event
from vlr_pipeline.save import normalize_filename
from vlr_pipeline.tables import tournament_hierarchy

html = lambda text: text.encode("utf-8").decode("iso-8859-1")
MENA = "VCT 2027: EMEA Kickoff - MENA Qualifier"


@pytest.mark.parametrize("event, stage, expected", [
    (MENA, "Playoffs", f"{MENA} Playoffs"),
    (MENA, "North Africa #2", MENA),
    ("VCT 2027: Pacific Kickoff - Oceania Qualifier", "Main Event",
     "VCT 2027: Pacific Kickoff - Oceania Qualifier Playoffs"),
    # Americas: el closed ya es un evento aparte que dice "Playoffs"
    ("VCT 2027: America Kickoff - North America Qualifier Playoffs", "Playoffs",
     "VCT 2027: America Kickoff - North America Qualifier Playoffs"),
    # un evento que no es qualifier no se toca
    ("VCT 2026: Pacific Stage 2", "Playoffs", "VCT 2026: Pacific Stage 2"),
    (MENA, None, MENA),
])
def test_stage_event(event, stage, expected):
    assert stage_event(event, stage) == expected


@pytest.mark.parametrize("event, tour_id, expected", [
    (MENA, "vct_2027_emea_kickoff_-_mena_qualifier_playoffs", (2027, "closed_qualifier", "MENA")),
    (html("VCT 2027: EMEA Kickoff - Türkiye Qualifier"), "vct_2027_emea_kickoff_-_türkiye_qualifier_playoffs",
     (2027, "closed_qualifier", html("Türkiye"))),
    ("VCT 2027: Pacific Kickoff - South Asia Qualifier", "vct_2027_pacific_kickoff_-_south_asia_qualifier_playoffs",
     (2027, "closed_qualifier", "South Asia")),
    ("VCT 2027: Pacific Kickoff - Oceania Qualifier", "vct_2027_pacific_kickoff_-_oceania_qualifier_playoffs",
     (2027, "closed_qualifier", "Oceania")),
])
def test_playoffs_get_own_closed_tour_id(event, tour_id, expected):
    folder = normalize_filename(stage_event(event, "Playoffs"))
    assert folder == tour_id
    # tour_id en tables/ es la forma html de la carpeta
    assert tournament_hierarchy(html(folder)) == expected


def test_reprocess_moves_rows_out_of_the_open_folder(tmp_path, monkeypatch):
    # 792549 / 792550: scrapeados con el tour_id del open antes de stage_event
    from vlr_pipeline import scraper

    url = "https://www.vlr.gg/792549/mix-my-miks-vs-gamax-esports-sf"
    other = "https://www.vlr.gg/791110/gamax-esports-vs-fc-capybara-gf"
    soup = BeautifulSoup(
        f"<html><head><title>A vs. B | {MENA} | Playoffs | Valorant match | VLR.gg</title></head></html>",
        "html.parser",
    )
    open_folder = tmp_path / normalize_filename(MENA)
    open_folder.mkdir()
    draft = open_folder / f"draft_{open_folder.name}.csv"
    draft.write_text(f"team,source_url\nMMM,{url}\nGMX,{other}\n", encoding="iso-8859-1")

    scraper.purge_open_folder(soup, normalize_filename(scraper.title_event(soup)), url, folder=str(tmp_path))

    assert draft.read_text(encoding="iso-8859-1") == f"team,source_url\nGMX,{other}\n"
