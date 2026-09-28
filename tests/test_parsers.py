"""process_match sobre html guardado: detecta cuando un cambio en parsers.py altera las filas.

Si vlr cambia el formato y hay que tocar los parsers, estos tests deberian seguir pasando
con el html viejo. Si el cambio de filas es intencional, regenerar tests/fixtures/expected/.
"""

import os

import pandas as pd
import pytest

from tests.conftest import EXPECTED_DIR, patch_offline
from vlr_pipeline.scraper import process_match

MATCHES = [
    # Bo3
    "https://www.vlr.gg/753455/team-liquid-vs-paper-rex-valorant-champions-2026-opening-c",
    # Bo5
    "https://www.vlr.gg/742481/nongshim-redforce-vs-global-esports-vct-2026-pacific-stage-2-gf",
]

EXPECTED_FILES = sorted(
    os.path.join(event, file)
    for event in os.listdir(EXPECTED_DIR)
    for file in os.listdir(os.path.join(EXPECTED_DIR, event))
)


def read_csv(path):
    return pd.read_csv(path, encoding="utf-8", dtype=str, keep_default_na=False)


@pytest.fixture(scope="module")
def scraped_dir(tmp_path_factory):
    monkeypatch = pytest.MonkeyPatch()
    patch_offline(monkeypatch)
    folder = tmp_path_factory.mktemp("csv")
    results = [process_match(url, folder=str(folder), encoding="iso-8859-1") for url in MATCHES]
    monkeypatch.undo()
    return str(folder), results


def test_matches_processed_ok(scraped_dir):
    _, results = scraped_dir
    for result in results:
        assert result["status"] == "ok", result["error"]
        assert result["has_performance"] is True
        assert result["has_economy"] is True


def test_same_files_as_expected(scraped_dir):
    folder, _ = scraped_dir
    written = sorted(
        os.path.relpath(os.path.join(dirpath, file), folder)
        for dirpath, _, files in os.walk(folder)
        for file in files
    )
    assert written == EXPECTED_FILES


@pytest.mark.parametrize("relative_path", EXPECTED_FILES)
def test_rows_match_expected(scraped_dir, relative_path):
    folder, _ = scraped_dir
    got = read_csv(os.path.join(folder, relative_path))
    expected = read_csv(os.path.join(EXPECTED_DIR, relative_path))
    pd.testing.assert_frame_equal(got, expected)


def test_reprocessing_does_not_duplicate(offline_vlr, tmp_path):
    """process_match purga las filas del match antes de extraer: correrlo dos veces no duplica."""
    url = MATCHES[0]
    process_match(url, folder=str(tmp_path), encoding="iso-8859-1")
    first = {path: len(read_csv(path)) for path in tmp_path.rglob("*.csv")}
    process_match(url, folder=str(tmp_path), encoding="iso-8859-1")
    second = {path: len(read_csv(path)) for path in tmp_path.rglob("*.csv")}
    assert first == second
