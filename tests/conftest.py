import gzip
import os
import re

import pytest
from bs4 import BeautifulSoup

from vlr_pipeline.tables import build_all

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_DIR = os.path.join(ROOT, "csv")
FIXTURES_DIR = os.path.join(ROOT, "tests", "fixtures")
HTML_DIR = os.path.join(FIXTURES_DIR, "html")
EXPECTED_DIR = os.path.join(FIXTURES_DIR, "expected")


def fixture_soup_open(url=None, decode="iso-8859-1"):
    """Reemplazo de fetch.soup_open que lee el html guardado en tests/fixtures/html/<series_id>/.

    Para agregar un match: bajar match/performance/economy.html y logs_<game_id>.html de cada
    mapa jugado (mismas urls que usan los parsers), comprimir con gzip y guardar el csv
    esperado en tests/fixtures/expected/.
    """
    series_id = re.search(r"vlr\.gg/(\d+)", url).group(1)
    logs_game = re.search(r"game=(\d+)&tab=logs", url)
    if logs_game:
        name = f"logs_{logs_game.group(1)}"
    elif "tab=performance" in url:
        name = "performance"
    elif "tab=economy" in url:
        name = "economy"
    else:
        name = "match"
    with gzip.open(os.path.join(HTML_DIR, series_id, f"{name}.html.gz")) as f:
        html = f.read().decode(decode)
    return BeautifulSoup(html, "html.parser")


def patch_offline(monkeypatch):
    """Sin red ni sleeps: los parsers leen los html de fixtures."""
    import vlr_pipeline.parsers as parsers
    import vlr_pipeline.scraper as scraper

    monkeypatch.setattr(parsers, "soup_open", fixture_soup_open)
    monkeypatch.setattr(scraper, "soup_open", fixture_soup_open)
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: None)


@pytest.fixture
def offline_vlr(monkeypatch):
    patch_offline(monkeypatch)


@pytest.fixture(scope="session")
def tables_dir(tmp_path_factory):
    """tables/ construido una sola vez desde el csv/ versionado."""
    path = tmp_path_factory.mktemp("tables")
    build_all(csv_dir=CSV_DIR, tables_dir=str(path))
    return str(path)
