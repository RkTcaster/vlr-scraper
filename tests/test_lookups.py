"""Todo mapa/agente que aparece en csv/ tiene que estar en lookups.py (si no, queda sin id/imagen)."""

import pandas as pd

from tests.conftest import CSV_DIR
from vlr_pipeline.lookups import agent_path_name, map_info
from vlr_pipeline.tables import concat_csv_from_different_folders

KNOWN_MAPS = set(map_info["map"])
# mismo nombre que arma build_agent_info
KNOWN_AGENTS = {path.split(".")[0].capitalize() for path in agent_path_name}


def values(df, columns):
    return set(pd.concat([df[column] for column in columns]).dropna()) - {"", "all"}


def test_draft_maps_in_lookups():
    df = concat_csv_from_different_folders(folder=CSV_DIR, prefix="draft")
    columns = [column for column in df.columns if "_select_" in column or column == "decider"]
    missing = values(df, columns) - KNOWN_MAPS
    assert not missing, f"agregar a map_info en lookups.py (y csv_process.ipynb): {sorted(missing)}"


def test_player_stats_maps_in_lookups():
    df = concat_csv_from_different_folders(folder=CSV_DIR, prefix="player_stats")
    missing = values(df, ["map"]) - KNOWN_MAPS
    assert not missing, f"agregar a map_info en lookups.py (y csv_process.ipynb): {sorted(missing)}"


def test_agents_in_lookups():
    df = concat_csv_from_different_folders(folder=CSV_DIR, prefix="player_stats")
    missing = values(df, ["agent"]) - KNOWN_AGENTS
    assert not missing, f"agregar a agent_path_name en lookups.py (y csv_process.ipynb): {sorted(missing)}"
