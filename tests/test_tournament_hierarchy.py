"""year / stage / subregion de table_tournament (handoff/VLR_SCRAPER_TOURNAMENT_HIERARCHY.md)."""

import pytest

from vlr_pipeline.tables import tournament_hierarchy

# valores cargados a mano en Supabase el 2026-11-08: el scraper tiene que producir lo mismo
EXPECTED = {
    **{f"vct_2026_{r}_kickoff": (2026, "kickoff", None) for r in ("americas", "emea", "pacific", "china")},
    **{f"vct_2026_{r}_stage_1": (2026, "stage_1", None) for r in ("americas", "emea", "pacific", "china")},
    **{f"vct_2026_{r}_stage_2": (2026, "stage_2", None) for r in ("americas", "emea", "pacific", "china")},
    "valorant_masters_santiago_2026": (2026, "masters", None),
    "valorant_masters_london_2026": (2026, "masters", None),
    "esports_world_cup_2026": (2026, "ewc", None),
    "valorant_champions_2026": (2026, "champions", None),
    # tour_id en forma html ("são" leido como latin-1), como queda en build_region_tournament
    "game_changers_2026_championship_sÃ£o_paulo": (2026, "game_changers", None),
    "vct_2027_america_kickoff_-_north_america_open_qualifier": (2027, "open_qualifier", "North America"),
    "vct_2027_america_kickoff_-_latam_north_open_qualifier": (2027, "open_qualifier", "LATAM North"),
    "vct_2027_america_kickoff_-_latam_south_open_qualifier": (2027, "open_qualifier", "LATAM South"),
    "vct_2027_emea_kickoff_-_europe_qualifier": (2027, "open_qualifier", "Europe"),
    # agregados 2026-11-09 (no estaban en la tabla de rviewer)
    "vct_2027_emea_kickoff_-_mena_qualifier": (2027, "open_qualifier", "MENA"),
    "vct_2027_america_kickoff_-_brazil_open_qualifier": (2027, "open_qualifier", "Brazil"),
    # 2026-11-11: tour_id y subregion en forma html ("ü" leido como latin-1); lower() sobre el tour_id
    # sin decodificar daba "tã¼rkiye" y la subregion salia "Tã¼Rkiye"
    "vct_2027_emea_kickoff_-_tÃ¼rkiye_qualifier": (2027, "open_qualifier", "TÃ¼rkiye"),
}


def test_normalize_filename_html_form():
    """La carpeta / tour_id sale del event en forma html: decodificar antes de lower()."""
    from vlr_pipeline.save import normalize_filename

    assert normalize_filename("VCT 2027: EMEA Kickoff - TÃ¼rkiye Qualifier") == (
        "vct_2027_emea_kickoff_-_türkiye_qualifier"
    )
    assert normalize_filename("Game Changers 2026: Championship SÃ£o Paulo") == (
        "game_changers_2026_championship_são_paulo"
    )
    # ya decodificado (nombre de carpeta): no cambia
    assert normalize_filename("vct_2027_emea_kickoff_-_türkiye_qualifier") == (
        "vct_2027_emea_kickoff_-_türkiye_qualifier"
    )


@pytest.mark.parametrize("tour_id, expected", EXPECTED.items())
def test_current_tournaments(tour_id, expected):
    assert tournament_hierarchy(tour_id) == expected


def test_closed_qualifier():
    assert tournament_hierarchy("vct_2027_america_kickoff_-_latam_south_closed_qualifier") == (
        2027, "closed_qualifier", "LATAM South",
    )


def test_unknown_stage_and_subregion_warn(caplog):
    assert tournament_hierarchy("challengers_2027_ascension_americas") == (2027, None, None)
    assert tournament_hierarchy("vct_2027_pacific_kickoff_-_south_asia_open_qualifier") == (
        2027, "open_qualifier", "South Asia",
    )
    assert "stage desconocido" in caplog.text
    assert "subregion nueva" in caplog.text
